"""Property 6: Context Adaptation モード設定構造の妥当性

Feature: agent-decision-engine
**Validates: Requirements 4.4**
"""

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.scorer import DecisionScorer
from app.services.data_loader import MappingDictionaryLoader

VALID_DETAIL_LEVELS = {"minimal", "standard", "comprehensive"}


def _get_scorer():
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  return DecisionScorer(loader)


def _get_context_adaptation_pairs():
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  mapping = loader.get()
  pairs = []
  for entry in mapping.mappings:
    if entry.mode_name is not None:
      pairs.append((entry.question_id, entry.choice_id))
  return pairs


_CA_PAIRS = _get_context_adaptation_pairs()


@given(pair=st.sampled_from(_CA_PAIRS))
@settings(max_examples=100)
def test_mode_config_structure(pair):
  """tone ≤50文字, detail ∈ valid set, focus ≤50文字

  **Validates: Requirements 4.4**
  """
  scorer = _get_scorer()
  question_id, choice_id = pair
  result = scorer.score_context_adaptation(question_id, choice_id)

  for mode_name, config in result.items():
    assert len(config["tone"]) <= 50, f"tone too long: {len(config['tone'])}"
    assert config["detail"] in VALID_DETAIL_LEVELS, f"Invalid detail: {config['detail']}"
    assert len(config["focus"]) <= 50, f"focus too long: {len(config['focus'])}"
