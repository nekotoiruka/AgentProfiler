"""Decision Engine REST API ルーター"""

from fastapi import APIRouter, HTTPException, Query

import aiosqlite

from app.decision_engine.dependencies import (
  get_answer_pipeline,
  get_decision_engine_settings,
  get_feedback_service,
)
from app.decision_engine.models import (
  FeedbackListResponse,
  FeedbackResponse,
  FeedbackSubmission,
)

from pathlib import Path

decision_router = APIRouter(prefix="/api")


def _get_db_path() -> str:
  """decision_engine.db のパスを返す"""
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  return str(data_dir / "decision_engine.db")


@decision_router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def create_feedback(body: FeedbackSubmission):
  """フィードバックを記録する"""
  service = get_feedback_service()
  await service.init_db()

  try:
    result = await service.record_feedback(
      agent_id=body.agent_id,
      thread_id=body.thread_id,
      turn_id=body.turn_id,
      feedback_type=body.feedback_type.value,
      user_correction=body.user_correction,
      original_response="",  # 本番では thread から取得
    )
  except ValueError as e:
    raise HTTPException(
      status_code=422,
      detail={"error": "validation_error", "message": str(e)},
    )

  return FeedbackResponse(
    feedback_id=result["feedback_id"],
    created_at=result["created_at"],
  )


@decision_router.get("/feedback/{agent_id}", response_model=FeedbackListResponse)
async def list_feedback(
  agent_id: str,
  limit: int = Query(default=20, ge=1, le=100),
  offset: int = Query(default=0, ge=0),
):
  """フィードバック一覧を取得する（ページネーション付き）"""
  db_path = _get_db_path()

  async with aiosqlite.connect(db_path) as db:
    db.row_factory = aiosqlite.Row

    # トータルカウント
    cursor = await db.execute(
      "SELECT COUNT(*) as cnt FROM feedback_records WHERE agent_id = ?",
      (agent_id,),
    )
    row = await cursor.fetchone()
    total = row["cnt"] if row else 0

    # ページネーション付き結果
    cursor = await db.execute(
      """SELECT id, agent_id, thread_id, turn_id, feedback_type,
              user_correction, original_response, created_at
      FROM feedback_records WHERE agent_id = ?
      ORDER BY created_at DESC LIMIT ? OFFSET ?""",
      (agent_id, limit, offset),
    )
    rows = await cursor.fetchall()

  items = [dict(row) for row in rows]
  return FeedbackListResponse(items=items, total=total, limit=limit, offset=offset)


@decision_router.get("/profiles/{profile_id}/modification-history")
async def get_modification_history(profile_id: str):
  """プロファイルの変更履歴を取得する"""
  service = get_feedback_service()
  await service.init_db()
  history = await service.get_modification_history(profile_id)
  return {"items": history}


@decision_router.get("/profiles/{profile_id}/decision-engine")
async def get_decision_engine_data(profile_id: str):
  """Decision engine データを取得する（ProfileGenerator 統合後に拡張予定）"""
  return {
    "profile_id": profile_id,
    "decision_model": None,
    "failure_patterns": None,
    "context_adaptation": None,
    "reasoning_flow": None,
    "rule_hierarchy": None,
  }


@decision_router.post("/sessions/{session_id}/re-normalize")
async def re_normalize_pending(session_id: str):
  """pending_normalization エントリを再処理する"""
  pipeline = get_answer_pipeline()
  await pipeline.init_db()
  count = await pipeline.re_normalize_pending(session_id)
  return {"re_normalized_count": count, "session_id": session_id}
