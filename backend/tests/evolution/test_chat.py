"""ChatService のユニットテスト

SQLite ベースのスレッド管理、会話履歴、
SSE ストリーミング、ルーティング連携を検証する。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.evolution.chat import ChatService
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.routing_engine import RoutingEngine


@pytest_asyncio.fixture
async def db_path(tmp_path) -> str:
  """テスト用の一時 DB パスを返す。"""
  return str(tmp_path / "test_evolution.db")


@pytest_asyncio.fixture
async def mock_routing_engine() -> RoutingEngine:
  """RoutingEngine のモック。route()/route_with_tools() が固定レスポンスを返す。"""
  engine = MagicMock(spec=RoutingEngine)
  engine.route = AsyncMock(return_value="Hello! I'm your assistant.")
  engine.route_with_tools = AsyncMock(return_value="Hello! I'm your assistant.")
  return engine


@pytest_asyncio.fixture
async def mock_clm() -> ContextLayerManager:
  """ContextLayerManager のモック。get_base_os/get_profile が正常に返る。"""
  clm = MagicMock(spec=ContextLayerManager)
  base_os = MagicMock()
  base_os.decision_style = "analytical"
  base_os.axes = {"extroverted_introverted": 0.7, "thinking_feeling": 0.3}
  base_os.do_not_list = ["Be rude", "Give medical advice"]
  clm.get_base_os = MagicMock(return_value=base_os)

  # get_profile mock for rich prompt
  profile = MagicMock()
  profile.persona = MagicMock()
  profile.persona.nickname = "TestAgent"
  profile.persona.age_range = ""
  profile.persona.role = ""
  profile.persona.industry = ""
  profile.persona.experience_years = ""
  profile.communication_tone = MagicMock()
  profile.communication_tone.pronoun = ""
  profile.communication_tone.formality = ""
  profile.communication_tone.text_style = ""
  profile.communication_tone.emotion_level = ""
  profile.communication_tone.humor = ""
  profile.communication_tone.response_length = ""
  profile.base_os = base_os
  profile.semantic_contexts = {}
  profile.lexical_tags = []
  clm.get_profile = MagicMock(return_value=profile)
  return clm


@pytest_asyncio.fixture
async def mock_clm_no_profile() -> ContextLayerManager:
  """ContextLayerManager のモック。get_base_os/get_profile が KeyError を送出する。"""
  clm = MagicMock(spec=ContextLayerManager)
  clm.get_base_os = MagicMock(side_effect=KeyError("Profile not loaded"))
  clm.get_profile = MagicMock(side_effect=KeyError("Profile not loaded"))
  return clm


@pytest_asyncio.fixture
async def chat_service(
  db_path: str,
  mock_routing_engine: RoutingEngine,
  mock_clm: ContextLayerManager,
) -> ChatService:
  """初期化済み ChatService を返す。"""
  svc = ChatService(
    db_path=db_path,
    routing_engine=mock_routing_engine,
    context_layer_manager=mock_clm,
    context_window=20,
  )
  await svc.init_db()
  return svc


@pytest_asyncio.fixture
async def chat_service_no_profile(
  db_path: str,
  mock_routing_engine: RoutingEngine,
  mock_clm_no_profile: ContextLayerManager,
) -> ChatService:
  """Base OS が取得できない ChatService を返す。"""
  svc = ChatService(
    db_path=db_path,
    routing_engine=mock_routing_engine,
    context_layer_manager=mock_clm_no_profile,
    context_window=20,
  )
  await svc.init_db()
  return svc


class TestInitDb:
  """init_db() のテスト"""

  @pytest.mark.asyncio
  async def test_creates_threads_table(self, db_path: str) -> None:
    """threads テーブルが正常に作成されること。"""
    engine = MagicMock(spec=RoutingEngine)
    clm = MagicMock(spec=ContextLayerManager)
    svc = ChatService(
      db_path=db_path,
      routing_engine=engine,
      context_layer_manager=clm,
    )
    await svc.init_db()
    # 2回目の呼び出しもエラーにならない (IF NOT EXISTS)
    await svc.init_db()

  @pytest.mark.asyncio
  async def test_idempotent_init(self, chat_service: ChatService) -> None:
    """init_db() を複数回呼んでもエラーにならないこと。"""
    await chat_service.init_db()
    await chat_service.init_db()


class TestSendMessage:
  """send_message() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_response_dict(self, chat_service: ChatService) -> None:
    """正常なレスポンス辞書が返ること。"""
    result = await chat_service.send_message("agent-001", "Hello!")
    assert "thread_id" in result
    assert result["agent_id"] == "agent-001"
    assert result["response"] == "Hello! I'm your assistant."
    assert "created_at" in result

  @pytest.mark.asyncio
  async def test_generates_thread_id_when_none(
    self, chat_service: ChatService
  ) -> None:
    """thread_id が None の場合、新規 UUID が生成されること。"""
    result = await chat_service.send_message("agent-001", "Hi")
    assert result["thread_id"] is not None
    assert len(result["thread_id"]) == 36  # UUID形式

  @pytest.mark.asyncio
  async def test_uses_provided_thread_id(
    self, chat_service: ChatService
  ) -> None:
    """指定した thread_id が使用されること。"""
    result = await chat_service.send_message(
      "agent-001", "Hi", thread_id="my-thread-123"
    )
    assert result["thread_id"] == "my-thread-123"

  @pytest.mark.asyncio
  async def test_stores_user_and_assistant_turns(
    self, chat_service: ChatService
  ) -> None:
    """ユーザーとアシスタントの両ターンが DB に保存されること。"""
    result = await chat_service.send_message("agent-001", "Hello!")
    history = await chat_service.get_history(result["thread_id"])
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello!"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hello! I'm your assistant."

  @pytest.mark.asyncio
  async def test_multiple_messages_in_thread(
    self, chat_service: ChatService
  ) -> None:
    """同一スレッドに複数メッセージが蓄積されること。"""
    r1 = await chat_service.send_message("agent-001", "First message")
    r2 = await chat_service.send_message(
      "agent-001", "Second message", thread_id=r1["thread_id"]
    )
    assert r1["thread_id"] == r2["thread_id"]
    history = await chat_service.get_history(r1["thread_id"])
    # 2回の send_message → user + assistant × 2 = 4ターン
    assert len(history) == 4

  @pytest.mark.asyncio
  async def test_calls_routing_engine(
    self, chat_service: ChatService, mock_routing_engine: RoutingEngine
  ) -> None:
    """RoutingEngine.route_with_tools() が呼び出されること。"""
    await chat_service.send_message("agent-001", "Test message")
    mock_routing_engine.route_with_tools.assert_called_once()
    call_kwargs = mock_routing_engine.route_with_tools.call_args
    assert "Test message" in call_kwargs.kwargs["utterance"]

  @pytest.mark.asyncio
  async def test_uses_default_prompt_when_profile_missing(
    self, chat_service_no_profile: ChatService
  ) -> None:
    """Base OS が取得できない場合、デフォルトプロンプトで動作すること。"""
    result = await chat_service_no_profile.send_message("agent-001", "Hello")
    assert result["response"] == "Hello! I'm your assistant."


class TestStreamResponse:
  """stream_response() のテスト"""

  @pytest.mark.asyncio
  async def test_yields_sse_event(self, chat_service: ChatService) -> None:
    """SSE 形式のイベントが yield されること。"""
    events = []
    async for event in chat_service.stream_response("agent-001", "Hi"):
      events.append(event)

    assert len(events) == 1
    assert events[0].startswith("data: ")
    assert events[0].endswith("\n\n")

  @pytest.mark.asyncio
  async def test_sse_payload_contains_response(
    self, chat_service: ChatService
  ) -> None:
    """SSE ペイロードにレスポンス内容が含まれること。"""
    events = []
    async for event in chat_service.stream_response("agent-001", "Hi"):
      events.append(event)

    # "data: " プレフィクスと末尾の "\n\n" を除去して JSON パース
    payload_str = events[0][len("data: "):-2]
    payload = json.loads(payload_str)
    assert payload["content"] == "Hello! I'm your assistant."
    assert payload["done"] is True
    assert "thread_id" in payload
    assert payload["agent_id"] == "agent-001"

  @pytest.mark.asyncio
  async def test_stream_stores_turns(self, chat_service: ChatService) -> None:
    """ストリーミング時もターンが DB に保存されること。"""
    events = []
    async for event in chat_service.stream_response("agent-001", "Hello"):
      events.append(event)

    payload_str = events[0][len("data: "):-2]
    payload = json.loads(payload_str)
    history = await chat_service.get_history(payload["thread_id"])
    assert len(history) == 2


class TestGetHistory:
  """get_history() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_empty_for_nonexistent_thread(
    self, chat_service: ChatService
  ) -> None:
    """存在しないスレッドでは空リストが返ること。"""
    history = await chat_service.get_history("nonexistent-thread")
    assert history == []

  @pytest.mark.asyncio
  async def test_returns_turns_in_chronological_order(
    self, chat_service: ChatService
  ) -> None:
    """履歴が時系列昇順で返ること。"""
    r = await chat_service.send_message("agent-001", "First")
    await chat_service.send_message(
      "agent-001", "Second", thread_id=r["thread_id"]
    )
    history = await chat_service.get_history(r["thread_id"])
    # 各ターンの created_at が昇順であること
    timestamps = [h["created_at"] for h in history]
    assert timestamps == sorted(timestamps)

  @pytest.mark.asyncio
  async def test_limit_parameter(self, chat_service: ChatService) -> None:
    """limit パラメータで返却件数を制限できること。"""
    r = await chat_service.send_message("agent-001", "Msg 1")
    await chat_service.send_message(
      "agent-001", "Msg 2", thread_id=r["thread_id"]
    )
    await chat_service.send_message(
      "agent-001", "Msg 3", thread_id=r["thread_id"]
    )
    # 全6ターン (3 send × 2 turns each)
    full_history = await chat_service.get_history(r["thread_id"])
    assert len(full_history) == 6

    # limit=3 で最新3件のみ
    limited = await chat_service.get_history(r["thread_id"], limit=3)
    assert len(limited) == 3
    # 最新3件は full_history の末尾3件と一致
    assert limited == full_history[-3:]

  @pytest.mark.asyncio
  async def test_history_contains_required_fields(
    self, chat_service: ChatService
  ) -> None:
    """各ターンに必須フィールドが含まれること。"""
    r = await chat_service.send_message("agent-001", "Test")
    history = await chat_service.get_history(r["thread_id"])
    for turn in history:
      assert "turn_id" in turn
      assert "role" in turn
      assert "content" in turn
      assert "created_at" in turn


class TestBuildSystemPrompt:
  """_build_system_prompt() のテスト"""

  @pytest.mark.asyncio
  async def test_includes_decision_style(
    self, chat_service: ChatService
  ) -> None:
    """システムプロンプトに decision_style が含まれること。"""
    prompt = chat_service._build_system_prompt("agent-001")
    assert "analytical" in prompt

  @pytest.mark.asyncio
  async def test_includes_do_not_list(
    self, chat_service: ChatService
  ) -> None:
    """システムプロンプトに do_not_list が含まれること。"""
    prompt = chat_service._build_system_prompt("agent-001")
    assert "Be rude" in prompt
    assert "Give medical advice" in prompt

  @pytest.mark.asyncio
  async def test_fallback_on_missing_profile(
    self, chat_service_no_profile: ChatService
  ) -> None:
    """Base OS 取得失敗時にデフォルトプロンプトが返ること。"""
    prompt = chat_service_no_profile._build_system_prompt("agent-001")
    assert "helpful AI assistant" in prompt


class TestContextWindow:
  """context_window のテスト"""

  @pytest.mark.asyncio
  async def test_respects_context_window(self, db_path: str) -> None:
    """context_window を超えた古いターンが切り捨てられること。"""
    engine = MagicMock(spec=RoutingEngine)
    engine.route = AsyncMock(return_value="Response")
    engine.route_with_tools = AsyncMock(return_value="Response")
    clm = MagicMock(spec=ContextLayerManager)
    clm.get_base_os = MagicMock(side_effect=KeyError("not loaded"))
    clm.get_profile = MagicMock(side_effect=KeyError("not loaded"))

    # context_window=4 に設定（最新4ターンのみ保持）
    svc = ChatService(
      db_path=db_path,
      routing_engine=engine,
      context_layer_manager=clm,
      context_window=4,
    )
    await svc.init_db()

    # 5回メッセージを送信（計10ターン）
    r = await svc.send_message("agent-001", "Msg 1")
    for i in range(2, 6):
      await svc.send_message(
        "agent-001", f"Msg {i}", thread_id=r["thread_id"]
      )

    # 内部の _get_recent_history を直接検証
    recent = await svc._get_recent_history(r["thread_id"], 4)
    assert len(recent) == 4
