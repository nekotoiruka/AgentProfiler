"""DiscussionEngine Decision Model 注入のユニットテスト

Task 10.7: _build_decision_prompt_section, _build_conflict_directives,
およびターン生成時の decision model 統合を検証する。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.decision_engine.models import (
  DecisionModelOutput,
  ReasoningFlowOutput,
)
from app.evolution.agent_manager import AgentManager, AgentRecord
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.discussion_engine import DiscussionEngine
from app.evolution.routing_engine import RoutingEngine
from app.models.profile import ProfileOutput


def _make_profile(
  profile_id: str = "prof_000001",
  decision_model: DecisionModelOutput | None = None,
  reasoning_flow: ReasoningFlowOutput | None = None,
) -> MagicMock:
  """テスト用 ProfileOutput モックを生成する。"""
  profile = MagicMock(spec=ProfileOutput)
  profile.profile_id = profile_id
  profile.decision_model = decision_model
  profile.reasoning_flow = reasoning_flow
  profile.persona = MagicMock()
  profile.persona.nickname = "TestAgent"
  profile.persona.age_range = "30代"
  profile.persona.role = "エンジニア"
  profile.persona.industry = "IT"
  profile.persona.experience_years = "10年"
  profile.communication_tone = MagicMock()
  profile.communication_tone.pronoun = "私"
  profile.communication_tone.formality = "カジュアル"
  profile.communication_tone.text_style = ""
  profile.communication_tone.emotion_level = ""
  profile.communication_tone.humor = ""
  profile.communication_tone.sentence_ending = ""
  profile.communication_tone.filler_words = ""
  profile.base_os = MagicMock()
  profile.base_os.decision_style = "analytical"
  profile.base_os.axes = {"extroverted_introverted": 0.7}
  profile.base_os.do_not_list = ["Be rude"]
  profile.semantic_contexts = {"problem_solving": "分析的に考える"}
  profile.lexical_tags = ["python", "gaming"]
  return profile


@pytest_asyncio.fixture
async def db_path(tmp_path) -> str:
  return str(tmp_path / "test_discussion_decision.db")


@pytest_asyncio.fixture
async def mock_routing_engine() -> RoutingEngine:
  engine = MagicMock(spec=RoutingEngine)
  engine.route_with_tools = AsyncMock(return_value="Decision-based response.")
  return engine


@pytest_asyncio.fixture
async def discussion_engine(db_path, mock_routing_engine) -> DiscussionEngine:
  clm = MagicMock(spec=ContextLayerManager)
  clm.get_profile = MagicMock(return_value=_make_profile())
  mgr = MagicMock(spec=AgentManager)
  mgr.get = AsyncMock(
    side_effect=lambda aid: AgentRecord(
      agent_id=aid,
      profile_id="prof_000001",
      display_name=f"Agent-{aid[:4]}",
      created_at="2024-01-01T00:00:00+00:00",
      is_active=True,
    )
  )
  engine = DiscussionEngine(
    db_path=db_path,
    routing_engine=mock_routing_engine,
    context_layer_manager=clm,
    agent_manager=mgr,
  )
  await engine.init_db()
  return engine


class TestBuildDecisionPromptSection:
  """_build_decision_prompt_section() のテスト"""

  def test_empty_when_no_decision_data(self, discussion_engine):
    """decision_model も reasoning_flow も無い場合は空文字列。"""
    profile = _make_profile(decision_model=None, reasoning_flow=None)
    result = discussion_engine._build_decision_prompt_section(profile)
    assert result == ""

  def test_includes_priorities_section(self, discussion_engine):
    """decision_model がある場合、priorities が含まれること。"""
    dm = DecisionModelOutput(
      priorities=["quality_first", "speed_first"],
      priority_weights={"quality_first": 1.0, "speed_first": 0.6},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.2},
    )
    profile = _make_profile(decision_model=dm)
    result = discussion_engine._build_decision_prompt_section(profile)

    assert "## My Decision Priorities" in result
    assert "quality_first (weight: 1.0)" in result
    assert "speed_first (weight: 0.6)" in result

  def test_priorities_sorted_descending(self, discussion_engine):
    """priorities が priority_weights の降順で並ぶこと。"""
    dm = DecisionModelOutput(
      priorities=["a", "b", "c"],
      priority_weights={"a": 0.3, "b": 1.0, "c": 0.7},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={},
    )
    profile = _make_profile(decision_model=dm)
    result = discussion_engine._build_decision_prompt_section(profile)

    lines = result.strip().split("\n")
    priority_lines = [l for l in lines if l.startswith(("1.", "2.", "3."))]
    assert "b (weight: 1.0)" in priority_lines[0]
    assert "c (weight: 0.7)" in priority_lines[1]
    assert "a (weight: 0.3)" in priority_lines[2]

  def test_includes_reasoning_flow(self, discussion_engine):
    """reasoning_flow がある場合、approach セクションが含まれること。"""
    rf = ReasoningFlowOutput(
      default_steps=["問題を定義する", "データを収集する", "仮説を立てる", "検証する"],
      verification_method="テスト駆動",
      learning_style="実践型",
    )
    profile = _make_profile(reasoning_flow=rf)
    result = discussion_engine._build_decision_prompt_section(profile)

    assert "## My Reasoning Approach" in result
    assert "1. 問題を定義する" in result
    assert "2. データを収集する" in result
    assert "3. 仮説を立てる" in result
    assert "4. 検証する" in result

  def test_includes_both_sections(self, discussion_engine):
    """decision_model と reasoning_flow 両方がある場合、両セクション含まれること。"""
    dm = DecisionModelOutput(
      priorities=["quality"],
      priority_weights={"quality": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={},
    )
    rf = ReasoningFlowOutput(
      default_steps=["step1", "step2", "step3", "step4"],
      verification_method="review",
      learning_style="visual",
    )
    profile = _make_profile(decision_model=dm, reasoning_flow=rf)
    result = discussion_engine._build_decision_prompt_section(profile)

    assert "## My Decision Priorities" in result
    assert "## My Reasoning Approach" in result


class TestBuildConflictDirectives:
  """_build_conflict_directives() のテスト"""

  def test_empty_when_no_decision_model(self, discussion_engine):
    """agent_profile に decision_model が無い場合は空リスト。"""
    agent_profile = _make_profile(decision_model=None)
    other = _make_profile(
      decision_model=DecisionModelOutput(
        priorities=["x"],
        priority_weights={"x": 1.0},
        escalation_rules=[],
        auto_approve_scope=[],
        tradeoff_tendencies={"speed_vs_quality": 0.8},
      )
    )
    result = discussion_engine._build_conflict_directives(agent_profile, [other])
    assert result == []

  def test_empty_when_other_has_no_decision_model(self, discussion_engine):
    """他エージェントに decision_model が無い場合は空リスト。"""
    dm = DecisionModelOutput(
      priorities=["x"],
      priority_weights={"x": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.2},
    )
    agent_profile = _make_profile(decision_model=dm)
    other = _make_profile(decision_model=None)
    result = discussion_engine._build_conflict_directives(agent_profile, [other])
    assert result == []

  def test_generates_directive_for_large_diff(self, discussion_engine):
    """差 >= 0.4 の次元で立場維持指示が生成されること。"""
    dm_agent = DecisionModelOutput(
      priorities=["x"],
      priority_weights={"x": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.1, "innovation_vs_stability": 0.9},
    )
    dm_other = DecisionModelOutput(
      priorities=["y"],
      priority_weights={"y": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.8, "innovation_vs_stability": 0.3},
    )
    agent_profile = _make_profile(decision_model=dm_agent)
    other_profile = _make_profile(decision_model=dm_other)

    result = discussion_engine._build_conflict_directives(agent_profile, [other_profile])

    # speed_vs_quality: |0.1 - 0.8| = 0.7 >= 0.4 → 生成
    # innovation_vs_stability: |0.9 - 0.3| = 0.6 >= 0.4 → 生成
    assert len(result) == 2
    assert any("speed_vs_quality" in d and "0.1" in d for d in result)
    assert any("innovation_vs_stability" in d and "0.9" in d for d in result)

  def test_no_directive_for_small_diff(self, discussion_engine):
    """差 < 0.4 の次元では指示が生成されないこと。"""
    dm_agent = DecisionModelOutput(
      priorities=["x"],
      priority_weights={"x": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.5},
    )
    dm_other = DecisionModelOutput(
      priorities=["y"],
      priority_weights={"y": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.6},
    )
    agent_profile = _make_profile(decision_model=dm_agent)
    other_profile = _make_profile(decision_model=dm_other)

    result = discussion_engine._build_conflict_directives(agent_profile, [other_profile])
    assert result == []

  def test_boundary_exactly_0_4_generates_directive(self, discussion_engine):
    """差がちょうど 0.4 の場合に指示が生成されること。"""
    dm_agent = DecisionModelOutput(
      priorities=["x"],
      priority_weights={"x": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"autonomy_vs_consensus": 0.2},
    )
    dm_other = DecisionModelOutput(
      priorities=["y"],
      priority_weights={"y": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"autonomy_vs_consensus": 0.6},
    )
    agent_profile = _make_profile(decision_model=dm_agent)
    other_profile = _make_profile(decision_model=dm_other)

    result = discussion_engine._build_conflict_directives(agent_profile, [other_profile])
    assert len(result) == 1
    assert "autonomy_vs_consensus" in result[0]
    assert "0.2" in result[0]

  def test_no_duplicates_with_multiple_conflicting_others(self, discussion_engine):
    """複数の他エージェントと対立しても同じ dimension の指示は重複しないこと。"""
    dm_agent = DecisionModelOutput(
      priorities=["x"],
      priority_weights={"x": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.1},
    )
    dm_other1 = DecisionModelOutput(
      priorities=["y"],
      priority_weights={"y": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.8},
    )
    dm_other2 = DecisionModelOutput(
      priorities=["z"],
      priority_weights={"z": 1.0},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={"speed_vs_quality": 0.9},
    )
    agent_profile = _make_profile(decision_model=dm_agent)
    other1 = _make_profile(decision_model=dm_other1)
    other2 = _make_profile(decision_model=dm_other2)

    result = discussion_engine._build_conflict_directives(agent_profile, [other1, other2])
    # 同じ dimension のディレクティブは1つだけ
    assert len(result) == 1
    assert "speed_vs_quality" in result[0]


class TestBuildDecisionPromptSectionWithoutReasoning:
  """_build_decision_prompt_section_without_reasoning() のテスト"""

  def test_includes_only_priorities(self, discussion_engine):
    """reasoning_flow を含まず priorities のみ返すこと。"""
    dm = DecisionModelOutput(
      priorities=["quality"],
      priority_weights={"quality": 1.0, "speed": 0.5},
      escalation_rules=[],
      auto_approve_scope=[],
      tradeoff_tendencies={},
    )
    rf = ReasoningFlowOutput(
      default_steps=["step1", "step2", "step3", "step4"],
      verification_method="review",
      learning_style="visual",
    )
    profile = _make_profile(decision_model=dm, reasoning_flow=rf)
    result = discussion_engine._build_decision_prompt_section_without_reasoning(profile)

    assert "## My Decision Priorities" in result
    assert "## My Reasoning Approach" not in result
    assert "quality (weight: 1.0)" in result

  def test_empty_when_no_decision_model(self, discussion_engine):
    """decision_model が無い場合は空文字列。"""
    profile = _make_profile(decision_model=None)
    result = discussion_engine._build_decision_prompt_section_without_reasoning(profile)
    assert result == ""


class TestTokenLimit:
  """トークン制限遵守のテスト"""

  def test_estimate_tokens(self, discussion_engine):
    """_estimate_tokens の簡易推定が正しいこと。"""
    assert DiscussionEngine._estimate_tokens("") == 1
    assert DiscussionEngine._estimate_tokens("a" * 100) == 25
    assert DiscussionEngine._estimate_tokens("a" * 4000) == 1000


class TestBackwardCompatibility:
  """後方互換性テスト: decision engine データが無い場合の動作"""

  @pytest.mark.asyncio
  async def test_run_turns_without_decision_data(self, discussion_engine):
    """decision_model/reasoning_flow が無くてもターンが正常に生成されること。"""
    turns = []
    async for turn in discussion_engine.run_turns(
      discussion_id="test-compat-001",
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=1,
    ):
      turns.append(turn)

    assert len(turns) == 2
    for turn in turns:
      assert turn.content == "Decision-based response."
