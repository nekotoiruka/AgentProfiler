"""Property 9: 重み調整のクランプ不変条件

w ∈ [0.0, 1.0], step = 0.1 で調整後の値が [0.0, 1.0] 範囲内を検証する。

**Validates: Requirements 11.5**
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.feedback_service import FeedbackService


@given(
  current=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
  direction=st.sampled_from(["increase", "decrease"]),
  step=st.floats(min_value=0.01, max_value=0.5, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=500)
def test_weight_always_in_range(current, direction, step):
  """調整後の重みは常に [0.0, 1.0] 範囲内"""
  service = FeedbackService(db_path=":memory:", threshold=10, step=0.1)
  result = service._adjust_weight(current, direction, step)

  assert 0.0 <= result <= 1.0, f"Weight {result} out of range after {direction} from {current} by {step}"


@given(
  current=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
  step=st.floats(min_value=0.01, max_value=0.5, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_increase_never_exceeds_one(current, step):
  """increase は 1.0 を超えない"""
  service = FeedbackService(db_path=":memory:", threshold=10, step=0.1)
  result = service._adjust_weight(current, "increase", step)
  assert result <= 1.0


@given(
  current=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
  step=st.floats(min_value=0.01, max_value=0.5, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_decrease_never_below_zero(current, step):
  """decrease は 0.0 を下回らない"""
  service = FeedbackService(db_path=":memory:", threshold=10, step=0.1)
  result = service._adjust_weight(current, "decrease", step)
  assert result >= 0.0
