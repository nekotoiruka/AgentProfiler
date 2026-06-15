"""Property 5: Failure Pattern サブカテゴリ分類の妥当性

Feature: agent-decision-engine
**Validates: Requirements 3.4**
"""

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.scorer import DecisionScorer
from app.services.data_loader import MappingDictionaryLoader

VALID_SUBCATEGORIES = {
  "degradation_triggers",
  "procrastination_patterns",
  "overconfidence_conditions",
  "recurring_mistakes",
}


def _get_scorer():
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  return DecisionScorer(loader)


def _get_failure_pairs():
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  mapping = loader.get()
  pairs = []
  for entry in mapping.mappings:
    if entry.subcategory is not None:
      pairs.append((entry.question_id, entry.choice_id))
  return pairs


_FAILURE_PAIRS = _get_failure_pairs()


@given(pair=st.sampled_from(_FAILURE_PAIRS))
@settings(max_examples=100)
def test_failure_pattern_valid_subcategory(pair):
  """全 valid ペアで分類結果が4サブカテゴリのいずれかに属する

  **Validates: Requirements 3.4**
  """
  scorer = _get_scorer()
  question_id, choice_id = pair
  subcategory, label = scorer.score_failure_pattern(question_id, choice_id)
  assert subcategory in VALID_SUBCATEGORIES, f"Invalid subcategory: {subcategory}"
  assert len(label) > 0, "Label must not be empty"
  assert len(label) <= 100, f"Label too long: {len(label)} chars"
