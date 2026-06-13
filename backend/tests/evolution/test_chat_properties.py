"""ChatService プロパティベーステスト

Feature: agent-evolution
Property 25: Conversation history accumulation
Property 26: Context window limit
Property 27: Chat turn persistence
Validates: Requirements 17.3, 17.4, 17.6
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.evolution.chat import ChatService
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.routing_engine import RoutingEngine


# --- Hypothesis ストラテジー ---

# agent_id: 英数字とハイフンで構成される文字列
_agent_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
  min_size=1,
  max_size=30,
).filter(lambda s: s.strip() != "")

# メッセージ: 1〜50文字のテキスト
_message_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
  min_size=1,
  max_size=50,
).filter(lambda s: s.strip() != "")

# メッセージ送信回数: 1〜5
_num_messages_st = st.integers(min_value=1, max_value=5)

# コンテキストウィンドウサイズ: 2〜10
_context_window_st = st.integers(min_value=2, max_value=10)


# --- ヘルパー ---


def _make_mock_routing_engine(response: str = "I am a helpful assistant.") -> RoutingEngine:
  """RoutingEngine のモック。route() が固定レスポンスを返す。"""
  engine = MagicMock(spec=RoutingEngine)
  engine.route = AsyncMock(return_value=response)
  return engine


def _make_mock_clm() -> ContextLayerManager:
  """ContextLayerManager のモック。get_base_os が KeyError を送出する（デフォルトプロンプト使用）。"""
  clm = MagicMock(spec=ContextLayerManager)
  clm.get_base_os = MagicMock(side_effect=KeyError("Profile not loaded"))
  return clm


async def _create_chat_service(tmp_path, context_window: int = 20) -> ChatService:
  """テスト用 ChatService を構築する。

  各呼び出しで一意の DB ファイルを使用し、example 間の衝突を回避する。
  """
  db_path = str(tmp_path / f"chat_{uuid.uuid4().hex}.db")
  svc = ChatService(
    db_path=db_path,
    routing_engine=_make_mock_routing_engine(),
    context_layer_manager=_make_mock_clm(),
    context_window=context_window,
  )
  await svc.init_db()
  return svc


# =============================================================================
# Property 25: Conversation history accumulation
# Feature: agent-evolution
# =============================================================================


class TestConversationHistoryAccumulation:
  """Property 25: After N messages, history has 2*N turns (user+assistant per message).

  N 回の send_message 呼び出し後、get_history で取得できるターン数が
  正確に 2*N（各メッセージにつき user + assistant の1ペア）であること。

  **Validates: Requirements 17.3**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_id=_agent_id_st,
    messages=st.lists(_message_st, min_size=1, max_size=5),
  )
  async def test_history_grows_by_two_per_message(
    self,
    agent_id: str,
    messages: list[str],
    tmp_path,
  ) -> None:
    """N 回 send_message 後、履歴に 2*N ターンが蓄積されること。

    **Validates: Requirements 17.3**
    """
    svc = await _create_chat_service(tmp_path)
    n = len(messages)

    # 同一スレッドに N 回メッセージを送信
    thread_id: str | None = None
    for msg in messages:
      result = await svc.send_message(agent_id, msg, thread_id=thread_id)
      thread_id = result["thread_id"]

    # 履歴を全件取得
    history = await svc.get_history(thread_id)

    assert len(history) == 2 * n, (
      f"Expected {2 * n} turns after {n} messages, got {len(history)}"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_id=_agent_id_st,
    messages=st.lists(_message_st, min_size=1, max_size=5),
  )
  async def test_history_alternates_user_assistant(
    self,
    agent_id: str,
    messages: list[str],
    tmp_path,
  ) -> None:
    """履歴のロールが user → assistant → user → assistant ... と交互であること。

    **Validates: Requirements 17.3**
    """
    svc = await _create_chat_service(tmp_path)

    thread_id: str | None = None
    for msg in messages:
      result = await svc.send_message(agent_id, msg, thread_id=thread_id)
      thread_id = result["thread_id"]

    history = await svc.get_history(thread_id)

    for i, turn in enumerate(history):
      expected_role = "user" if i % 2 == 0 else "assistant"
      assert turn["role"] == expected_role, (
        f"Turn {i}: expected role='{expected_role}', got '{turn['role']}'"
      )


# =============================================================================
# Property 26: Context window limit
# Feature: agent-evolution
# =============================================================================


class TestContextWindowLimit:
  """Property 26: _get_recent_history never returns more than context_window turns.

  コンテキストウィンドウサイズ W を設定し、任意の数のメッセージ送信後、
  _get_recent_history(thread_id, W) の結果が W を超えないこと。

  **Validates: Requirements 17.4**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_id=_agent_id_st,
    messages=st.lists(_message_st, min_size=1, max_size=5),
    context_window=_context_window_st,
  )
  async def test_recent_history_bounded_by_context_window(
    self,
    agent_id: str,
    messages: list[str],
    context_window: int,
    tmp_path,
  ) -> None:
    """_get_recent_history の結果が context_window 以下であること。

    **Validates: Requirements 17.4**
    """
    svc = await _create_chat_service(tmp_path, context_window=context_window)

    thread_id: str | None = None
    for msg in messages:
      result = await svc.send_message(agent_id, msg, thread_id=thread_id)
      thread_id = result["thread_id"]

    # 内部メソッドを直接検証
    recent = await svc._get_recent_history(thread_id, context_window)

    assert len(recent) <= context_window, (
      f"_get_recent_history returned {len(recent)} turns, "
      f"but context_window is {context_window}"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_id=_agent_id_st,
    messages=st.lists(_message_st, min_size=3, max_size=5),
    context_window=st.integers(min_value=2, max_value=4),
  )
  async def test_context_window_returns_most_recent_turns(
    self,
    agent_id: str,
    messages: list[str],
    context_window: int,
    tmp_path,
  ) -> None:
    """context_window が全ターン数未満の場合、最新のターンが返ること。

    **Validates: Requirements 17.4**
    """
    svc = await _create_chat_service(tmp_path, context_window=context_window)

    thread_id: str | None = None
    for msg in messages:
      result = await svc.send_message(agent_id, msg, thread_id=thread_id)
      thread_id = result["thread_id"]

    # 全履歴と最新 context_window 件を比較
    full_history = await svc.get_history(thread_id)
    recent = await svc._get_recent_history(thread_id, context_window)

    # recent は full_history の末尾 context_window 件と一致
    expected = [
      {"role": h["role"], "content": h["content"]}
      for h in full_history[-context_window:]
    ]
    assert recent == expected, (
      f"_get_recent_history should return last {context_window} turns of full history"
    )


# =============================================================================
# Property 27: Chat turn persistence
# Feature: agent-evolution
# =============================================================================


class TestChatTurnPersistence:
  """Property 27: Every stored turn is retrievable via get_history.

  send_message で保存された全ターン（user + assistant）が
  get_history で正確に取得できること。

  **Validates: Requirements 17.6**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_id=_agent_id_st,
    messages=st.lists(_message_st, min_size=1, max_size=5),
  )
  async def test_all_user_messages_persisted(
    self,
    agent_id: str,
    messages: list[str],
    tmp_path,
  ) -> None:
    """全ユーザーメッセージが get_history で取得できること。

    **Validates: Requirements 17.6**
    """
    svc = await _create_chat_service(tmp_path)

    thread_id: str | None = None
    for msg in messages:
      result = await svc.send_message(agent_id, msg, thread_id=thread_id)
      thread_id = result["thread_id"]

    history = await svc.get_history(thread_id)

    # ユーザーターンのコンテンツを抽出
    user_turns = [h["content"] for h in history if h["role"] == "user"]

    assert user_turns == messages, (
      f"User messages mismatch: expected {messages}, got {user_turns}"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_id=_agent_id_st,
    messages=st.lists(_message_st, min_size=1, max_size=5),
  )
  async def test_all_assistant_responses_persisted(
    self,
    agent_id: str,
    messages: list[str],
    tmp_path,
  ) -> None:
    """全アシスタントレスポンスが get_history で取得できること。

    **Validates: Requirements 17.6**
    """
    expected_response = "I am a helpful assistant."
    svc = await _create_chat_service(tmp_path)

    thread_id: str | None = None
    for msg in messages:
      result = await svc.send_message(agent_id, msg, thread_id=thread_id)
      thread_id = result["thread_id"]

    history = await svc.get_history(thread_id)

    # アシスタントターンのコンテンツを抽出
    assistant_turns = [h["content"] for h in history if h["role"] == "assistant"]

    assert len(assistant_turns) == len(messages), (
      f"Expected {len(messages)} assistant turns, got {len(assistant_turns)}"
    )
    for turn_content in assistant_turns:
      assert turn_content == expected_response, (
        f"Assistant content mismatch: expected '{expected_response}', got '{turn_content}'"
      )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_id=_agent_id_st,
    messages=st.lists(_message_st, min_size=1, max_size=5),
  )
  async def test_each_turn_has_required_fields(
    self,
    agent_id: str,
    messages: list[str],
    tmp_path,
  ) -> None:
    """各ターンに turn_id, role, content, created_at が含まれること。

    **Validates: Requirements 17.6**
    """
    svc = await _create_chat_service(tmp_path)

    thread_id: str | None = None
    for msg in messages:
      result = await svc.send_message(agent_id, msg, thread_id=thread_id)
      thread_id = result["thread_id"]

    history = await svc.get_history(thread_id)

    required_fields = {"turn_id", "role", "content", "created_at"}
    for i, turn in enumerate(history):
      missing = required_fields - set(turn.keys())
      assert not missing, (
        f"Turn {i} missing fields: {missing}"
      )
      # turn_id は UUID 形式
      assert len(turn["turn_id"]) == 36, (
        f"Turn {i}: turn_id should be UUID format, got '{turn['turn_id']}'"
      )
      # created_at は非空文字列
      assert turn["created_at"], (
        f"Turn {i}: created_at should not be empty"
      )
