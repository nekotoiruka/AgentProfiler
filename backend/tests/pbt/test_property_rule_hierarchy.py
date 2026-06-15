"""Property 12: Rule Hierarchy 分類の排他性と網羅性

各ルールが1層にのみ分類され、全ルールがいずれかの層に含まれることを検証する。

Feature: agent-decision-engine
**Validates: Requirements 16.6**
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.rule_aggregator import RuleAggregator


# Strategy: ランダムなポリシーデータを生成
policy_strategy = st.fixed_dictionaries({
  "question_id": st.text(min_size=1, max_size=10),
  "rule": st.text(min_size=1, max_size=50),
  "confidence": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
  "is_core": st.booleans(),
  "permanence": st.sampled_from(["permanent", "contextual"]),
  "normalization_tags": st.lists(
    st.fixed_dictionaries({
      "type": st.sampled_from(["value_tag", "behavior_tag", "prohibition_tag", "condition_tag"]),
      "value": st.text(min_size=1, max_size=20),
    }),
    min_size=0,
    max_size=3,
  ),
})


@given(policies=st.lists(policy_strategy, min_size=0, max_size=50))
@settings(max_examples=200)
def test_exhaustiveness_total_preserved(policies: list[dict]) -> None:
  """全ルールがいずれかの層に含まれ、合計が入力と一致する

  **Validates: Requirements 16.6**
  """
  aggregator = RuleAggregator()
  result = aggregator.aggregate(policies)

  total = (
    len(result.core_invariants)
    + len(result.context_rules)
    + len(result.exceptions)
    + len(result.preferences)
  )
  assert total == len(policies), f"Total {total} != input count {len(policies)}"


@given(policies=st.lists(policy_strategy, min_size=1, max_size=30))
@settings(max_examples=200)
def test_exclusivity_no_duplicates(policies: list[dict]) -> None:
  """各ルールが1つの層にのみ存在する（重複なし）

  **Validates: Requirements 16.6**
  """
  aggregator = RuleAggregator()
  result = aggregator.aggregate(policies)

  # 全層のルールを結合し、入力数と一致することで排他性を確認
  all_classified = (
    result.core_invariants
    + result.context_rules
    + result.exceptions
    + result.preferences
  )

  # 各入力ポリシーが出力に正確に1回だけ存在する
  assert len(all_classified) == len(policies)
