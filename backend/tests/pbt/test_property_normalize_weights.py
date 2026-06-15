"""Property 1: Priority Weight 正規化の不変条件

Feature: agent-decision-engine
**Validates: Requirements 1.7**
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock

from app.decision_engine.scorer import DecisionScorer
from app.models.mapping import (
  MappingDictionary,
  MappingMetadata,
  MappingEntry,
  MappingScores,
  AxisBound,
  TheoreticalBounds,
)


def _make_scorer() -> DecisionScorer:
  """最小構成の DecisionScorer を生成するヘルパー"""
  loader = MagicMock()
  loader.get.return_value = MappingDictionary(
    metadata=MappingMetadata(
      version="3.0",
      theoretical_bounds=TheoreticalBounds(
        extroverted_introverted=AxisBound(min=-120, max=156),
        sensing_intuition=AxisBound(min=-106, max=131),
        thinking_feeling=AxisBound(min=-129, max=137),
        judging_perceiving=AxisBound(min=-119, max=137),
      ),
    ),
    mappings=[],
  )
  return DecisionScorer(loader)


@given(
  weights=st.dictionaries(
    keys=st.text(
      min_size=1,
      max_size=20,
      alphabet=st.characters(whitelist_categories=("L", "N")),
    ),
    values=st.integers(min_value=-1000, max_value=1000),
    min_size=1,
    max_size=20,
  )
)
@settings(max_examples=200)
def test_normalize_weights_range_and_max(weights: dict[str, int]) -> None:
  """非空辞書に対し:
  - 全出力値が [0.0, 1.0] 範囲
  - 最大値が 1.0
  - 全値が小数点2桁

  **Validates: Requirements 1.7**
  """
  scorer = _make_scorer()

  result = scorer.normalize_weights(weights)

  # 全値が [0.0, 1.0] 範囲内
  for v in result.values():
    assert 0.0 <= v <= 1.0, f"Value {v} out of range [0.0, 1.0]"

  # 少なくとも1つの値が 1.0（最大値保証）
  assert 1.0 in result.values(), "Max value must be 1.0"

  # 全値が小数点2桁に丸められている
  for v in result.values():
    assert v == round(v, 2), f"Value {v} not rounded to 2 decimal places"
