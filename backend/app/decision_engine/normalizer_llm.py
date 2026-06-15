"""LLM ベース正規化クライアント: 自由記述テキストからの構造化タグ・ポリシー抽出"""

import json
import logging
import time
from dataclasses import dataclass

from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Structured Output 用 JSON Schema
_NORMALIZATION_SCHEMA = {
  "type": "object",
  "properties": {
    "tags": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": {
            "type": "string",
            "enum": ["value_tag", "behavior_tag", "prohibition_tag", "condition_tag"],
          },
          "value": {"type": "string"},
        },
        "required": ["type", "value"],
        "additionalProperties": False,
      },
    },
    "policy_text": {"type": "string"},
  },
  "required": ["tags", "policy_text"],
  "additionalProperties": False,
}

# 正規化用システムプロンプト
_NORMALIZATION_SYSTEM_PROMPT = """あなたはユーザー回答の正規化エキスパートです。質問に対するユーザーの自由記述回答を分析し、構造化タグとポリシールールを抽出してください。

## タグ種別（1〜3個を抽出）

- value_tag: 価値観・信念を表すタグ（例: "品質重視", "チームワーク優先"）
- behavior_tag: 行動パターンを表すタグ（例: "即断即決", "慎重に情報収集"）
- prohibition_tag: 禁止事項・避けるべきことを表すタグ（例: "曖昧な指示を出さない", "感情的な判断を避ける"）
- condition_tag: 条件・例外を表すタグ（例: "緊急時を除き", "チーム規模が5人以上の場合"）

## ルール

- タグは1〜3個抽出する
- 各タグの value は50文字以内の簡潔な日本語
- policy_text は "when_{状況}: {行動指示}" 形式で、エージェントが従うべき一文ルールを生成する
- 回答内容のみから判断し、推測を最小限にする
- policy_text の例: "when_deadline_pressure: 品質より速度を優先し、最小限の成果物を提出する"
"""


@dataclass
class NormalizationResult:
  """LLM 正規化結果"""

  tags: list[dict[str, str]]  # [{type: "value_tag"|"behavior_tag"|..., value: str}]
  policy_text: str  # "when_X: Y" 形式のポリシールール


class LLMNormalizer:
  """LLM ベース正規化クライアント

  自由記述テキストから:
  1. normalization_tags (4種: value_tag, behavior_tag, prohibition_tag, condition_tag) を抽出
  2. policy_text ("when_X: Y" 形式) を生成

  リトライ: 最大2回、exponential backoff (1s, 2s)
  """

  VALID_TAG_TYPES = ("value_tag", "behavior_tag", "prohibition_tag", "condition_tag")
  MAX_RETRIES = 2

  def __init__(self, llm_client: LLMClient, model: str = "gpt-4.1-mini"):
    self._llm = llm_client
    self._model = model

  async def normalize(self, question_text: str, answer_text: str) -> NormalizationResult | None:
    """自由記述テキストを正規化する

    Returns:
      NormalizationResult or None (LLM 呼び出し失敗時 or パース失敗時)
    """
    if not self._llm.enabled:
      logger.debug("LLM normalizer skipped: client not enabled")
      return None

    prompt = self._build_prompt(question_text, answer_text)

    for attempt in range(self.MAX_RETRIES + 1):
      try:
        response = self._call_llm(prompt)
        result = self._parse_response(response)
        if result is not None:
          return result
        logger.warning("Parse failed on attempt %d", attempt + 1)
      except Exception as e:
        logger.warning("LLM call failed on attempt %d: %s", attempt + 1, e)

      if attempt < self.MAX_RETRIES:
        time.sleep(2**attempt)  # 1s, 2s backoff

    return None

  def _build_prompt(self, question_text: str, answer_text: str) -> str:
    """正規化用システムプロンプトを構築する"""
    return f"質問: {question_text}\n\nユーザーの回答: {answer_text}"

  def _call_llm(self, prompt: str) -> str:
    """LLM API を呼び出して応答テキストを取得する

    LLMClient の内部 OpenAI クライアントを直接使用し、
    Structured Output (JSON Schema) で出力形式を保証する。
    """
    # LLMClient の OpenAI クライアントに直接アクセス
    response = self._llm._client.responses.create(
      model=self._model,
      instructions=_NORMALIZATION_SYSTEM_PROMPT,
      input=prompt,
      text={
        "format": {
          "type": "json_schema",
          "name": "normalization_result",
          "strict": True,
          "schema": _NORMALIZATION_SCHEMA,
        }
      },
    )
    return response.output_text

  def _parse_response(self, response: str) -> NormalizationResult | None:
    """LLM レスポンスをパースして NormalizationResult に変換する

    Validates:
    - tags is a non-empty list
    - Each tag has valid type (one of VALID_TAG_TYPES)
    - Each tag value is ≤50 characters
    - policy_text is a non-empty string starting with "when_"
    """
    try:
      data = json.loads(response)
    except (json.JSONDecodeError, TypeError):
      logger.warning("Failed to parse LLM response as JSON")
      return None

    # tags バリデーション
    tags = data.get("tags")
    if not isinstance(tags, list) or len(tags) == 0:
      logger.warning("Invalid tags: must be a non-empty list")
      return None

    validated_tags: list[dict[str, str]] = []
    for tag in tags:
      if not isinstance(tag, dict):
        logger.warning("Invalid tag entry: not a dict")
        return None

      tag_type = tag.get("type")
      tag_value = tag.get("value")

      if tag_type not in self.VALID_TAG_TYPES:
        logger.warning("Invalid tag type: %s", tag_type)
        return None

      if not isinstance(tag_value, str) or len(tag_value) == 0 or len(tag_value) > 50:
        logger.warning("Invalid tag value: must be 1-50 chars, got %s", tag_value)
        return None

      validated_tags.append({"type": tag_type, "value": tag_value})

    # policy_text バリデーション
    policy_text = data.get("policy_text")
    if not isinstance(policy_text, str) or len(policy_text) == 0:
      logger.warning("Invalid policy_text: must be a non-empty string")
      return None

    if not policy_text.startswith("when_"):
      logger.warning("Invalid policy_text: must start with 'when_'")
      return None

    return NormalizationResult(tags=validated_tags, policy_text=policy_text)
