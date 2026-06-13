"""PromptEngine プロパティベーステスト

Feature: agent-evolution
Property 1: Prompt faithfulness
Property 2: Axes score descriptor mapping
Property 3: Prompt rejects invalid profile
Property 4: Prompt token limit invariant
Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.models.scores import NormalizedScores
from app.models.profile import (
  BaseOS, ContextLayers, ProfileOutput, Persona, CommunicationTone,
)
from app.evolution.prompt_engine import (
  PromptEngine, PromptResult, SCORE_DESCRIPTORS, AXIS_POLES, DESCRIPTOR_TEMPLATES,
)


# --- Hypothesis ストラテジー ---

# 有効な profile_id: "prof_" + 6桁ゼロパディング
_valid_profile_id_st = st.integers(min_value=0, max_value=999999).map(
  lambda n: f"prof_{n:06d}"
)

# 有効な axes スコア (0.0〜1.0, NaN/Inf 除外)
_valid_axis_score_st = st.floats(
  min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)

# 有効な NormalizedScores
_valid_axes_st = st.builds(
  NormalizedScores,
  extroverted_introverted=_valid_axis_score_st,
  sensing_intuition=_valid_axis_score_st,
  thinking_feeling=_valid_axis_score_st,
  judging_perceiving=_valid_axis_score_st,
)

# 有効な decision_style (非空文字列、テンプレートに含まれることを検証するため ASCII)
_valid_decision_style_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=30,
)

# 有効な do_not_list (1〜4件の非空文字列)
_valid_do_not_list_st = st.lists(
  st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=30,
  ),
  min_size=1,
  max_size=4,
)

# 有効な BaseOS
_valid_base_os_st = st.builds(
  BaseOS,
  axes=_valid_axes_st,
  decision_style=_valid_decision_style_st,
  do_not_list=_valid_do_not_list_st,
)

# 有効な lexical_tags (5〜10件、テスト速度のため上限抑制)
_valid_lexical_tags_st = st.lists(
  st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
  ),
  min_size=5,
  max_size=10,
)

# 有効な semantic_contexts 値 (10〜100文字)
_valid_context_value_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
  min_size=10,
  max_size=100,
)

# 有効な semantic_contexts (1〜3ドメイン)
_valid_semantic_contexts_st = st.dictionaries(
  keys=st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
  ),
  values=_valid_context_value_st,
  min_size=1,
  max_size=3,
)

# 有効な ContextLayers (固定値)
_valid_context_layers_st = st.just(ContextLayers(base_os=1, lexical_tags=2, semantic_contexts=3))

# 有効な ProfileOutput
_valid_profile_st = st.builds(
  ProfileOutput,
  profile_id=_valid_profile_id_st,
  base_os=_valid_base_os_st,
  lexical_tags=_valid_lexical_tags_st,
  semantic_contexts=_valid_semantic_contexts_st,
  context_layers=_valid_context_layers_st,
)


# =============================================================================
# Property 1: Prompt faithfulness
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_prompt_contains_decision_style(profile: ProfileOutput) -> None:
  """生成プロンプトに decision_style テキストが含まれる。

  **Validates: Requirements 1.1, 1.4**
  """
  engine = PromptEngine(max_tokens=8000)
  result = engine.generate(profile)

  assert profile.base_os.decision_style in result.prompt, (
    f"decision_style '{profile.base_os.decision_style}' not found in prompt"
  )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_prompt_contains_all_do_not_list_items(profile: ProfileOutput) -> None:
  """生成プロンプトに全ての do_not_list アイテムが含まれる。

  **Validates: Requirements 1.1, 1.5**
  """
  engine = PromptEngine(max_tokens=8000)
  result = engine.generate(profile)

  for item in profile.base_os.do_not_list:
    assert item in result.prompt, (
      f"do_not_list item '{item}' not found in prompt"
    )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_prompt_contains_trait_descriptions(profile: ProfileOutput) -> None:
  """生成プロンプトに各軸のトレイト記述が含まれる。

  axes の各スコアに対応する記述子テンプレートの出力文が
  プロンプト内に存在することを検証する。

  **Validates: Requirements 1.1, 1.2, 1.3**
  """
  engine = PromptEngine(max_tokens=8000)
  result = engine.generate(profile)

  # 各軸について、対応する記述文がプロンプトに含まれることを検証
  axes = profile.base_os.axes
  for axis_name, (first_pole, second_pole) in AXIS_POLES.items():
    score = getattr(axes, axis_name)
    descriptor = engine._map_score_to_descriptor(score)
    template = DESCRIPTOR_TEMPLATES[descriptor]
    expected_text = template.format(first_pole=first_pole, second_pole=second_pole)
    assert expected_text in result.prompt, (
      f"Trait description '{expected_text}' for axis '{axis_name}' "
      f"(score={score}, descriptor={descriptor}) not found in prompt"
    )


# =============================================================================
# Property 2: Axes score descriptor mapping
# Feature: agent-evolution
# =============================================================================

# 全有効スコア範囲をカバーするストラテジー
_valid_score_st = st.floats(
  min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)

# 有効な記述子の集合
VALID_DESCRIPTORS = {
  "strong_second_pole",
  "moderate_second_pole",
  "balanced",
  "moderate_first_pole",
  "strong_first_pole",
}


@settings(max_examples=500)
@given(score=_valid_score_st)
def test_descriptor_mapping_returns_valid_descriptor(score: float) -> None:
  """任意の [0.0, 1.0] スコアが5つの有効記述子のいずれかにマッピングされる。

  **Validates: Requirements 1.2**
  """
  engine = PromptEngine()
  descriptor = engine._map_score_to_descriptor(score)

  assert descriptor in VALID_DESCRIPTORS, (
    f"Score {score} mapped to unknown descriptor '{descriptor}'"
  )


@settings(max_examples=500)
@given(score=_valid_score_st)
def test_descriptor_mapping_is_deterministic(score: float) -> None:
  """同一スコアに対する記述子マッピングは決定的（何度呼んでも同じ結果）。

  **Validates: Requirements 1.2**
  """
  engine = PromptEngine()
  result1 = engine._map_score_to_descriptor(score)
  result2 = engine._map_score_to_descriptor(score)
  result3 = engine._map_score_to_descriptor(score)

  assert result1 == result2 == result3, (
    f"Non-deterministic mapping for score {score}: "
    f"{result1}, {result2}, {result3}"
  )


@settings(max_examples=200)
@given(
  score=_valid_score_st,
  data=st.data(),
)
def test_descriptor_mapping_covers_all_ranges(score: float, data) -> None:
  """スコア範囲に応じた期待記述子と実際の記述子が一致する。

  Score ranges:
  - 0.0–0.29: strong_second_pole
  - 0.30–0.49: moderate_second_pole
  - 0.50: balanced
  - 0.51–0.70: moderate_first_pole
  - 0.71–1.0: strong_first_pole

  **Validates: Requirements 1.2, 1.3**
  """
  engine = PromptEngine()
  descriptor = engine._map_score_to_descriptor(score)
  rounded = round(score, 2)

  # 期待される記述子を独自に判定
  if rounded <= 0.29:
    expected = "strong_second_pole"
  elif rounded <= 0.49:
    expected = "moderate_second_pole"
  elif rounded == 0.50:
    expected = "balanced"
  elif rounded <= 0.70:
    expected = "moderate_first_pole"
  else:
    expected = "strong_first_pole"

  assert descriptor == expected, (
    f"Score {score} (rounded={rounded}): "
    f"expected '{expected}', got '{descriptor}'"
  )


# =============================================================================
# Property 3: Prompt rejects invalid profile
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_missing_base_os_raises_value_error(profile: ProfileOutput) -> None:
  """base_os が None の場合、ValueError が発生する。

  **Validates: Requirements 1.6**
  """
  engine = PromptEngine()
  # base_os を None に設定（model_construct で pydantic 制約スキップ）
  invalid_profile = ProfileOutput.model_construct(
    profile_id=profile.profile_id,
    persona=profile.persona,
    communication_tone=profile.communication_tone,
    base_os=None,
    lexical_tags=profile.lexical_tags,
    semantic_contexts=profile.semantic_contexts,
    context_layers=profile.context_layers,
  )

  with pytest.raises(ValueError, match="base_os"):
    engine.generate(invalid_profile)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_missing_axes_raises_value_error(profile: ProfileOutput) -> None:
  """base_os.axes が None の場合、ValueError が発生する。

  **Validates: Requirements 1.6**
  """
  engine = PromptEngine()
  # axes を None にした BaseOS を構築
  invalid_base_os = BaseOS.model_construct(
    axes=None,
    decision_style=profile.base_os.decision_style,
    do_not_list=profile.base_os.do_not_list,
  )
  invalid_profile = profile.model_copy(update={"base_os": invalid_base_os})

  with pytest.raises(ValueError, match="axes"):
    engine.generate(invalid_profile)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_empty_decision_style_raises_value_error(profile: ProfileOutput) -> None:
  """base_os.decision_style が空文字列の場合、ValueError が発生する。

  **Validates: Requirements 1.6**
  """
  engine = PromptEngine()
  invalid_base_os = BaseOS.model_construct(
    axes=profile.base_os.axes,
    decision_style="",
    do_not_list=profile.base_os.do_not_list,
  )
  invalid_profile = profile.model_copy(update={"base_os": invalid_base_os})

  with pytest.raises(ValueError, match="decision_style"):
    engine.generate(invalid_profile)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_empty_do_not_list_raises_value_error(profile: ProfileOutput) -> None:
  """base_os.do_not_list が空リストの場合、ValueError が発生する。

  **Validates: Requirements 1.6**
  """
  engine = PromptEngine()
  invalid_base_os = BaseOS.model_construct(
    axes=profile.base_os.axes,
    decision_style=profile.base_os.decision_style,
    do_not_list=[],
  )
  invalid_profile = profile.model_copy(update={"base_os": invalid_base_os})

  with pytest.raises(ValueError, match="do_not_list"):
    engine.generate(invalid_profile)


# =============================================================================
# Property 4: Prompt token limit invariant
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_generated_prompt_within_default_token_limit(profile: ProfileOutput) -> None:
  """デフォルト max_tokens=4000 の場合、生成プロンプトのトークン数は上限以内。

  **Validates: Requirements 1.1, 1.6**
  """
  engine = PromptEngine(max_tokens=4000)
  result = engine.generate(profile)

  assert result.token_count <= 4000, (
    f"Token count {result.token_count} exceeds max_tokens=4000"
  )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  max_tokens=st.integers(min_value=500, max_value=10000),
)
def test_generated_prompt_within_custom_token_limit(
  profile: ProfileOutput, max_tokens: int
) -> None:
  """任意の max_tokens 設定でも、生成プロンプトのトークン数は上限以内。

  トークン数超過時は ValueError が発生するため、正常完了した場合は
  必ず token_count <= max_tokens が成立する。

  **Validates: Requirements 1.1, 1.6**
  """
  engine = PromptEngine(max_tokens=max_tokens)

  try:
    result = engine.generate(profile)
    # 正常完了 → トークン数は制限以内
    assert result.token_count <= max_tokens, (
      f"Token count {result.token_count} exceeds max_tokens={max_tokens}"
    )
  except ValueError as e:
    # トークン上限超過エラー → 期待通りの動作
    assert "exceeds token limit" in str(e)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_token_count_matches_estimation(profile: ProfileOutput) -> None:
  """token_count は len(prompt) // 4 のトークン推定式と一致する。

  **Validates: Requirements 1.1**
  """
  engine = PromptEngine(max_tokens=8000)
  result = engine.generate(profile)

  # トークン推定: len(text) // 4 (最低1)
  expected_tokens = max(1, len(result.prompt) // 4)
  assert result.token_count == expected_tokens, (
    f"Token count {result.token_count} != expected {expected_tokens} "
    f"(prompt length={len(result.prompt)})"
  )
