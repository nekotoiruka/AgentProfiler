"""Compatibility & Recommendation エンドポイントの統合テスト

httpx AsyncClient を使用し、相性診断・レコメンドエンドポイントの
成功レスポンス (2xx) とエラーレスポンス (404) を検証する。

Validates: Requirements 19.5, 19.6, 20.4, 20.5
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.evolution import dependencies as evo_deps
from app.evolution.agent_manager import AgentManager, AgentRecord
from app.evolution.compatibility import CompatibilityEngine
from app.evolution.context_layer_manager import ContextLayerManager
from app.main import app
from app.models.profile import BaseOS
from app.models.scores import NormalizedScores


# --- テストデータ ---

AGENT_1_ID = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
AGENT_2_ID = "bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb"
AGENT_3_ID = "cccccccc-1111-2222-3333-cccccccccccc"

BASE_OS_1 = BaseOS(
  axes=NormalizedScores(
    extroverted_introverted=0.8,
    sensing_intuition=0.3,
    thinking_feeling=0.9,
    judging_perceiving=0.2,
  ),
  decision_style="analytical_planner",
  do_not_list=["rush decisions"],
)

BASE_OS_2 = BaseOS(
  axes=NormalizedScores(
    extroverted_introverted=0.2,
    sensing_intuition=0.7,
    thinking_feeling=0.1,
    judging_perceiving=0.8,
  ),
  decision_style="intuitive_explorer",
  do_not_list=["ignore details"],
)


def _make_record(agent_id: str, profile_id: str, display_name: str, is_active: bool = True) -> AgentRecord:
  return AgentRecord(
    agent_id=agent_id,
    profile_id=profile_id,
    display_name=display_name,
    created_at="2025-01-01T00:00:00+00:00",
    is_active=is_active,
  )


# --- フィクスチャ ---


@pytest.fixture
def mock_clm():
  """ContextLayerManager のモック"""
  clm = MagicMock(spec=ContextLayerManager)

  def get_base_os_side_effect(profile_id: str):
    if profile_id == "prof_000001":
      return BASE_OS_1
    elif profile_id == "prof_000002":
      return BASE_OS_2
    raise KeyError(f"Profile '{profile_id}' is not loaded")

  clm.get_base_os = MagicMock(side_effect=get_base_os_side_effect)
  return clm


@pytest.fixture
def mock_agent_manager():
  """AgentManager のモック"""
  mgr = AsyncMock(spec=AgentManager)

  record_1 = _make_record(AGENT_1_ID, "prof_000001", "Agent One")
  record_2 = _make_record(AGENT_2_ID, "prof_000002", "Agent Two")

  async def get_side_effect(agent_id: str):
    if agent_id == AGENT_1_ID:
      return record_1
    elif agent_id == AGENT_2_ID:
      return record_2
    return None

  mgr.get = AsyncMock(side_effect=get_side_effect)
  mgr.list_all_active = AsyncMock(return_value=[record_1, record_2])
  return mgr


@pytest.fixture(autouse=True)
def setup_services(mock_clm, mock_agent_manager):
  """Evolution サービスをモックで差し替える。"""
  original_services = evo_deps._services.copy()
  evo_deps._services["context_layer_manager"] = mock_clm
  evo_deps._services["agent_manager"] = mock_agent_manager
  evo_deps._services["compatibility_engine"] = CompatibilityEngine()
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


# --- GET /api/v1/evolution/compatibility/{agent_id_1}/{agent_id_2} ---


class TestCompatibilityEndpoint:
  """相性診断エンドポイントの統合テスト

  Validates: Requirements 19.5, 19.6
  """

  async def test_compatibility_success(self, client: AsyncClient) -> None:
    """2エージェント間の相性レポートが正常に返る。"""
    resp = await client.get(
      f"/api/v1/evolution/compatibility/{AGENT_1_ID}/{AGENT_2_ID}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id_1"] == AGENT_1_ID
    assert body["agent_id_2"] == AGENT_2_ID
    assert "overall_score" in body
    assert 0.0 <= body["overall_score"] <= 100.0
    assert "cosine_similarity" in body
    assert 0.0 <= body["cosine_similarity"] <= 1.0
    assert "complementarity_score" in body
    assert 0.0 <= body["complementarity_score"] <= 1.0
    assert "per_axis_comparison" in body
    assert "classification" in body
    assert body["classification"] in [
      "highly_similar",
      "moderately_similar",
      "complementary",
      "contrasting",
    ]
    assert "relationship_type" in body
    assert "reason" in body
    assert "recommended_interaction_mode" in body

  async def test_compatibility_agent_1_not_found(self, client: AsyncClient, mock_agent_manager) -> None:
    """agent_id_1 が存在しない場合に 404 を返す。"""
    resp = await client.get(
      f"/api/v1/evolution/compatibility/nonexistent-id/{AGENT_2_ID}"
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]

  async def test_compatibility_agent_2_not_found(self, client: AsyncClient, mock_agent_manager) -> None:
    """agent_id_2 が存在しない場合に 404 を返す。"""
    resp = await client.get(
      f"/api/v1/evolution/compatibility/{AGENT_1_ID}/nonexistent-id"
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]

  async def test_compatibility_inactive_agent_404(self, client: AsyncClient, mock_agent_manager) -> None:
    """非アクティブなエージェントで 404 を返す。"""
    inactive_record = _make_record(AGENT_3_ID, "prof_000003", "Inactive", is_active=False)

    async def get_side_effect(agent_id: str):
      if agent_id == AGENT_1_ID:
        return _make_record(AGENT_1_ID, "prof_000001", "Agent One")
      elif agent_id == AGENT_3_ID:
        return inactive_record
      return None

    mock_agent_manager.get = AsyncMock(side_effect=get_side_effect)

    resp = await client.get(
      f"/api/v1/evolution/compatibility/{AGENT_1_ID}/{AGENT_3_ID}"
    )
    assert resp.status_code == 404
    assert "not active" in resp.json()["detail"]

  async def test_compatibility_per_axis_structure(self, client: AsyncClient) -> None:
    """per_axis_comparison が全4軸の比較データを含む。"""
    resp = await client.get(
      f"/api/v1/evolution/compatibility/{AGENT_1_ID}/{AGENT_2_ID}"
    )
    assert resp.status_code == 200
    per_axis = resp.json()["per_axis_comparison"]
    expected_axes = [
      "extroverted_introverted",
      "sensing_intuition",
      "thinking_feeling",
      "judging_perceiving",
    ]
    for axis in expected_axes:
      assert axis in per_axis
      assert "agent_1" in per_axis[axis]
      assert "agent_2" in per_axis[axis]
      assert "diff" in per_axis[axis]


# --- GET /api/v1/evolution/agents/{agent_id}/recommendations ---


class TestRecommendationsEndpoint:
  """レコメンドエンドポイントの統合テスト

  Validates: Requirements 20.4, 20.5
  """

  async def test_recommendations_success(self, client: AsyncClient) -> None:
    """正常にレコメンドが返る（2体以上アクティブ）。"""
    resp = await client.get(
      f"/api/v1/evolution/agents/{AGENT_1_ID}/recommendations"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == AGENT_1_ID
    assert "most_heated_debate" in body
    assert "business_partner" in body
    assert isinstance(body["most_heated_debate"], list)
    assert isinstance(body["business_partner"], list)

  async def test_recommendations_contains_scores(self, client: AsyncClient) -> None:
    """各レコメンドに score と explanation が含まれる。"""
    resp = await client.get(
      f"/api/v1/evolution/agents/{AGENT_1_ID}/recommendations"
    )
    assert resp.status_code == 200
    body = resp.json()
    for category in ["most_heated_debate", "business_partner"]:
      for rec in body[category]:
        assert "agent_id" in rec
        assert "display_name" in rec
        assert "score" in rec
        assert "explanation" in rec

  async def test_recommendations_agent_not_found_404(self, client: AsyncClient, mock_agent_manager) -> None:
    """存在しないエージェントで 404 を返す。"""
    resp = await client.get(
      "/api/v1/evolution/agents/nonexistent-id/recommendations"
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]

  async def test_recommendations_less_than_2_agents(self, client: AsyncClient, mock_agent_manager) -> None:
    """アクティブエージェントが2体未満の場合に空レコメンド + メッセージを返す。"""
    # 1体のみアクティブ
    mock_agent_manager.list_all_active = AsyncMock(
      return_value=[_make_record(AGENT_1_ID, "prof_000001", "Agent One")]
    )

    resp = await client.get(
      f"/api/v1/evolution/agents/{AGENT_1_ID}/recommendations"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["most_heated_debate"] == []
    assert body["business_partner"] == []
    assert "message" in body

  async def test_recommendations_inactive_agent_404(self, client: AsyncClient, mock_agent_manager) -> None:
    """非アクティブなエージェントで 404 を返す。"""
    async def get_side_effect(agent_id: str):
      if agent_id == AGENT_3_ID:
        return _make_record(AGENT_3_ID, "prof_000003", "Inactive", is_active=False)
      return None

    mock_agent_manager.get = AsyncMock(side_effect=get_side_effect)

    resp = await client.get(
      f"/api/v1/evolution/agents/{AGENT_3_ID}/recommendations"
    )
    assert resp.status_code == 404
    assert "not active" in resp.json()["detail"]
