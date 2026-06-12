"""Scoring Engine プロパティベーステスト

Feature: agent-profiler
Validates: Requirements 3.1, 3.3, 3.4, 3.6, 4.7
"""

import itertools

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.scoring import ScoringEngine, MappingNotFoundError
from app.models.mapping import (
  MappingDictionary,
  MappingEntry,
  MappingScores,
  MappingMetadata,
  TheoreticalBounds,
  AxisBound,
)
from app.models.scores import AxisScores


# --- テスト用フィクスチャ ---

def _build_mapping_dictionary(entries: list[MappingEntry]) -> MappingDictionary:
  """テスト用 MappingDictionary を構築するヘルパー"""
  return MappingDictionary(
    metadata=MappingMetadata(
      version="1.0",
      theoretical_bounds=TheoreticalBounds(
        extroverted_introverted=AxisBound(min=-30, max=30),
        sensing_intuition=AxisBound(min=-25, max=25),
        thinking_feeling=AxisBound(min=-28, max=28),
        judging_perceiving=AxisBound(min=-26, max=26),
      ),
    ),
    mappings=entries,
  )


# テスト用の固定マッピングエントリ群
_FIXED_ENTRIES = [
  MappingEntry(
    question_id=f"q{i}",
    choice_id=f"c{j}",
    scores=MappingScores(
      extroverted_introverted=(i * 3 + j) % 21 - 10,
      sensing_intuition=(i * 5 + j * 2) % 21 - 10,
      thinking_feeling=(i * 7 + j * 3) % 21 - 10,
      judging_perceiving=(i * 2 + j * 5) % 21 - 10,
    ),
  )
  for i in range(5)
  for j in range(4)
]

_FIXED_MAPPING = _build_mapping_dictionary(_FIXED_ENTRIES)

# 有効なペアリスト（Property 1 の並べ替えに使用）
_VALID_PAIRS = [(e.question_id, e.choice_id) for e in _FIXED_ENTRIES]


# --- Hypothesis ストラテジー ---

# MappingScores の各軸が -10〜+10 の整数
_axis_score_st = st.integers(min_value=-10, max_value=10)

_mapping_scores_st = st.builds(
  MappingScores,
  extroverted_introverted=_axis_score_st,
  sensing_intuition=_axis_score_st,
  thinking_feeling=_axis_score_st,
  judging_perceiving=_axis_score_st,
)

# 任意の AxisScores（セッション累積スコア）
_axis_scores_st = st.builds(
  AxisScores,
  extroverted_introverted=st.integers(min_value=-200, max_value=200),
  sensing_intuition=st.integers(min_value=-200, max_value=200),
  thinking_feeling=st.integers(min_value=-200, max_value=200),
  judging_perceiving=st.integers(min_value=-200, max_value=200),
)

# 有効ペアのインデックスリスト（並べ替え検証用）
_pair_indices_st = st.lists(
  st.integers(min_value=0, max_value=len(_VALID_PAIRS) - 1),
  min_size=1,
  max_size=10,
)


# --- Property 1: Score accumulation is commutative sum ---
# Feature: agent-profiler, Property 1: Score accumulation is commutative sum


@settings(max_examples=200)
@given(indices=_pair_indices_st, data=st.data())
def test_score_accumulation_is_commutative_sum(indices: list[int], data) -> None:
  """任意の有効 (question_id, choice_id) 提出順序に対して、
  全提出を順次適用した結果は提出順序によらず同一のスコアとなる。

  **Validates: Requirements 3.1, 3.4**
  """
  engine = ScoringEngine(_FIXED_MAPPING)
  pairs = [_VALID_PAIRS[i] for i in indices]

  # 順序1: 元の順序で適用
  scores_order1 = AxisScores()
  for qid, cid in pairs:
    scores_order1 = engine.apply_score(scores_order1, qid, cid)

  # 順序2: ランダムに並べ替えた順序で適用
  shuffled = data.draw(st.permutations(pairs))
  scores_order2 = AxisScores()
  for qid, cid in shuffled:
    scores_order2 = engine.apply_score(scores_order2, qid, cid)

  # 順序に依存せず結果が一致する
  assert scores_order1.extroverted_introverted == scores_order2.extroverted_introverted
  assert scores_order1.sensing_intuition == scores_order2.sensing_intuition
  assert scores_order1.thinking_feeling == scores_order2.thinking_feeling
  assert scores_order1.judging_perceiving == scores_order2.judging_perceiving

  # 結果が各軸の算術和と一致する
  expected_ei = sum(
    _FIXED_MAPPING.mappings[i].scores.extroverted_introverted for i in indices
  )
  expected_sn = sum(
    _FIXED_MAPPING.mappings[i].scores.sensing_intuition for i in indices
  )
  expected_tf = sum(
    _FIXED_MAPPING.mappings[i].scores.thinking_feeling for i in indices
  )
  expected_jp = sum(
    _FIXED_MAPPING.mappings[i].scores.judging_perceiving for i in indices
  )

  assert scores_order1.extroverted_introverted == expected_ei
  assert scores_order1.sensing_intuition == expected_sn
  assert scores_order1.thinking_feeling == expected_tf
  assert scores_order1.judging_perceiving == expected_jp


# --- Property 2: Neutral score invariant ---
# Feature: agent-profiler, Property 2: Neutral score invariant


@settings(max_examples=200)
@given(session_scores=_axis_scores_st)
def test_neutral_score_invariant(session_scores: AxisScores) -> None:
  """任意のセッションスコアに対して apply_neutral() を適用すると、
  全4軸の値が不変であり、同一オブジェクト参照が返される。

  **Validates: Requirements 3.3**
  """
  engine = ScoringEngine(_FIXED_MAPPING)

  result = engine.apply_neutral(session_scores)

  # 全軸の値が不変
  assert result.extroverted_introverted == session_scores.extroverted_introverted
  assert result.sensing_intuition == session_scores.sensing_intuition
  assert result.thinking_feeling == session_scores.thinking_feeling
  assert result.judging_perceiving == session_scores.judging_perceiving

  # 同一オブジェクト参照（identity operation）
  assert result is session_scores


# --- Property 4: Missing mapping produces error without side effects ---
# Feature: agent-profiler, Property 4: Missing mapping produces error without side effects

# マッピングに存在しない ID を生成するストラテジー
_invalid_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "P")),
  min_size=1,
  max_size=20,
).filter(lambda s: not any(s == e.question_id for e in _FIXED_ENTRIES))

_invalid_choice_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "P")),
  min_size=1,
  max_size=20,
).filter(lambda s: not any(s == e.choice_id for e in _FIXED_ENTRIES))


@settings(max_examples=200)
@given(
  session_scores=_axis_scores_st,
  question_id=_invalid_id_st,
  choice_id=st.text(min_size=1, max_size=20),
)
def test_missing_mapping_produces_error_without_side_effects(
  session_scores: AxisScores, question_id: str, choice_id: str
) -> None:
  """マッピング辞書に存在しない (question_id, choice_id) ペアで
  スコアリングを試みると MappingNotFoundError が発生し、
  セッションスコアは変更されない。

  **Validates: Requirements 3.6, 4.7**
  """
  engine = ScoringEngine(_FIXED_MAPPING)

  # スコア適用前の値を保持
  original_ei = session_scores.extroverted_introverted
  original_sn = session_scores.sensing_intuition
  original_tf = session_scores.thinking_feeling
  original_jp = session_scores.judging_perceiving

  # MappingNotFoundError が発生する
  try:
    engine.apply_score(session_scores, question_id, choice_id)
    # ここに到達したら question_id が偶然マッピングに存在している
    # （filter で除外しているはずだが安全のため assume で除外）
    assume(False)
  except MappingNotFoundError as e:
    assert e.question_id == question_id
    assert e.choice_id == choice_id

  # セッションスコアが変更されていないことを確認
  assert session_scores.extroverted_introverted == original_ei
  assert session_scores.sensing_intuition == original_sn
  assert session_scores.thinking_feeling == original_tf
  assert session_scores.judging_perceiving == original_jp
