"""ハイブリッド・ルーティングエンジン

発話の複雑度に基づき、ローカル SLM (ollama) とクラウド LLM (OpenAI) を
適応的に振り分けるルーティングコンポーネント。
"""

import logging
from enum import Enum

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class Complexity(str, Enum):
  """発話の複雑度分類"""

  LIGHT = "light"
  DEEP = "deep"


class RoutingEngine:
  """発話複雑度に基づく LLM ルーティング

  分類基準 (優先度順):
  1. routing_hint が指定されている → hint に従う ("light" / "deep")
  2. matched_tags が非空 → DEEP (ドメイン固有語が含まれるため)
  3. トークン数が閾値以上 → DEEP
  4. 上記いずれにも該当しない → LIGHT

  ルーティング先:
  - LIGHT → SLM (ollama-compatible API: POST /api/chat)
  - DEEP → Cloud LLM (OpenAI-compatible AsyncOpenAI)
  - SLM 不通時 → Cloud LLM にフォールバック
  - Cloud LLM 不通時 → RuntimeError 送出
  """

  def __init__(
    self,
    token_threshold: int = 50,
    lexical_retriever=None,
    slm_base_url: str = "http://localhost:11434",
    slm_model: str = "llama3.2",
    cloud_base_url: str = "https://api.openai.com/v1",
    cloud_model: str = "gpt-4.1-mini",
    cloud_api_key: str = "",
  ) -> None:
    self._token_threshold = token_threshold
    self._lexical_retriever = lexical_retriever
    self._slm_base_url = slm_base_url.rstrip("/")
    self._slm_model = slm_model
    self._cloud_base_url = cloud_base_url
    self._cloud_model = cloud_model
    self._cloud_api_key = cloud_api_key

  def classify(
    self,
    utterance: str,
    matched_tags: list[str] | None = None,
    routing_hint: str | None = None,
  ) -> Complexity:
    """発話の複雑度を分類する

    優先度:
    1. routing_hint (有効値: "light", "deep") → 直接採用
    2. matched_tags が非空 → DEEP
    3. token_count >= threshold → DEEP
    4. それ以外 → LIGHT

    Args:
      utterance: ユーザー発話テキスト
      matched_tags: Lexical_Retriever によるマッチ済みタグ
      routing_hint: 明示的なルーティング指示 ("light" / "deep")

    Returns:
      Complexity.LIGHT or Complexity.DEEP
    """
    # 1. routing_hint が有効なら直接採用
    if routing_hint is not None:
      hint_lower = routing_hint.lower()
      if hint_lower == "light":
        return Complexity.LIGHT
      if hint_lower == "deep":
        return Complexity.DEEP

    # 2. matched_tags が非空ならドメイン固有 → DEEP
    if matched_tags and len(matched_tags) > 0:
      return Complexity.DEEP

    # 3. トークン数で判定 (空白分割)
    token_count = len(utterance.split())
    if token_count >= self._token_threshold:
      return Complexity.DEEP

    # 4. デフォルト: LIGHT
    return Complexity.LIGHT

  async def route(
    self,
    utterance: str,
    system_prompt: str,
    matched_tags: list[str] | None = None,
    routing_hint: str | None = None,
  ) -> str:
    """分類結果に応じて適切な LLM にリクエストし、レスポンスを返す

    LIGHT → SLM (ollama POST /api/chat)
    DEEP → Cloud LLM (AsyncOpenAI)
    SLM 不通時 → Cloud LLM フォールバック
    Cloud LLM 不通時 → RuntimeError 送出

    Args:
      utterance: ユーザー発話テキスト
      system_prompt: システムプロンプト
      matched_tags: Lexical_Retriever によるマッチ済みタグ
      routing_hint: 明示的なルーティング指示

    Returns:
      LLM からのレスポンステキスト

    Raises:
      RuntimeError: 全 LLM バックエンドが利用不可の場合
    """
    complexity = self.classify(utterance, matched_tags, routing_hint)
    logger.debug("Utterance classified as %s", complexity.value)

    if complexity == Complexity.LIGHT:
      # SLM を試行し、失敗時は Cloud にフォールバック
      response = await self._call_slm(utterance, system_prompt)
      if response is not None:
        return response
      logger.warning("SLM unavailable, falling back to Cloud LLM")
      return await self._call_cloud(utterance, system_prompt)
    else:
      # DEEP → Cloud LLM 直接
      return await self._call_cloud(utterance, system_prompt)

  async def _call_slm(self, utterance: str, system_prompt: str) -> str | None:
    """ollama-compatible SLM API にリクエストする

    POST {slm_base_url}/api/chat
    リクエストボディ: { model, messages, stream: false }

    Returns:
      レスポンステキスト。接続失敗・エラー時は None。
    """
    url = f"{self._slm_base_url}/api/chat"
    payload = {
      "model": self._slm_model,
      "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": utterance},
      ],
      "stream": False,
    }

    try:
      async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # ollama レスポンス形式: { "message": { "content": "..." } }
        content = data.get("message", {}).get("content", "")
        logger.debug("SLM response received (%d chars)", len(content))
        return content
    except (httpx.HTTPError, httpx.ConnectError, Exception) as e:
      logger.warning("SLM call failed: %s", e)
      return None

  async def _call_cloud(self, utterance: str, system_prompt: str) -> str:
    """OpenAI-compatible Cloud LLM API にリクエストする

    AsyncOpenAI を使用して chat.completions.create を呼び出す。

    Returns:
      レスポンステキスト

    Raises:
      RuntimeError: Cloud LLM が利用不可の場合
    """
    try:
      client = AsyncOpenAI(
        api_key=self._cloud_api_key,
        base_url=self._cloud_base_url,
      )
      response = await client.chat.completions.create(
        model=self._cloud_model,
        messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": utterance},
        ],
      )
      content = response.choices[0].message.content or ""
      logger.debug("Cloud LLM response received (%d chars)", len(content))
      return content
    except Exception as e:
      logger.error("Cloud LLM call failed: %s", e)
      raise RuntimeError(
        f"No LLM backend available: Cloud LLM error: {e}"
      ) from e
