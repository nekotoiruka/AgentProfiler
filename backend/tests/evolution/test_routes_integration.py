"""Evolution REST API 統合テスト

httpx AsyncClient を使用し、全 Evolution エンドポイントの
成功レスポンス (2xx) とエラーレスポンス (404, 422) を検証する。

Validates: Requirements 11.7, 11.8
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.evolution import dependencies as evo_deps
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.routing_engine import Complexity
from app.evolution.semantic_cache import SemanticCache
from app.main import app


# --- テストデータ ---

VALID_PROFILE_PAYLOAD = {
  "profile_id": "prof_000001",
  "base_os": {
    "axes": {
      "extroverted_introverted": 0.7,
      "sensing_intuition": 0.4,
      "thinking_feeling": 0.8,
      "judging_perceiving": 0.3,
    },
    "decision_style": "analytical_planner",
    "do_not_list": ["rush decisions", "skip reviews"],
  },
  "lexical_tags": ["python", "fastapi", "vue", "docker", "typescript"],
  "semantic_contexts": {
    "problem_solving": "分析的にアプローチし段階的に解決する",
  },
  "context_layers": {"base_os": 1, "lexical_tags": 2, "semantic_contexts": 3},
}


# --- フィクスチャ ---


@pytest.fixture
def mock_clm():
  """ContextLayerManager のモック"""
  clm = MagicMock(spec=ContextLayerManager)
  clm.load_profile = AsyncMock()
  clm.get_skill_context = AsyncMock(return_value=["python", "fastapi"])
  clm._lexical_retrievers = {}
  return clm


@pytest.fixture
def mock_cache():
  """SemanticCache のモック"""
  cache = AsyncMock(spec=SemanticCache)
  cache.lookup = AsyncMock(return_value=None)
  cache.store = AsyncMock()
  cache.get_stats = AsyncMock(
    return_value={"total_entries": 5, "hit_rate": 0.4, "avg_similarity": 0.85}
  )
  cache.invalidate = AsyncMock(return_value=3)
  return cache


@pytest.fixture
def mock_routing():
  """RoutingEngine のモック"""
  routing = MagicMock()
  routing.classify = MagicMock(return_value=Complexity.LIGHT)
  routing.route = AsyncMock(return_value="LLM の応答テキスト")
  return routing


@pytest.fixture
def mock_prompt_engine():
  """PromptEngine のモック"""
  engine = MagicMock()
  engine.generate = MagicMock(return_value="Generated system prompt")
  return engine


@pytest.fixture(autouse=True)
def setup_services(mock_clm, mock_cache, mock_routing, mock_prompt_engine):
  """Evolution サービスをモックで差し替える。

  テストごとに _services を上書きし、テスト後にクリアする。
  """
  original_services = evo_deps._services.copy()
  evo_deps._services["context_layer_manager"] = mock_clm
  evo_deps._services["semantic_cache"] = mock_cache
  evo_deps._services["routing_engine"] = mock_routing
  evo_deps._services["prompt_engine"] = mock_prompt_engine
  evo_deps._services["settings"] = MagicMock()
  yield
  evo_deps._services.clear()
  evo_deps._services.update(original_services)


@pytest.fixture
async def client():
  """httpx AsyncClient (ASGI transport)"""
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    yield ac


# --- POST /api/v1/evolution/profiles ---


class TestLoadProfile:
  """POST /profiles エンドポイントの統合テスト"""

  async def test_load_profile_success(self, client: AsyncClient) -> None:
    """正常な ProfileOutput でプロファイルロードが成功する。"""
    resp = await client.post(
      "/api/v1/evolution/profiles", json=VALID_PROFILE_PAYLOAD
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile_id"] == "prof_000001"
    assert body["status"] == "loaded"
    assert "timestamp" in body

  async def test_load_profile_validation_error_invalid_profile_id(
    self, client: AsyncClient
  ) -> None:
    """profile_id フォーマット不正で 422 を返す。"""
    payload = {**VALID_PROFILE_PAYLOAD, "profile_id": "invalid_id"}
    resp = await client.post("/api/v1/evolution/profiles", json=payload)
    assert resp.status_code == 422

  async def test_load_profile_validation_error_missing_field(
    self, client: AsyncClient
  ) -> None:
    """必須フィールド欠落で 422 を返す。"""
    payload = {**VALID_PROFILE_PAYLOAD}
    del payload["base_os"]
    resp = await client.post("/api/v1/evolution/profiles", json=payload)
    assert resp.status_code == 422

  async def test_load_profile_evolution_validation_error(
    self, client: AsyncClient, mock_clm
  ) -> None:
    """lexical_tags 不足で Evolution 固有バリデーションエラー (422)。"""
    payload = {
      **VALID_PROFILE_PAYLOAD,
      "lexical_tags": ["a", "b", "c", "d", "e"],
      "semantic_contexts": {"ps": "short"},  # 10文字未満 → バリデーションエラー
    }
    resp = await client.post("/api/v1/evolution/profiles", json=payload)
    assert resp.status_code == 422


# --- POST /api/v1/evolution/search ---


class TestHybridSearch:
  """POST /search エンドポイントの統合テスト"""

  async def test_search_success(self, client: AsyncClient, mock_clm) -> None:
    """ロード済みプロファイルに対してハイブリッド検索が成功する。"""
    # get_base_os が成功するように設定（プロファイルがロード済みを模倣）
    from app.models.profile import BaseOS
    from app.models.scores import NormalizedScores

    base_os = BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.7,
        sensing_intuition=0.4,
        thinking_feeling=0.8,
        judging_perceiving=0.3,
      ),
      decision_style="analytical_planner",
      do_not_list=["rush decisions", "skip reviews"],
    )
    mock_clm.get_base_os.return_value = base_os

    # LexicalRetriever のモックを設定
    mock_lexical = MagicMock()
    mock_lexical.search.return_value = ["python"]
    mock_clm._lexical_retrievers = {"prof_000001": mock_lexical}

    # SemanticRetriever モックを DI
    mock_semantic_retriever = AsyncMock()
    mock_semantic_retriever.search = AsyncMock(return_value=[])
    evo_deps._services["semantic_retriever"] = mock_semantic_retriever

    payload = {"query": "python web framework", "profile_id": "prof_000001"}
    resp = await client.post("/api/v1/evolution/search", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body

  async def test_search_unloaded_profile_404(
    self, client: AsyncClient, mock_clm
  ) -> None:
    """未ロードプロファイルで 404 を返す。"""
    mock_clm.get_base_os.side_effect = KeyError("Profile 'prof_000099' is not loaded")

    payload = {"query": "anything", "profile_id": "prof_000099"}
    resp = await client.post("/api/v1/evolution/search", json=payload)
    assert resp.status_code == 404
    assert "not loaded" in resp.json()["detail"]


# --- POST /api/v1/evolution/infer ---


class TestInfer:
  """POST /infer エンドポイントの統合テスト"""

  async def test_infer_unloaded_profile_404(
    self, client: AsyncClient, mock_clm
  ) -> None:
    """未ロードプロファイルで 404 を返す。"""
    mock_clm.get_base_os.side_effect = KeyError("Profile 'prof_000099' is not loaded")

    payload = {"profile_id": "prof_000099", "utterance": "hello"}
    resp = await client.post("/api/v1/evolution/infer", json=payload)
    assert resp.status_code == 404
    assert "not loaded" in resp.json()["detail"]

  async def test_infer_success_cache_miss(
    self, client: AsyncClient, mock_clm, mock_cache, mock_routing
  ) -> None:
    """キャッシュミス時に LLM ルーティングが実行される。"""
    from app.models.profile import BaseOS
    from app.models.scores import NormalizedScores

    base_os = BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.7,
        sensing_intuition=0.4,
        thinking_feeling=0.8,
        judging_perceiving=0.3,
      ),
      decision_style="analytical_planner",
      do_not_list=["rush decisions", "skip reviews"],
    )
    mock_clm.get_base_os.return_value = base_os
    mock_cache.lookup.return_value = None
    mock_routing.route.return_value = "LLM response text"

    payload = {"profile_id": "prof_000001", "utterance": "Pythonの特徴を教えて"}
    resp = await client.post("/api/v1/evolution/infer", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "LLM response text"
    assert body["cache_hit"] is False
    assert body["complexity"] in ("light", "deep")

  async def test_infer_success_cache_hit(
    self, client: AsyncClient, mock_clm, mock_cache, mock_routing
  ) -> None:
    """キャッシュヒット時はキャッシュされたレスポンスを返す。"""
    from app.models.profile import BaseOS
    from app.models.scores import NormalizedScores

    base_os = BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.7,
        sensing_intuition=0.4,
        thinking_feeling=0.8,
        judging_perceiving=0.3,
      ),
      decision_style="analytical_planner",
      do_not_list=["rush decisions", "skip reviews"],
    )
    mock_clm.get_base_os.return_value = base_os
    mock_cache.lookup.return_value = "cached response"

    payload = {"profile_id": "prof_000001", "utterance": "hello"}
    resp = await client.post("/api/v1/evolution/infer", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "cached response"
    assert body["cache_hit"] is True


# --- GET /api/v1/evolution/profiles/{profile_id}/prompt ---


class TestGetPrompt:
  """GET /profiles/{profile_id}/prompt エンドポイントの統合テスト"""

  async def test_get_prompt_success(
    self, client: AsyncClient, mock_clm
  ) -> None:
    """ロード済みプロファイルのプロンプト取得が成功する。"""
    from app.models.profile import BaseOS
    from app.models.scores import NormalizedScores

    base_os = BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.7,
        sensing_intuition=0.4,
        thinking_feeling=0.8,
        judging_perceiving=0.3,
      ),
      decision_style="analytical_planner",
      do_not_list=["rush decisions", "skip reviews"],
    )
    mock_clm.get_base_os.return_value = base_os

    resp = await client.get("/api/v1/evolution/profiles/prof_000001/prompt")
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile_id"] == "prof_000001"
    assert "prompt" in body
    # プロンプトにパーソナリティ情報が含まれる
    assert "analytical_planner" in body["prompt"]
    assert "rush decisions" in body["prompt"]

  async def test_get_prompt_unloaded_profile_404(
    self, client: AsyncClient, mock_clm
  ) -> None:
    """未ロードプロファイルで 404 を返す。"""
    mock_clm.get_base_os.side_effect = KeyError(
      "Profile 'prof_000099' is not loaded"
    )

    resp = await client.get("/api/v1/evolution/profiles/prof_000099/prompt")
    assert resp.status_code == 404
    assert "not loaded" in resp.json()["detail"]


# --- GET /api/v1/evolution/profiles/{profile_id}/cache/stats ---


class TestGetCacheStats:
  """GET /profiles/{profile_id}/cache/stats エンドポイントの統合テスト"""

  async def test_get_cache_stats_success(
    self, client: AsyncClient, mock_clm, mock_cache
  ) -> None:
    """ロード済みプロファイルのキャッシュ統計取得が成功する。"""
    from app.models.profile import BaseOS
    from app.models.scores import NormalizedScores

    base_os = BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.7,
        sensing_intuition=0.4,
        thinking_feeling=0.8,
        judging_perceiving=0.3,
      ),
      decision_style="analytical_planner",
      do_not_list=["rush decisions", "skip reviews"],
    )
    mock_clm.get_base_os.return_value = base_os

    resp = await client.get("/api/v1/evolution/profiles/prof_000001/cache/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_entries"] == 5
    assert body["hit_rate"] == 0.4
    assert body["avg_similarity"] == 0.85

  async def test_get_cache_stats_unloaded_profile_404(
    self, client: AsyncClient, mock_clm
  ) -> None:
    """未ロードプロファイルで 404 を返す。"""
    mock_clm.get_base_os.side_effect = KeyError(
      "Profile 'prof_000099' is not loaded"
    )

    resp = await client.get("/api/v1/evolution/profiles/prof_000099/cache/stats")
    assert resp.status_code == 404
    assert "not loaded" in resp.json()["detail"]


# --- DELETE /api/v1/evolution/profiles/{profile_id}/cache ---


class TestInvalidateCache:
  """DELETE /profiles/{profile_id}/cache エンドポイントの統合テスト"""

  async def test_invalidate_cache_success(
    self, client: AsyncClient, mock_clm, mock_cache
  ) -> None:
    """ロード済みプロファイルのキャッシュ削除が成功する。"""
    from app.models.profile import BaseOS
    from app.models.scores import NormalizedScores

    base_os = BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.7,
        sensing_intuition=0.4,
        thinking_feeling=0.8,
        judging_perceiving=0.3,
      ),
      decision_style="analytical_planner",
      do_not_list=["rush decisions", "skip reviews"],
    )
    mock_clm.get_base_os.return_value = base_os

    resp = await client.delete("/api/v1/evolution/profiles/prof_000001/cache")
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile_id"] == "prof_000001"
    assert body["deleted_entries"] == 3
    assert body["status"] == "invalidated"

  async def test_invalidate_cache_unloaded_profile_404(
    self, client: AsyncClient, mock_clm
  ) -> None:
    """未ロードプロファイルで 404 を返す。"""
    mock_clm.get_base_os.side_effect = KeyError(
      "Profile 'prof_000099' is not loaded"
    )

    resp = await client.delete("/api/v1/evolution/profiles/prof_000099/cache")
    assert resp.status_code == 404
    assert "not loaded" in resp.json()["detail"]
