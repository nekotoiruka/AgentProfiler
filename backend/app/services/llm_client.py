"""LLMクライアント: OpenAI / Azure OpenAI Responses API 連携

Other自由記述テキストから4軸スコアを推定するために使用する。
Structured Output (JSON Schema) で出力形式を保証する。
"""

import json
import logging
import os
from dataclasses import dataclass

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class AxisScoreResult:
  """LLMによる4軸スコア推定結果"""

  extroverted_introverted: int
  sensing_intuition: int
  thinking_feeling: int
  judging_perceiving: int
  reasoning: str


# Structured Output 用の JSON Schema
_SCORING_SCHEMA = {
  "type": "object",
  "properties": {
    "extroverted_introverted": {
      "type": "integer",
      "description": "外向(+)〜内向(-) スコア (-10〜+10)",
    },
    "sensing_intuition": {
      "type": "integer",
      "description": "感覚(+)〜直観(-) スコア (-10〜+10)",
    },
    "thinking_feeling": {
      "type": "integer",
      "description": "論理(+)〜感情(-) スコア (-10〜+10)",
    },
    "judging_perceiving": {
      "type": "integer",
      "description": "計画(+)〜柔軟(-) スコア (-10〜+10)",
    },
    "reasoning": {
      "type": "string",
      "description": "スコア判定の根拠（1〜2文）",
    },
  },
  "required": [
    "extroverted_introverted",
    "sensing_intuition",
    "thinking_feeling",
    "judging_perceiving",
    "reasoning",
  ],
  "additionalProperties": False,
}

# スコアリング用システムプロンプト
_SCORING_SYSTEM_PROMPT = """あなたは心理測定の専門家です。質問に対するユーザーの自由記述回答を分析し、4軸思考特性スコアを判定してください。

軸の定義:
- extroverted_introverted: 正=外向的（集団志向、対話重視、即行動）、負=内向的（個人志向、内省重視、熟考）
- sensing_intuition: 正=感覚的（具体的事実、データ、実績、手順重視）、負=直観的（抽象、パターン、可能性、ビジョン重視）
- thinking_feeling: 正=論理的（客観、効率、分析、正確性重視）、負=感情的（共感、調和、人間関係、チーム重視）
- judging_perceiving: 正=計画的（構造、スケジュール、事前準備重視）、負=柔軟的（臨機応変、探索、即興重視）

ルール:
- 各スコアは -10 から +10 の整数
- 明確な傾向が見られない軸は 0
- 強い傾向は ±7〜10、中程度は ±3〜6、弱い傾向は ±1〜2
- 回答テキストの内容のみから判断し、推測を最小限に"""


class LLMClient:
  """OpenAI / Azure OpenAI Responses API クライアント

  環境変数で接続先を切り替え:
    LLM_PROVIDER=openai → OpenAI 直接
    LLM_PROVIDER=azure → Azure OpenAI
  """

  def __init__(self) -> None:
    provider = os.getenv("LLM_PROVIDER", "openai")
    self._model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if provider == "azure":
      endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
      api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
      self._model = os.getenv("AZURE_OPENAI_MODEL", "gpt-4.1-mini")
      self._client = OpenAI(
        api_key=api_key,
        base_url=f"{endpoint}/openai/v1/",
      )
      logger.info("LLM client initialized (Azure): model=%s", self._model)
    else:
      api_key = os.getenv("OPENAI_API_KEY", "")
      self._client = OpenAI(api_key=api_key)
      logger.info("LLM client initialized (OpenAI): model=%s", self._model)

    self._enabled = bool(api_key)
    if not self._enabled:
      logger.warning("LLM client disabled: no API key configured")

  @property
  def enabled(self) -> bool:
    """APIキーが設定されていて利用可能かどうか"""
    return self._enabled

  def score_free_text(
    self, question_text: str, user_text: str
  ) -> AxisScoreResult | None:
    """自由記述テキストから4軸スコアを推定する

    Args:
      question_text: 質問のテキスト
      user_text: ユーザーの自由記述回答

    Returns:
      AxisScoreResult: 推定スコアと根拠。失敗時は None。
    """
    if not self._enabled:
      logger.debug("LLM scoring skipped: client not enabled")
      return None

    user_message = (
      f"質問: {question_text}\n\n"
      f"ユーザーの回答: {user_text}"
    )

    try:
      response = self._client.responses.create(
        model=self._model,
        instructions=_SCORING_SYSTEM_PROMPT,
        input=user_message,
        text={
          "format": {
            "type": "json_schema",
            "name": "axis_scores",
            "strict": True,
            "schema": _SCORING_SCHEMA,
          }
        },
      )

      # Structured Output のパース
      raw_text = response.output_text
      data = json.loads(raw_text)

      # スコアを -10〜+10 にクランプ
      result = AxisScoreResult(
        extroverted_introverted=max(-10, min(10, data["extroverted_introverted"])),
        sensing_intuition=max(-10, min(10, data["sensing_intuition"])),
        thinking_feeling=max(-10, min(10, data["thinking_feeling"])),
        judging_perceiving=max(-10, min(10, data["judging_perceiving"])),
        reasoning=data.get("reasoning", ""),
      )

      logger.info(
        "LLM scoring result: EI=%d, SN=%d, TF=%d, JP=%d | %s",
        result.extroverted_introverted,
        result.sensing_intuition,
        result.thinking_feeling,
        result.judging_perceiving,
        result.reasoning[:50],
      )

      return result

    except Exception as e:
      logger.error("LLM scoring failed: %s", e)
      return None
