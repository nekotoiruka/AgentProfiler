"""Property 14: Core Invariant 候補の分類基準と上限

confidence >= 0.8 AND permanence = "permanent" AND is_core = True の条件、上限10件を検証する。

**Validates: Requirements 17.5**
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.rule_aggregator import RuleAggregator


# Generate policies that may or may not qualify as core invariants
policy_strategy = st.fixed_dictionaries({
  "question_id": st.text(min_size=1, max_size=10),
  "rule": st.text(min_size=1, max_size=50),
  "confidence": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
  "is_core": st.booleans(),
  "permanence": st.sampled_from(["permanent", "contextual"]),
  "normalization_tags": st.lists(
    st.fixed_dictionaries({
      "type": st.sampled_from(["value_tag", "behavior_tag", "prohibition_tag"]),  # No condition_tag
      "value": st.text(min_size=1, max_size=20),
    }),
    min_size=0,
    max_size=2,
  ),
})


@given(policies=st.lists(policy_strategy, min_size=0, max_size=50))
@settings(max_examples=200)
def test_core_invariant_limit(policies):
  """core_invariants は最大10件に制限される"""
  aggregator = RuleAggregator()
  result = aggregator.aggregate(policies, max_core=10)

  assert len(result.core_invariants) <= 10


@given(policies=st.lists(policy_strategy, min_size=0, max_size=50))
@settings(max_examples=200)
def test_core_invariants_meet_criteria(policies):
  """core_invariants の全エントリが条件を満たす"""
  aggregator = RuleAggregator()
  result = aggregator.aggregate(policies)

  for policy in result.core_invariants:
    assert policy["confidence"] >= 0.8, f"Core invariant confidence {policy['confidence']} < 0.8"
    assert policy["permanence"] == "permanent", f"Core invariant permanence is {policy['permanence']}"
    assert policy["is_core"] is True, "Core invariant must have is_core=True"
    # Must not have condition_tag
    tags = policy.get("normalization_tags", [])
    has_condition = any(t.get("type") == "condition_tag" for t in tags)
    assert not has_condition, "Core invariant must not have condition_tag"
