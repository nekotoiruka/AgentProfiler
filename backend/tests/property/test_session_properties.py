"""Session Manager プロパティベーステスト

Feature: agent-profiler
Property 12: Session answer persistence round-trip
Property 13: Session state machine transitions
Validates: Requirements 10.1, 10.3, 10.5, 10.6, 10.7
"""

import asyncio
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.models.session import Answer, Session
from app.services.session_manager import (
  SessionManager,
  SessionNotFoundError,
  SessionNotModifiableError,
)


# --- Hypothesis ストラテジー ---

# question_id: 英数字で 1〜20 文字
_question_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=20,
)

# choice_id: 英数字で 1〜10 文字
_choice_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=10,
)

# free-text: 1〜100 文字
_text_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
  min_size=1,
  max_size=100,
)

# total_questions: セッションの総質問数
_total_questions_st = st.integers(min_value=1, max_value=20)


def _make_db_path() -> Path:
  """各テスト例で独立した一時DBパスを生成する"""
  tmp_dir = tempfile.mkdtemp()
  return Path(tmp_dir) / "test.db"


# --- Property 12: Session answer persistence round-trip ---
# Feature: agent-profiler, Property 12: Session answer persistence round-trip


@settings(max_examples=200)
@given(
  question_id=_question_id_st,
  choice_id=_choice_id_st,
  total_questions=_total_questions_st,
)
def test_session_answer_persistence_round_trip_choice(
  question_id: str,
  choice_id: str,
  total_questions: int,
) -> None:
  """任意の choice_id 回答をアクティブセッションに送信後、
  即座にセッションを取得すると、正しい question_id, choice_id,
  および有効な timestamp が格納されていることを検証する。

  **Validates: Requirements 10.1, 10.5**
  """

  async def _inner() -> None:
    db_path = _make_db_path()
    mgr = SessionManager(db_path=db_path, total_questions=total_questions)
    await mgr.init_db()

    session_id = await mgr.create_session()

    # 回答送信
    await mgr.submit_answer(
      session_id=session_id,
      question_id=question_id,
      choice_id=choice_id,
    )

    # セッション取得
    session = await mgr.get_session(session_id)

    # 回答が格納されている
    assert question_id in session.answers
    answer = session.answers[question_id]
    assert answer.question_id == question_id
    assert answer.choice_id == choice_id
    assert answer.text is None
    # タイムスタンプが有効（datetime型である）
    assert isinstance(answer.submitted_at, datetime)

  asyncio.run(_inner())


@settings(max_examples=200)
@given(
  question_id=_question_id_st,
  text_content=_text_st,
  total_questions=_total_questions_st,
)
def test_session_answer_persistence_round_trip_text(
  question_id: str,
  text_content: str,
  total_questions: int,
) -> None:
  """任意のフリーテキスト回答をアクティブセッションに送信後、
  即座にセッションを取得すると、正しい question_id, text,
  および有効な timestamp が格納されていることを検証する。

  **Validates: Requirements 10.1, 10.5**
  """

  async def _inner() -> None:
    db_path = _make_db_path()
    mgr = SessionManager(db_path=db_path, total_questions=total_questions)
    await mgr.init_db()

    session_id = await mgr.create_session()

    # フリーテキスト回答送信
    await mgr.submit_answer(
      session_id=session_id,
      question_id=question_id,
      text=text_content,
    )

    # セッション取得
    session = await mgr.get_session(session_id)

    # 回答が格納されている
    assert question_id in session.answers
    answer = session.answers[question_id]
    assert answer.question_id == question_id
    assert answer.choice_id is None
    assert answer.text == text_content
    assert isinstance(answer.submitted_at, datetime)

  asyncio.run(_inner())


@settings(max_examples=200)
@given(
  question_id=_question_id_st,
  first_choice=_choice_id_st,
  second_choice=_choice_id_st,
  total_questions=_total_questions_st,
)
def test_session_answer_overwrite_stores_latest_only(
  question_id: str,
  first_choice: str,
  second_choice: str,
  total_questions: int,
) -> None:
  """同じ question_id に対して2回回答を送信した場合、
  最新の回答のみが格納されることを検証する。

  **Validates: Requirements 10.1, 10.5**
  """
  # 異なる回答でのみテスト意味がある
  assume(first_choice != second_choice)

  async def _inner() -> None:
    db_path = _make_db_path()
    mgr = SessionManager(db_path=db_path, total_questions=total_questions)
    await mgr.init_db()

    session_id = await mgr.create_session()

    # 1回目の回答
    await mgr.submit_answer(
      session_id=session_id,
      question_id=question_id,
      choice_id=first_choice,
    )

    # 2回目の回答（上書き）
    await mgr.submit_answer(
      session_id=session_id,
      question_id=question_id,
      choice_id=second_choice,
    )

    # セッション取得
    session = await mgr.get_session(session_id)

    # 最新の回答のみが格納されている
    assert question_id in session.answers
    answer = session.answers[question_id]
    assert answer.choice_id == second_choice

  asyncio.run(_inner())


# --- Property 13: Session state machine transitions ---
# Feature: agent-profiler, Property 13: Session state machine transitions


@settings(max_examples=200)
@given(total_questions=st.integers(min_value=1, max_value=10))
def test_session_transitions_to_complete_when_all_answered(
  total_questions: int,
) -> None:
  """N問のセッションで全N問を回答後に mark_complete() を呼ぶと、
  セッションは "complete" に遷移する。

  **Validates: Requirements 10.3**
  """

  async def _inner() -> None:
    db_path = _make_db_path()
    mgr = SessionManager(db_path=db_path, total_questions=total_questions)
    await mgr.init_db()

    session_id = await mgr.create_session()

    # 全問回答
    for i in range(total_questions):
      await mgr.submit_answer(
        session_id=session_id,
        question_id=f"q_{i}",
        choice_id=f"c_{i}",
      )

    # 完了判定
    assert await mgr.is_complete(session_id) is True

    # 完了マーク
    await mgr.mark_complete(session_id)

    # ステータス確認
    session = await mgr.get_session(session_id)
    assert session.status == "complete"

  asyncio.run(_inner())


@settings(max_examples=200)
@given(
  total_questions=st.integers(min_value=2, max_value=10),
  data=st.data(),
)
def test_session_not_complete_when_partially_answered(
  total_questions: int,
  data: st.DataObject,
) -> None:
  """N問のセッションで N 未満の回答数では is_complete() が False を返す。

  **Validates: Requirements 10.3**
  """
  # 1 〜 total_questions-1 の回答数を生成
  n_answered = data.draw(
    st.integers(min_value=1, max_value=total_questions - 1)
  )

  async def _inner() -> None:
    db_path = _make_db_path()
    mgr = SessionManager(db_path=db_path, total_questions=total_questions)
    await mgr.init_db()

    session_id = await mgr.create_session()

    # 一部回答
    for i in range(n_answered):
      await mgr.submit_answer(
        session_id=session_id,
        question_id=f"q_{i}",
        choice_id=f"c_{i}",
      )

    # 未完了
    assert await mgr.is_complete(session_id) is False

  asyncio.run(_inner())


@settings(max_examples=200)
@given(
  total_questions=st.integers(min_value=1, max_value=10),
  extra_question_id=_question_id_st,
  extra_choice_id=_choice_id_st,
)
def test_complete_session_rejects_submissions(
  total_questions: int,
  extra_question_id: str,
  extra_choice_id: str,
) -> None:
  """完了セッションへの回答送信は SessionNotModifiableError で拒否される。

  **Validates: Requirements 10.7**
  """

  async def _inner() -> None:
    db_path = _make_db_path()
    mgr = SessionManager(db_path=db_path, total_questions=total_questions)
    await mgr.init_db()

    session_id = await mgr.create_session()

    # 全問回答して完了
    for i in range(total_questions):
      await mgr.submit_answer(
        session_id=session_id,
        question_id=f"q_{i}",
        choice_id=f"c_{i}",
      )
    await mgr.mark_complete(session_id)

    # 完了セッションへの追加回答は拒否
    rejected = False
    try:
      await mgr.submit_answer(
        session_id=session_id,
        question_id=extra_question_id,
        choice_id=extra_choice_id,
      )
    except SessionNotModifiableError:
      rejected = True

    assert rejected is True

  asyncio.run(_inner())


@settings(max_examples=200)
@given(
  total_questions=st.integers(min_value=1, max_value=10),
  extra_question_id=_question_id_st,
  extra_choice_id=_choice_id_st,
)
def test_expired_session_rejects_submissions(
  total_questions: int,
  extra_question_id: str,
  extra_choice_id: str,
) -> None:
  """30日超非アクティブセッションへの回答送信は拒否される。

  **Validates: Requirements 10.6, 10.7**
  """

  async def _inner() -> None:
    db_path = _make_db_path()
    mgr = SessionManager(db_path=db_path, total_questions=total_questions)
    await mgr.init_db()

    session_id = await mgr.create_session()

    # updated_at を31日前に直接操作して有効期限切れ状態を作る
    expired_time = (
      datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat()
    async with aiosqlite.connect(db_path) as db:
      await db.execute(
        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
        (expired_time, session_id),
      )
      await db.commit()

    # 期限切れセッションへの回答送信は拒否される
    rejected = False
    try:
      await mgr.submit_answer(
        session_id=session_id,
        question_id=extra_question_id,
        choice_id=extra_choice_id,
      )
    except SessionNotModifiableError:
      rejected = True

    assert rejected is True

  asyncio.run(_inner())


@settings(max_examples=200)
@given(total_questions=st.integers(min_value=1, max_value=10))
def test_expired_session_status_on_get(
  total_questions: int,
) -> None:
  """30日超非アクティブセッションを get_session() すると
  status が "expired" に遷移していることを検証する。

  **Validates: Requirements 10.6**
  """

  async def _inner() -> None:
    db_path = _make_db_path()
    mgr = SessionManager(db_path=db_path, total_questions=total_questions)
    await mgr.init_db()

    session_id = await mgr.create_session()

    # updated_at を31日前に直接操作
    expired_time = (
      datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat()
    async with aiosqlite.connect(db_path) as db:
      await db.execute(
        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
        (expired_time, session_id),
      )
      await db.commit()

    # セッション取得
    session = await mgr.get_session(session_id)

    # expired に遷移している
    assert session.status == "expired"

  asyncio.run(_inner())
