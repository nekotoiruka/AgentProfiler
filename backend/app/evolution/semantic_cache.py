"""セマンティック・キャッシュ

SQLite ベースで類似発話の LLM 推論をバイパスするキャッシュ層。
発話の埋め込みベクトルを用いた cosine similarity 検索で、
同一・類似の発話に対する LLM レスポンスを再利用する。
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta

import aiosqlite
import numpy as np

from app.evolution.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


class SemanticCache:
  """SQLite ベースのセマンティック・キャッシュ

  発話の埋め込みベクトルを用いた類似度検索で、
  同一・類似の発話に対する LLM レスポンスを再利用する。
  SQLite 不通時はキャッシュをバイパスし直接推論にフォールバックする。
  """

  def __init__(
    self,
    db_path: str,
    embedding_client: EmbeddingClient,
    threshold: float = 0.92,
    eviction_days: int = 7,
  ) -> None:
    self._db_path = db_path
    self._embedding_client = embedding_client
    self._threshold = threshold
    self._eviction_days = eviction_days

  async def init_db(self) -> None:
    """キャッシュテーブルとインデックスを初期化する

    semantic_cache テーブルを作成し、profile_id にインデックスを付与する。
    SQLite 不通時は例外をログ出力して握りつぶす。
    """
    try:
      async with aiosqlite.connect(self._db_path) as db:
        await db.execute("""
          CREATE TABLE IF NOT EXISTS semantic_cache (
            entry_id TEXT PRIMARY KEY,
            embedding_blob BLOB NOT NULL,
            utterance_text TEXT NOT NULL,
            response_text TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_accessed_at TEXT NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0
          )
        """)
        await db.execute("""
          CREATE INDEX IF NOT EXISTS idx_cache_profile
          ON semantic_cache(profile_id)
        """)
        await db.commit()
      logger.info("SemanticCache DB initialized: %s", self._db_path)
    except Exception as e:
      logger.error("SemanticCache init_db failed: %s", e)

  async def lookup(self, profile_id: str, utterance: str) -> str | None:
    """キャッシュヒット検索

    発話の埋め込みを生成し、指定 profile_id のエントリと cosine similarity を比較。
    閾値以上のエントリがあれば response_text を返し、hit_count と last_accessed_at を更新する。

    Args:
      profile_id: 検索対象のプロファイル ID
      utterance: ユーザー発話テキスト

    Returns:
      キャッシュヒット時は response_text、ミス時は None。
      SQLite 不通時・Embedding 取得失敗時も None を返す。
    """
    try:
      # 発話の埋め込みを生成
      query_embedding = await self._embedding_client.embed(utterance)
      if query_embedding.size == 0:
        return None

      async with aiosqlite.connect(self._db_path) as db:
        cursor = await db.execute(
          "SELECT entry_id, embedding_blob, response_text FROM semantic_cache WHERE profile_id = ?",
          (profile_id,),
        )
        rows = await cursor.fetchall()

        best_entry_id: str | None = None
        best_score: float = 0.0
        best_response: str | None = None

        for entry_id, embedding_blob, response_text in rows:
          stored_embedding = np.frombuffer(embedding_blob, dtype=np.float32)
          score = self._cosine_similarity(query_embedding, stored_embedding)
          if score >= self._threshold and score > best_score:
            best_entry_id = entry_id
            best_score = score
            best_response = response_text

        if best_entry_id is not None:
          # hit_count と last_accessed_at を更新
          now = datetime.now(timezone.utc).isoformat()
          await db.execute(
            "UPDATE semantic_cache SET hit_count = hit_count + 1, last_accessed_at = ? WHERE entry_id = ?",
            (now, best_entry_id),
          )
          await db.commit()
          logger.debug(
            "Cache hit for profile=%s, score=%.4f", profile_id, best_score
          )
          return best_response

      return None
    except Exception as e:
      logger.error("SemanticCache lookup failed: %s", e)
      return None

  async def store(self, profile_id: str, utterance: str, response: str) -> None:
    """キャッシュミス後のエントリ保存

    発話の埋め込みを生成し、新規エントリとして SQLite に保存する。

    Args:
      profile_id: プロファイル ID
      utterance: ユーザー発話テキスト
      response: LLM が生成したレスポンステキスト
    """
    try:
      embedding = await self._embedding_client.embed(utterance)
      if embedding.size == 0:
        logger.warning("Cannot store cache: embedding generation failed")
        return

      entry_id = str(uuid.uuid4())
      now = datetime.now(timezone.utc).isoformat()

      async with aiosqlite.connect(self._db_path) as db:
        await db.execute(
          """
          INSERT INTO semantic_cache
            (entry_id, embedding_blob, utterance_text, response_text, profile_id, created_at, last_accessed_at, hit_count)
          VALUES (?, ?, ?, ?, ?, ?, ?, 0)
          """,
          (
            entry_id,
            embedding.tobytes(),
            utterance,
            response,
            profile_id,
            now,
            now,
          ),
        )
        await db.commit()
      logger.debug("Cache stored: entry_id=%s, profile=%s", entry_id, profile_id)
    except Exception as e:
      logger.error("SemanticCache store failed: %s", e)

  async def evict_stale(self) -> int:
    """期限切れエントリの削除

    last_accessed_at が eviction_days 日より古いエントリを削除する。

    Returns:
      削除されたエントリ数。SQLite 不通時は 0 を返す。
    """
    try:
      cutoff = datetime.now(timezone.utc) - timedelta(days=self._eviction_days)
      cutoff_str = cutoff.isoformat()

      async with aiosqlite.connect(self._db_path) as db:
        cursor = await db.execute(
          "DELETE FROM semantic_cache WHERE last_accessed_at < ?",
          (cutoff_str,),
        )
        count = cursor.rowcount
        await db.commit()
      logger.info("Evicted %d stale cache entries (cutoff=%s)", count, cutoff_str)
      return count
    except Exception as e:
      logger.error("SemanticCache evict_stale failed: %s", e)
      return 0

  async def invalidate(self, profile_id: str) -> int:
    """指定プロファイルのキャッシュ全削除

    Args:
      profile_id: 削除対象のプロファイル ID

    Returns:
      削除されたエントリ数。SQLite 不通時は 0 を返す。
    """
    try:
      async with aiosqlite.connect(self._db_path) as db:
        cursor = await db.execute(
          "DELETE FROM semantic_cache WHERE profile_id = ?",
          (profile_id,),
        )
        count = cursor.rowcount
        await db.commit()
      logger.info("Invalidated %d cache entries for profile=%s", count, profile_id)
      return count
    except Exception as e:
      logger.error("SemanticCache invalidate failed: %s", e)
      return 0

  async def get_stats(self, profile_id: str) -> dict:
    """キャッシュ統計情報を取得する

    Args:
      profile_id: 統計対象のプロファイル ID

    Returns:
      {
        "total_entries": int,
        "hit_rate": float,  # total_hits / total_entries (0.0 if no entries)
        "avg_similarity": float,  # 将来の拡張用、現時点では 0.0
      }
      SQLite 不通時は全て 0 の辞書を返す。
    """
    try:
      async with aiosqlite.connect(self._db_path) as db:
        cursor = await db.execute(
          "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM semantic_cache WHERE profile_id = ?",
          (profile_id,),
        )
        row = await cursor.fetchone()
        total_entries = row[0] if row else 0
        total_hits = row[1] if row else 0

        hit_rate = total_hits / total_entries if total_entries > 0 else 0.0

      return {
        "total_entries": total_entries,
        "hit_rate": hit_rate,
        "avg_similarity": 0.0,
      }
    except Exception as e:
      logger.error("SemanticCache get_stats failed: %s", e)
      return {
        "total_entries": 0,
        "hit_rate": 0.0,
        "avg_similarity": 0.0,
      }

  @staticmethod
  def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """2ベクトル間の cosine similarity を計算する

    ゼロベクトルの場合は 0.0 を返す。
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
      return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
