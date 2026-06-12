# Feature: agent-profiler, Property 5: Normalization bounds and formula
"""Normalizer プロパティテスト

Property 5: For any raw axis score and theoretical bounds (min, max) where
min ≠ max, the normalized value SHALL equal round_half_up((raw - min) /
(max - min), 2) clamped to [0.00, 1.00]. The output SHALL always be a float
with exactly two decimal places in the range 0.00 to 1.00 regardless of input.

**Validates: Requirements 5.1, 5.3, 5.4**
"""

from decimal import Decimal, ROUND_HALF_UP

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.normalizer import Normalizer
from app.models import AxisScores, NormalizedScores, TheoreticalBounds, AxisBound


# -- ヘルパー: 期待値を独自に計算 --

def expected_normalized(raw: int, bound_min: int, bound_max: int) -> float:
  """テスト側で独自に正規化期待値を計算する（実装と独立）"""
  normalized = (raw - bound_min) / (bound_max - bound_min)
  # クランプ
  clamped = max(0.0, min(1.0, normalized))
  # round-half-up 2桁
  result = Decimal(str(clamped)).quantize(
    Decimal("0.01"), rounding=ROUND_HALF_UP
  )
  return float(result)


def has_two_decimal_places(value: float) -> bool:
  """値が小数点以下2桁以内であることを確認"""
  d = Decimal(str(value))
  # exponent が -2 以上（桁数が2以下）であること
  return d.as_tuple().exponent >= -2


# -- ストラテジー --

# 合理的な整数範囲で bounds を生成（min < max を保証）
reasonable_bounds = st.integers(min_value=-100, max_value=100)
# raw score は bounds 範囲内外どちらも含む
raw_scores = st.integers(min_value=-200, max_value=200)


@settings(max_examples=200)
@given(
  raw=raw_scores,
  bound_min=reasonable_bounds,
  bound_max=reasonable_bounds,
)
def test_normalization_formula_matches_expected(
  raw: int, bound_min: int, bound_max: int
) -> None:
  """正規化結果が期待公式と一致する（min ≠ max の場合）

  **Validates: Requirements 5.1, 5.3, 5.4**
  """
  # min ≠ max を前提条件とする
  assume(bound_min != bound_max)
  # min < max に正規化
  if bound_min > bound_max:
    bound_min, bound_max = bound_max, bound_min

  # Normalizer を構築（全軸同じ bounds を使用）
  bounds = TheoreticalBounds(
    extroverted_introverted=AxisBound(min=bound_min, max=bound_max),
    sensing_intuition=AxisBound(min=bound_min, max=bound_max),
    thinking_feeling=AxisBound(min=bound_min, max=bound_max),
    judging_perceiving=AxisBound(min=bound_min, max=bound_max),
  )
  normalizer = Normalizer(theoretical_bounds=bounds)

  # 全軸に同じ raw score を設定
  raw_axis_scores = AxisScores(
    extroverted_introverted=raw,
    sensing_intuition=raw,
    thinking_feeling=raw,
    judging_perceiving=raw,
  )

  result = normalizer.normalize(raw_axis_scores)

  # 期待値を計算
  expected = expected_normalized(raw, bound_min, bound_max)

  # 全軸の結果が期待値と一致
  assert result.extroverted_introverted == expected
  assert result.sensing_intuition == expected
  assert result.thinking_feeling == expected
  assert result.judging_perceiving == expected


@settings(max_examples=200)
@given(
  raw=raw_scores,
  bound_min=reasonable_bounds,
  bound_max=reasonable_bounds,
)
def test_normalized_value_always_in_range(
  raw: int, bound_min: int, bound_max: int
) -> None:
  """正規化結果が常に [0.00, 1.00] の範囲内である

  **Validates: Requirements 5.1, 5.3**
  """
  assume(bound_min != bound_max)
  if bound_min > bound_max:
    bound_min, bound_max = bound_max, bound_min

  bounds = TheoreticalBounds(
    extroverted_introverted=AxisBound(min=bound_min, max=bound_max),
    sensing_intuition=AxisBound(min=bound_min, max=bound_max),
    thinking_feeling=AxisBound(min=bound_min, max=bound_max),
    judging_perceiving=AxisBound(min=bound_min, max=bound_max),
  )
  normalizer = Normalizer(theoretical_bounds=bounds)

  raw_axis_scores = AxisScores(
    extroverted_introverted=raw,
    sensing_intuition=raw,
    thinking_feeling=raw,
    judging_perceiving=raw,
  )

  result = normalizer.normalize(raw_axis_scores)

  # 全軸が [0.00, 1.00] の範囲内
  for axis_value in [
    result.extroverted_introverted,
    result.sensing_intuition,
    result.thinking_feeling,
    result.judging_perceiving,
  ]:
    assert 0.0 <= axis_value <= 1.0, (
      f"Normalized value {axis_value} is out of range [0.0, 1.0]"
    )


@settings(max_examples=200)
@given(
  raw=raw_scores,
  bound_min=reasonable_bounds,
  bound_max=reasonable_bounds,
)
def test_normalized_value_has_two_decimal_places(
  raw: int, bound_min: int, bound_max: int
) -> None:
  """正規化結果が常に小数点以下2桁以内である

  **Validates: Requirements 5.4**
  """
  assume(bound_min != bound_max)
  if bound_min > bound_max:
    bound_min, bound_max = bound_max, bound_min

  bounds = TheoreticalBounds(
    extroverted_introverted=AxisBound(min=bound_min, max=bound_max),
    sensing_intuition=AxisBound(min=bound_min, max=bound_max),
    thinking_feeling=AxisBound(min=bound_min, max=bound_max),
    judging_perceiving=AxisBound(min=bound_min, max=bound_max),
  )
  normalizer = Normalizer(theoretical_bounds=bounds)

  raw_axis_scores = AxisScores(
    extroverted_introverted=raw,
    sensing_intuition=raw,
    thinking_feeling=raw,
    judging_perceiving=raw,
  )

  result = normalizer.normalize(raw_axis_scores)

  # 全軸が小数点以下2桁以内
  for axis_value in [
    result.extroverted_introverted,
    result.sensing_intuition,
    result.thinking_feeling,
    result.judging_perceiving,
  ]:
    assert has_two_decimal_places(axis_value), (
      f"Value {axis_value} has more than 2 decimal places"
    )


@settings(max_examples=200)
@given(
  bound_val=reasonable_bounds,
  raw=raw_scores,
)
def test_min_equals_max_returns_half(
  bound_val: int, raw: int
) -> None:
  """min == max の場合、正規化結果は 0.5 を返す

  **Validates: Requirements 5.1**
  """
  # min == max のケース
  bounds = TheoreticalBounds(
    extroverted_introverted=AxisBound(min=bound_val, max=bound_val),
    sensing_intuition=AxisBound(min=bound_val, max=bound_val),
    thinking_feeling=AxisBound(min=bound_val, max=bound_val),
    judging_perceiving=AxisBound(min=bound_val, max=bound_val),
  )
  normalizer = Normalizer(theoretical_bounds=bounds)

  raw_axis_scores = AxisScores(
    extroverted_introverted=raw,
    sensing_intuition=raw,
    thinking_feeling=raw,
    judging_perceiving=raw,
  )

  result = normalizer.normalize(raw_axis_scores)

  # 全軸が 0.5
  assert result.extroverted_introverted == 0.5
  assert result.sensing_intuition == 0.5
  assert result.thinking_feeling == 0.5
  assert result.judging_perceiving == 0.5
