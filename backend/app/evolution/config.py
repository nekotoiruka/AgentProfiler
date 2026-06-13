"""Evolution システム設定管理

環境変数 or .env ファイルから読み込む。
EVOLUTION_ プレフィクスで名前空間を分離。
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class EvolutionSettings(BaseSettings):
  """Evolution システム全コンポーネントの一元設定

  環境変数プレフィクス: EVOLUTION_
  例: EVOLUTION_EMBEDDING_MODEL, EVOLUTION_CLOUD_LLM_API_KEY
  """

  # Embedding
  embedding_model: str = "text-embedding-ada-002"

  # Semantic Search
  semantic_search_top_k: int = Field(default=3, ge=1, le=50)
  semantic_search_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

  # Semantic Cache
  semantic_cache_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
  cache_eviction_days: int = Field(default=7, ge=1)

  # Routing
  routing_token_threshold: int = Field(default=50, ge=1)
  hybrid_search_weight: float = Field(default=0.5, ge=0.0, le=1.0)

  # Cloud LLM
  cloud_llm_base_url: str = "https://api.openai.com/v1"
  cloud_llm_model: str = "gpt-4.1-mini"
  cloud_llm_api_key: str  # 必須 — 未設定時にスタートアップエラー

  # SLM (ollama)
  slm_base_url: str = "http://localhost:11434"
  slm_model: str = "llama3.2"

  # MCP
  mcp_transport: str = Field(default="stdio", pattern=r"^(stdio|sse)$")
  mcp_sse_port: int = Field(default=8081, ge=1, le=65535)
  mcp_sse_host: str = "localhost"

  # Prompt
  max_prompt_tokens: int = Field(default=4000, ge=100)

  model_config = {"env_prefix": "EVOLUTION_", "env_file": ".env", "extra": "ignore"}
