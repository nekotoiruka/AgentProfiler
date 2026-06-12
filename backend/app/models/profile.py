"""プロファイル出力モデル: 3層コンテキストレイヤー対応構造"""

from pydantic import BaseModel, Field

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
  lexical_tags: int = 2
  semantic_contexts: int = 3


class ProfileOutput(BaseModel):
  """最終プロファイルJSON出力

  profile_id フォーマット: "prof_" + 6桁ゼロパディング番号
  """

  profile_id: str = Field(..., pattern=r"^prof_\d{6}$")
  base_os: BaseOS
  lexical_tags: list[str] = Field(..., min_length=5, max_length=50)
  semantic_contexts: dict[str, str]
  context_layers: ContextLayers = Field(default_factory=ContextLayers)
