"""Decision Engine システム設定"""

from pydantic import Field
from pydantic_settings import BaseSettings


class DecisionEngineSettings(BaseSettings):
  """Decision Engine システム設定

  環境変数 DECISION_ プレフィクスで名前空間を分離。
  """

  # フィードバック
  feedback_threshold: int = Field(default=10, ge=1)
  weight_adjustment_step: float = Field(default=0.1, ge=0.01, le=0.5)
  max_core_invariants: int = Field(default=10, ge=1, le=50)

  # LLM 正規化
  normalization_model: str = "gpt-4.1-mini"
  normalization_max_tokens: int = Field(default=500, ge=100)

  # プロンプト制限
  max_prompt_tokens: int = Field(default=4000, ge=100)

  # 確信度マッピング (1-5 スケール → 0.0-1.0)
  confidence_mapping: dict[int, float] = {
    1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8, 5: 1.0,
  }

  model_config = {"env_prefix": "DECISION_", "env_file": ".env", "extra": "ignore"}
