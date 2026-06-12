"""マッピング辞書モデル: スコアリングロジック定義"""

from pydantic import BaseModel, Field


class MappingScores(BaseModel):
  """1エントリあたりの4軸スコア値（-10〜+10）"""

  extroverted_introverted: int = Field(..., ge=-10, le=10)
  sensing_intuition: int = Field(..., ge=-10, le=10)
  thinking_feeling: int = Field(..., ge=-10, le=10)
  judging_perceiving: int = Field(..., ge=-10, le=10)


class MappingEntry(BaseModel):
  """マッピング辞書の1エントリ

  question_id + choice_id の組み合わせに対する
  4軸スコアベクトルを定義する。
  """

  question_id: str
  choice_id: str
  scores: MappingScores


class AxisBound(BaseModel):
  """1軸の理論的スコア範囲"""

  min: int
  max: int


class TheoreticalBounds(BaseModel):
  """全軸の理論的最小/最大値

  正規化計算に使用: (raw - min) / (max - min)
  """

  extroverted_introverted: AxisBound
  sensing_intuition: AxisBound
  thinking_feeling: AxisBound
  judging_perceiving: AxisBound


class MappingMetadata(BaseModel):
  """マッピング辞書のメタデータ"""

  version: str = "1.0"
  theoretical_bounds: TheoreticalBounds


class MappingDictionary(BaseModel):
  """マッピング辞書全体

  スコアリングロジックを外部ファイル（JSON/YAML）で管理し、
  コード変更なしでチューニング可能にする。
  """

  metadata: MappingMetadata
  mappings: list[MappingEntry]
