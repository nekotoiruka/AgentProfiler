"""ハイブリッド・ルーティングエンジン

発話の複雑度に基づき、ローカル SLM (ollama) とクラウド LLM (OpenAI) を
適応的に振り分けるルーティングコンポーネント。

Cloud LLM は OpenAI Responses API を使用し、function calling による
ツール呼び出し（記憶検索等）をサポートする。
"""

import json
import logging
from enum import Enum
from typing import Any

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


# チャット用ツール定義: プロファイルの記憶/経験を検索する
MEMORY_SEARCH_TOOL = {
  "type": "function",
  "name": "search_memory",
  "description": (
    "このペルソナの記憶・経験・価値観・習慣に関する情報を検索します。"
    "ユーザーの質問に答えるために、自分自身の経験や考え方を思い出す必要があるときに使ってください。"
    "例: 趣味について聞かれたとき、仕事の進め方について聞かれたとき、好きなものについて聞かれたとき"
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "検索クエリ。自分の記憶から探したい内容を自然言語で指定する",
      },
    },
    "required": ["query"],
    "additionalProperties": False,
  },
  "strict": True,
}


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
  - DEEP → Cloud LLM (OpenAI Responses API + function calling)
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

    ツールなしの単純なテキスト生成。DiscussionEngine 等で使用。

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
      response = await self._call_slm(utterance, system_prompt)
      if response is not None:
        return response
      logger.warning("SLM unavailable, falling back to Cloud LLM")
      return await self._call_cloud(utterance, system_prompt)
    else:
      return await self._call_cloud(utterance, system_prompt)

  async def route_with_tools(
    self,
    utterance: str,
    system_prompt: str,
    tools: list[dict] | None = None,
    tool_executor: Any = None,
    max_tool_rounds: int = 3,
  ) -> str:
    """Responses API + function calling でツール呼び出し付き推論を実行する。

    モデルが tool を呼んだ場合、tool_executor で実行し結果を返却、
    再度モデルに投げるループを最大 max_tool_rounds 回繰り返す。

    Args:
      utterance: ユーザー発話テキスト
      system_prompt: システムプロンプト（instructions として使用）
      tools: ツール定義リスト（None の場合はツールなし）
      tool_executor: async callable(name, args) → str のツール実行関数
      max_tool_rounds: ツール呼び出しの最大ラウンド数

    Returns:
      最終的なテキストレスポンス

    Raises:
      RuntimeError: Cloud LLM が利用不可の場合
    """
    try:
      client = AsyncOpenAI(api_key=self._cloud_api_key)

      # Responses API の input リストを構築
      input_list: list[dict] = [
        {"role": "user", "content": utterance},
      ]

      for round_num in range(max_tool_rounds + 1):
        # Responses API 呼び出し
        kwargs: dict[str, Any] = {
          "model": self._cloud_model,
          "instructions": system_prompt,
          "input": input_list,
        }
        if tools:
          kwargs["tools"] = tools

        response = await client.responses.create(**kwargs)

        # レスポンス output を確認: function_call があるか？
        has_tool_call = False
        for item in response.output:
          if item.type == "function_call":
            has_tool_call = True
            break

        if not has_tool_call:
          # ツール呼び出しなし → テキスト出力を返す
          return response.output_text or ""

        # ツール呼び出しがある → 実行して結果を input に追加
        # まず output 全体を input に追加（モデルの発話として）
        input_list += response.output

        for item in response.output:
          if item.type == "function_call":
            name = item.name
            args = json.loads(item.arguments)
            logger.info(
              "Tool call round %d: %s(%s)",
              round_num + 1, name, json.dumps(args, ensure_ascii=False)[:100],
            )

            # ツール実行
            if tool_executor is not None:
              result = await tool_executor(name, args)
            else:
              result = f"Tool '{name}' not available"

            # function_call_output を追加
            input_list.append({
              "type": "function_call_output",
              "call_id": item.call_id,
              "output": str(result),
            })

      # max_tool_rounds を超えた場合: 最後にツールなしで呼び出す
      logger.warning("Max tool rounds exceeded, forcing final response")
      response = await client.responses.create(
        model=self._cloud_model,
        instructions=system_prompt,
        input=input_list,
      )
      return response.output_text or ""

    except Exception as e:
      logger.error("Cloud LLM (Responses API) call failed: %s", e)
      raise RuntimeError(
        f"No LLM backend available: Cloud LLM error: {e}"
      ) from e

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
        content = data.get("message", {}).get("content", "")
        logger.debug("SLM response received (%d chars)", len(content))
        return content
    except (httpx.HTTPError, httpx.ConnectError, Exception) as e:
      logger.warning("SLM call failed: %s", e)
      return None

  async def _call_cloud(self, utterance: str, system_prompt: str) -> str:
    """OpenAI Responses API でツールなしのテキスト生成を実行する。

    Returns:
      レスポンステキスト

    Raises:
      RuntimeError: Cloud LLM が利用不可の場合
    """
    try:
      client = AsyncOpenAI(api_key=self._cloud_api_key)
      response = await client.responses.create(
        model=self._cloud_model,
        instructions=system_prompt,
        input=utterance,
      )
      content = response.output_text or ""
      logger.debug("Cloud LLM response received (%d chars)", len(content))
      return content
    except Exception as e:
      logger.error("Cloud LLM call failed: %s", e)
      raise RuntimeError(
        f"No LLM backend available: Cloud LLM error: {e}"
      ) from e
