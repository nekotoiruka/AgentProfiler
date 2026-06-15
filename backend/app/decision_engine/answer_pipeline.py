"""回答3層構造化パイプライン (Raw → Normalized → Policy)"""

import json
import logging
from datetime import datetime, timezone

import aiosqlite

from app.decision_engine.models import AnswerMetadata, Permanence
from app.decision_engine.normalizer_llm import LLMNormalizer

logger = logging.getLogger(__name__)


class AnswerPipeline:
  """回答3層構造化パイプライン

  定義済み選択肢: Mapping Dictionary の policy_text を直接使用（LLM不要）
  自由記述: LLM で正規化を試行し、失敗時は pending としてマーク

  DB Schema (answer_layers):
    id INTEGER PRIMARY KEY AUTOINCREMENT
    session_id TEXT NOT NULL
    question_id TEXT NOT NULL
    raw_json TEXT NOT NULL
    normalized_json TEXT
    policy_text TEXT
    normalization_tags TEXT
    permanence TEXT NOT NULL DEFAULT 'permanent'
    confidence REAL NOT NULL DEFAULT 0.6
    exception_note TEXT
    is_core_rule INTEGER NOT NULL DEFAULT 0
    ambiguity REAL NOT NULL DEFAULT 0.0
    created_at TEXT NOT NULL
    updated_at TEXT NOT NULL
  """

  def __init__(self, db_path: str, llm_normalizer: LLMNormalizer):
    self._db_path = db_path
    self._normalizer = llm_normalizer

  async def init_db(self) -> None:
    """answer_layers テーブルとインデックスを作成する"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS answer_layers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL,
          question_id TEXT NOT NULL,
          raw_json TEXT NOT NULL,
          normalized_json TEXT,
          policy_text TEXT,
          normalization_tags TEXT,
          permanence TEXT NOT NULL DEFAULT 'permanent',
          confidence REAL NOT NULL DEFAULT 0.6,
          exception_note TEXT,
          is_core_rule INTEGER NOT NULL DEFAULT 0,
          ambiguity REAL NOT NULL DEFAULT 0.0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_answer_layers_session
        ON answer_layers(session_id, question_id)
      """)
      await db.commit()

  async def process_predefined(
    self,
    session_id: str,
    question_id: str,
    choice_id: str,
    choice_label: str,
    policy_text: str,
    normalized_tags: list[dict] | None = None,
    metadata: AnswerMetadata | None = None,
  ) -> dict:
    """定義済み選択肢を3層構造で保存する（LLM不要）

    Returns:
      Saved record dict with raw, normalized, policy fields
    """
    meta = metadata or AnswerMetadata()
    now = datetime.now(timezone.utc).isoformat()

    raw = {"question_id": question_id, "choice_id": choice_id, "choice_label": choice_label}
    normalized = {"tags": normalized_tags} if normalized_tags else None

    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        """INSERT INTO answer_layers
        (session_id, question_id, raw_json, normalized_json, policy_text, normalization_tags,
         permanence, confidence, exception_note, is_core_rule, ambiguity, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
          session_id, question_id, json.dumps(raw, ensure_ascii=False),
          json.dumps(normalized, ensure_ascii=False) if normalized else None,
          policy_text,
          json.dumps(normalized_tags, ensure_ascii=False) if normalized_tags else None,
          meta.permanence.value, meta.confidence, meta.exception_note,
          int(meta.is_core_rule), meta.ambiguity, now, now,
        ),
      )
      await db.commit()

    return {"raw": raw, "normalized": normalized, "policy": policy_text, "is_pending": False}

  async def process_free_text(
    self,
    session_id: str,
    question_id: str,
    text: str,
    question_text: str = "",
    metadata: AnswerMetadata | None = None,
  ) -> dict:
    """自由記述回答を3層構造で保存する

    LLM正規化を試行し、失敗時はpendingとしてマーク。

    Returns:
      Saved record dict. is_pending=True if normalization failed.
    """
    meta = metadata or AnswerMetadata()
    now = datetime.now(timezone.utc).isoformat()

    raw = {"question_id": question_id, "free_text": text}

    # LLM正規化を試行
    result = await self._normalizer.normalize(question_text, text)

    if result is not None:
      normalized = {"tags": result.tags}
      policy_text = result.policy_text
      normalization_tags = result.tags
      is_pending = False
    else:
      normalized = None
      policy_text = None
      normalization_tags = None
      is_pending = True
      logger.info("Normalization pending for session=%s question=%s", session_id, question_id)

    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        """INSERT INTO answer_layers
        (session_id, question_id, raw_json, normalized_json, policy_text, normalization_tags,
         permanence, confidence, exception_note, is_core_rule, ambiguity, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
          session_id, question_id, json.dumps(raw, ensure_ascii=False),
          json.dumps(normalized, ensure_ascii=False) if normalized else None,
          policy_text,
          json.dumps(normalization_tags, ensure_ascii=False) if normalization_tags else None,
          meta.permanence.value, meta.confidence, meta.exception_note,
          int(meta.is_core_rule), meta.ambiguity, now, now,
        ),
      )
      await db.commit()

    return {"raw": raw, "normalized": normalized, "policy": policy_text, "is_pending": is_pending}

  async def re_normalize_pending(self, session_id: str) -> int:
    """pending エントリの再正規化を試行する

    Returns:
      再正規化に成功したエントリ数
    """
    success_count = 0

    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute(
        """SELECT id, question_id, raw_json FROM answer_layers
        WHERE session_id = ? AND policy_text IS NULL""",
        (session_id,),
      )
      rows = await cursor.fetchall()

      for row in rows:
        raw = json.loads(row["raw_json"])
        free_text = raw.get("free_text", "")
        if not free_text:
          continue

        result = await self._normalizer.normalize("", free_text)
        if result is not None:
          now = datetime.now(timezone.utc).isoformat()
          normalized = {"tags": result.tags}
          await db.execute(
            """UPDATE answer_layers SET
            normalized_json = ?, policy_text = ?, normalization_tags = ?, updated_at = ?
            WHERE id = ?""",
            (
              json.dumps(normalized, ensure_ascii=False),
              result.policy_text,
              json.dumps(result.tags, ensure_ascii=False),
              now,
              row["id"],
            ),
          )
          success_count += 1

      await db.commit()

    logger.info("Re-normalized %d/%d pending entries for session=%s", success_count, len(rows), session_id)
    return success_count

  async def get_all_policies(self, session_id: str) -> list[dict]:
    """セッションの全ポリシーを取得する（作成順）

    Returns:
      [{question_id, rule, confidence, is_core, permanence, normalization_tags}, ...]
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute(
        """SELECT question_id, policy_text, confidence, is_core_rule, permanence, normalization_tags
        FROM answer_layers
        WHERE session_id = ? AND policy_text IS NOT NULL
        ORDER BY created_at ASC""",
        (session_id,),
      )
      rows = await cursor.fetchall()

    policies = []
    for row in rows:
      tags = json.loads(row["normalization_tags"]) if row["normalization_tags"] else []
      policies.append({
        "question_id": row["question_id"],
        "rule": row["policy_text"],
        "confidence": row["confidence"],
        "is_core": bool(row["is_core_rule"]),
        "permanence": row["permanence"],
        "normalization_tags": tags,
      })

    return policies
