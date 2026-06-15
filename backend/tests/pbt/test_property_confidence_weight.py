"""Property 13: 確信度による重み乗算の正確性

base_weight (1〜10) × confidence (0.2〜1.0) = 実効重み増分

**Validates: Requirements 17.4**
"""

from hypothesis import given, settings
from hypothesis import strategies as st


def apply_confidence(base_weight: int, confidence: float) -> float:
  """確信度を適用した実効重みを算出する

  この関数は DecisionScorer に将来統合される予定のロジックを
  独立して検証する。
  """
  return round(base_weight * confidence, 2)


@given(
  base_weight=st.integers(min_value=1, max_value=10),
  confidence=st.floats(min_value=0.2, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=500)
def test_confidence_weight_multiplication(base_weight: int, confidence: float) -> None:
  """base_weight × confidence の実効重み増分が正しい範囲にあること

  **Validates: Requirements 17.4**
  """
  result = apply_confidence(base_weight, confidence)

  # 結果は [0.2, 10.0] の範囲内
  assert 0.2 <= result <= 10.0, f"Effective weight {result} out of range [0.2, 10.0]"

  # base_weight × confidence と一致（浮動小数点丸め考慮）
  expected = round(base_weight * confidence, 2)
  assert result == expected, f"Expected {expected}, got {result}"


@given(
  base_weight=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_max_confidence_preserves_weight(base_weight: int) -> None:
  """confidence=1.0 の場合、base_weight がそのまま返る"""
  result = apply_confidence(base_weight, 1.0)
  assert result == float(base_weight)


@given(
  base_weight=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_min_confidence_reduces_weight(base_weight: int) -> None:
  """confidence=0.2 の場合、base_weight × 0.2 になる"""
  result = apply_confidence(base_weight, 0.2)
  expected = round(base_weight * 0.2, 2)
  assert result == expected
