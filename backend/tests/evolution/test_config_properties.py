"""設定バリデーション プロパティベーステスト

Feature: agent-evolution
Property 16: Configuration defaults
Validates: Requirements 13.2
"""

import os
from unittest.mock import patch

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from pydantic import ValidationError

from app.evolution.config import EvolutionSettings


# --- Hypothesis ストラテジー ---

# 有効な semantic_search_top_k (1〜50)
_valid_top_k_st = st.integers(min_value=1, max_value=50)

# 有効な semantic_search_threshold (0.0〜1.0)
_valid_threshold_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# 有効な semantic_cache_threshold (0.0〜1.0)
_valid_cache_threshold_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# 有効な cache_eviction_days (1〜)
_valid_eviction_days_st = st.integers(min_value=1, max_value=365)

# 有効な routing_token_threshold (1〜)
_valid_routing_threshold_st = st.integers(min_value=1, max_value=10000)

# 有効な hybrid_search_weight (0.0〜1.0)
_valid_weight_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# 有効な mcp_sse_port (1〜65535)
_valid_port_st = st.integers(min_value=1, max_value=65535)

# 有効な max_prompt_tokens (100〜)
_valid_max_tokens_st = st.integers(min_value=100, max_value=100000)

# 有効な mcp_transport ("stdio" or "sse")
_valid_transport_st = st.sampled_from(["stdio", "sse"])

# 有効な API キー（非空文字列）
_valid_api_key_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=100,
)

# 範囲外の top_k
_invalid_top_k_st = st.one_of(
  st.integers(min_value=-100, max_value=0),
  st.integers(min_value=51, max_value=1000),
)

# 無効な mcp_transport
_invalid_transport_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=20,
).filter(lambda s: s not in ("stdio", "sse"))


# --- ヘルパー ---

def _build_env(overrides: dict[str, str] | None = None) -> dict[str, str]:
  """テスト用の最小限の環境変数辞書を構築する。

  EVOLUTION_ プレフィクスの変数のみを含み、
  .env ファイルの影響を完全に排除する。
  """
  # 既存の EVOLUTION_ 系をすべて除去した環境を基盤にする
  base = {k: v for k, v in os.environ.items() if not k.startswith("EVOLUTION_")}
  if overrides:
    base.update(overrides)
  return base


# =============================================================================
# Property 16: Configuration defaults
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
  api_key=_valid_api_key_st,
  top_k=_valid_top_k_st,
  threshold=_valid_threshold_st,
  cache_threshold=_valid_cache_threshold_st,
  eviction_days=_valid_eviction_days_st,
  routing_threshold=_valid_routing_threshold_st,
  weight=_valid_weight_st,
  port=_valid_port_st,
  max_tokens=_valid_max_tokens_st,
  transport=_valid_transport_st,
)
def test_valid_config_produces_valid_instance(
  api_key: str,
  top_k: int,
  threshold: float,
  cache_threshold: float,
  eviction_days: int,
  routing_threshold: int,
  weight: float,
  port: int,
  max_tokens: int,
  transport: str,
) -> None:
  """任意の有効な設定値の組み合わせで EvolutionSettings インスタンスが
  正常に生成される。

  **Validates: Requirements 13.2**
  """
  env = _build_env({
    "EVOLUTION_CLOUD_LLM_API_KEY": api_key,
    "EVOLUTION_SEMANTIC_SEARCH_TOP_K": str(top_k),
    "EVOLUTION_SEMANTIC_SEARCH_THRESHOLD": str(threshold),
    "EVOLUTION_SEMANTIC_CACHE_THRESHOLD": str(cache_threshold),
    "EVOLUTION_CACHE_EVICTION_DAYS": str(eviction_days),
    "EVOLUTION_ROUTING_TOKEN_THRESHOLD": str(routing_threshold),
    "EVOLUTION_HYBRID_SEARCH_WEIGHT": str(weight),
    "EVOLUTION_MCP_SSE_PORT": str(port),
    "EVOLUTION_MAX_PROMPT_TOKENS": str(max_tokens),
    "EVOLUTION_MCP_TRANSPORT": transport,
  })

  with patch.dict(os.environ, env, clear=True):
    settings_instance = EvolutionSettings(_env_file=None)

  # 各フィールドが正しく設定される
  assert settings_instance.cloud_llm_api_key == api_key
  assert settings_instance.semantic_search_top_k == top_k
  assert settings_instance.semantic_search_threshold == threshold
  assert settings_instance.semantic_cache_threshold == cache_threshold
  assert settings_instance.cache_eviction_days == eviction_days
  assert settings_instance.routing_token_threshold == routing_threshold
  assert settings_instance.hybrid_search_weight == weight
  assert settings_instance.mcp_sse_port == port
  assert settings_instance.max_prompt_tokens == max_tokens
  assert settings_instance.mcp_transport == transport


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(api_key=_valid_api_key_st)
def test_defaults_correctly_applied(api_key: str) -> None:
  """cloud_llm_api_key のみ設定した場合、他のフィールドにデフォルト値が
  正しく適用される。

  **Validates: Requirements 13.2**
  """
  env = _build_env({"EVOLUTION_CLOUD_LLM_API_KEY": api_key})

  with patch.dict(os.environ, env, clear=True):
    settings_instance = EvolutionSettings(_env_file=None)

  # デフォルト値の検証
  assert settings_instance.embedding_model == "text-embedding-ada-002"
  assert settings_instance.semantic_search_top_k == 3
  assert settings_instance.semantic_search_threshold == 0.7
  assert settings_instance.semantic_cache_threshold == 0.92
  assert settings_instance.cache_eviction_days == 7
  assert settings_instance.routing_token_threshold == 50
  assert settings_instance.hybrid_search_weight == 0.5
  assert settings_instance.cloud_llm_base_url == "https://api.openai.com/v1"
  assert settings_instance.cloud_llm_model == "gpt-4.1-mini"
  assert settings_instance.slm_base_url == "http://localhost:11434"
  assert settings_instance.slm_model == "llama3.2"
  assert settings_instance.mcp_transport == "stdio"
  assert settings_instance.mcp_sse_port == 8081
  assert settings_instance.mcp_sse_host == "localhost"
  assert settings_instance.max_prompt_tokens == 4000


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=st.data())
def test_missing_api_key_raises_validation_error(data) -> None:
  """cloud_llm_api_key が未設定の場合 ValidationError が発生する。

  **Validates: Requirements 13.2**
  """
  # API キーを含まない環境
  env = _build_env()

  with patch.dict(os.environ, env, clear=True):
    try:
      EvolutionSettings(_env_file=None)
      assert False, "cloud_llm_api_key 未設定で ValidationError が発生すべき"
    except ValidationError as e:
      # cloud_llm_api_key に関するエラーであることを確認
      error_fields = [err["loc"][-1] for err in e.errors()]
      assert "cloud_llm_api_key" in error_fields


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
  api_key=_valid_api_key_st,
  invalid_top_k=_invalid_top_k_st,
)
def test_out_of_range_top_k_raises_validation_error(
  api_key: str,
  invalid_top_k: int,
) -> None:
  """semantic_search_top_k が範囲外 (< 1 or > 50) の場合 ValidationError が発生する。

  **Validates: Requirements 13.2**
  """
  env = _build_env({
    "EVOLUTION_CLOUD_LLM_API_KEY": api_key,
    "EVOLUTION_SEMANTIC_SEARCH_TOP_K": str(invalid_top_k),
  })

  with patch.dict(os.environ, env, clear=True):
    try:
      EvolutionSettings(_env_file=None)
      assert False, f"top_k={invalid_top_k} で ValidationError が発生すべき"
    except ValidationError as e:
      error_fields = [err["loc"][-1] for err in e.errors()]
      assert "semantic_search_top_k" in error_fields


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
  api_key=_valid_api_key_st,
  invalid_transport=_invalid_transport_st,
)
def test_invalid_mcp_transport_raises_validation_error(
  api_key: str,
  invalid_transport: str,
) -> None:
  """mcp_transport が "stdio" / "sse" 以外の場合 ValidationError が発生する。

  **Validates: Requirements 13.2**
  """
  env = _build_env({
    "EVOLUTION_CLOUD_LLM_API_KEY": api_key,
    "EVOLUTION_MCP_TRANSPORT": invalid_transport,
  })

  with patch.dict(os.environ, env, clear=True):
    try:
      EvolutionSettings(_env_file=None)
      assert False, f"transport='{invalid_transport}' で ValidationError が発生すべき"
    except ValidationError as e:
      error_fields = [err["loc"][-1] for err in e.errors()]
      assert "mcp_transport" in error_fields
