"""PromptEngine Decision Engine テンプレート拡張テスト

Task 10.4: Decision Engine セクションのプロンプト生成と truncation 検証
Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import pytest

from app.decision_engine.models import (
  ContextAdaptationOutput,
  DecisionModelOutput,
  FailurePatternsOutput,
  ReasoningFlowOutput,
)
from app.models.profile import BaseOS, ContextLayers, Persona, CommunicationTone, ProfileOutput
from app.models.scores import NormalizedScores
from app.evolution.prompt_engine import PromptEngine


def _make_base_profile(**overrides) -> ProfileOutput:
  """テスト用の基本 ProfileOutput を生成する。"""
  defaults = {
    "profile_id": "prof_000001",
    "persona": Persona(),
    "communication_tone": CommunicationTone(),
    "base_os": BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.5,
        sensing_intuition=0.5,
        thinking_feeling=0.5,
        judging_perceiving=0.5,
      ),
      decision_style="Balanced",
      do_not_list=["Never lie"],
    ),
    "lexical_tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "semantic_contexts": {"problem_solving": "Analytical approach"},
    "context_layers": ContextLayers(),
  }
  defaults.update(overrides)
  return ProfileOutput(**defaults)


def _make_decision_model() -> DecisionModelOutput:
  """テスト用 DecisionModelOutput を生成する。"""
  return DecisionModelOutput(
    priorities=["customer_first", "speed_first", "quality"],
    priority_weights={
      "customer_first": 1.0,
      "speed_first": 0.7,
      "quality": 0.5,
    },
    escalation_rules=["When budget exceeds $10K"],
    auto_approve_scope=["Minor bug fixes"],
    tradeoff_tendencies={
      "speed_vs_quality": 0.3,
      "innovation_vs_stability": 0.8,
    },
  )


def _make_failure_patterns() -> FailurePatternsOutput:
  """テスト用 FailurePatternsOutput を生成する。"""
  return FailurePatternsOutput(
    degradation_triggers=["Under deadline pressure", "After 8pm"],
    procrastination_patterns=["Large ambiguous tasks"],
    overconfidence_conditions=["Familiar domain"],
    recurring_mistakes=["Skipping tests", "Overengineering"],
  )


def _make_context_adaptation() -> ContextAdaptationOutput:
  """テスト用 ContextAdaptationOutput を生成する。"""
  return ContextAdaptationOutput(
    modes={
      "executive_report": {"tone": "formal", "detail": "minimal", "focus": "outcomes"},
      "deep_review": {"tone": "technical", "detail": "comprehensive", "focus": "accuracy"},
    },
    switch_triggers={
      "audience": ["executive present", "board meeting"],
      "urgency": ["deadline today", "production down"],
    },
  )


def _make_reasoning_flow() -> ReasoningFlowOutput:
  """テスト用 ReasoningFlowOutput を生成する。"""
  return ReasoningFlowOutput(
    default_steps=[
      "Understand the problem",
      "Gather context",
      "Propose solutions",
      "Evaluate tradeoffs",
      "Implement",
    ],
    verification_method="Write tests first",
    learning_style="Hands-on experimentation",
  )


# =============================================================================
# Requirement 7.1: Decision Framework セクション
# =============================================================================


class TestDecisionFrameworkSection:
  """decision_model がある場合、Decision Framework セクションが生成される。"""

  def test_decision_framework_section_present(self):
    """Validates: Requirements 7.1"""
    profile = _make_base_profile(decision_model=_make_decision_model())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "## Decision Framework" in result.prompt

  def test_priorities_sorted_by_weight_descending(self):
    """優先順位が weight 降順でリストされる。Validates: Requirements 7.1"""
    profile = _make_base_profile(decision_model=_make_decision_model())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    # weight 降順: customer_first(1.0) > speed_first(0.7) > quality(0.5)
    cf_pos = result.prompt.index("customer_first (weight: 1.0)")
    sf_pos = result.prompt.index("speed_first (weight: 0.7)")
    q_pos = result.prompt.index("quality (weight: 0.5)")
    assert cf_pos < sf_pos < q_pos

  def test_tradeoff_tendencies_subsection(self):
    """tradeoff_tendencies が Tradeoff Tendencies サブセクションに含まれる。Validates: Requirements 7.1"""
    profile = _make_base_profile(decision_model=_make_decision_model())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "### Tradeoff Tendencies" in result.prompt
    assert "speed_vs_quality: 0.3" in result.prompt
    assert "innovation_vs_stability: 0.8" in result.prompt


# =============================================================================
# Requirement 7.2: Known Weaknesses & Guardrails セクション
# =============================================================================


class TestFailurePatternsSection:
  """failure_patterns がある場合、Known Weaknesses セクションが生成される。"""

  def test_weaknesses_section_present(self):
    """Validates: Requirements 7.2"""
    profile = _make_base_profile(failure_patterns=_make_failure_patterns())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "## Known Weaknesses & Guardrails" in result.prompt

  def test_degradation_triggers_with_warning_emoji(self):
    """degradation_triggers が ⚠️ プレフィックスで表示される。Validates: Requirements 7.2"""
    profile = _make_base_profile(failure_patterns=_make_failure_patterns())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "⚠️ Under deadline pressure" in result.prompt
    assert "⚠️ After 8pm" in result.prompt

  def test_recurring_mistakes_with_cycle_emoji(self):
    """recurring_mistakes が 🔄 プレフィックスで表示される。Validates: Requirements 7.2"""
    profile = _make_base_profile(failure_patterns=_make_failure_patterns())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "🔄 Skipping tests" in result.prompt
    assert "🔄 Overengineering" in result.prompt


# =============================================================================
# Requirement 7.3: Context Adaptation Rules セクション
# =============================================================================


class TestContextAdaptationSection:
  """context_adaptation がある場合、Context Adaptation Rules セクションが生成される。"""

  def test_context_adaptation_section_present(self):
    """Validates: Requirements 7.3"""
    profile = _make_base_profile(context_adaptation=_make_context_adaptation())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "## Context Adaptation Rules" in result.prompt

  def test_mode_definitions(self):
    """各モードの tone/detail/focus が表示される。Validates: Requirements 7.3"""
    profile = _make_base_profile(context_adaptation=_make_context_adaptation())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "### executive_report" in result.prompt
    assert "- Tone: formal" in result.prompt
    assert "- Detail: minimal" in result.prompt
    assert "- Focus: outcomes" in result.prompt
    assert "### deep_review" in result.prompt

  def test_switch_conditions(self):
    """switch_triggers が Switch Conditions セクションに含まれる。Validates: Requirements 7.3"""
    profile = _make_base_profile(context_adaptation=_make_context_adaptation())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "Switch Conditions:" in result.prompt
    assert "audience: executive present, board meeting" in result.prompt
    assert "urgency: deadline today, production down" in result.prompt


# =============================================================================
# Requirement 7.4: Default Reasoning Process セクション
# =============================================================================


class TestReasoningFlowSection:
  """reasoning_flow がある場合、Default Reasoning Process セクションが生成される。"""

  def test_reasoning_process_section_present(self):
    """Validates: Requirements 7.4"""
    profile = _make_base_profile(reasoning_flow=_make_reasoning_flow())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "## Default Reasoning Process" in result.prompt

  def test_numbered_steps(self):
    """default_steps が番号付きリストで表示される。Validates: Requirements 7.4"""
    profile = _make_base_profile(reasoning_flow=_make_reasoning_flow())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "1. Understand the problem" in result.prompt
    assert "2. Gather context" in result.prompt
    assert "3. Propose solutions" in result.prompt
    assert "4. Evaluate tradeoffs" in result.prompt
    assert "5. Implement" in result.prompt

  def test_verification_and_learning_style(self):
    """verification_method と learning_style が表示される。Validates: Requirements 7.4"""
    profile = _make_base_profile(reasoning_flow=_make_reasoning_flow())
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "- Verification: Write tests first" in result.prompt
    assert "- Learning Style: Hands-on experimentation" in result.prompt


# =============================================================================
# Requirement 7.5: 後方互換性
# =============================================================================


class TestBackwardCompatibility:
  """decision engine フィールドなしのプロファイルでは従来通り動作する。"""

  def test_no_decision_engine_sections_when_fields_absent(self):
    """Validates: Requirements 7.5"""
    profile = _make_base_profile()
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "## Decision Framework" not in result.prompt
    assert "## Known Weaknesses & Guardrails" not in result.prompt
    assert "## Context Adaptation Rules" not in result.prompt
    assert "## Default Reasoning Process" not in result.prompt

  def test_base_prompt_structure_unchanged(self):
    """既存のプロンプト構造が維持される。Validates: Requirements 7.5"""
    profile = _make_base_profile()
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "# あなたの人格設定" in result.prompt
    assert "## 思考特性" in result.prompt
    assert "## 意思決定スタイル" in result.prompt
    assert "## 絶対にやってはいけないこと" in result.prompt
    assert "## 重要な指示" in result.prompt


# =============================================================================
# Requirement 7.6: Truncation（トークン制限遵守）
# =============================================================================


class TestTruncation:
  """max_tokens 超過時に低優先度セクションから順に除外される。"""

  def _make_full_profile(self) -> ProfileOutput:
    """全 decision engine セクションを含むプロファイルを生成する。"""
    return _make_base_profile(
      decision_model=_make_decision_model(),
      failure_patterns=_make_failure_patterns(),
      context_adaptation=_make_context_adaptation(),
      reasoning_flow=_make_reasoning_flow(),
    )

  def test_all_sections_included_when_within_limit(self):
    """トークン制限内なら全セクションが含まれる。Validates: Requirements 7.6"""
    profile = self._make_full_profile()
    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "## Decision Framework" in result.prompt
    assert "## Known Weaknesses & Guardrails" in result.prompt
    assert "## Context Adaptation Rules" in result.prompt
    assert "## Default Reasoning Process" in result.prompt

  def test_reasoning_flow_truncated_first(self):
    """reasoning_flow が最初に truncate される。Validates: Requirements 7.6"""
    profile = self._make_full_profile()
    # 全セクション含むプロンプトの長さを取得して、ギリギリ超過する max_tokens を設定
    engine_full = PromptEngine(max_tokens=8000)
    full_result = engine_full.generate(profile)
    full_tokens = full_result.token_count

    # reasoning_flow なしのプロンプトのトークン数を推定
    profile_no_rf = _make_base_profile(
      decision_model=_make_decision_model(),
      failure_patterns=_make_failure_patterns(),
      context_adaptation=_make_context_adaptation(),
      reasoning_flow=None,
    )
    no_rf_result = engine_full.generate(profile_no_rf)
    no_rf_tokens = no_rf_result.token_count

    # max_tokens を full よりは小さいが no_rf よりは大きく設定
    # → reasoning_flow だけが truncate されるべき
    mid_tokens = (full_tokens + no_rf_tokens) // 2
    engine = PromptEngine(max_tokens=mid_tokens)
    result = engine.generate(profile)

    assert "## Decision Framework" in result.prompt
    assert "## Known Weaknesses & Guardrails" in result.prompt
    assert "## Context Adaptation Rules" in result.prompt
    assert "## Default Reasoning Process" not in result.prompt

  def test_context_adaptation_truncated_second(self):
    """context_adaptation が2番目に truncate される。Validates: Requirements 7.6"""
    profile = self._make_full_profile()
    engine_full = PromptEngine(max_tokens=8000)

    # reasoning_flow + context_adaptation なしのプロンプト
    profile_no_rf_ca = _make_base_profile(
      decision_model=_make_decision_model(),
      failure_patterns=_make_failure_patterns(),
      context_adaptation=None,
      reasoning_flow=None,
    )
    no_rf_ca_result = engine_full.generate(profile_no_rf_ca)

    # reasoning_flow なしのプロンプト
    profile_no_rf = _make_base_profile(
      decision_model=_make_decision_model(),
      failure_patterns=_make_failure_patterns(),
      context_adaptation=_make_context_adaptation(),
      reasoning_flow=None,
    )
    no_rf_result = engine_full.generate(profile_no_rf)

    # max_tokens を no_rf よりは小さいが no_rf_ca よりは大きく設定
    mid_tokens = (no_rf_result.token_count + no_rf_ca_result.token_count) // 2
    engine = PromptEngine(max_tokens=mid_tokens)
    result = engine.generate(profile)

    assert "## Decision Framework" in result.prompt
    assert "## Known Weaknesses & Guardrails" in result.prompt
    assert "## Context Adaptation Rules" not in result.prompt
    assert "## Default Reasoning Process" not in result.prompt

  def test_failure_patterns_truncated_third(self):
    """failure_patterns が3番目に truncate される。Validates: Requirements 7.6"""
    profile = self._make_full_profile()
    engine_full = PromptEngine(max_tokens=8000)

    # decision_model のみのプロンプト
    profile_dm_only = _make_base_profile(
      decision_model=_make_decision_model(),
      failure_patterns=None,
      context_adaptation=None,
      reasoning_flow=None,
    )
    dm_only_result = engine_full.generate(profile_dm_only)

    # decision_model + failure_patterns のプロンプト
    profile_dm_fp = _make_base_profile(
      decision_model=_make_decision_model(),
      failure_patterns=_make_failure_patterns(),
      context_adaptation=None,
      reasoning_flow=None,
    )
    dm_fp_result = engine_full.generate(profile_dm_fp)

    # max_tokens を dm_fp よりは小さいが dm_only よりは大きく設定
    mid_tokens = (dm_fp_result.token_count + dm_only_result.token_count) // 2
    engine = PromptEngine(max_tokens=mid_tokens)
    result = engine.generate(profile)

    assert "## Decision Framework" in result.prompt
    assert "## Known Weaknesses & Guardrails" not in result.prompt
    assert "## Context Adaptation Rules" not in result.prompt
    assert "## Default Reasoning Process" not in result.prompt

  def test_decision_model_truncated_last(self):
    """decision_model が最後に truncate される。Validates: Requirements 7.6"""
    profile = self._make_full_profile()
    engine_full = PromptEngine(max_tokens=8000)

    # 全 decision engine セクションなしのプロンプト
    profile_none = _make_base_profile()
    none_result = engine_full.generate(profile_none)

    # decision_model のみのプロンプト
    profile_dm_only = _make_base_profile(
      decision_model=_make_decision_model(),
      failure_patterns=None,
      context_adaptation=None,
      reasoning_flow=None,
    )
    dm_only_result = engine_full.generate(profile_dm_only)

    # max_tokens を dm_only よりは小さいが none よりは大きく設定
    mid_tokens = (dm_only_result.token_count + none_result.token_count) // 2
    engine = PromptEngine(max_tokens=mid_tokens)
    result = engine.generate(profile)

    assert "## Decision Framework" not in result.prompt
    assert "## Known Weaknesses & Guardrails" not in result.prompt
    assert "## Context Adaptation Rules" not in result.prompt
    assert "## Default Reasoning Process" not in result.prompt

  def test_token_count_never_exceeds_max_tokens(self):
    """truncation 後のトークン数は常に max_tokens 以内。Validates: Requirements 7.6"""
    profile = self._make_full_profile()
    # 非常に小さい max_tokens でもエラーにならないか（基本プロンプトが収まる限り）
    engine_full = PromptEngine(max_tokens=8000)
    base_result = engine_full.generate(_make_base_profile())

    # 基本プロンプトが収まる最低限のトークン数でテスト
    engine = PromptEngine(max_tokens=base_result.token_count + 10)
    result = engine.generate(profile)
    assert result.token_count <= base_result.token_count + 10
