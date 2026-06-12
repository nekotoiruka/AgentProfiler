"""SessionManager ユニットテスト

セッション作成・回答保存・完了・有効期限管理のテスト。
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.session_manager import (
  SessionManager,
  SessionNotFoundError,
  SessionNotModifiableError,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
  """テスト用の一時DBパス"""
  return tmp_path / "test_sessions.db"


@pytest.fixture
async def manager(db_path: Path) -> SessionManager:
  """初期化済みSessionManagerを返す"""
  mgr = SessionManager(db_path=db_path, total_questions=3)
  await mgr.init_db()
  return mgr


class TestCreateSession:
  """create_session のテスト"""

  async def test_returns_uuid_string(self, manager: SessionManager):
    session_id = await manager.create_session()
    # UUID4形式: 8-4-4-4-12 の36文字
    assert len(session_id) == 36
    assert session_id.count("-") == 4

  async def test_creates_active_session(self, manager: SessionManager):
    session_id = await manager.create_session()
    session = await manager.get_session(session_id)
    assert session.status == "active"
    assert session.session_id == session_id
    assert session.answers == {}

  async def test_unique_ids(self, manager: SessionManager):
    id1 = await manager.create_session()
    id2 = await manager.create_session()
    assert id1 != id2


class TestGetSession:
  """get_session のテスト"""

  async def test_not_found_raises_error(self, manager: SessionManager):
    with pytest.raises(SessionNotFoundError):
      await manager.get_session("nonexistent-id")

  async def test_returns_session_with_answers(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.submit_answer(session_id, "q1", choice_id="a")
    session = await manager.get_session(session_id)
    assert "q1" in session.answers
    assert session.answers["q1"].choice_id == "a"


class TestSubmitAnswer:
  """submit_answer のテスト"""

  async def test_saves_choice_answer(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.submit_answer(session_id, "q1", choice_id="b")
    session = await manager.get_session(session_id)
    assert session.answers["q1"].choice_id == "b"
    assert session.answers["q1"].text is None

  async def test_saves_text_answer(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.submit_answer(session_id, "q1", text="自由記述テスト")
    session = await manager.get_session(session_id)
    assert session.answers["q1"].text == "自由記述テスト"
    assert session.answers["q1"].choice_id is None

  async def test_overwrites_previous_answer(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.submit_answer(session_id, "q1", choice_id="a")
    await manager.submit_answer(session_id, "q1", choice_id="c")
    session = await manager.get_session(session_id)
    assert session.answers["q1"].choice_id == "c"

  async def test_records_timestamp(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.submit_answer(session_id, "q1", choice_id="a")
    session = await manager.get_session(session_id)
    assert session.answers["q1"].submitted_at is not None

  async def test_not_found_raises_error(self, manager: SessionManager):
    with pytest.raises(SessionNotFoundError):
      await manager.submit_answer("nonexistent", "q1", choice_id="a")

  async def test_complete_session_raises_error(self, manager: SessionManager):
    session_id = await manager.create_session()
    # 全質問回答して完了させる
    await manager.submit_answer(session_id, "q1", choice_id="a")
    await manager.submit_answer(session_id, "q2", choice_id="b")
    await manager.submit_answer(session_id, "q3", choice_id="c")
    await manager.mark_complete(session_id)

    with pytest.raises(SessionNotModifiableError):
      await manager.submit_answer(session_id, "q1", choice_id="d")

  async def test_expired_session_raises_error(
    self, manager: SessionManager, db_path: Path
  ):
    import aiosqlite

    session_id = await manager.create_session()

    # updated_at を31日前に強制変更
    old_time = (
      datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat()
    async with aiosqlite.connect(db_path) as db:
      await db.execute(
        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
        (old_time, session_id),
      )
      await db.commit()

    with pytest.raises(SessionNotModifiableError):
      await manager.submit_answer(session_id, "q1", choice_id="a")


class TestIsComplete:
  """is_complete のテスト"""

  async def test_incomplete_returns_false(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.submit_answer(session_id, "q1", choice_id="a")
    assert await manager.is_complete(session_id) is False

  async def test_all_answered_returns_true(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.submit_answer(session_id, "q1", choice_id="a")
    await manager.submit_answer(session_id, "q2", choice_id="b")
    await manager.submit_answer(session_id, "q3", choice_id="c")
    assert await manager.is_complete(session_id) is True

  async def test_not_found_raises_error(self, manager: SessionManager):
    with pytest.raises(SessionNotFoundError):
      await manager.is_complete("nonexistent")


class TestMarkComplete:
  """mark_complete のテスト"""

  async def test_changes_status_to_complete(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.mark_complete(session_id)
    session = await manager.get_session(session_id)
    assert session.status == "complete"

  async def test_not_found_raises_error(self, manager: SessionManager):
    with pytest.raises(SessionNotFoundError):
      await manager.mark_complete("nonexistent")

  async def test_already_complete_raises_error(self, manager: SessionManager):
    session_id = await manager.create_session()
    await manager.mark_complete(session_id)
    with pytest.raises(SessionNotModifiableError):
      await manager.mark_complete(session_id)


class TestUpdateScores:
  """update_scores のテスト"""

  async def test_saves_scores_and_profile_id(self, manager: SessionManager):
    from app.models.scores import AxisScores, NormalizedScores

    session_id = await manager.create_session()
    raw = AxisScores(
      extroverted_introverted=10,
      sensing_intuition=-5,
      thinking_feeling=3,
      judging_perceiving=0,
    )
    norm = NormalizedScores(
      extroverted_introverted=0.75,
      sensing_intuition=0.30,
      thinking_feeling=0.60,
      judging_perceiving=0.50,
    )
    await manager.update_scores(session_id, raw, norm, "prof_000001")
    session = await manager.get_session(session_id)
    assert session.raw_scores == raw
    assert session.normalized_scores == norm
    assert session.profile_id == "prof_000001"

  async def test_not_found_raises_error(self, manager: SessionManager):
    from app.models.scores import AxisScores, NormalizedScores

    raw = AxisScores()
    norm = NormalizedScores(
      extroverted_introverted=0.5,
      sensing_intuition=0.5,
      thinking_feeling=0.5,
      judging_perceiving=0.5,
    )
    with pytest.raises(SessionNotFoundError):
      await manager.update_scores("nonexistent", raw, norm, "prof_000001")


class TestExpiration:
  """30日超非活動セッションの自動失効テスト"""

  async def test_get_session_expires_inactive(
    self, manager: SessionManager, db_path: Path
  ):
    import aiosqlite

    session_id = await manager.create_session()

    # updated_at を31日前に強制変更
    old_time = (
      datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat()
    async with aiosqlite.connect(db_path) as db:
      await db.execute(
        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
        (old_time, session_id),
      )
      await db.commit()

    session = await manager.get_session(session_id)
    assert session.status == "expired"

  async def test_29_days_not_expired(
    self, manager: SessionManager, db_path: Path
  ):
    import aiosqlite

    session_id = await manager.create_session()

    # updated_at を29日前に設定 → 期限切れではない
    recent_time = (
      datetime.now(timezone.utc) - timedelta(days=29)
    ).isoformat()
    async with aiosqlite.connect(db_path) as db:
      await db.execute(
        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
        (recent_time, session_id),
      )
      await db.commit()

    session = await manager.get_session(session_id)
    assert session.status == "active"
