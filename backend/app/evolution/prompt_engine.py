"""動的プロンプト生成エンジン

ProfileOutput の base_os セクションを Jinja2 テンプレートで
システムプロンプトに変換する。axes スコアから強度記述子を導出し、
do_not_list をガードレール、decision_style を意思決定アプローチとして挿入する。
"""

import logging
from dataclasses import dataclass

from jinja2 import Environment, BaseLoader

from app.models.profile import ProfileOutput

logger = logging.getLogger(__name__)

# axes score → 強度記述子マッピング
# 0.0–0.29: strong second pole
# 0.30–0.49: moderate second pole
# 0.50: balanced
# 0.51–0.70: moderate first pole
# 0.71–1.0: strong first pole
SCORE_DESCRIPTORS: list[tuple[float, float, str]] = [
  (0.0, 0.29, "strong_second_pole"),
  (0.30, 0.49, "moderate_second_pole"),
  (0.50, 0.50, "balanced"),
  (0.51, 0.70, "moderate_first_pole"),
  (0.71, 1.0, "strong_first_pole"),
]

# 軸名と両極ラベルのマッピング（記述的テキスト生成用）
AXIS_POLES: dict[str, tuple[str, str]] = {
  "extroverted_introverted": ("Extroverted", "Introverted"),
  "sensing_intuition": ("Sensing", "Intuition"),
  "thinking_feeling": ("Thinking", "Feeling"),
  "judging_perceiving": ("Judging", "Perceiving"),
}

# 記述子 → 人間可読文テンプレート
# first_pole / second_pole をフォーマットで挿入する
DESCRIPTOR_TEMPLATES: dict[str, str] = {
  "strong_first_pole": "You have a strong {first_pole} orientation.",
  "moderate_first_pole": "You have a moderate {first_pole} tendency.",
  "balanced": "You are balanced between {first_pole} and {second_pole}.",
  "moderate_second_pole": "You have a moderate {second_pole} tendency.",
  "strong_second_pole": "You have a strong {second_pole} orientation.",
}

DEFAULT_TEMPLATE = """\
You are an AI agent with the following personality profile.

## Personality Traits
{% for trait in traits %}
- {{ trait }}
{% endfor %}

## Values & Decision Style

Your primary decision-making approach is: {{ decision_style }}

## Guardrails

You MUST NOT perform the following actions under any circumstances:
{% for item in do_not_list %}
- {{ item }}
{% endfor %}
{% if communication_tone %}

## Communication Tone
{% if communication_tone.pronoun %}
- Pronoun: {{ communication_tone.pronoun }}
{% endif %}
{% if communication_tone.formality %}
- Formality: {{ communication_tone.formality }}
{% endif %}
{% if communication_tone.text_style %}
- Text style: {{ communication_tone.text_style }}
{% endif %}
{% if communication_tone.emotion_level %}
- Emotion level: {{ communication_tone.emotion_level }}
{% endif %}
{% if communication_tone.humor %}
- Humor: {{ communication_tone.humor }}
{% endif %}
{% if communication_tone.response_length %}
- Response length: {{ communication_tone.response_length }}
{% endif %}
{% endif %}
"""


@dataclass
class PromptResult:
  """プロンプト生成結果"""

  prompt: str
  token_count: int


class PromptEngine:
  """ProfileOutput → システムプロンプト変換エンジン

  Jinja2 テンプレートを用いてプロファイルデータから
  パーソナリティ特性・ガードレールを含むプロンプトを生成する。
  """

  def __init__(self, max_tokens: int = 4000, template_str: str | None = None):
    """PromptEngine を初期化する。

    Args:
      max_tokens: 生成プロンプトの最大トークン数（デフォルト4000）
      template_str: カスタム Jinja2 テンプレート文字列。None の場合デフォルトを使用
    """
    self._max_tokens = max_tokens
    self._env = Environment(loader=BaseLoader())
    self._template = self._env.from_string(template_str or DEFAULT_TEMPLATE)
    logger.info("PromptEngine initialized (max_tokens=%d)", max_tokens)

  def generate(self, profile: ProfileOutput) -> PromptResult:
    """プロファイルからシステムプロンプトを生成する。

    Args:
      profile: Agent Profiler が生成した ProfileOutput

    Returns:
      PromptResult: 生成されたプロンプト文字列とトークン数

    Raises:
      ValueError: base_os セクションまたは必須フィールドが欠落している場合
      ValueError: 生成プロンプトが max_tokens を超過した場合
    """
    self._validate_base_os(profile)

    # axes → 強度記述子 → 人間可読文に変換
    traits = self._build_trait_descriptions(profile)

    # communication_tone がすべて空文字かどうかを判定
    tone = profile.communication_tone
    has_tone = any([
      tone.pronoun, tone.formality, tone.text_style,
      tone.emotion_level, tone.humor, tone.response_length,
    ])

    # テンプレートレンダリング
    prompt = self._template.render(
      traits=traits,
      decision_style=profile.base_os.decision_style,
      do_not_list=profile.base_os.do_not_list,
      communication_tone=tone if has_tone else None,
    )

    token_count = self._estimate_tokens(prompt)

    if token_count > self._max_tokens:
      raise ValueError(
        f"Generated prompt exceeds token limit: "
        f"{token_count} > {self._max_tokens}"
      )

    logger.debug("Prompt generated: %d tokens", token_count)
    return PromptResult(prompt=prompt, token_count=token_count)

  def _validate_base_os(self, profile: ProfileOutput) -> None:
    """base_os セクションの存在と必須フィールドを検証する。

    Raises:
      ValueError: base_os が None、または必須フィールドが欠落している場合
    """
    if profile.base_os is None:
      raise ValueError("ProfileOutput is missing the 'base_os' section")

    missing_fields: list[str] = []

    if profile.base_os.axes is None:
      missing_fields.append("axes")

    if not profile.base_os.decision_style:
      missing_fields.append("decision_style")

    if not profile.base_os.do_not_list:
      missing_fields.append("do_not_list")

    if missing_fields:
      raise ValueError(
        f"base_os is missing required fields: {', '.join(missing_fields)}"
      )

  def _build_trait_descriptions(self, profile: ProfileOutput) -> list[str]:
    """axes スコアから人間可読なトレイト記述文のリストを構築する。"""
    traits: list[str] = []
    axes = profile.base_os.axes

    for axis_name, (first_pole, second_pole) in AXIS_POLES.items():
      score = getattr(axes, axis_name)
      descriptor = self._map_score_to_descriptor(score)
      template = DESCRIPTOR_TEMPLATES[descriptor]
      trait_text = template.format(
        first_pole=first_pole,
        second_pole=second_pole,
      )
      traits.append(trait_text)

    return traits

  def _map_score_to_descriptor(self, score: float) -> str:
    """正規化スコア [0.0, 1.0] → 強度記述子文字列。

    Args:
      score: 0.0〜1.0 の正規化スコア

    Returns:
      強度記述子（例: "strong_first_pole", "balanced" 等）
    """
    # 小数点2桁に丸めてマッチング精度を確保
    rounded = round(score, 2)
    for low, high, descriptor in SCORE_DESCRIPTORS:
      if low <= rounded <= high:
        return descriptor
    # フォールバック: 範囲外の場合（理論上到達しない）
    logger.warning("Score %.4f out of expected range, defaulting to balanced", score)
    return "balanced"

  @staticmethod
  def _estimate_tokens(text: str) -> int:
    """テキストのトークン数を簡易推定する。

    近似式: len(text) / 4（英語テキストの平均的なトークン/文字比率）
    日本語を含む場合はやや保守的な推定になるが、安全側に倒す。
    """
    return max(1, len(text) // 4)
