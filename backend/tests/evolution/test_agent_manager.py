"""AgentManager のユニットテスト

SQLite ベースの CRUD 操作、profile_id バリデーション、
ソフトデリートの動作を検証する。
"""

import uuid
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from app.evolution.agent_manager import AgentManager, AgentRecord
from app.evolution.context_layer_manager import ContextLayerManager


@pytest_asyncio.fixture
async def db_path(tmp_path) -> str:
  """テスト用の一時 DB パスを返す。"""
  return str(tmp_path / "test_evolution.db")


@pytest_asyncio.fixture
async def mock_clm() -> ContextLayerManager:
  """ContextLayerManager のモック。get_base_os が正常に返る。"""
  clm = MagicMock(spec=ContextLayerManager)
  clm.get_base_os = MagicMock(return_value=MagicMock())
  return clm


@pytest_asyncio.fixture
async def mock_clm_no_profile() -> ContextLayerManager:
  """ContextLayerManager のモック。get_base_os が KeyError を送出する。"""
  clm = MagicMock(spec=ContextLayerManager)
  clm.get_base_os = MagicMock(
    side_effect=KeyError("Profile 'prof_999999' is not loaded")
  )
  return clm


@pytest_asyncio.fixture
async def manager(db_path: str, mock_clm: ContextLayerManager) -> AgentManager:
  """初期化済み AgentManager を返す。"""
  mgr = AgentManager(db_path=db_path, context_layer_manager=mock_clm)
  await mgr.init_db()
  return mgr


@pytest_asyncio.fixture
async def manager_no_clm(db_path: str) -> AgentManager:
  """ContextLayerManager なしの AgentManager を返す。"""
  mgr = AgentManager(db_path=db_path, context_layer_manager=None)
  await mgr.init_db()
  return mgr


class TestInitDb:
  """init_db() のテスト"""

  @pytest.mark.asyncio
  async def test_creates_agents_table(self, db_path: str) -> None:
    """agents テーブルが正常に作成されること。"""
    mgr = AgentManager(db_path=db_path)
    await mgr.init_db()
    # 2回目の呼び出しもエラーにならない (IF NOT EXISTS)
    await mgr.init_db()

  @pytest.mark.asyncio
  async def test_idempotent_init(self, manager: AgentManager) -> None:
    """init_db() を複数回呼んでもエラーにならないこと。"""
    await manager.init_db()
    await manager.init_db()


class TestCreate:
  """create() のテスト"""

  @pytest.mark.asyncio
  async def test_creates_agent_record(self, manager: AgentManager) -> None:
    """エージェントレコードが正常に作成されること。"""
    record = await manager.create("prof_000001", "Test Agent")
    assert record.profile_id == "prof_000001"
    assert record.display_name == "Test Agent"
    assert record.is_active is True
    # agent_id は UUID v4 形式
    uuid.UUID(record.agent_id, version=4)
    # created_at は ISO 8601 形式
    assert "T" in record.created_at

  @pytest.mark.asyncio
  async def test_creates_unique_agent_ids(self, manager: AgentManager) -> None:
    """複数エージェント作成時に一意の agent_id が生成されること。"""
    r1 = await manager.create("prof_000001", "Agent 1")
    r2 = await manager.create("prof_000001", "Agent 2")
    assert r1.agent_id != r2.agent_id

  @pytest.mark.asyncio
  async def test_multiple_agents_per_profile(self, manager: AgentManager) -> None:
    """1つの profile_id に複数のエージェントを紐付けられること。"""
    await manager.create("prof_000001", "Agent A")
    await manager.create("prof_000001", "Agent B")
    await manager.create("prof_000001", "Agent C")
    agents = await manager.list_active("prof_000001")
    assert len(agents) == 3

  @pytest.mark.asyncio
  async def test_rejects_unloaded_profile(
    self, db_path: str, mock_clm_no_profile: ContextLayerManager
  ) -> None:
    """未ロードの profile_id で ValueError が送出されること。"""
    mgr = AgentManager(
      db_path=db_path, context_layer_manager=mock_clm_no_profile
    )
    await mgr.init_db()
    with pytest.raises(ValueError, match="Profile .* is not loaded"):
      await mgr.create("prof_999999", "Should Fail")

  @pytest.mark.asyncio
  async def test_creates_without_clm(self, manager_no_clm: AgentManager) -> None:
    """ContextLayerManager なしでもエージェント作成可能。"""
    record = await manager_no_clm.create("prof_000001", "No CLM Agent")
    assert record.profile_id == "prof_000001"
    assert record.is_active is True


class TestGet:
  """get() のテスト"""

  @pytest.mark.asyncio
  async def test_get_existing_agent(self, manager: AgentManager) -> None:
    """存在するエージェントを取得できること。"""
    created = await manager.create("prof_000001", "My Agent")
    fetched = await manager.get(created.agent_id)
    assert fetched is not None
    assert fetched.agent_id == created.agent_id
    assert fetched.profile_id == "prof_000001"
    assert fetched.display_name == "My Agent"
    assert fetched.is_active is True

  @pytest.mark.asyncio
  async def test_get_nonexistent_agent(self, manager: AgentManager) -> None:
    """存在しない agent_id では None が返ること。"""
    result = await manager.get("nonexistent-id")
    assert result is None


class TestListActive:
  """list_active() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_active_agents_only(self, manager: AgentManager) -> None:
    """is_active=True のエージェントのみ返すこと。"""
    r1 = await manager.create("prof_000001", "Active Agent")
    r2 = await manager.create("prof_000001", "Deleted Agent")
    await manager.soft_delete(r2.agent_id)

    agents = await manager.list_active("prof_000001")
    assert len(agents) == 1
    assert agents[0].agent_id == r1.agent_id

  @pytest.mark.asyncio
  async def test_filters_by_profile_id(self, manager: AgentManager) -> None:
    """指定 profile_id のエージェントのみ返すこと。"""
    # mock_clm はどの profile_id でも成功するので両方作成可能
    await manager.create("prof_000001", "Profile 1 Agent")
    await manager.create("prof_000002", "Profile 2 Agent")

    agents_1 = await manager.list_active("prof_000001")
    agents_2 = await manager.list_active("prof_000002")
    assert len(agents_1) == 1
    assert len(agents_2) == 1
    assert agents_1[0].display_name == "Profile 1 Agent"
    assert agents_2[0].display_name == "Profile 2 Agent"

  @pytest.mark.asyncio
  async def test_returns_empty_for_no_agents(self, manager: AgentManager) -> None:
    """エージェント未作成の profile_id では空リストが返ること。"""
    agents = await manager.list_active("prof_000099")
    assert agents == []


class TestUpdateDisplayName:
  """update_display_name() のテスト"""

  @pytest.mark.asyncio
  async def test_updates_display_name(self, manager: AgentManager) -> None:
    """表示名が正常に更新されること。"""
    created = await manager.create("prof_000001", "Old Name")
    updated = await manager.update_display_name(created.agent_id, "New Name")
    assert updated.display_name == "New Name"
    assert updated.agent_id == created.agent_id

  @pytest.mark.asyncio
  async def test_raises_for_nonexistent_agent(self, manager: AgentManager) -> None:
    """存在しない agent_id で ValueError が送出されること。"""
    with pytest.raises(ValueError, match="Agent .* not found"):
      await manager.update_display_name("nonexistent-id", "Name")


class TestSoftDelete:
  """soft_delete() のテスト"""

  @pytest.mark.asyncio
  async def test_sets_is_active_false(self, manager: AgentManager) -> None:
    """ソフトデリート後に is_active=False になること。"""
    created = await manager.create("prof_000001", "To Delete")
    await manager.soft_delete(created.agent_id)

    record = await manager.get(created.agent_id)
    assert record is not None
    assert record.is_active is False

  @pytest.mark.asyncio
  async def test_raises_for_nonexistent_agent(self, manager: AgentManager) -> None:
    """存在しない agent_id で ValueError が送出されること。"""
    with pytest.raises(ValueError, match="Agent .* not found"):
      await manager.soft_delete("nonexistent-id")

  @pytest.mark.asyncio
  async def test_deleted_agent_not_in_active_list(
    self, manager: AgentManager
  ) -> None:
    """ソフトデリートされたエージェントは list_active に含まれないこと。"""
    r1 = await manager.create("prof_000001", "Agent Keep")
    r2 = await manager.create("prof_000001", "Agent Remove")
    await manager.soft_delete(r2.agent_id)

    agents = await manager.list_active("prof_000001")
    agent_ids = [a.agent_id for a in agents]
    assert r1.agent_id in agent_ids
    assert r2.agent_id not in agent_ids
