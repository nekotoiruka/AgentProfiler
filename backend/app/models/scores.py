"""スコアモデル: 4軸スコアおよび正規化スコア"""

from pydantic import BaseModel, Field


class AxisScores(BaseModel):
  """4軸の累積スコア（整数値）

  各軸は質問回答ごとに-10〜+10の範囲で加算され、
  セッション全体での合計値を保持する。
  """

  extroverted_introverted: int = 0
  sensing_intuition: int = 0
  thinking_feeling: int = 0
  judging_perceiving: int = 0


class NormalizedScores(BaseModel):
  """正規化後の4軸スコア（0.00〜1.00）

  理論的最小/最大値を用いたmin-max正規化後の値。
  round-half-up で小数点2桁に丸める。
  """

  extroverted_introverted: float = Field(..., ge=0.0, le=1.0)
  sensing_intuition: float = Field(..., ge=0.0, le=1.0)
  thinking_feeling: float = Field(..., ge=0.0, le=1.0)
  judging_perceiving: float = Field(..., ge=0.0, le=1.0)
