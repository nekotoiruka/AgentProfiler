"""フィードバック記録・重み調整サービス"""

import json
import logging
from datetime import datetime, timezone

import aiosqlite

logger = logging.getLogger(__name__)

# 次元キーワードマッピング: フィードバックテキストから次元を特定
DIMENSION_KEYWORDS = {
  "root_cause_first": ["根本原因", "root cause", "原因分析", "根本"],
  "customer_first": ["顧客", "ユーザー", "customer", "user", "UX"],
  "speed_first": ["スピード", "速度", "迅速", "speed", "fast", "quick"],
  "data_driven": ["データ", "定量", "数値", "data", "metrics", "エビデンス"],
  "consensus_driven": ["合意", "チーム", "全員", "consensus", "team"],
  "long_term_bias": ["長期", "将来", "持続", "long-term", "sustainable"],
  "speed_vs_quality": ["品質", "スピード", "quality", "speed"],
  "innovation_vs_stability": ["革新", "安定", "innovation", "stability"],
  "individual_vs_team": ["個人", "チーム", "individual", "team"],
  "autonomy_vs_consensus": ["自律", "合意", "autonomy", "consensus"],
}


class FeedbackService:
  """フィードバック記録・重み調整サービス

  ユーザーがエージェント回答を評価し、10件以上の reject が
  特定次元に蓄積した場合に自動重み調整を実行する。

  重み調整アルゴリズム:
  1. reject の user_correction テキストからキーワードを抽出
  2. priority / tradeoff 次元とのマッチングを実行
  3. マッチした次元の重みを ±0.1 調整（方向は修正パターンから推定）
  4. 結果を 0.0〜1.0 にクランプ
  5. modification_history に記録
  """

  def __init__(self, db_path: str, threshold: int = 10, step: float = 0.1):
    self._db_path = db_path
    self._threshold = threshold
    self._step = step

  async def init_db(self) -> None:
    """feedback_records テーブルを初期化する"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS feedback_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          agent_id TEXT NOT NULL,
          thread_id TEXT NOT NULL,
          turn_id TEXT NOT NULL,
          feedback_type TEXT NOT NULL CHECK(feedback_type IN ('approve', 'reject')),
          user_correction TEXT,
          original_response TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_agent_date
        ON feedback_records(agent_id, created_at)
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_agent_type
        ON feedback_records(agent_id, feedback_type)
      """)
      # 変更履歴テーブル
      await db.execute("""
        CREATE TABLE IF NOT EXISTS modification_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_id TEXT NOT NULL,
          field_name TEXT NOT NULL,
          previous_value REAL NOT NULL,
          new_value REAL NOT NULL,
          adjustment_reason TEXT NOT NULL,
          feedback_count INTEGER NOT NULL,
          created_at TEXT NOT NULL
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_modification_profile
        ON modification_history(profile_id, created_at)
      """)
      await db.commit()

  async def record_feedback(
    self,
    agent_id: str,
    thread_id: str,
    turn_id: str,
    feedback_type: str,
    user_correction: str | None,
    original_response: str,
  ) -> dict:
    """フィードバックを記録する

    Returns:
      {feedback_id: int, created_at: str}

    Raises:
      ValueError: feedback_type が "reject" で user_correction が空の場合
    """
    if feedback_type == "reject" and not user_correction:
      raise ValueError("user_correction is required for reject feedback")

    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(self._db_path) as db:
      cursor = await db.execute(
        """INSERT INTO feedback_records
        (agent_id, thread_id, turn_id, feedback_type, user_correction, original_response, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (agent_id, thread_id, turn_id, feedback_type, user_correction, original_response, now),
      )
      await db.commit()
      feedback_id = cursor.lastrowid

    return {"feedback_id": feedback_id, "created_at": now}

  async def check_and_adjust(
    self, agent_id: str, current_weights: dict[str, float] | None = None
  ) -> list[dict]:
    """蓄積フィードバックを分析し、重み調整を実行する

    Returns:
      実行された調整のリスト [{field_name, previous_value, new_value, adjustment_reason, feedback_count, timestamp}]
    """
    if current_weights is None:
      return []

    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute(
        """SELECT user_correction FROM feedback_records
        WHERE agent_id = ? AND feedback_type = 'reject' AND user_correction IS NOT NULL""",
        (agent_id,),
      )
      rows = await cursor.fetchall()

    corrections = [row["user_correction"] for row in rows]

    if len(corrections) < self._threshold:
      return []

    # キーワード抽出と次元マッチング
    dimension_counts = self._extract_dimension_keywords(corrections)

    adjustments = []
    now = datetime.now(timezone.utc).isoformat()

    for dimension, count in dimension_counts.items():
      if count >= self._threshold and dimension in current_weights:
        previous = current_weights[dimension]
        # 修正が多い → 現在の重みを下げる方向
        new_value = self._adjust_weight(previous, "decrease", self._step)

        if new_value != previous:
          adjustment = {
            "field_name": dimension,
            "previous_value": previous,
            "new_value": new_value,
            "adjustment_reason": f"{count}件のrejectフィードバックで'{dimension}'次元の調整が必要と判定",
            "feedback_count": count,
            "timestamp": now,
          }
          adjustments.append(adjustment)
          current_weights[dimension] = new_value

    # 調整結果を modification_history に保存
    if adjustments:
      async with aiosqlite.connect(self._db_path) as db:
        for adj in adjustments:
          await db.execute(
            """INSERT INTO modification_history
            (profile_id, field_name, previous_value, new_value, adjustment_reason, feedback_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, adj["field_name"], adj["previous_value"], adj["new_value"],
             adj["adjustment_reason"], adj["feedback_count"], adj["timestamp"]),
          )
        await db.commit()

    return adjustments

  async def get_modification_history(self, profile_id: str) -> list[dict]:
    """プロファイルの変更履歴を時系列順で取得する"""
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute(
        """SELECT field_name, previous_value, new_value, adjustment_reason, feedback_count, created_at
        FROM modification_history
        WHERE profile_id = ?
        ORDER BY created_at ASC""",
        (profile_id,),
      )
      rows = await cursor.fetchall()

    return [
      {
        "field_name": row["field_name"],
        "previous_value": row["previous_value"],
        "new_value": row["new_value"],
        "adjustment_reason": row["adjustment_reason"],
        "feedback_count": row["feedback_count"],
        "timestamp": row["created_at"],
      }
      for row in rows
    ]

  def _extract_dimension_keywords(self, corrections: list[str]) -> dict[str, int]:
    """修正テキスト群から次元キーワードの出現頻度を集計する"""
    counts: dict[str, int] = {}

    for correction in corrections:
      text_lower = correction.lower()
      for dimension, keywords in DIMENSION_KEYWORDS.items():
        for keyword in keywords:
          if keyword.lower() in text_lower:
            counts[dimension] = counts.get(dimension, 0) + 1
            break  # 1つの修正テキストにつき各次元1回のみカウント

    return counts

  def _adjust_weight(self, current: float, direction: str, step: float) -> float:
    """重みを調整し 0.0〜1.0 にクランプする"""
    adjusted = current + step if direction == "increase" else current - step
    return round(max(0.0, min(1.0, adjusted)), 2)
