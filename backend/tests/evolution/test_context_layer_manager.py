"""ContextLayerManager のユニットテスト

Layer 1/2/3 の初期化・検索・フォールバック動作を検証する。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.semantic_retriever import SemanticResult
from app.models.profile import (
  BaseOS,
  ContextLayers,
  ProfileOutput,
)
from app.models.scores import NormalizedScores


def _make_profile(
  profile_id: str = "prof_000001",
  base_os_layer: int = 1,
  lexical_layer: int = 2,
  semantic_layer: int = 3,
) -> ProfileOutput:
  """テスト用 ProfileOutput を生成する。"""
  return ProfileOutput(
    profile_id=profile_id,
    base_os=BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.7,
        sensing_intuition=0.4,
        thinking_feeling=0.8,
        judging_perceiving=0.3,
      ),
      decision_style="analytical_planner",
      do_not_list=["rush decisions", "skip reviews"],
    ),
    lexical_tags=["python", "fastapi", "vue", "docker", "typescript"],
    semantic_contexts={
      "problem_solving": "分析的にアプローチし段階的に解決する",
      "communication_style": "論理的で簡潔な表現を好む",
    },
    context_layers=ContextLayers(
      base_os=base_os_layer,
      lexical_tags=lexical_layer,
      semantic_contexts=semantic_layer,
    ),
  )


@pytest.fixture
def manager() -> ContextLayerManager:
  """デフォルト ContextLayerManager（SemanticRetriever なし）。"""
  return ContextLayerManager()


@pytest.fixture
def manager_with_semantic() -> ContextLayerManager:
  """SemanticRetriever モック付き ContextLayerManager。"""
  mock_retriever = AsyncMock()
  mock_retriever.index_profile = AsyncMock()
  mock_retriever.search = AsyncMock(return_value=[])
  return ContextLayerManager(semantic_retriever=mock_retriever)


class TestLoadProfile:
  """load_profile() のテスト"""

  @pytest.mark.asyncio
  async def test_load_profile_success(self, manager: ContextLayerManager) -> None:
    """正常な ProfileOutput をロードできること。"""
    profile = _make_profile()
    await manager.load_profile(profile)

    # Layer 1: Base OS がキャッシュされている
    assert manager.get_base_os("prof_000001") == profile.base_os

  @pytest.mark.asyncio
  async def test_load_profile_invalid_base_os_layer(
    self, manager: ContextLayerManager
  ) -> None:
    """base_os が Layer 1 以外の場合は ValueError。"""
    profile = _make_profile(base_os_layer=2)
    with pytest.raises(ValueError, match="context_layers.base_os must be 1"):
      await manager.load_profile(profile)

  @pytest.mark.asyncio
  async def test_load_profile_invalid_lexical_layer(
    self, manager: ContextLayerManager
  ) -> None:
    """lexical_tags が Layer 2 以外の場合は ValueError。"""
    profile = _make_profile(lexical_layer=1)
    with pytest.raises(ValueError, match="context_layers.lexical_tags must be 2"):
      await manager.load_profile(profile)

  @pytest.mark.asyncio
  async def test_load_profile_invalid_semantic_layer(
    self, manager: ContextLayerManager
  ) -> None:
    """semantic_contexts が Layer 3 以外の場合は ValueError。"""
    profile = _make_profile(semantic_layer=1)
    with pytest.raises(ValueError, match="context_layers.semantic_contexts must be 3"):
      await manager.load_profile(profile)

  @pytest.mark.asyncio
  async def test_load_profile_indexes_semantic_retriever(
    self, manager_with_semantic: ContextLayerManager
  ) -> None:
    """SemanticRetriever が設定されていれば index_profile が呼ばれる。"""
    profile = _make_profile()
    await manager_with_semantic.load_profile(profile)
    manager_with_semantic._semantic_retriever.index_profile.assert_called_once_with(
      "prof_000001", profile.semantic_contexts
    )


class TestGetBaseOS:
  """get_base_os() のテスト"""

  @pytest.mark.asyncio
  async def test_get_base_os_returns_cached_data(
    self, manager: ContextLayerManager
  ) -> None:
    """ロード済みの Base OS データを返すこと。"""
    profile = _make_profile()
    await manager.load_profile(profile)
    base_os = manager.get_base_os("prof_000001")
    assert base_os.decision_style == "analytical_planner"
    assert base_os.do_not_list == ["rush decisions", "skip reviews"]

  def test_get_base_os_raises_key_error_for_unloaded(
    self, manager: ContextLayerManager
  ) -> None:
    """未ロードの profile_id で KeyError が送出されること。"""
    with pytest.raises(KeyError, match="Profile 'prof_999999' is not loaded"):
      manager.get_base_os("prof_999999")

  @pytest.mark.asyncio
  async def test_base_os_cache_shared_across_calls(
    self, manager: ContextLayerManager
  ) -> None:
    """同一 profile_id の Base OS はキャッシュ共有（同一オブジェクト）。"""
    profile = _make_profile()
    await manager.load_profile(profile)
    os1 = manager.get_base_os("prof_000001")
    os2 = manager.get_base_os("prof_000001")
    # 同じインメモリオブジェクトが返される（再フェッチしない）
    assert os1 is os2


class TestGetSkillContext:
  """get_skill_context() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_matching_tags(
    self, manager: ContextLayerManager
  ) -> None:
    """function_name / params がタグと一致する場合にタグを返す。"""
    profile = _make_profile()
    await manager.load_profile(profile)
    # "python" は lexical_tags に含まれる
    results = await manager.get_skill_context(
      "prof_000001", "python", {"lang": "fastapi"}
    )
    assert "python" in results
    assert "fastapi" in results

  @pytest.mark.asyncio
  async def test_returns_empty_for_no_match(
    self, manager: ContextLayerManager
  ) -> None:
    """マッチするタグがない場合は空リスト。"""
    profile = _make_profile()
    await manager.load_profile(profile)
    results = await manager.get_skill_context(
      "prof_000001", "unknown_func", {"x": "nonexistent"}
    )
    assert results == []

  @pytest.mark.asyncio
  async def test_returns_empty_for_unloaded_profile(
    self, manager: ContextLayerManager
  ) -> None:
    """未ロードの profile_id では空リスト。"""
    results = await manager.get_skill_context(
      "prof_999999", "func", {"a": "b"}
    )
    assert results == []

  @pytest.mark.asyncio
  async def test_skips_falsy_param_values(
    self, manager: ContextLayerManager
  ) -> None:
    """空文字列や None のパラメータ値はクエリに含まれない。"""
    profile = _make_profile()
    await manager.load_profile(profile)
    results = await manager.get_skill_context(
      "prof_000001", "python", {"a": "", "b": None, "c": 0}
    )
    # "python" は function_name から一致
    assert "python" in results


class TestGetSemanticContext:
  """get_semantic_context() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_local_fallback_without_retriever(
    self, manager: ContextLayerManager
  ) -> None:
    """SemanticRetriever 未設定時はローカルデータを全件返す。"""
    profile = _make_profile()
    await manager.load_profile(profile)
    result = await manager.get_semantic_context("prof_000001", "problem solving")
    assert "problem_solving" in result
    assert "communication_style" in result

  @pytest.mark.asyncio
  async def test_returns_semantic_retriever_results(
    self, manager_with_semantic: ContextLayerManager
  ) -> None:
    """SemanticRetriever の検索結果を domain → text 辞書で返す。"""
    # モックの search が結果を返すよう設定
    manager_with_semantic._semantic_retriever.search = AsyncMock(
      return_value=[
        SemanticResult(domain="problem_solving", text="分析的アプローチ", score=0.95),
      ]
    )
    profile = _make_profile()
    await manager_with_semantic.load_profile(profile)
    result = await manager_with_semantic.get_semantic_context(
      "prof_000001", "problem solving"
    )
    assert result == {"problem_solving": "分析的アプローチ"}

  @pytest.mark.asyncio
  async def test_fallback_on_timeout(self) -> None:
    """SemanticRetriever がタイムアウトした場合はローカルフォールバック。"""
    mock_retriever = AsyncMock()
    mock_retriever.index_profile = AsyncMock()

    async def slow_search(*args, **kwargs):
      await asyncio.sleep(10)  # タイムアウトより長い
      return []

    mock_retriever.search = slow_search
    mgr = ContextLayerManager(semantic_retriever=mock_retriever, mcp_timeout=0.01)
    profile = _make_profile()
    await mgr.load_profile(profile)

    result = await mgr.get_semantic_context("prof_000001", "anything")
    # ローカルフォールバックが返される
    assert "problem_solving" in result
    assert "communication_style" in result

  @pytest.mark.asyncio
  async def test_fallback_on_retriever_error(self) -> None:
    """SemanticRetriever がエラーを返した場合はローカルフォールバック。"""
    mock_retriever = AsyncMock()
    mock_retriever.index_profile = AsyncMock()
    mock_retriever.search = AsyncMock(side_effect=RuntimeError("API error"))
    mgr = ContextLayerManager(semantic_retriever=mock_retriever)
    profile = _make_profile()
    await mgr.load_profile(profile)

    result = await mgr.get_semantic_context("prof_000001", "query")
    assert "problem_solving" in result

  @pytest.mark.asyncio
  async def test_returns_empty_for_unloaded_profile(
    self, manager: ContextLayerManager
  ) -> None:
    """未ロードの profile_id では空辞書。"""
    result = await manager.get_semantic_context("prof_999999", "query")
    assert result == {}

  @pytest.mark.asyncio
  async def test_fallback_when_retriever_returns_empty(
    self, manager_with_semantic: ContextLayerManager
  ) -> None:
    """SemanticRetriever が空結果を返した場合はローカルフォールバック。"""
    manager_with_semantic._semantic_retriever.search = AsyncMock(return_value=[])
    profile = _make_profile()
    await manager_with_semantic.load_profile(profile)
    result = await manager_with_semantic.get_semantic_context(
      "prof_000001", "query"
    )
    # 空結果 → ローカルフォールバック
    assert "problem_solving" in result


class TestCacheSharing:
  """複数プロファイル間のキャッシュ独立性テスト"""

  @pytest.mark.asyncio
  async def test_multiple_profiles_independent(self) -> None:
    """異なる profile_id のキャッシュは独立していること。"""
    mgr = ContextLayerManager()
    profile1 = _make_profile(profile_id="prof_000001")
    profile2 = ProfileOutput(
      profile_id="prof_000002",
      base_os=BaseOS(
        axes=NormalizedScores(
          extroverted_introverted=0.2,
          sensing_intuition=0.9,
          thinking_feeling=0.5,
          judging_perceiving=0.6,
        ),
        decision_style="intuitive_explorer",
        do_not_list=["rigid plans"],
      ),
      lexical_tags=["react", "nodejs", "graphql", "aws", "rust"],
      semantic_contexts={
        "creativity": "直感的に発想し実験を重ねる",
      },
      context_layers=ContextLayers(base_os=1, lexical_tags=2, semantic_contexts=3),
    )

    await mgr.load_profile(profile1)
    await mgr.load_profile(profile2)

    # 各プロファイルの Base OS が独立
    os1 = mgr.get_base_os("prof_000001")
    os2 = mgr.get_base_os("prof_000002")
    assert os1.decision_style == "analytical_planner"
    assert os2.decision_style == "intuitive_explorer"

    # Layer 2: 各プロファイル固有のタグが検索可能
    r1 = await mgr.get_skill_context("prof_000001", "python", {})
    r2 = await mgr.get_skill_context("prof_000002", "react", {})
    assert "python" in r1
    assert "react" in r2

    # Layer 3: ローカルデータが独立
    s1 = await mgr.get_semantic_context("prof_000001", "solving")
    s2 = await mgr.get_semantic_context("prof_000002", "creativity")
    assert "problem_solving" in s1
    assert "creativity" in s2
    assert "creativity" not in s1
