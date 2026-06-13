"""Semantic Retriever: cosine similarity ベクトル検索

numpy でインメモリベクトルインデックスを保持し、
クエリ埋め込みとの cosine similarity で上位 k 件を返す。
profile_id ごとにキャッシュを分離し、Embedding API 不通時は空結果にフォールバックする。
"""

import logging
from dataclasses import dataclass

import numpy as np

from app.evolution.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


@dataclass
class SemanticResult:
  """セマンティック検索結果"""

  domain: str
  text: str
  score: float


class SemanticRetriever:
  """cosine similarity ベクトル検索

  numpy でインメモリベクトルインデックスを保持し、
  クエリ埋め込みとの cosine similarity で上位 k 件を返す。
  """

  def __init__(
    self,
    embedding_client: EmbeddingClient,
    top_k: int = 3,
    threshold: float = 0.7,
  ):
    """SemanticRetriever を初期化する。

    Args:
      embedding_client: 埋め込みベクトル生成クライアント
      top_k: 返却する最大件数
      threshold: cosine similarity の最低閾値
    """
    self._embedding_client = embedding_client
    self._top_k = top_k
    self._threshold = threshold
    # profile_id → (domains list, texts list, embeddings_matrix np.ndarray shape (n, dim))
    self._cache: dict[str, tuple[list[str], list[str], np.ndarray]] = {}
    logger.debug(
      "SemanticRetriever initialized: top_k=%d, threshold=%.2f",
      self._top_k,
      self._threshold,
    )

  async def index_profile(
    self, profile_id: str, semantic_contexts: dict[str, str]
  ) -> None:
    """プロファイルの semantic_contexts を埋め込み化してインデックスに追加する。

    embed_batch() で全テキストの埋め込みを一括生成し、キャッシュに保存する。
    API 不通時（空配列が返却された場合）は warning ログを出力し、キャッシュには何も保存しない。

    Args:
      profile_id: プロファイル識別子
      semantic_contexts: domain → テキストの辞書
    """
    if not semantic_contexts:
      logger.warning("index_profile: empty semantic_contexts for profile_id=%s", profile_id)
      return

    domains = list(semantic_contexts.keys())
    texts = list(semantic_contexts.values())

    # バッチ埋め込み生成
    embeddings = await self._embedding_client.embed_batch(texts)

    # API 不通時のフォールバック: 空行列が返された場合はキャッシュしない
    if embeddings.size == 0:
      logger.warning(
        "index_profile: Embedding API returned empty result for profile_id=%s, skipping cache",
        profile_id,
      )
      return

    self._cache[profile_id] = (domains, texts, embeddings)
    logger.info(
      "index_profile: cached %d embeddings for profile_id=%s",
      len(domains),
      profile_id,
    )

  async def search(
    self, profile_id: str, query: str
  ) -> list[SemanticResult]:
    """クエリに最も類似する semantic_contexts を返す。

    profile_id がキャッシュに存在しない場合は空リストを返す。
    クエリ埋め込み生成に失敗した場合（空配列）も空リストを返す。
    cosine similarity >= threshold の上位 k 件を降順ソートで返却する。

    Args:
      profile_id: 検索対象のプロファイル識別子
      query: 検索クエリテキスト

    Returns:
      SemanticResult のリスト（スコア降順、最大 top_k 件）
    """
    # キャッシュ未登録の場合は空リスト
    if profile_id not in self._cache:
      logger.debug("search: profile_id=%s not in cache, returning empty", profile_id)
      return []

    domains, texts, embeddings_matrix = self._cache[profile_id]

    # クエリ埋め込み生成
    query_embedding = await self._embedding_client.embed(query)

    # API 不通時のフォールバック: 空ベクトルの場合は空リスト
    if query_embedding.size == 0:
      logger.warning(
        "search: query embedding failed for profile_id=%s, returning empty",
        profile_id,
      )
      return []

    # 全キャッシュベクトルとの cosine similarity を計算
    results: list[SemanticResult] = []
    for i, cached_vec in enumerate(embeddings_matrix):
      score = self.cosine_similarity(query_embedding, cached_vec)
      if score >= self._threshold:
        results.append(SemanticResult(
          domain=domains[i],
          text=texts[i],
          score=score,
        ))

    # スコア降順ソート → top-k 件に制限
    results.sort(key=lambda r: r.score, reverse=True)
    return results[: self._top_k]

  @staticmethod
  def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """2ベクトル間の cosine similarity を計算する。

    いずれかのベクトルがゼロベクトルの場合は 0.0 を返す。

    Args:
      a: ベクトル A
      b: ベクトル B

    Returns:
      cosine similarity 値 (0.0〜1.0)
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
      return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
