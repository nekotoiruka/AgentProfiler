"""PackageGenerator Decision Engine 拡張のユニットテスト

Task 10.9: decision engine データがある場合のパッケージ生成を検証する。
- system_prompt.md に "## Decision Framework" / "## Self-Awareness" 追加
- skills/decision-rules/SKILL.md 生成
- tools/reasoning_flow.json 生成
- config.json に context_adaptation 追加
- decision engine データなしの場合は追加ファイルを生成しない（後方互換性）

Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

import json

import pytest

from app.decision_engine.models import (
  ContextAdaptationOutput,
  DecisionModelOutput,
  FailurePatternsOutput,
  ReasoningFlowOutput,
)
from app.evolution.package_generator import PackageGenerator
from app.evolution.prompt_engine import PromptEngine
from app.models.profile import (
  BaseOS,
  ContextLayers,
  Persona,
  CommunicationTone,
  ProfileOutput,
)
from app.models.scores import NormalizedScores


# --- フィクスチャ ---

@pytest.fixture
def prompt_engine() -> PromptEngine:
  return PromptEngine(max_tokens=8000)


@pytest.fixture
def generator(prompt_engine: PromptEngine) -> PackageGenerator:
  return PackageGenerator(prompt_engine)


@pytest.fixture
def base_profile() -> ProfileOutput:
  """Decision Engine データなしの最小プロファイル"""
  return ProfileOutput(
    profile_id="prof_000001",
    persona=Persona(nickname="TestUser", role="Engineer", industry="Tech"),
    communication_tone=CommunicationTone(pronoun="私", formality="敬語"),
    base_os=BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.6,
        sensing_intuition=0.4,
        thinking_feeling=0.7,
        judging_perceiving=0.3,
      ),
      decision_style="analytical",
      do_not_list=["曖昧な回答をしない"],
    ),
    lexical_tags=["python", "fastapi", "vue", "typescript", "docker"],
    semantic_contexts={"problem_solving": "論理的にアプローチ"},
    context_layers=ContextLayers(),
  )


@pytest.fixture
def decision_model() -> DecisionModelOutput:
  return DecisionModelOutput(
    priorities=["quality", "speed", "cost"],
    priority_weights={"quality": 1.0, "speed": 0.7, "cost": 0.4},
    escalation_rules=["予算超過の場合は上長に確認", "セキュリティリスクがある場合は報告"],
    auto_approve_scope=["バグ修正", "ドキュメント更新"],
    tradeoff_tendencies={
      "speed_vs_quality": 0.8,
      "innovation_vs_stability": 0.3,
    },
  )


@pytest.fixture
def failure_patterns() -> FailurePatternsOutput:
  return FailurePatternsOutput(
    degradation_triggers=["睡眠不足", "連続会議"],
    procrastination_patterns=["大きなタスクを先延ばし"],
    overconfidence_conditions=["過去の成功体験が多い分野"],
    recurring_mistakes=["テスト不足でリリース"],
  )


@pytest.fixture
def context_adaptation() -> ContextAdaptationOutput:
  return ContextAdaptationOutput(
    modes={
      "executive_report": {"tone": "formal", "detail": "minimal", "focus": "results"},
      "deep_review": {"tone": "analytical", "detail": "comprehensive", "focus": "accuracy"},
    },
    switch_triggers={
      "audience": ["経営層への報告時"],
      "urgency": ["障害発生時"],
    },
  )


@pytest.fixture
def reasoning_flow() -> ReasoningFlowOutput:
  return ReasoningFlowOutput(
    default_steps=["問題定義", "情報収集", "仮説立案", "検証"],
    verification_method="データで裏付け確認",
    learning_style="実践型学習",
  )


@pytest.fixture
def full_profile(
  base_profile: ProfileOutput,
  decision_model: DecisionModelOutput,
  failure_patterns: FailurePatternsOutput,
  context_adaptation: ContextAdaptationOutput,
  reasoning_flow: ReasoningFlowOutput,
) -> ProfileOutput:
  """全 Decision Engine データを含むプロファイル"""
  return base_profile.model_copy(update={
    "decision_model": decision_model,
    "failure_patterns": failure_patterns,
    "context_adaptation": context_adaptation,
    "reasoning_flow": reasoning_flow,
  })


# =============================================================================
# Req 8.5: 後方互換性 — decision engine データなしでは追加ファイル非生成
# =============================================================================


class TestBackwardCompatibility:
  """Decision Engine データが無い場合は追加ファイルを生成しない"""

  def test_no_decision_rules_skill_without_decision_model(
    self, generator: PackageGenerator, base_profile: ProfileOutput
  ) -> None:
    """decision_model が None なら skills/decision-rules/SKILL.md 非生成"""
    files = generator.generate(base_profile, "agent-001", "Test Agent")
    assert "skills/decision-rules/SKILL.md" not in files

  def test_no_reasoning_flow_tool_without_reasoning_flow(
    self, generator: PackageGenerator, base_profile: ProfileOutput
  ) -> None:
    """reasoning_flow が None なら tools/reasoning_flow.json 非生成"""
    files = generator.generate(base_profile, "agent-001", "Test Agent")
    assert "tools/reasoning_flow.json" not in files

  def test_no_context_adaptation_in_config_without_data(
    self, generator: PackageGenerator, base_profile: ProfileOutput
  ) -> None:
    """context_adaptation が None なら config.json に含まれない"""
    files = generator.generate(base_profile, "agent-001", "Test Agent")
    config = json.loads(files["config.json"])
    assert "context_adaptation" not in config

  def test_no_self_awareness_section_without_failure_patterns(
    self, generator: PackageGenerator, base_profile: ProfileOutput
  ) -> None:
    """failure_patterns が None なら ## Self-Awareness 非表示"""
    files = generator.generate(base_profile, "agent-001", "Test Agent")
    assert "## Self-Awareness" not in files["system_prompt.md"]


# =============================================================================
# Req 8.1: system_prompt.md に "## Decision Framework" セクション
# =============================================================================


class TestDecisionFrameworkSection:
  """system_prompt.md に Decision Framework セクション追加"""

  def test_decision_framework_in_system_prompt(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """decision_model がある場合、## Decision Framework が含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    assert "## Decision Framework" in files["system_prompt.md"]

  def test_decision_framework_lists_priorities_with_weights(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """priorities が weight 付きでリストされる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["system_prompt.md"]
    assert "quality (weight: 1.0)" in content
    assert "speed (weight: 0.7)" in content
    assert "cost (weight: 0.4)" in content

  def test_decision_framework_lists_tradeoff_tendencies(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """tradeoff_tendencies がリストされる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["system_prompt.md"]
    assert "speed_vs_quality" in content
    assert "innovation_vs_stability" in content


# =============================================================================
# Req 8.4: system_prompt.md に "## Self-Awareness" セクション
# =============================================================================


class TestSelfAwarenessSection:
  """system_prompt.md に Self-Awareness セクション追加"""

  def test_self_awareness_in_system_prompt(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """failure_patterns がある場合、## Self-Awareness が含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    assert "## Self-Awareness" in files["system_prompt.md"]

  def test_self_awareness_lists_all_subcategories(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """全4サブカテゴリの内容が含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["system_prompt.md"]
    # degradation_triggers
    assert "睡眠不足" in content
    assert "連続会議" in content
    # procrastination_patterns
    assert "大きなタスクを先延ばし" in content
    # overconfidence_conditions
    assert "過去の成功体験が多い分野" in content
    # recurring_mistakes
    assert "テスト不足でリリース" in content

  def test_self_awareness_has_subcategory_headers(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """サブカテゴリヘッダーが含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["system_prompt.md"]
    assert "### Degradation Triggers" in content
    assert "### Procrastination Patterns" in content
    assert "### Overconfidence Conditions" in content
    assert "### Recurring Mistakes" in content


# =============================================================================
# Req 8.2: skills/decision-rules/SKILL.md 生成
# =============================================================================


class TestDecisionRulesSkill:
  """skills/decision-rules/SKILL.md の生成"""

  def test_skill_file_generated_with_decision_model(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """decision_model がある場合に SKILL.md が生成される"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    assert "skills/decision-rules/SKILL.md" in files

  def test_skill_has_yaml_frontmatter(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """YAML frontmatter が含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["skills/decision-rules/SKILL.md"]
    assert content.startswith("---\n")
    assert "name: decision-rules" in content
    assert "description:" in content
    assert "metadata:" in content
    assert "generated-by: agent-profiler" in content
    assert "profile-id: prof_000001" in content
    assert 'version: "1.0"' in content
    # frontmatter が閉じている
    assert content.count("---") >= 2

  def test_skill_contains_escalation_rules(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """## Escalation Rules セクションが含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["skills/decision-rules/SKILL.md"]
    assert "## Escalation Rules" in content
    assert "予算超過の場合は上長に確認" in content
    assert "セキュリティリスクがある場合は報告" in content

  def test_skill_contains_auto_approve_scope(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """## Auto-Approve Scope セクションが含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["skills/decision-rules/SKILL.md"]
    assert "## Auto-Approve Scope" in content
    assert "バグ修正" in content
    assert "ドキュメント更新" in content

  def test_skill_contains_tradeoff_tendencies_table(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """## Tradeoff Tendencies テーブルが含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["skills/decision-rules/SKILL.md"]
    assert "## Tradeoff Tendencies" in content
    assert "| Dimension | Score | Interpretation |" in content
    assert "speed_vs_quality" in content
    assert "0.8" in content


# =============================================================================
# Req 8.3: tools/reasoning_flow.json 生成
# =============================================================================


class TestReasoningFlowTool:
  """tools/reasoning_flow.json の生成"""

  def test_reasoning_flow_file_generated(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """reasoning_flow がある場合にファイルが生成される"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    assert "tools/reasoning_flow.json" in files

  def test_reasoning_flow_valid_json(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """有効な JSON で 2-space indent"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["tools/reasoning_flow.json"]
    data = json.loads(content)
    assert isinstance(data, dict)
    # 2-space indent の確認
    assert "  " in content
    # タブでないことを確認
    assert "\t" not in content

  def test_reasoning_flow_contains_required_keys(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """default_steps, verification_method, learning_style が含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    data = json.loads(files["tools/reasoning_flow.json"])
    assert "default_steps" in data
    assert "verification_method" in data
    assert "learning_style" in data

  def test_reasoning_flow_values_match_profile(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """値がプロファイルの reasoning_flow と一致する"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    data = json.loads(files["tools/reasoning_flow.json"])
    assert data["default_steps"] == ["問題定義", "情報収集", "仮説立案", "検証"]
    assert data["verification_method"] == "データで裏付け確認"
    assert data["learning_style"] == "実践型学習"

  def test_reasoning_flow_utf8_encoding(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """UTF-8 エンコーディングで日本語が正しく保存される"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    content = files["tools/reasoning_flow.json"]
    # ensure_ascii=False で日本語が直接埋め込まれる
    assert "問題定義" in content
    assert "\\u" not in content  # Unicode エスケープされていない


# =============================================================================
# Req 8.6: config.json に context_adaptation 追加
# =============================================================================


class TestConfigContextAdaptation:
  """config.json に context_adaptation を追加"""

  def test_context_adaptation_in_config(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """context_adaptation がある場合に config.json に含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    config = json.loads(files["config.json"])
    assert "context_adaptation" in config

  def test_context_adaptation_contains_modes(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """modes 辞書が含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    config = json.loads(files["config.json"])
    modes = config["context_adaptation"]["modes"]
    assert "executive_report" in modes
    assert modes["executive_report"]["tone"] == "formal"
    assert modes["executive_report"]["detail"] == "minimal"

  def test_context_adaptation_contains_switch_triggers(
    self, generator: PackageGenerator, full_profile: ProfileOutput
  ) -> None:
    """switch_triggers 辞書が含まれる"""
    files = generator.generate(full_profile, "agent-001", "Test Agent")
    config = json.loads(files["config.json"])
    triggers = config["context_adaptation"]["switch_triggers"]
    assert "audience" in triggers
    assert "urgency" in triggers
