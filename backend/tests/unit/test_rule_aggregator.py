"""RuleAggregator ユニットテスト"""

import pytest

from app.decision_engine.rule_aggregator import RuleAggregator, RuleHierarchy


@pytest.fixture
def aggregator() -> RuleAggregator:
  """テスト用 RuleAggregator"""
  return RuleAggregator()


class TestAggregateEmptyInput:
  def test_empty_input_returns_empty_hierarchy(self, aggregator: RuleAggregator) -> None:
    """空リスト入力で全層が空の RuleHierarchy を返す"""
    result = aggregator.aggregate([])
    assert result == RuleHierarchy(
      core_invariants=[],
      context_rules=[],
      exceptions=[],
      preferences=[],
    )


class TestCoreInvariantClassification:
  def test_is_core_high_confidence_permanent(self, aggregator: RuleAggregator) -> None:
    """is_core=True, confidence>=0.8, permanence="permanent" → core_invariants"""
    policy = {
      "question_id": "dm_001",
      "rule": "when_decision: 根本原因を最優先する",
      "confidence": 0.9,
      "is_core": True,
      "permanence": "permanent",
      "normalization_tags": [],
    }
    result = aggregator.aggregate([policy])
    assert len(result.core_invariants) == 1
    assert result.core_invariants[0] == policy

  def test_core_requires_is_core_true(self, aggregator: RuleAggregator) -> None:
    """is_core=False ではcore_invariantsに分類されない"""
    policy = {
      "question_id": "dm_002",
      "rule": "some rule",
      "confidence": 0.9,
      "is_core": False,
      "permanence": "permanent",
      "normalization_tags": [],
    }
    result = aggregator.aggregate([policy])
    assert len(result.core_invariants) == 0
    # confidence >= 0.5 なので context_rules
    assert len(result.context_rules) == 1

  def test_core_requires_high_confidence(self, aggregator: RuleAggregator) -> None:
    """confidence < 0.8 ではcore_invariantsに分類されない"""
    policy = {
      "question_id": "dm_003",
      "rule": "some rule",
      "confidence": 0.7,
      "is_core": True,
      "permanence": "permanent",
      "normalization_tags": [],
    }
    result = aggregator.aggregate([policy])
    assert len(result.core_invariants) == 0
    # confidence >= 0.5 なので context_rules
    assert len(result.context_rules) == 1

  def test_core_requires_permanent(self, aggregator: RuleAggregator) -> None:
    """permanence != "permanent" ではcore_invariantsに分類されない"""
    policy = {
      "question_id": "dm_004",
      "rule": "some rule",
      "confidence": 0.9,
      "is_core": True,
      "permanence": "contextual",
      "normalization_tags": [],
    }
    result = aggregator.aggregate([policy])
    assert len(result.core_invariants) == 0
    # confidence >= 0.5 なので context_rules
    assert len(result.context_rules) == 1


class TestExceptionClassification:
  def test_condition_tag_present(self, aggregator: RuleAggregator) -> None:
    """normalization_tags に condition_tag がある → exceptions"""
    policy = {
      "question_id": "fp_001",
      "rule": "when_tired: 重要判断を避ける",
      "confidence": 0.9,
      "is_core": True,
      "permanence": "permanent",
      "normalization_tags": [{"type": "condition_tag", "value": "疲労時"}],
    }
    result = aggregator.aggregate([policy])
    assert len(result.exceptions) == 1
    assert result.exceptions[0] == policy
    # condition_tag があれば core 条件を満たしていても exceptions が優先
    assert len(result.core_invariants) == 0

  def test_condition_tag_with_other_tags(self, aggregator: RuleAggregator) -> None:
    """他のタグと混在していても condition_tag があれば exceptions"""
    policy = {
      "question_id": "fp_002",
      "rule": "exception rule",
      "confidence": 0.6,
      "is_core": False,
      "permanence": "permanent",
      "normalization_tags": [
        {"type": "value_tag", "value": "慎重さ"},
        {"type": "condition_tag", "value": "夜間作業時"},
      ],
    }
    result = aggregator.aggregate([policy])
    assert len(result.exceptions) == 1
    assert len(result.context_rules) == 0


class TestContextRuleClassification:
  def test_medium_confidence_not_core(self, aggregator: RuleAggregator) -> None:
    """confidence>=0.5, is_core=False, condition_tagなし → context_rules"""
    policy = {
      "question_id": "ca_001",
      "rule": "when_executive_audience: 結論ファースト",
      "confidence": 0.6,
      "is_core": False,
      "permanence": "permanent",
      "normalization_tags": [{"type": "behavior_tag", "value": "結論ファースト"}],
    }
    result = aggregator.aggregate([policy])
    assert len(result.context_rules) == 1
    assert result.context_rules[0] == policy

  def test_confidence_exactly_0_5(self, aggregator: RuleAggregator) -> None:
    """confidence=0.5 の境界値 → context_rules"""
    policy = {
      "question_id": "ca_002",
      "rule": "borderline rule",
      "confidence": 0.5,
      "is_core": False,
      "permanence": "contextual",
      "normalization_tags": [],
    }
    result = aggregator.aggregate([policy])
    assert len(result.context_rules) == 1


class TestPreferenceClassification:
  def test_low_confidence(self, aggregator: RuleAggregator) -> None:
    """confidence < 0.5 → preferences"""
    policy = {
      "question_id": "rf_001",
      "rule": "when_learning: 動画で学ぶ",
      "confidence": 0.3,
      "is_core": False,
      "permanence": "contextual",
      "normalization_tags": [],
    }
    result = aggregator.aggregate([policy])
    assert len(result.preferences) == 1
    assert result.preferences[0] == policy

  def test_zero_confidence(self, aggregator: RuleAggregator) -> None:
    """confidence=0.0 → preferences"""
    policy = {
      "question_id": "rf_002",
      "rule": "weak rule",
      "confidence": 0.0,
      "is_core": False,
      "permanence": "permanent",
      "normalization_tags": [],
    }
    result = aggregator.aggregate([policy])
    assert len(result.preferences) == 1


class TestMaxCoreInvariants:
  def test_overflow_demoted_to_context_rules(self, aggregator: RuleAggregator) -> None:
    """core_invariants がmax_coreを超過 → 超過分がcontext_rulesに降格"""
    policies = [
      {
        "question_id": f"dm_{i:03d}",
        "rule": f"core rule {i}",
        "confidence": 0.8 + (i * 0.01),
        "is_core": True,
        "permanence": "permanent",
        "normalization_tags": [],
      }
      for i in range(12)
    ]
    result = aggregator.aggregate(policies, max_core=10)
    assert len(result.core_invariants) == 10
    assert len(result.context_rules) == 2

  def test_overflow_sorted_by_confidence_desc(self, aggregator: RuleAggregator) -> None:
    """core_invariants はconfidence降順でソートされ、低confidence側が降格"""
    policies = [
      {
        "question_id": "dm_low",
        "rule": "low confidence core",
        "confidence": 0.80,
        "is_core": True,
        "permanence": "permanent",
        "normalization_tags": [],
      },
      {
        "question_id": "dm_high",
        "rule": "high confidence core",
        "confidence": 0.99,
        "is_core": True,
        "permanence": "permanent",
        "normalization_tags": [],
      },
    ]
    result = aggregator.aggregate(policies, max_core=1)
    # confidence 最高の1件のみ core に残る
    assert len(result.core_invariants) == 1
    assert result.core_invariants[0]["question_id"] == "dm_high"
    # 残りは context_rules へ降格
    assert len(result.context_rules) == 1
    assert result.context_rules[0]["question_id"] == "dm_low"

  def test_exactly_at_max_core(self, aggregator: RuleAggregator) -> None:
    """ちょうどmax_core件の場合は降格なし"""
    policies = [
      {
        "question_id": f"dm_{i:03d}",
        "rule": f"core rule {i}",
        "confidence": 0.9,
        "is_core": True,
        "permanence": "permanent",
        "normalization_tags": [],
      }
      for i in range(10)
    ]
    result = aggregator.aggregate(policies, max_core=10)
    assert len(result.core_invariants) == 10
    assert len(result.context_rules) == 0


class TestMixedInput:
  def test_mixed_policies_correctly_classified(self, aggregator: RuleAggregator) -> None:
    """複合入力が正しく4層に分類される"""
    policies = [
      # core_invariant: is_core + high confidence + permanent
      {
        "question_id": "dm_001",
        "rule": "core: root cause first",
        "confidence": 0.95,
        "is_core": True,
        "permanence": "permanent",
        "normalization_tags": [{"type": "value_tag", "value": "根本原因"}],
      },
      # exception: condition_tag present
      {
        "question_id": "fp_001",
        "rule": "exception: avoid decision when tired",
        "confidence": 0.8,
        "is_core": True,
        "permanence": "permanent",
        "normalization_tags": [{"type": "condition_tag", "value": "疲労時"}],
      },
      # context_rule: confidence>=0.5, not core
      {
        "question_id": "ca_001",
        "rule": "context: use formal tone for executives",
        "confidence": 0.7,
        "is_core": False,
        "permanence": "permanent",
        "normalization_tags": [{"type": "behavior_tag", "value": "フォーマル"}],
      },
      # preference: low confidence
      {
        "question_id": "rf_001",
        "rule": "preference: prefer video learning",
        "confidence": 0.3,
        "is_core": False,
        "permanence": "contextual",
        "normalization_tags": [],
      },
    ]
    result = aggregator.aggregate(policies)
    assert len(result.core_invariants) == 1
    assert result.core_invariants[0]["question_id"] == "dm_001"
    assert len(result.exceptions) == 1
    assert result.exceptions[0]["question_id"] == "fp_001"
    assert len(result.context_rules) == 1
    assert result.context_rules[0]["question_id"] == "ca_001"
    assert len(result.preferences) == 1
    assert result.preferences[0]["question_id"] == "rf_001"

  def test_total_count_preserved(self, aggregator: RuleAggregator) -> None:
    """全ルールがいずれかの層に含まれ、合計数が一致する"""
    policies = [
      {"question_id": "a", "rule": "r1", "confidence": 0.95, "is_core": True, "permanence": "permanent", "normalization_tags": []},
      {"question_id": "b", "rule": "r2", "confidence": 0.6, "is_core": False, "permanence": "permanent", "normalization_tags": []},
      {"question_id": "c", "rule": "r3", "confidence": 0.3, "is_core": False, "permanence": "contextual", "normalization_tags": []},
      {"question_id": "d", "rule": "r4", "confidence": 0.8, "is_core": False, "permanence": "permanent", "normalization_tags": [{"type": "condition_tag", "value": "条件"}]},
    ]
    result = aggregator.aggregate(policies)
    total = (
      len(result.core_invariants)
      + len(result.context_rules)
      + len(result.exceptions)
      + len(result.preferences)
    )
    assert total == len(policies)
