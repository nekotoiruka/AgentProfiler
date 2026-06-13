"""ContextLayerManager プロパティベーステスト

Feature: agent-evolution
Property 5: Context layer assignment validation
Validates: Requirements 2.3, 2.4, 3.6, 4.6
"""

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.evolution.context_layer_manager import ContextLayerManager
from app.models.profile import BaseOS, ContextLayers, ProfileOutput
from app.models.scores import NormalizedScores


# --- Hypothesis ストラテジー ---

# 0.0〜1.0 の float (axes 値)
_axis_score_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# NormalizedScores ストラテジー
_normalized_scores_st = st.builds(
  NormalizedScores,
  extroverted_introverted=_axis_score_st,
  sensing_intuition=_axis_score_st,
  thinking_feeling=_axis_score_st,
  judging_perceiving=_axis_score_st,
)

# decision_style ストラテジー
_decision_style_st = st.sampled_from([
  "analytical_planner",
  "intuitive_explorer",
  "balanced",
  "pragmatic_adapter",
  "structured_thinker",
])

# do_not_list ストラテジー (1〜4 件)
_do_not_list_st = st.lists(
  st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
  min_size=1,
  max_size=4,
)

# BaseOS ストラテジー
_base_os_st = st.builds(
  BaseOS,
  axes=_normalized_scores_st,
  decision_style=_decision_style_st,
  do_not_list=_do_not_list_st,
)

# lexical_tags ストラテジー (5〜20 件)
_tag_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
  min_size=1,
  max_size=20,
)
_lexical_tags_st = st.lists(_tag_st, min_size=5, max_size=20)

# semantic_contexts ストラテジー (1〜5 件、各値 10〜50 文字)
_semantic_value_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
  min_size=10,
  max_size=50,
)
_semantic_contexts_st = st.dictionaries(
  keys=st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=3,
    max_size=20,
  ),
  values=_semantic_value_st,
  min_size=1,
  max_size=5,
)

# profile_id ストラテジー (prof_ + 6桁)
_profile_id_st = st.integers(min_value=0, max_value=999999).map(
  lambda n: f"prof_{n:06d}"
)


def _build_profile(
  profile_id: str = "prof_000001",
  base_os: BaseOS | None = None,
  lexical_tags: list[str] | None = None,
  semantic_contexts: dict[str, str] | None = None,
  base_os_layer: int = 1,
  lexical_layer: int = 2,
  semantic_layer: int = 3,
) -> ProfileOutput:
  """テスト用 ProfileOutput ヘルパー。"""
  if base_os is None:
    base_os = BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.5,
        sensing_intuition=0.5,
        thinking_feeling=0.5,
        judging_perceiving=0.5,
      ),
      decision_style="balanced",
      do_not_list=["item1"],
    )
  if lexical_tags is None:
    lexical_tags = ["python", "fastapi", "vue", "docker", "typescript"]
  if semantic_contexts is None:
    semantic_contexts = {"domain1": "text content at least 10 chars"}
  return ProfileOutput(
    profile_id=profile_id,
    base_os=base_os,
    lexical_tags=lexical_tags,
    semantic_contexts=semantic_contexts,
    context_layers=ContextLayers(
      base_os=base_os_layer,
      lexical_tags=lexical_layer,
      semantic_contexts=semantic_layer,
    ),
  )


# =============================================================================
# Property 5: Context layer assignment validation
# Feature: agent-evolution
# =============================================================================


class TestValidLayerAssignment:
  """正しい context_layers 割り当て (base_os=1, lexical_tags=2, semantic_contexts=3) が受理される。"""

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    profile_id=_profile_id_st,
    base_os=_base_os_st,
    lexical_tags=_lexical_tags_st,
    semantic_contexts=_semantic_contexts_st,
  )
  @pytest.mark.asyncio
  async def test_valid_layers_accepted(
    self,
    profile_id: str,
    base_os: BaseOS,
    lexical_tags: list[str],
    semantic_contexts: dict[str, str],
  ) -> None:
    """正しい layer 割り当て (1, 2, 3) の ProfileOutput は例外なく受理される。

    **Validates: Requirements 2.3, 2.4**
    """
    profile = _build_profile(
      profile_id=profile_id,
      base_os=base_os,
      lexical_tags=lexical_tags,
      semantic_contexts=semantic_contexts,
      base_os_layer=1,
      lexical_layer=2,
      semantic_layer=3,
    )
    manager = ContextLayerManager()
    # ValueError が送出されないこと
    await manager.load_profile(profile)


class TestInvalidBaseOsLayer:
  """base_os != 1 のとき ValueError が送出される。"""

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    invalid_layer=st.integers(min_value=-100, max_value=100).filter(lambda x: x != 1),
  )
  @pytest.mark.asyncio
  async def test_invalid_base_os_layer_raises(self, invalid_layer: int) -> None:
    """context_layers.base_os != 1 のとき ValueError が送出される。

    **Validates: Requirements 2.3**
    """
    profile = _build_profile(base_os_layer=invalid_layer)
    manager = ContextLayerManager()
    with pytest.raises(ValueError, match="context_layers.base_os must be 1"):
      await manager.load_profile(profile)


class TestInvalidLexicalLayer:
  """lexical_tags != 2 のとき ValueError が送出される。"""

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    invalid_layer=st.integers(min_value=-100, max_value=100).filter(lambda x: x != 2),
  )
  @pytest.mark.asyncio
  async def test_invalid_lexical_layer_raises(self, invalid_layer: int) -> None:
    """context_layers.lexical_tags != 2 のとき ValueError が送出される。

    **Validates: Requirements 3.6**
    """
    profile = _build_profile(lexical_layer=invalid_layer)
    manager = ContextLayerManager()
    with pytest.raises(ValueError, match="context_layers.lexical_tags must be 2"):
      await manager.load_profile(profile)


class TestInvalidSemanticLayer:
  """semantic_contexts != 3 のとき ValueError が送出される。"""

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    invalid_layer=st.integers(min_value=-100, max_value=100).filter(lambda x: x != 3),
  )
  @pytest.mark.asyncio
  async def test_invalid_semantic_layer_raises(self, invalid_layer: int) -> None:
    """context_layers.semantic_contexts != 3 のとき ValueError が送出される。

    **Validates: Requirements 4.6**
    """
    profile = _build_profile(semantic_layer=invalid_layer)
    manager = ContextLayerManager()
    with pytest.raises(ValueError, match="context_layers.semantic_contexts must be 3"):
      await manager.load_profile(profile)


class TestBaseOsRoundTrip:
  """load_profile 後に get_base_os が同一の BaseOS データを返す。"""

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    profile_id=_profile_id_st,
    base_os=_base_os_st,
    lexical_tags=_lexical_tags_st,
  )
  @pytest.mark.asyncio
  async def test_get_base_os_returns_same_data(
    self,
    profile_id: str,
    base_os: BaseOS,
    lexical_tags: list[str],
  ) -> None:
    """load_profile 後に get_base_os が同一の BaseOS データを返す。

    axes スコア、decision_style、do_not_list がすべて保存・復元される。

    **Validates: Requirements 2.3, 2.4**
    """
    profile = _build_profile(
      profile_id=profile_id,
      base_os=base_os,
      lexical_tags=lexical_tags,
    )
    manager = ContextLayerManager()
    await manager.load_profile(profile)

    result = manager.get_base_os(profile_id)

    # axes の全軸値が一致
    assert result.axes.extroverted_introverted == base_os.axes.extroverted_introverted
    assert result.axes.sensing_intuition == base_os.axes.sensing_intuition
    assert result.axes.thinking_feeling == base_os.axes.thinking_feeling
    assert result.axes.judging_perceiving == base_os.axes.judging_perceiving
    # decision_style が一致
    assert result.decision_style == base_os.decision_style
    # do_not_list が一致
    assert result.do_not_list == base_os.do_not_list


class TestSkillContextMatching:
  """get_skill_context がクエリトークンに一致するタグのみを返す。"""

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    lexical_tags=_lexical_tags_st,
    data=st.data(),
  )
  @pytest.mark.asyncio
  async def test_skill_context_returns_matching_tags_only(
    self,
    lexical_tags: list[str],
    data,
  ) -> None:
    """get_skill_context は function_name + params からクエリを構成し、
    一致するタグのみを返す。返却されたタグはすべてクエリトークンに含まれる。

    **Validates: Requirements 3.6, 4.6**
    """
    profile = _build_profile(lexical_tags=lexical_tags)
    manager = ContextLayerManager()
    await manager.load_profile(profile)

    # lexical_tags からサブセットを選んで function_name / params を構成
    subset_size = data.draw(
      st.integers(min_value=1, max_value=min(3, len(lexical_tags)))
    )
    indices = data.draw(
      st.lists(
        st.integers(min_value=0, max_value=len(lexical_tags) - 1),
        min_size=subset_size,
        max_size=subset_size,
        unique=True,
      )
    )
    selected_tags = [lexical_tags[i] for i in indices]

    # 最初のタグを function_name、残りを params に配置
    function_name = selected_tags[0]
    params = {f"p{i}": tag for i, tag in enumerate(selected_tags[1:])}

    results = await manager.get_skill_context(
      "prof_000001", function_name, params
    )

    # 結果は空でないか、クエリトークンにマッチするタグだけを含む
    # クエリトークンの構築: function_name + params 値を " " で結合 → tokenize
    from app.evolution.lexical_retriever import LexicalRetriever
    query_parts = [function_name] + [str(v) for v in params.values() if v]
    query = " ".join(query_parts)
    retriever = LexicalRetriever(lexical_tags)
    tokens = retriever.tokenize(query)

    # 返却されたすべてのタグが、クエリトークンに一致する
    for tag in results:
      assert tag.lower() in tokens, (
        f"Returned tag '{tag}' does not match any query token: {tokens}"
      )
