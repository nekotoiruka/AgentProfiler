"""Property 2: Tradeoff Tendency スコア範囲制約

choice "a" → tendency_score ∈ [0.0, 0.3]
choice "b" → tendency_score ∈ [0.7, 1.0]

全有効トレードオフエントリに対して、Mapping Dictionary のスコア範囲が
要件 2.4 の制約を満たすことを検証する。

**Validates: Requirements 2.4**
"""

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.scorer import DecisionScorer
from app.services.data_loader import MappingDictionaryLoader


def _get_scorer() -> DecisionScorer:
  """実データを使用した DecisionScorer インスタンスを生成する"""
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  return DecisionScorer(loader)


def _get_tradeoff_question_ids() -> list[str]:
  """Mapping Dictionary からトレードオフ質問IDを抽出する"""
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  mapping = loader.get()
  ids: set[str] = set()
  for entry in mapping.mappings:
    if entry.conflict_pair is not None:
      ids.add(entry.question_id)
  return sorted(ids)


# トレードオフ質問IDを事前に取得
_TRADEOFF_IDS = _get_tradeoff_question_ids()


@given(question_id=st.sampled_from(_TRADEOFF_IDS))
@settings(max_examples=50)
def test_tradeoff_choice_a_range(question_id: str) -> None:
  """choice 'a' の tendency_score は [0.0, 0.3] の範囲内であること

  **Validates: Requirements 2.4**
  """
  scorer = _get_scorer()
  pair, score = scorer.score_tradeoff(question_id, "a")
  assert 0.0 <= score <= 0.3, (
    f"Choice 'a' score {score} for {question_id} not in [0.0, 0.3]"
  )


@given(question_id=st.sampled_from(_TRADEOFF_IDS))
@settings(max_examples=50)
def test_tradeoff_choice_b_range(question_id: str) -> None:
  """choice 'b' の tendency_score は [0.7, 1.0] の範囲内であること

  **Validates: Requirements 2.4**
  """
  scorer = _get_scorer()
  pair, score = scorer.score_tradeoff(question_id, "b")
  assert 0.7 <= score <= 1.0, (
    f"Choice 'b' score {score} for {question_id} not in [0.7, 1.0]"
  )
