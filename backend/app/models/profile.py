"""プロファイル出力モデル: 3層コンテキストレイヤー対応構造"""

from pydantic import BaseModel, Field

from app.decision_engine.models import (
  AnswerMetadataSummary,
  ContextAdaptationOutput,
  DecisionModelOutput,
  FailurePatternsOutput,
  ModificationHistoryEntry,
  ReasoningFlowOutput,
  RuleHierarchyOutput,
)
from app.models.scores import NormalizedScores


class BaseOS(BaseModel):
  """Layer 1: エージェント基本OS（常駐レイヤー）

  axes: 正規化された4軸スコア
  decision_style: 支配的ポールの組み合わせラベル
  do_not_list: エージェントが避けるべき行動（強い偏りがある軸から導出）
  """

  axes: NormalizedScores
  decision_style: str
  do_not_list: list[str] = Field(..., min_length=1, max_length=4)


class ContextLayers(BaseModel):
  """プロファイルセクションとレイヤー番号のマッピング

  Layer 1: Base OS（常時ロード）
  Layer 2: Agent Skills（タスク固有、オンデマンド）
  Layer 3: MCP（ハイブリッド検索による動的フェッチ）
  """

  base_os: int = 1
  decision_model: int = 1
  failure_patterns: int = 1
  context_adaptation: int = 2
  reasoning_flow: int = 2
  lexical_tags: int = 2
  semantic_contexts: int = 3


class Persona(BaseModel):
  """ユーザーの基本属性"""

  nickname: str = ""
  age_range: str = ""
  role: str = ""
  industry: str = ""
  experience_years: str = ""


class CommunicationTone(BaseModel):
  """コミュニケーションスタイル・口調設定"""

  pronoun: str = ""
  formality: str = ""
  text_style: str = ""
  emotion_level: str = ""
  humor: str = ""
  response_length: str = ""
  sentence_ending: str = ""
  filler_words: str = ""


class Values(BaseModel):
  """価値観・信念"""

  work_belief: str = ""
  team_stance: str = ""
  conflict_approach: str = ""
  failure_attitude: str = ""
  change_attitude: str = ""


class ProfileOutput(BaseModel):
  """最終プロファイルJSON出力

  profile_id フォーマット: "prof_" + 6桁ゼロパディング番号
  """

  profile_id: str = Field(..., pattern=r"^prof_\d{6}$")
  persona: Persona = Field(default_factory=Persona)
  communication_tone: CommunicationTone = Field(default_factory=CommunicationTone)
  base_os: BaseOS
  lexical_tags: list[str] = Field(..., min_length=5, max_length=500)
  semantic_contexts: dict[str, str]
  context_layers: ContextLayers = Field(default_factory=ContextLayers)
  # Decision Engine フィールド
  decision_model: DecisionModelOutput | None = None
  failure_patterns: FailurePatternsOutput | None = None
  context_adaptation: ContextAdaptationOutput | None = None
  reasoning_flow: ReasoningFlowOutput | None = None
  decision_rules: list[dict] | None = None
  rule_hierarchy: RuleHierarchyOutput | None = None
  modification_history: list[ModificationHistoryEntry] | None = None
  answer_metadata_summary: AnswerMetadataSummary | None = None
