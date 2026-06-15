"""ChatService のモード検出・failure_patterns インデックスのテスト

Task 10.6: ModeDetector 統合の検証。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.decision_engine.mode_detector import ModeDetector
from app.evolution.chat import ChatService
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.routing_engine import RoutingEngine


@pytest_asyncio.fixture
async def db_path(tmp_path) -> str:
  """テスト用の一時 DB パスを返す。"""
  return str(tmp_path / "test_chat_mode.db")


@pytest_asyncio.fixture
async def mock_routing_engine() -> RoutingEngine:
  """RoutingEngine のモック。"""
  engine = MagicMock(spec=RoutingEngine)
  engine.route_with_tools = AsyncMock(return_value="Response from assistant.")
  return engine


@pytest_asyncio.fixture
async def mock_clm() -> ContextLayerManager:
  """ContextLayerManager のモック。"""
  clm = MagicMock(spec=ContextLayerManager)
  base_os = MagicMock()
  base_os.decision_style = "analytical"
  base_os.axes = {"extroverted_introverted": 0.7}
  base_os.do_not_list = ["Be rude"]
  clm.get_base_os = MagicMock(return_value=base_os)

  profile = MagicMock()
  profile.profile_id = "prof_000001"
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
  profile.failure_patterns = None
  clm.get_profile = MagicMock(return_value=profile)
  clm._semantic_retriever = None
  clm._semantic_contexts_local = {}
  return clm


class TestDetectAndApplyMode:
  """_detect_and_apply_mode() のテスト"""

  @pytest.mark.asyncio
  async def test_skips_when_no_mode_detector(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """ModeDetector が None の場合、プロンプトは変更されない。"""
    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
      mode_detector=None,
    )
    original_prompt = "Base system prompt."
    result = svc._detect_and_apply_mode("agent-001", "hello", original_prompt)
    assert result == original_prompt

  @pytest.mark.asyncio
  async def test_appends_mode_prompt_when_detected(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """モードが検出された場合、プロンプトに追記される。"""
    context_adaptation = {
      "modes": {
        "emergency": {"tone": "direct", "detail": "minimal", "focus": "action"},
      },
      "switch_triggers": {
        "urgency": ["緊急", "障害"],
      },
    }
    detector = ModeDetector(context_adaptation=context_adaptation)
    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
      mode_detector=detector,
    )
    original_prompt = "Base system prompt."
    # 緊急キーワードを含むメッセージ
    result = svc._detect_and_apply_mode("agent-001", "本番障害が発生しました", original_prompt)
    assert "## Current Mode: emergency" in result
    assert "Tone: direct" in result
    assert "Detail: minimal" in result
    assert "Focus: action" in result
    assert result.startswith(original_prompt)

  @pytest.mark.asyncio
  async def test_no_change_when_no_mode_detected(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """モードが検出されない場合、プロンプトは変更されない。"""
    context_adaptation = {
      "modes": {
        "emergency": {"tone": "direct", "detail": "minimal", "focus": "action"},
      },
      "switch_triggers": {
        "urgency": ["緊急"],
      },
    }
    detector = ModeDetector(context_adaptation=context_adaptation)
    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
      mode_detector=detector,
    )
    original_prompt = "Base system prompt."
    result = svc._detect_and_apply_mode("agent-001", "普通のメッセージ", original_prompt)
    assert result == original_prompt

  @pytest.mark.asyncio
  async def test_mode_detection_uses_recent_turns(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """直近ターンの内容がモード検出に使用される。"""
    context_adaptation = {
      "modes": {
        "deep_review": {"tone": "thoughtful", "detail": "comprehensive", "focus": "analysis"},
      },
      "switch_triggers": {
        "mental_state": ["設計レビュー"],
      },
    }
    detector = ModeDetector(context_adaptation=context_adaptation)
    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
      mode_detector=detector,
    )
    original_prompt = "Base system prompt."
    # メッセージ自体にはキーワードがないが、直近ターンにある
    recent = [{"role": "user", "content": "設計レビューをお願いします"}]
    result = svc._detect_and_apply_mode("agent-001", "よろしく", original_prompt, recent)
    assert "## Current Mode: deep_review" in result

  @pytest.mark.asyncio
  async def test_send_message_integrates_mode_detection(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """send_message 内でモード検出が統合されていることを確認。"""
    context_adaptation = {
      "modes": {
        "emergency": {"tone": "direct", "detail": "minimal", "focus": "action"},
      },
      "switch_triggers": {
        "urgency": ["緊急"],
      },
    }
    detector = ModeDetector(context_adaptation=context_adaptation)
    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
      mode_detector=detector,
    )
    await svc.init_db()

    result = await svc.send_message("agent-001", "緊急対応が必要です")
    assert result["response"] == "Response from assistant."

    # route_with_tools に渡されたシステムプロンプトを確認
    call_kwargs = mock_routing_engine.route_with_tools.call_args
    system_prompt_used = call_kwargs.kwargs["system_prompt"]
    assert "## Current Mode: emergency" in system_prompt_used


class TestIndexFailurePatterns:
  """_index_failure_patterns() のテスト"""

  @pytest.mark.asyncio
  async def test_skips_when_no_failure_patterns(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """failure_patterns が None の場合、何もしない。"""
    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
    )
    profile = MagicMock()
    profile.failure_patterns = None
    # エラーなく完了すること
    await svc._index_failure_patterns(profile)

  @pytest.mark.asyncio
  async def test_indexes_degradation_triggers(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """degradation_triggers がローカルキャッシュにインデックスされる。"""
    mock_clm._semantic_retriever = None
    mock_clm._semantic_contexts_local = {"prof_000001": {}}

    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
    )

    profile = MagicMock()
    profile.profile_id = "prof_000001"
    profile.failure_patterns = MagicMock()
    profile.failure_patterns.degradation_triggers = ["睡眠不足", "連続残業"]
    profile.failure_patterns.recurring_mistakes = []

    await svc._index_failure_patterns(profile)

    contexts = mock_clm._semantic_contexts_local["prof_000001"]
    assert "degradation_triggers" in contexts
    assert "睡眠不足" in contexts["degradation_triggers"]
    assert "連続残業" in contexts["degradation_triggers"]

  @pytest.mark.asyncio
  async def test_indexes_recurring_mistakes(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """recurring_mistakes がローカルキャッシュにインデックスされる。"""
    mock_clm._semantic_retriever = None
    mock_clm._semantic_contexts_local = {"prof_000001": {}}

    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
    )

    profile = MagicMock()
    profile.profile_id = "prof_000001"
    profile.failure_patterns = MagicMock()
    profile.failure_patterns.degradation_triggers = []
    profile.failure_patterns.recurring_mistakes = ["テスト忘れ", "ドキュメント更新漏れ"]

    await svc._index_failure_patterns(profile)

    contexts = mock_clm._semantic_contexts_local["prof_000001"]
    assert "recurring_mistakes" in contexts
    assert "テスト忘れ" in contexts["recurring_mistakes"]
    assert "ドキュメント更新漏れ" in contexts["recurring_mistakes"]

  @pytest.mark.asyncio
  async def test_indexes_both_triggers_and_mistakes(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """degradation_triggers と recurring_mistakes の両方がインデックスされる。"""
    mock_clm._semantic_retriever = None
    mock_clm._semantic_contexts_local = {"prof_000001": {}}

    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
    )

    profile = MagicMock()
    profile.profile_id = "prof_000001"
    profile.failure_patterns = MagicMock()
    profile.failure_patterns.degradation_triggers = ["疲労"]
    profile.failure_patterns.recurring_mistakes = ["確認不足"]

    await svc._index_failure_patterns(profile)

    contexts = mock_clm._semantic_contexts_local["prof_000001"]
    assert "degradation_triggers" in contexts
    assert "recurring_mistakes" in contexts

  @pytest.mark.asyncio
  async def test_uses_semantic_retriever_when_available(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """SemanticRetriever がある場合、そちらにインデックスする。"""
    mock_retriever = AsyncMock()
    mock_retriever.index_profile = AsyncMock()
    mock_clm._semantic_retriever = mock_retriever

    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
    )

    profile = MagicMock()
    profile.profile_id = "prof_000001"
    profile.failure_patterns = MagicMock()
    profile.failure_patterns.degradation_triggers = ["締切直前"]
    profile.failure_patterns.recurring_mistakes = ["typo"]

    await svc._index_failure_patterns(profile)

    mock_retriever.index_profile.assert_called_once()
    call_args = mock_retriever.index_profile.call_args
    assert call_args[0][0] == "prof_000001"
    entries = call_args[0][1]
    assert "degradation_triggers" in entries
    assert "recurring_mistakes" in entries

  @pytest.mark.asyncio
  async def test_send_message_indexes_failure_patterns_once(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """send_message で failure_patterns のインデックスが1回だけ行われる。"""
    mock_clm._semantic_retriever = None
    mock_clm._semantic_contexts_local = {"prof_000001": {}}

    # プロファイルに failure_patterns を設定
    profile = mock_clm.get_profile.return_value
    profile.profile_id = "prof_000001"
    fp = MagicMock()
    fp.degradation_triggers = ["過労"]
    fp.recurring_mistakes = ["見落とし"]
    profile.failure_patterns = fp

    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
    )
    await svc.init_db()

    # 1回目の送信でインデックスされる
    await svc.send_message("agent-001", "Hello")
    contexts = mock_clm._semantic_contexts_local.get("prof_000001", {})
    assert "degradation_triggers" in contexts

    # 2回目はインデックス済みなので再インデックスされない
    mock_clm._semantic_contexts_local["prof_000001"] = {}  # リセット
    await svc.send_message("agent-001", "Hello again")
    # リセット後なので空のまま（再インデックスされてない）
    assert mock_clm._semantic_contexts_local["prof_000001"] == {}


class TestNoPerformancePenalty:
  """context_adaptation なし時の性能ペナルティなしを確認"""

  @pytest.mark.asyncio
  async def test_no_overhead_without_context_adaptation(
    self, db_path: str, mock_routing_engine, mock_clm
  ) -> None:
    """mode_detector が None の場合、追加処理なしで動作する。"""
    svc = ChatService(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
      mode_detector=None,
    )
    await svc.init_db()

    result = await svc.send_message("agent-001", "緊急対応お願い")
    # モード検出なしで通常レスポンスが返る
    assert result["response"] == "Response from assistant."

    # route_with_tools に渡されたプロンプトにモードセクションがない
    call_kwargs = mock_routing_engine.route_with_tools.call_args
    system_prompt_used = call_kwargs.kwargs["system_prompt"]
    assert "## Current Mode:" not in system_prompt_used
