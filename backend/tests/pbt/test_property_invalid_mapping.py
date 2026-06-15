"""Property 3: 無効マッピングの一貫した拒否

存在しない question_id/choice_id の組み合わせで、
全4種のスコアリングメソッドが一貫して MappingNotFoundError を送出することを検証する。

**Validates: Requirements 1.5, 2.5, 3.5, 4.5, 5.7**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock

from app.decision_engine.scorer import DecisionScorer, MappingNotFoundError
from app.models.mapping import (
  MappingDictionary,
  MappingMetadata,
  MappingEntry,
  MappingScores,
  AxisBound,
  TheoreticalBounds,
)

# テスト用に最小限の有効エントリを持つスコアラーを構築
METADATA = MappingMetadata(
  version="3.0",
  theoretical_bounds=TheoreticalBounds(
    extroverted_introverted=AxisBound(min=-120, max=156),
    sensing_intuition=AxisBound(min=-106, max=131),
    thinking_feeling=AxisBound(min=-129, max=137),
    judging_perceiving=AxisBound(min=-119, max=137),
  ),
)


def _make_scorer() -> DecisionScorer:
  """有効エントリ1件のみを持つ DecisionScorer を生成する"""
  loader = MagicMock()
  loader.get.return_value = MappingDictionary(
    metadata=METADATA,
    mappings=[
      MappingEntry(
        question_id="dm_001",
        choice_id="a",
        scores=MappingScores(
          extroverted_introverted=0,
          sensing_intuition=0,
          thinking_feeling=0,
          judging_perceiving=0,
        ),
        priority_labels=["test"],
        weights={"test": 5},
        policy_text="when_test: test",
      ),
    ],
  )
  return DecisionScorer(loader)


@given(
  question_id=st.text(min_size=1, max_size=30).filter(lambda x: not x.startswith("dm_")),
  choice_id=st.text(min_size=1, max_size=5),
)
@settings(max_examples=200)
def test_all_methods_reject_invalid_mapping(question_id: str, choice_id: str) -> None:
  """存在しない question_id/choice_id の組み合わせで全メソッドが MappingNotFoundError を送出

  全4種のスコアリングメソッド（score_decision_model, score_tradeoff,
  score_failure_pattern, score_context_adaptation）が一貫して
  同一の例外を発生させることを検証する。

  **Validates: Requirements 1.5, 2.5, 3.5, 4.5, 5.7**
  """
  scorer = _make_scorer()

  with pytest.raises(MappingNotFoundError):
    scorer.score_decision_model(question_id, choice_id)

  with pytest.raises(MappingNotFoundError):
    scorer.score_tradeoff(question_id, choice_id)

  with pytest.raises(MappingNotFoundError):
    scorer.score_failure_pattern(question_id, choice_id)

  with pytest.raises(MappingNotFoundError):
    scorer.score_context_adaptation(question_id, choice_id)
