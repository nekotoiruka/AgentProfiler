"""Property 10: 4軸スコアとパイプラインの並行動作

全質問に3層パイプラインが適用されても、4軸スコア（base_os.axes, decision_style, do_not_list）
の計算結果が従来ロジックと同一であることを検証する。

**Validates: Requirements 12.7, 12.3**
"""

from pathlib import Path
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.profile_generator import ProfileGenerator
from app.decision_engine.rule_aggregator import RuleAggregator
from app.decision_engine.scorer import DecisionScorer
from app.models.scores import NormalizedScores
from app.models.session import Answer
from app.services.data_loader import MappingDictionaryLoader


def _get_scorer():
  """実データからDecisionScorerを生成するヘルパー"""
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  loader.load()
  return DecisionScorer(loader)


# Strategy: 4軸の正規化スコア
normalized_scores_strategy = st.builds(
  NormalizedScores,
  extroverted_introverted=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
  sensing_intuition=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
  thinking_feeling=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
  judging_perceiving=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)


@given(scores=normalized_scores_strategy)
@settings(max_examples=100)
def test_base_os_unchanged_with_scorer(scores):
  """scorer の有無にかかわらず base_os の計算結果は同一

  **Validates: Requirements 12.7, 12.3**
  """
  pg = ProfileGenerator()
  pg.reset_counter()
  scorer = _get_scorer()
  aggregator = RuleAggregator()

  # 最低限の質問データ（lexical_tags生成のため空でも通る）
  answers: list[Answer] = []
  questions: list = []

  # scorer なし
  pg._counter = 0
  result_without = pg.generate(scores, answers, questions)

  # scorer あり
  pg._counter = 0
  result_with = pg.generate(scores, answers, questions, scorer=scorer, aggregator=aggregator)

  # base_os は完全一致
  assert result_without.base_os.axes == result_with.base_os.axes
  assert result_without.base_os.decision_style == result_with.base_os.decision_style
  assert result_without.base_os.do_not_list == result_with.base_os.do_not_list
