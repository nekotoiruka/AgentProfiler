"""Property 8: フィードバック記録のラウンドトリップ

送信した全フィールドが取得時に変更なく保持されることを検証する。

**Validates: Requirements 11.3**
"""

import os
import tempfile

import aiosqlite
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.feedback_service import FeedbackService


uuid_strategy = st.from_regex(
  r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
  fullmatch=True,
)


@given(
  agent_id=uuid_strategy,
  thread_id=uuid_strategy,
  turn_id=uuid_strategy,
  user_correction=st.text(min_size=1, max_size=200),
  original_response=st.text(min_size=1, max_size=500),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_feedback_roundtrip_reject(agent_id, thread_id, turn_id, user_correction, original_response):
  """reject フィードバックの全フィールドが保持される"""
  fd, db_path = tempfile.mkstemp(suffix=".db")
  os.close(fd)

  try:
    service = FeedbackService(db_path=db_path, threshold=10, step=0.1)
    await service.init_db()

    result = await service.record_feedback(
      agent_id=agent_id,
      thread_id=thread_id,
      turn_id=turn_id,
      feedback_type="reject",
      user_correction=user_correction,
      original_response=original_response,
    )

    # DB から直接取得して検証
    async with aiosqlite.connect(db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute(
        "SELECT * FROM feedback_records WHERE id = ?", (result["feedback_id"],)
      )
      row = await cursor.fetchone()

    assert row["agent_id"] == agent_id
    assert row["thread_id"] == thread_id
    assert row["turn_id"] == turn_id
    assert row["feedback_type"] == "reject"
    assert row["user_correction"] == user_correction
    assert row["original_response"] == original_response
    assert row["created_at"] == result["created_at"]
  finally:
    if os.path.exists(db_path):
      os.unlink(db_path)


@given(
  agent_id=uuid_strategy,
  thread_id=uuid_strategy,
  turn_id=uuid_strategy,
  original_response=st.text(min_size=1, max_size=500),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_feedback_roundtrip_approve(agent_id, thread_id, turn_id, original_response):
  """approve フィードバックの全フィールドが保持される"""
  fd, db_path = tempfile.mkstemp(suffix=".db")
  os.close(fd)

  try:
    service = FeedbackService(db_path=db_path, threshold=10, step=0.1)
    await service.init_db()

    result = await service.record_feedback(
      agent_id=agent_id,
      thread_id=thread_id,
      turn_id=turn_id,
      feedback_type="approve",
      user_correction=None,
      original_response=original_response,
    )

    async with aiosqlite.connect(db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute(
        "SELECT * FROM feedback_records WHERE id = ?", (result["feedback_id"],)
      )
      row = await cursor.fetchone()

    assert row["agent_id"] == agent_id
    assert row["feedback_type"] == "approve"
    assert row["user_correction"] is None
    assert row["original_response"] == original_response
  finally:
    if os.path.exists(db_path):
      os.unlink(db_path)
