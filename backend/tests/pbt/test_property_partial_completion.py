"""Property 4: 部分完了時のセクション非生成

各カテゴリ未完了時に該当セクション出力が None であることを検証する。

**Validates: Requirements 1.8, 2.7, 3.7, 4.8, 5.10**
"""

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.profile_generator import ProfileGenerator
from app.decision_engine.scorer import DecisionScorer
from app.models.session import Answer
from app.services.data_loader import MappingDictionaryLoader


def _get_scorer():
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  return DecisionScorer(loader)


def _make_answers(prefix: str, count: int, max_id: int = 10) -> list[Answer]:
  """指定プレフィクスで count 件の回答を生成"""
  answers = []
  for i in range(1, count + 1):
    answers.append(Answer(
      question_id=f"{prefix}{i:03d}",
      choice_id="a",
    ))
  return answers


# decision_model: 10問必要 → 0〜9問だと None
@given(count=st.integers(min_value=0, max_value=9))
@settings(max_examples=20)
def test_decision_model_incomplete_returns_none(count):
  """dm_ 回答が10問未満で decision_model は None"""
  pg = ProfileGenerator()
  pg.reset_counter()
  scorer = _get_scorer()

  answers = _make_answers("dm_", count)
  result = pg._build_decision_model(answers, scorer)
  assert result is None


# failure_patterns: 7問必要 → 0〜6問だと None
@given(count=st.integers(min_value=0, max_value=6))
@settings(max_examples=14)
def test_failure_patterns_incomplete_returns_none(count):
  """fp_ 回答が7問未満で failure_patterns は None"""
  pg = ProfileGenerator()
  scorer = _get_scorer()

  answers = _make_answers("fp_", count, max_id=7)
  result = pg._build_failure_patterns(answers, scorer)
  assert result is None


# context_adaptation: 5問必要 → 0〜4問だと None
@given(count=st.integers(min_value=0, max_value=4))
@settings(max_examples=10)
def test_context_adaptation_incomplete_returns_none(count):
  """ca_ 回答が5問未満で context_adaptation は None"""
  pg = ProfileGenerator()
  scorer = _get_scorer()

  answers = _make_answers("ca_", count, max_id=5)
  result = pg._build_context_adaptation(answers, scorer)
  assert result is None


# reasoning_flow: 5問必要 → 0〜4問だと None
@given(count=st.integers(min_value=0, max_value=4))
@settings(max_examples=10)
def test_reasoning_flow_incomplete_returns_none(count):
  """rf_ 回答が5問未満で reasoning_flow は None"""
  pg = ProfileGenerator()

  answers = _make_answers("rf_", count, max_id=5)
  result = pg._build_reasoning_flow(answers)
  assert result is None
