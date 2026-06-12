"""Progress計算 プロパティベーステスト

Feature: agent-profiler, Property 15: Progress percentage calculation
Validates: Requirements 1.3, 1.4
"""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.progress import calculate_progress


# --- Hypothesis ストラテジー ---

# total > 0 かつ 0 <= answered <= total の整数ペア
_progress_pair_st = st.integers(min_value=1, max_value=1000).flatmap(
  lambda total: st.tuples(
    st.integers(min_value=0, max_value=total),
    st.just(total),
  )
)

# カテゴリ進捗用: 複数カテゴリそれぞれに (answered, total) ペア
_category_progress_st = st.lists(
  st.integers(min_value=1, max_value=50).flatmap(
    lambda total: st.tuples(
      st.integers(min_value=0, max_value=total),
      st.just(total),
    )
  ),
  min_size=1,
  max_size=5,
)


# --- Property 15: Progress percentage calculation ---
# Feature: agent-profiler, Property 15: Progress percentage calculation


@settings(max_examples=200)
@given(pair=_progress_pair_st)
def test_overall_progress_equals_floor_percentage(pair: tuple[int, int]) -> None:
  """任意の (answered, total) ペア (0 <= answered <= total, total > 0) に対して、
  全体進捗 == floor(answered / total × 100) となる。

  **Validates: Requirements 1.3, 1.4**
  """
  answered, total = pair

  result = calculate_progress(answered, total)

  expected = math.floor(answered / total * 100)
  assert result == expected


@settings(max_examples=200)
@given(pair=_progress_pair_st)
def test_progress_always_in_range_0_to_100(pair: tuple[int, int]) -> None:
  """進捗率は常に [0, 100] の範囲内の整数である。

  **Validates: Requirements 1.3, 1.4**
  """
  answered, total = pair

  result = calculate_progress(answered, total)

  assert isinstance(result, int)
  assert 0 <= result <= 100


@settings(max_examples=200)
@given(pair=_progress_pair_st)
def test_progress_is_integer(pair: tuple[int, int]) -> None:
  """進捗率は常に整数型を返す。

  **Validates: Requirements 1.3, 1.4**
  """
  answered, total = pair

  result = calculate_progress(answered, total)

  assert isinstance(result, int)
  # float ではなく純粋な int であることを確認
  assert type(result) is int


@settings(max_examples=200)
@given(total=st.integers(min_value=1, max_value=1000))
def test_progress_zero_when_no_answers(total: int) -> None:
  """answered == 0 のとき、進捗率は必ず 0 となる。

  **Validates: Requirements 1.3, 1.4**
  """
  result = calculate_progress(0, total)

  assert result == 0


@settings(max_examples=200)
@given(total=st.integers(min_value=1, max_value=1000))
def test_progress_100_when_all_answered(total: int) -> None:
  """answered == total のとき、進捗率は必ず 100 となる。

  **Validates: Requirements 1.3, 1.4**
  """
  result = calculate_progress(total, total)

  assert result == 100


@settings(max_examples=200)
@given(categories=_category_progress_st)
def test_category_progress_equals_floor_percentage(
  categories: list[tuple[int, int]],
) -> None:
  """各カテゴリの進捗率が floor(answered_in_category / total_in_category × 100)
  と等しいことを検証する。

  **Validates: Requirements 1.3, 1.4**
  """
  for answered, total in categories:
    result = calculate_progress(answered, total)
    expected = math.floor(answered / total * 100)
    assert result == expected


@settings(max_examples=200)
@given(pair=_progress_pair_st)
def test_progress_monotonically_non_decreasing(pair: tuple[int, int]) -> None:
  """answered を 1 増やすと進捗率は減少しない（単調非減少）。

  **Validates: Requirements 1.3, 1.4**
  """
  answered, total = pair

  result_current = calculate_progress(answered, total)

  if answered < total:
    result_next = calculate_progress(answered + 1, total)
    assert result_next >= result_current
