"""プロファイルバリデーション プロパティベーステスト

Feature: agent-evolution
Property 14: Profile validation acceptance
Property 15: Profile validation rejection
Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7
"""

from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.models.scores import NormalizedScores
from app.models.profile import BaseOS, ContextLayers, ProfileOutput
from app.evolution.models import (
  validate_profile_for_evolution,
  ProfileValidationError,
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

# 有効な decision_style (非空文字列)
_valid_decision_style_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "P")),
  min_size=1,
  max_size=50,
)

# 有効な do_not_list (1〜4件の非空文字列)
_valid_do_not_list_st = st.lists(
  st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
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

# 有効な lexical_tags (5〜20件、テスト実行時間のため上限を抑える)
_valid_lexical_tags_st = st.lists(
  st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
  ),
  min_size=5,
  max_size=20,
)

# 有効な semantic_contexts 値 (10〜2000文字)
_valid_context_value_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
  min_size=10,
  max_size=100,  # テスト速度のため短めに
)

# 有効な semantic_contexts (1〜5ドメイン)
_valid_semantic_contexts_st = st.dictionaries(
  keys=st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
  ),
  values=_valid_context_value_st,
  min_size=1,
  max_size=5,
)

# 有効な ContextLayers (固定値: base_os=1, lexical_tags=2, semantic_contexts=3)
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
# Property 14: Profile validation acceptance
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(profile=_valid_profile_st)
def test_valid_profiles_pass_validation(profile: ProfileOutput) -> None:
  """有効な ProfileOutput は validate_profile_for_evolution で例外が発生しない。

  全制約を満たすプロファイルを生成し、バリデーションが正常に通過することを検証する。

  **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7**
  """
  # バリデーションが例外なしで完了する（戻り値 None）
  result = validate_profile_for_evolution(profile)
  assert result is None


# =============================================================================
# Property 15: Profile validation rejection
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  short_text=st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=0,
    max_size=9,
  ),
)
def test_short_semantic_context_rejected(
  profile: ProfileOutput, short_text: str
) -> None:
  """semantic_contexts の値が 10文字未満の場合、ProfileValidationError が発生する。

  **Validates: Requirements 10.5**
  """
  # semantic_contexts に短すぎるエントリを注入
  invalid_contexts = dict(profile.semantic_contexts)
  invalid_contexts["__test_short__"] = short_text

  # pydantic モデルを直接構築（model_construct で制約スキップ）
  invalid_profile = profile.model_copy(update={"semantic_contexts": invalid_contexts})

  try:
    validate_profile_for_evolution(invalid_profile)
    assert False, "短い semantic_contexts 値で ProfileValidationError が発生すべき"
  except ProfileValidationError as e:
    # エラーメッセージに該当ドメインの情報が含まれる
    assert any("__test_short__" in err for err in e.errors)
    assert any("shorter than 10" in err for err in e.errors)


@settings(
  max_examples=50,
  suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example],
)
@given(
  profile=_valid_profile_st,
  long_text=st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=2001,
    max_size=2050,
  ),
)
def test_long_semantic_context_rejected(
  profile: ProfileOutput, long_text: str
) -> None:
  """semantic_contexts の値が 2000文字超の場合、ProfileValidationError が発生する。

  **Validates: Requirements 10.5**
  """
  # semantic_contexts に長すぎるエントリを注入
  invalid_contexts = dict(profile.semantic_contexts)
  invalid_contexts["__test_long__"] = long_text

  invalid_profile = profile.model_copy(update={"semantic_contexts": invalid_contexts})

  try:
    validate_profile_for_evolution(invalid_profile)
    assert False, "長い semantic_contexts 値で ProfileValidationError が発生すべき"
  except ProfileValidationError as e:
    assert any("__test_long__" in err for err in e.errors)
    assert any("exceeds 2000" in err for err in e.errors)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  wrong_base_os=st.integers().filter(lambda x: x != 1),
  wrong_lexical=st.integers().filter(lambda x: x != 2),
  wrong_semantic=st.integers().filter(lambda x: x != 3),
)
def test_wrong_context_layers_rejected(
  profile: ProfileOutput,
  wrong_base_os: int,
  wrong_lexical: int,
  wrong_semantic: int,
) -> None:
  """context_layers の値が規定値と異なる場合、ProfileValidationError が発生する。

  base_os=1, lexical_tags=2, semantic_contexts=3 以外は全て拒否される。

  **Validates: Requirements 10.6, 10.7**
  """
  # 不正な ContextLayers を構築（model_construct で pydantic 制約をスキップ）
  invalid_layers = ContextLayers.model_construct(
    base_os=wrong_base_os,
    lexical_tags=wrong_lexical,
    semantic_contexts=wrong_semantic,
  )
  invalid_profile = profile.model_copy(update={"context_layers": invalid_layers})

  try:
    validate_profile_for_evolution(invalid_profile)
    assert False, "不正な context_layers で ProfileValidationError が発生すべき"
  except ProfileValidationError as e:
    # 各レイヤーのエラーメッセージが含まれる
    error_text = " ".join(e.errors)
    assert "context_layers.base_os must be 1" in error_text
    assert "context_layers.lexical_tags must be 2" in error_text
    assert "context_layers.semantic_contexts must be 3" in error_text


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  wrong_value=st.integers().filter(lambda x: x != 1),
)
def test_wrong_base_os_layer_only_rejected(
  profile: ProfileOutput,
  wrong_value: int,
) -> None:
  """context_layers.base_os のみ不正な場合でも適切にエラー報告される。

  **Validates: Requirements 10.6**
  """
  invalid_layers = ContextLayers.model_construct(
    base_os=wrong_value,
    lexical_tags=2,
    semantic_contexts=3,
  )
  invalid_profile = profile.model_copy(update={"context_layers": invalid_layers})

  try:
    validate_profile_for_evolution(invalid_profile)
    assert False, "不正な context_layers.base_os で ProfileValidationError が発生すべき"
  except ProfileValidationError as e:
    assert any("context_layers.base_os must be 1" in err for err in e.errors)
    # 他のレイヤーエラーは含まれない
    assert not any("context_layers.lexical_tags" in err for err in e.errors)
    assert not any("context_layers.semantic_contexts" in err for err in e.errors)
