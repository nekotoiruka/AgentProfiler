"""マッピング辞書モデル: スコアリングロジック定義"""

from pydantic import BaseModel, Field


class MappingScores(BaseModel):
  """1エントリあたりの4軸スコア値（-10〜+10）"""

  extroverted_introverted: int = Field(..., ge=-10, le=10)
  sensing_intuition: int = Field(..., ge=-10, le=10)
  thinking_feeling: int = Field(..., ge=-10, le=10)
  judging_perceiving: int = Field(..., ge=-10, le=10)


class NormalizedTag(BaseModel):
  """正規化タグ: 回答の意味を分類するタグ"""

  type: str = Field(..., pattern=r"^(value_tag|behavior_tag|prohibition_tag|condition_tag)$")
  value: str = Field(..., max_length=50)


class ModeConfig(BaseModel):
  """コンテキスト適応モードの設定"""

  tone: str = Field(..., max_length=50)
  detail: str = Field(..., pattern=r"^(minimal|standard|comprehensive)$")
  focus: str = Field(..., max_length=50)


class MappingEntry(BaseModel):
  """マッピング辞書の1エントリ

  question_id + choice_id の組み合わせに対する
  4軸スコアベクトルと、3層パイプライン用の
  policy_text / normalized_tags を定義する。

  新規カテゴリ（decision_model, tradeoff_scenarios,
  failure_patterns, context_adaptation, reasoning_flow）は
  各カテゴリ固有のフィールドを追加で持つ。
  """

  question_id: str
  choice_id: str
  scores: MappingScores

  # 3層パイプライン共通フィールド（v3.0 で全エントリに追加）
  policy_text: str | None = Field(default=None, max_length=200)
  normalized_tags: list[NormalizedTag] | None = None

  # decision_model 固有フィールド
  priority_labels: list[str] | None = None
  weights: dict[str, int] | None = None

  # tradeoff_scenarios 固有フィールド
  conflict_pair: str | None = None
  tendency_score: float | None = Field(default=None, ge=0.0, le=1.0)

  # failure_patterns 固有フィールド
  subcategory: str | None = None
  label: str | None = Field(default=None, max_length=100)

  # context_adaptation 固有フィールド
  mode_name: str | None = None
  mode_config: ModeConfig | None = None
  trigger: str | None = None

  # reasoning_flow 固有フィールド（single_select のみ）
  field: str | None = None
  value: str | None = None


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


class AxisPolarity(BaseModel):
  """軸の極性説明"""

  extroverted_introverted: str
  sensing_intuition: str
  thinking_feeling: str
  judging_perceiving: str


class MappingMetadata(BaseModel):
  """マッピング辞書のメタデータ"""

  version: str = "3.0"
  pipeline_scope: str | None = None
  decision_engine_categories: list[str] | None = None
  axis_polarity: AxisPolarity | None = None
  theoretical_bounds: TheoreticalBounds


class MappingDictionary(BaseModel):
  """マッピング辞書全体

  スコアリングロジックを外部ファイル（JSON/YAML）で管理し、
  コード変更なしでチューニング可能にする。
  v3.0: 全エントリに policy_text + normalized_tags を追加し、
  新規 decision engine カテゴリのエントリを含む。
  """

  metadata: MappingMetadata
  mappings: list[MappingEntry]
