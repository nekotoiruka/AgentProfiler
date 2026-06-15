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
# あなたの人格設定
{% if persona and persona.nickname %}
あなたは「{{ persona.nickname }}」という名前の人格です。
{% if persona.age_range %}年齢層: {{ persona.age_range }}{% endif %}
{% if persona.role %}、役割: {{ persona.role }}{% endif %}
{% if persona.industry %}、業界: {{ persona.industry }}{% endif %}
{% if persona.experience_years %}、経験: {{ persona.experience_years }}{% endif %}

{% endif %}
{% if communication_tone %}
## 話し方のルール（必ず守ること）
{% if communication_tone.pronoun %}
- 一人称: 「{{ communication_tone.pronoun }}」を使う
{% endif %}
{% if communication_tone.formality %}
- 敬語/カジュアル: {{ communication_tone.formality }}
{% endif %}
{% if communication_tone.text_style %}
- テキストの特徴: {{ communication_tone.text_style }}
{% endif %}
{% if communication_tone.emotion_level %}
- 感情表現: {{ communication_tone.emotion_level }}
{% endif %}
{% if communication_tone.humor %}
- ユーモア: {{ communication_tone.humor }}
{% endif %}
{% if communication_tone.sentence_ending %}
- 文末表現の癖: {{ communication_tone.sentence_ending }}
{% endif %}
{% if communication_tone.filler_words %}
- よく使うフィラー: {{ communication_tone.filler_words }}
{% endif %}
{% if communication_tone.response_length %}
- 回答の長さ: {{ communication_tone.response_length }}
{% endif %}

{% endif %}
## 思考特性

{% for trait in traits %}
- {{ trait }}
{% endfor %}
{% if semantic_contexts %}

## あなたの思考パターン・価値観
{% for domain, description in semantic_contexts.items() %}

### {{ domain_labels.get(domain, domain) }}
{{ description }}
{% endfor %}
{% endif %}
{% if lexical_tags %}

## 関心事・趣味・スキル（キーワード）

{{ lexical_tags | join(', ') }}
{% endif %}

## 意思決定スタイル

あなたの意思決定の型: 「{{ decision_style }}」

## 絶対にやってはいけないこと
{% for item in do_not_list %}
- {{ item }}
{% endfor %}
{% if decision_model %}

## Decision Framework
{% for priority in decision_model_sorted %}
- {{ priority.name }} (weight: {{ priority.weight }})
{% endfor %}
{% if decision_model.tradeoff_tendencies %}

### Tradeoff Tendencies
{% for pair, score in decision_model.tradeoff_tendencies.items() %}
- {{ pair }}: {{ score }}
{% endfor %}
{% endif %}
{% endif %}
{% if failure_patterns %}

## Known Weaknesses & Guardrails
{% for trigger in failure_patterns.degradation_triggers %}
⚠️ {{ trigger }}
{% endfor %}
{% for mistake in failure_patterns.recurring_mistakes %}
🔄 {{ mistake }}
{% endfor %}
{% endif %}
{% if context_adaptation %}

## Context Adaptation Rules
{% for mode_name, config in context_adaptation.modes.items() %}
### {{ mode_name }}
- Tone: {{ config.tone }}
- Detail: {{ config.detail }}
- Focus: {{ config.focus }}
{% endfor %}
{% if context_adaptation.switch_triggers %}
Switch Conditions:
{% for category, conditions in context_adaptation.switch_triggers.items() %}
- {{ category }}: {{ conditions | join(", ") }}
{% endfor %}
{% endif %}
{% endif %}
{% if reasoning_flow %}

## Default Reasoning Process
{% for step in reasoning_flow.default_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
- Verification: {{ reasoning_flow.verification_method }}
- Learning Style: {{ reasoning_flow.learning_style }}
{% endif %}

## 重要な指示

上記の人格設定に基づいて一貫した受け答えをしてください。\
あなたは AI ではなく、この人格を持つ人間として振る舞います。\
質問されたら、この人格の経験・価値観・好みに基づいて答えてください。\
「AIなので趣味はありません」のような返答は絶対にしないでください。
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

    # persona がすべて空文字かどうかを判定
    persona = profile.persona
    has_persona = any([
      persona.nickname, persona.role, persona.industry,
    ])

    # ドメインラベルマッピング
    domain_labels = {
      "problem_solving": "問題解決の仕方",
      "communication_style": "コミュニケーションの傾向",
      "work_rhythm": "仕事のリズム",
      "analog_habits": "アナログな習慣",
      "lifestyle_preferences": "ライフスタイルの好み",
    }

    # Decision Engine セクションの抽出
    decision_model = profile.decision_model
    failure_patterns = profile.failure_patterns
    context_adaptation = profile.context_adaptation
    reasoning_flow = profile.reasoning_flow

    # decision_model_sorted: priority_weights を weight 降順にソートしたリスト
    decision_model_sorted = self._build_decision_model_sorted(decision_model)

    # トークン制限遵守のための段階的 truncation
    # 優先順位（低い方から先に削除）:
    #   1. reasoning_flow（最初に truncate）
    #   2. context_adaptation
    #   3. failure_patterns
    #   4. decision_model（最後に truncate）
    prompt = self._render_with_truncation(
      traits=traits,
      decision_style=profile.base_os.decision_style,
      do_not_list=profile.base_os.do_not_list,
      communication_tone=tone if has_tone else None,
      persona=persona if has_persona else None,
      semantic_contexts=profile.semantic_contexts if profile.semantic_contexts else None,
      lexical_tags=profile.lexical_tags if profile.lexical_tags else None,
      domain_labels=domain_labels,
      decision_model=decision_model,
      decision_model_sorted=decision_model_sorted,
      failure_patterns=failure_patterns,
      context_adaptation=context_adaptation,
      reasoning_flow=reasoning_flow,
    )

    token_count = self._estimate_tokens(prompt)

    if token_count > self._max_tokens:
      raise ValueError(
        f"Generated prompt exceeds token limit: "
        f"{token_count} > {self._max_tokens}"
      )

    logger.debug("Prompt generated: %d tokens", token_count)
    return PromptResult(prompt=prompt, token_count=token_count)

  def _build_decision_model_sorted(self, decision_model) -> list[dict]:
    """decision_model の priority_weights を weight 降順でソートする。

    Returns:
      [{name: str, weight: float}, ...] のリスト（weight 降順）
    """
    if decision_model is None:
      return []
    weights = decision_model.priority_weights
    if not weights:
      return []
    return sorted(
      [{"name": k, "weight": v} for k, v in weights.items()],
      key=lambda x: x["weight"],
      reverse=True,
    )

  def _render_with_truncation(
    self,
    *,
    traits,
    decision_style,
    do_not_list,
    communication_tone,
    persona,
    semantic_contexts,
    lexical_tags,
    domain_labels,
    decision_model,
    decision_model_sorted,
    failure_patterns,
    context_adaptation,
    reasoning_flow,
  ) -> str:
    """トークン制限を考慮しつつテンプレートをレンダリングする。

    max_tokens 超過時は低優先度セクションから順に除外して再レンダリングする。
    truncation 順序: reasoning_flow → context_adaptation → failure_patterns → decision_model
    """
    # 全セクション込みでレンダリング
    prompt = self._template.render(
      traits=traits,
      decision_style=decision_style,
      do_not_list=do_not_list,
      communication_tone=communication_tone,
      persona=persona,
      semantic_contexts=semantic_contexts,
      lexical_tags=lexical_tags,
      domain_labels=domain_labels,
      decision_model=decision_model,
      decision_model_sorted=decision_model_sorted,
      failure_patterns=failure_patterns,
      context_adaptation=context_adaptation,
      reasoning_flow=reasoning_flow,
    )

    if self._estimate_tokens(prompt) <= self._max_tokens:
      return prompt

    # Step 1: reasoning_flow を除外
    logger.debug("Truncating reasoning_flow section to fit token limit")
    prompt = self._template.render(
      traits=traits,
      decision_style=decision_style,
      do_not_list=do_not_list,
      communication_tone=communication_tone,
      persona=persona,
      semantic_contexts=semantic_contexts,
      lexical_tags=lexical_tags,
      domain_labels=domain_labels,
      decision_model=decision_model,
      decision_model_sorted=decision_model_sorted,
      failure_patterns=failure_patterns,
      context_adaptation=context_adaptation,
      reasoning_flow=None,
    )

    if self._estimate_tokens(prompt) <= self._max_tokens:
      return prompt

    # Step 2: context_adaptation を除外
    logger.debug("Truncating context_adaptation section to fit token limit")
    prompt = self._template.render(
      traits=traits,
      decision_style=decision_style,
      do_not_list=do_not_list,
      communication_tone=communication_tone,
      persona=persona,
      semantic_contexts=semantic_contexts,
      lexical_tags=lexical_tags,
      domain_labels=domain_labels,
      decision_model=decision_model,
      decision_model_sorted=decision_model_sorted,
      failure_patterns=failure_patterns,
      context_adaptation=None,
      reasoning_flow=None,
    )

    if self._estimate_tokens(prompt) <= self._max_tokens:
      return prompt

    # Step 3: failure_patterns を除外
    logger.debug("Truncating failure_patterns section to fit token limit")
    prompt = self._template.render(
      traits=traits,
      decision_style=decision_style,
      do_not_list=do_not_list,
      communication_tone=communication_tone,
      persona=persona,
      semantic_contexts=semantic_contexts,
      lexical_tags=lexical_tags,
      domain_labels=domain_labels,
      decision_model=decision_model,
      decision_model_sorted=decision_model_sorted,
      failure_patterns=None,
      context_adaptation=None,
      reasoning_flow=None,
    )

    if self._estimate_tokens(prompt) <= self._max_tokens:
      return prompt

    # Step 4: decision_model を除外（全 decision engine セクション無効）
    logger.debug("Truncating decision_model section to fit token limit")
    prompt = self._template.render(
      traits=traits,
      decision_style=decision_style,
      do_not_list=do_not_list,
      communication_tone=communication_tone,
      persona=persona,
      semantic_contexts=semantic_contexts,
      lexical_tags=lexical_tags,
      domain_labels=domain_labels,
      decision_model=None,
      decision_model_sorted=[],
      failure_patterns=None,
      context_adaptation=None,
      reasoning_flow=None,
    )

    return prompt

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
