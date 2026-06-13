"""RoutingEngine ユニットテスト

classify() のロジック検証と route() のモック統合テスト。
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.evolution.routing_engine import RoutingEngine, Complexity


class TestClassify:
  """classify() メソッドのテスト"""

  def setup_method(self):
    self.engine = RoutingEngine(token_threshold=5)

  def test_routing_hint_light(self):
    """routing_hint="light" が最優先で LIGHT を返す"""
    result = self.engine.classify(
      "this is a very long utterance with many tokens exceeding threshold",
      matched_tags=["python", "fastapi"],
      routing_hint="light",
    )
    assert result == Complexity.LIGHT

  def test_routing_hint_deep(self):
    """routing_hint="deep" が最優先で DEEP を返す"""
    result = self.engine.classify(
      "hi",
      matched_tags=None,
      routing_hint="deep",
    )
    assert result == Complexity.DEEP

  def test_routing_hint_case_insensitive(self):
    """routing_hint は大文字小文字を無視する"""
    assert self.engine.classify("hi", routing_hint="LIGHT") == Complexity.LIGHT
    assert self.engine.classify("hi", routing_hint="Deep") == Complexity.DEEP

  def test_routing_hint_invalid_falls_through(self):
    """無効な routing_hint はスキップして次の基準で判定する"""
    # matched_tags が空でトークン数も閾値未満 → LIGHT
    result = self.engine.classify("short", routing_hint="invalid")
    assert result == Complexity.LIGHT

  def test_matched_tags_non_empty_returns_deep(self):
    """matched_tags が非空なら DEEP"""
    result = self.engine.classify("hello", matched_tags=["python"])
    assert result == Complexity.DEEP

  def test_matched_tags_empty_list_uses_token_count(self):
    """matched_tags が空リストならトークン数で判定"""
    result = self.engine.classify("hi", matched_tags=[])
    assert result == Complexity.LIGHT

  def test_matched_tags_none_uses_token_count(self):
    """matched_tags が None ならトークン数で判定"""
    result = self.engine.classify("hi", matched_tags=None)
    assert result == Complexity.LIGHT

  def test_token_count_below_threshold_returns_light(self):
    """トークン数が閾値未満なら LIGHT"""
    # threshold=5, "one two three four" → 4 tokens
    result = self.engine.classify("one two three four")
    assert result == Complexity.LIGHT

  def test_token_count_at_threshold_returns_deep(self):
    """トークン数が閾値と等しい場合は DEEP"""
    # threshold=5, 5 tokens
    result = self.engine.classify("one two three four five")
    assert result == Complexity.DEEP

  def test_token_count_above_threshold_returns_deep(self):
    """トークン数が閾値を超える場合は DEEP"""
    result = self.engine.classify("one two three four five six")
    assert result == Complexity.DEEP

  def test_empty_utterance_returns_light(self):
    """空文字列は LIGHT (トークン数 0)"""
    result = self.engine.classify("")
    assert result == Complexity.LIGHT

  def test_priority_hint_over_tags(self):
    """routing_hint は matched_tags より優先"""
    result = self.engine.classify(
      "complex query",
      matched_tags=["python", "asyncio"],
      routing_hint="light",
    )
    assert result == Complexity.LIGHT

  def test_priority_tags_over_token_count(self):
    """matched_tags はトークン数より優先（DEEP に分類）"""
    # threshold=5, "hi" → 1 token (normally LIGHT)
    # しかし matched_tags があるので DEEP
    result = self.engine.classify("hi", matched_tags=["python"])
    assert result == Complexity.DEEP


class TestRoute:
  """route() メソッドのテスト"""

  def setup_method(self):
    self.engine = RoutingEngine(
      token_threshold=5,
      slm_base_url="http://localhost:11434",
      slm_model="llama3.2",
      cloud_base_url="https://api.openai.com/v1",
      cloud_model="gpt-4.1-mini",
      cloud_api_key="test-key",
    )

  @pytest.mark.asyncio
  async def test_light_routes_to_slm(self):
    """LIGHT 分類時は SLM にルーティングされる"""
    with patch.object(
      self.engine, "_call_slm", new_callable=AsyncMock
    ) as mock_slm:
      mock_slm.return_value = "SLM response"
      result = await self.engine.route("hi", "system prompt")
      assert result == "SLM response"
      mock_slm.assert_called_once_with("hi", "system prompt")

  @pytest.mark.asyncio
  async def test_deep_routes_to_cloud(self):
    """DEEP 分類時は Cloud LLM にルーティングされる"""
    with patch.object(
      self.engine, "_call_cloud", new_callable=AsyncMock
    ) as mock_cloud:
      mock_cloud.return_value = "Cloud response"
      result = await self.engine.route(
        "hi", "system prompt", routing_hint="deep"
      )
      assert result == "Cloud response"
      mock_cloud.assert_called_once_with("hi", "system prompt")

  @pytest.mark.asyncio
  async def test_slm_fallback_to_cloud(self):
    """SLM 不通時は Cloud LLM にフォールバックする"""
    with (
      patch.object(
        self.engine, "_call_slm", new_callable=AsyncMock
      ) as mock_slm,
      patch.object(
        self.engine, "_call_cloud", new_callable=AsyncMock
      ) as mock_cloud,
    ):
      mock_slm.return_value = None  # SLM unavailable
      mock_cloud.return_value = "Cloud fallback response"
      result = await self.engine.route("hi", "system prompt")
      assert result == "Cloud fallback response"
      mock_slm.assert_called_once()
      mock_cloud.assert_called_once()

  @pytest.mark.asyncio
  async def test_cloud_unavailable_raises_runtime_error(self):
    """Cloud LLM 不通時は RuntimeError が送出される"""
    with patch.object(
      self.engine, "_call_cloud", new_callable=AsyncMock
    ) as mock_cloud:
      mock_cloud.side_effect = RuntimeError("No LLM backend available")
      with pytest.raises(RuntimeError, match="No LLM backend available"):
        await self.engine.route("hi", "system prompt", routing_hint="deep")

  @pytest.mark.asyncio
  async def test_slm_and_cloud_both_unavailable(self):
    """SLM も Cloud も不通時は RuntimeError が送出される"""
    with (
      patch.object(
        self.engine, "_call_slm", new_callable=AsyncMock
      ) as mock_slm,
      patch.object(
        self.engine, "_call_cloud", new_callable=AsyncMock
      ) as mock_cloud,
    ):
      mock_slm.return_value = None
      mock_cloud.side_effect = RuntimeError("No LLM backend available")
      with pytest.raises(RuntimeError):
        await self.engine.route("hi", "system prompt")


class TestCallSlm:
  """_call_slm() メソッドのテスト"""

  def setup_method(self):
    self.engine = RoutingEngine(
      slm_base_url="http://localhost:11434",
      slm_model="llama3.2",
    )

  @pytest.mark.asyncio
  async def test_successful_slm_call(self):
    """正常な ollama レスポンスをパースする"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
      "message": {"role": "assistant", "content": "Hello!"}
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
      mock_client = AsyncMock()
      mock_client.post.return_value = mock_response
      mock_client.__aenter__ = AsyncMock(return_value=mock_client)
      mock_client.__aexit__ = AsyncMock(return_value=False)
      mock_client_cls.return_value = mock_client

      result = await self.engine._call_slm("hello", "be helpful")
      assert result == "Hello!"

  @pytest.mark.asyncio
  async def test_slm_connection_error_returns_none(self):
    """SLM 接続エラー時は None を返す"""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_cls:
      mock_client = AsyncMock()
      mock_client.post.side_effect = httpx.ConnectError("Connection refused")
      mock_client.__aenter__ = AsyncMock(return_value=mock_client)
      mock_client.__aexit__ = AsyncMock(return_value=False)
      mock_client_cls.return_value = mock_client

      result = await self.engine._call_slm("hello", "be helpful")
      assert result is None


class TestCallCloud:
  """_call_cloud() メソッドのテスト"""

  def setup_method(self):
    self.engine = RoutingEngine(
      cloud_base_url="https://api.openai.com/v1",
      cloud_model="gpt-4.1-mini",
      cloud_api_key="test-key",
    )

  @pytest.mark.asyncio
  async def test_successful_cloud_call(self):
    """正常な OpenAI レスポンスをパースする"""
    mock_choice = MagicMock()
    mock_choice.message.content = "Cloud response"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("app.evolution.routing_engine.AsyncOpenAI") as mock_openai_cls:
      mock_client = AsyncMock()
      mock_client.chat.completions.create.return_value = mock_response
      mock_openai_cls.return_value = mock_client

      result = await self.engine._call_cloud("hello", "be helpful")
      assert result == "Cloud response"

  @pytest.mark.asyncio
  async def test_cloud_error_raises_runtime_error(self):
    """Cloud LLM エラー時は RuntimeError が送出される"""
    with patch("app.evolution.routing_engine.AsyncOpenAI") as mock_openai_cls:
      mock_client = AsyncMock()
      mock_client.chat.completions.create.side_effect = Exception("API Error")
      mock_openai_cls.return_value = mock_client

      with pytest.raises(RuntimeError, match="No LLM backend available"):
        await self.engine._call_cloud("hello", "be helpful")
