"""Normalizer: min-max正規化によるスコア変換"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from app.models import AxisScores, NormalizedScores, TheoreticalBounds

logger = logging.getLogger(__name__)

# round-half-upで小数点2桁に丸めるための量子化指定
_QUANTIZE_TWO_PLACES = Decimal("0.01")


class Normalizer:
  """理論的最小/最大値を用いたmin-max正規化

  正規化公式: (raw - min) / (max - min)
  - クランプ: 結果が0未満→0.0、1超→1.0
  - 丸め: round-half-up で小数点2桁
  - min == max: 0.5 を返し warning ログ出力
  """

  def __init__(self, theoretical_bounds: TheoreticalBounds) -> None:
    self._bounds = theoretical_bounds

  def normalize(self, raw_scores: AxisScores) -> NormalizedScores:
    """全4軸を正規化して NormalizedScores を返す"""
    return NormalizedScores(
      extroverted_introverted=self._normalize_axis(
        raw_scores.extroverted_introverted,
        self._bounds.extroverted_introverted.min,
        self._bounds.extroverted_introverted.max,
        "extroverted_introverted",
      ),
      sensing_intuition=self._normalize_axis(
        raw_scores.sensing_intuition,
        self._bounds.sensing_intuition.min,
        self._bounds.sensing_intuition.max,
        "sensing_intuition",
      ),
      thinking_feeling=self._normalize_axis(
        raw_scores.thinking_feeling,
        self._bounds.thinking_feeling.min,
        self._bounds.thinking_feeling.max,
        "thinking_feeling",
      ),
      judging_perceiving=self._normalize_axis(
        raw_scores.judging_perceiving,
        self._bounds.judging_perceiving.min,
        self._bounds.judging_perceiving.max,
        "judging_perceiving",
      ),
    )

  def _normalize_axis(
    self, raw: int, bound_min: int, bound_max: int, axis_name: str
  ) -> float:
    """1軸の正規化処理

    min == max の場合は計算不能のため 0.5 を返す（warning出力）。
    それ以外は min-max 正規化 → クランプ → round-half-up 2桁。
    """
    if bound_min == bound_max:
      logger.warning(
        "Axis '%s' has min == max (%d). Returning 0.5 as fallback.",
        axis_name,
        bound_min,
      )
      return 0.5

    # min-max正規化
    normalized = (raw - bound_min) / (bound_max - bound_min)

    # クランプ: 範囲外は 0.0 / 1.0 に制限
    normalized = max(0.0, min(1.0, normalized))

    # round-half-up で小数点2桁に丸める
    result = Decimal(str(normalized)).quantize(
      _QUANTIZE_TWO_PLACES, rounding=ROUND_HALF_UP
    )

    return float(result)
