"""Decision Engine Pydantic データモデル"""

from enum import Enum

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
  """フィードバック種別"""

  APPROVE = "approve"
  REJECT = "reject"


class Permanence(str, Enum):
  """回答の恒常性"""

  PERMANENT = "permanent"
  CONTEXTUAL = "contextual"


class NormalizationTagType(str, Enum):
  """正規化タグ種別"""

  VALUE_TAG = "value_tag"
  BEHAVIOR_TAG = "behavior_tag"
  PROHIBITION_TAG = "prohibition_tag"
  CONDITION_TAG = "condition_tag"


class NormalizationTag(BaseModel):
  """正規化タグ: 自由記述テキストの分類結果"""

  type: NormalizationTagType
  value: str = Field(..., max_length=50)


class AnswerMetadata(BaseModel):
  """回答メタデータ: 恒常性・確信度・例外条件等"""

  permanence: Permanence = Permanence.PERMANENT
  confidence: float = Field(default=0.6, ge=0.2, le=1.0)
  exception_note: str | None = Field(default=None, max_length=200)
  is_core_rule: bool = False
  ambiguity: float = Field(default=0.0, ge=0.0, le=1.0)


class ThreeLayerAnswerModel(BaseModel):
  """3層構造化回答モデル: Raw → Normalized → Policy"""

  raw: dict
  normalized: dict | None = None
  policy: str | None = None


class FeedbackSubmission(BaseModel):
  """フィードバック送信リクエスト"""

  agent_id: str = Field(..., pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
  thread_id: str = Field(..., pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
  turn_id: str = Field(..., pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
  feedback_type: FeedbackType
  user_correction: str | None = Field(default=None, min_length=1, max_length=2000)


class FeedbackResponse(BaseModel):
  """フィードバック記録レスポンス"""

  feedback_id: int
  created_at: str


class FeedbackListResponse(BaseModel):
  """フィードバック一覧レスポンス"""

  items: list[dict]
  total: int
  limit: int
  offset: int


class ModificationHistoryEntry(BaseModel):
  """重み調整履歴エントリ"""

  field_name: str
  previous_value: float
  new_value: float
  adjustment_reason: str = Field(..., max_length=200)
  feedback_count: int
  timestamp: str


class DecisionModelOutput(BaseModel):
  """意思決定モデル出力: 優先順位・重み・ルール・トレードオフ"""

  priorities: list[str] = Field(..., min_length=1, max_length=10)
  priority_weights: dict[str, float]
  escalation_rules: list[str] = Field(default_factory=list, max_length=10)
  auto_approve_scope: list[str] = Field(default_factory=list, max_length=10)
  tradeoff_tendencies: dict[str, float]
  pending_other_answers: list[str] = Field(default_factory=list)


class FailurePatternsOutput(BaseModel):
  """失敗パターン出力: 4サブカテゴリ"""

  degradation_triggers: list[str] = Field(default_factory=list, max_length=10)
  procrastination_patterns: list[str] = Field(default_factory=list, max_length=10)
  overconfidence_conditions: list[str] = Field(default_factory=list, max_length=10)
  recurring_mistakes: list[str] = Field(default_factory=list, max_length=10)


class ContextAdaptationOutput(BaseModel):
  """コンテキスト適応出力: モード定義とスイッチトリガー"""

  modes: dict[str, dict[str, str]]
  switch_triggers: dict[str, list[str]]


class ReasoningFlowOutput(BaseModel):
  """推論フロー出力: デフォルトステップ・検証方法・学習スタイル"""

  default_steps: list[str] = Field(..., min_length=4, max_length=6)
  verification_method: str = Field(..., max_length=100)
  learning_style: str = Field(..., max_length=100)


class RuleHierarchyOutput(BaseModel):
  """ルール優先順位体系出力: 4層ヒエラルキー"""

  core_invariants: list[dict]
  context_rules: list[dict]
  exceptions: list[dict]
  preferences: list[dict]


class AnswerMetadataSummary(BaseModel):
  """回答メタデータ統計サマリ"""

  total_answers: int
  core_rule_count: int
  contextual_count: int
  average_confidence: float
  high_ambiguity_count: int
