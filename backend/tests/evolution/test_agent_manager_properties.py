"""AgentManager プロパティベーステスト

Feature: agent-evolution
Property 22: Agent ID uniqueness and multi-agent ownership
Property 23: Agent CRUD round-trip
Property 24: Active agents filter
Validates: Requirements 16.1, 16.3, 16.4, 16.7
"""

import uuid
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.evolution.agent_manager import AgentManager, AgentRecord
from app.evolution.context_layer_manager import ContextLayerManager


# --- Hypothesis ストラテジー ---

# profile_id: "prof_" + 6桁
_profile_id_st = st.from_regex(r"prof_[0-9]{6}", fullmatch=True)

# display_name: 1〜30文字（英数字・かな・漢字含む表示名）
_display_name_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
  min_size=1,
  max_size=30,
).filter(lambda s: s.strip() != "")

# エージェント作成数 (2〜10)
_num_agents_st = st.integers(min_value=2, max_value=10)


# --- ヘルパー ---


def _make_mock_clm() -> ContextLayerManager:
  """ContextLayerManager のモック。get_base_os が正常に返る。"""
  clm = MagicMock(spec=ContextLayerManager)
  clm.get_base_os = MagicMock(return_value=MagicMock())
  return clm


async def _create_manager(tmp_path) -> AgentManager:
  """テスト用 AgentManager を構築する。

  各呼び出しで一意の DB ファイルを使用し、example 間の衝突を回避する。
  """
  db_path = str(tmp_path / f"evolution_{uuid.uuid4().hex}.db")
  clm = _make_mock_clm()
  mgr = AgentManager(db_path=db_path, context_layer_manager=clm)
  await mgr.init_db()
  return mgr


# =============================================================================
# Property 22: Agent ID uniqueness and multi-agent ownership
# Feature: agent-evolution
# =============================================================================


class TestAgentIdUniqueness:
  """Property 22: Multiple agents created for same profile always have unique UUIDs.

  同一 profile_id に対して N 個のエージェントを作成した場合、
  全 agent_id が一意な UUID v4 であり、同じ profile_id に紐付く。

  **Validates: Requirements 16.1, 16.3**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    num_agents=_num_agents_st,
    display_name=_display_name_st,
  )
  async def test_all_agent_ids_unique(
    self,
    profile_id: str,
    num_agents: int,
    display_name: str,
    tmp_path,
  ) -> None:
    """N 個のエージェント作成で全 agent_id が一意な UUID v4 であること。

    **Validates: Requirements 16.1, 16.3**
    """
    mgr = await _create_manager(tmp_path)

    records: list[AgentRecord] = []
    for i in range(num_agents):
      record = await mgr.create(profile_id, f"{display_name}_{i}")
      records.append(record)

    # 全 agent_id が一意
    agent_ids = [r.agent_id for r in records]
    assert len(set(agent_ids)) == num_agents, (
      f"Expected {num_agents} unique agent_ids, got {len(set(agent_ids))} unique "
      f"out of {agent_ids}"
    )

    # 各 agent_id が UUID v4 形式
    for aid in agent_ids:
      parsed = uuid.UUID(aid, version=4)
      assert str(parsed) == aid, (
        f"agent_id '{aid}' is not a valid UUID v4"
      )

    # 全レコードが同一 profile_id に紐付く
    for record in records:
      assert record.profile_id == profile_id, (
        f"Expected profile_id='{profile_id}', got '{record.profile_id}'"
      )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    names=st.lists(_display_name_st, min_size=2, max_size=5, unique=True),
  )
  async def test_multi_agent_ownership(
    self,
    profile_id: str,
    names: list[str],
    tmp_path,
  ) -> None:
    """同一 profile_id に複数エージェントが紐付き、list_active で全件返ること。

    **Validates: Requirements 16.1, 16.3**
    """
    mgr = await _create_manager(tmp_path)

    for name in names:
      await mgr.create(profile_id, name)

    active = await mgr.list_active(profile_id)
    assert len(active) == len(names), (
      f"Expected {len(names)} active agents, got {len(active)}"
    )

    # 全エージェントが同一 profile_id
    for agent in active:
      assert agent.profile_id == profile_id


# =============================================================================
# Property 23: Agent CRUD round-trip
# Feature: agent-evolution
# =============================================================================


class TestAgentCrudRoundTrip:
  """Property 23: create → get returns same data.

  create() で作成したエージェントを get() で取得すると、
  同一の agent_id, profile_id, display_name が返される。

  **Validates: Requirements 16.4**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    display_name=_display_name_st,
  )
  async def test_create_then_get_returns_same_data(
    self,
    profile_id: str,
    display_name: str,
    tmp_path,
  ) -> None:
    """create(profile_id, name) → get(agent_id) returns matching record.

    **Validates: Requirements 16.4**
    """
    mgr = await _create_manager(tmp_path)

    created = await mgr.create(profile_id, display_name)
    fetched = await mgr.get(created.agent_id)

    assert fetched is not None, "get() should return a record for a created agent"
    assert fetched.agent_id == created.agent_id, (
      f"agent_id mismatch: created={created.agent_id}, fetched={fetched.agent_id}"
    )
    assert fetched.profile_id == profile_id, (
      f"profile_id mismatch: expected={profile_id}, fetched={fetched.profile_id}"
    )
    assert fetched.display_name == display_name, (
      f"display_name mismatch: expected={display_name}, fetched={fetched.display_name}"
    )
    assert fetched.is_active is True, (
      "Newly created agent should be active"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    original_name=_display_name_st,
    new_name=_display_name_st,
  )
  async def test_update_display_name_reflected(
    self,
    profile_id: str,
    original_name: str,
    new_name: str,
    tmp_path,
  ) -> None:
    """update_display_name() 後、get() で新しい名前が返ること。

    **Validates: Requirements 16.4**
    """
    mgr = await _create_manager(tmp_path)

    created = await mgr.create(profile_id, original_name)
    await mgr.update_display_name(created.agent_id, new_name)

    fetched = await mgr.get(created.agent_id)
    assert fetched is not None
    assert fetched.display_name == new_name, (
      f"display_name after update: expected='{new_name}', got='{fetched.display_name}'"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    display_name=_display_name_st,
  )
  async def test_soft_delete_sets_inactive(
    self,
    profile_id: str,
    display_name: str,
    tmp_path,
  ) -> None:
    """soft_delete() 後、get() で is_active=False が返ること。

    **Validates: Requirements 16.4**
    """
    mgr = await _create_manager(tmp_path)

    created = await mgr.create(profile_id, display_name)
    await mgr.soft_delete(created.agent_id)

    fetched = await mgr.get(created.agent_id)
    assert fetched is not None, "get() should still return record after soft_delete"
    assert fetched.is_active is False, (
      f"Expected is_active=False after soft_delete, got={fetched.is_active}"
    )


# =============================================================================
# Property 24: Active agents filter
# Feature: agent-evolution
# =============================================================================


class TestActiveAgentsFilter:
  """Property 24: soft_delete removes from list_active but not from get.

  soft_delete されたエージェントは list_active() から除外されるが、
  get() では引き続き取得可能（is_active=False）。

  **Validates: Requirements 16.7**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    names=st.lists(_display_name_st, min_size=2, max_size=6, unique=True),
    delete_count=st.integers(min_value=1, max_value=3),
  )
  async def test_soft_deleted_excluded_from_list_active(
    self,
    profile_id: str,
    names: list[str],
    delete_count: int,
    tmp_path,
  ) -> None:
    """soft_delete したエージェントは list_active から除外されること。

    **Validates: Requirements 16.7**
    """
    # delete_count が names 数を超えないよう調整
    actual_delete = min(delete_count, len(names) - 1)

    mgr = await _create_manager(tmp_path)

    records: list[AgentRecord] = []
    for name in names:
      r = await mgr.create(profile_id, name)
      records.append(r)

    # 先頭 actual_delete 件を soft_delete
    deleted_ids = set()
    for i in range(actual_delete):
      await mgr.soft_delete(records[i].agent_id)
      deleted_ids.add(records[i].agent_id)

    # list_active から除外されている
    active = await mgr.list_active(profile_id)
    active_ids = {a.agent_id for a in active}

    assert len(active) == len(names) - actual_delete, (
      f"Expected {len(names) - actual_delete} active agents, got {len(active)}"
    )

    for did in deleted_ids:
      assert did not in active_ids, (
        f"Soft-deleted agent '{did}' should not appear in list_active"
      )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    display_name=_display_name_st,
  )
  async def test_soft_deleted_still_accessible_via_get(
    self,
    profile_id: str,
    display_name: str,
    tmp_path,
  ) -> None:
    """soft_delete 後も get() で取得可能（is_active=False）。

    **Validates: Requirements 16.7**
    """
    mgr = await _create_manager(tmp_path)

    created = await mgr.create(profile_id, display_name)
    await mgr.soft_delete(created.agent_id)

    # get() で取得可能
    fetched = await mgr.get(created.agent_id)
    assert fetched is not None, (
      "get() should return record even after soft_delete"
    )
    assert fetched.is_active is False, (
      "Soft-deleted agent should have is_active=False"
    )
    assert fetched.agent_id == created.agent_id
    assert fetched.display_name == display_name

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    names=st.lists(_display_name_st, min_size=3, max_size=6, unique=True),
  )
  async def test_list_active_contains_only_active_records(
    self,
    profile_id: str,
    names: list[str],
    tmp_path,
  ) -> None:
    """list_active() の結果は全て is_active=True であること。

    **Validates: Requirements 16.7**
    """
    mgr = await _create_manager(tmp_path)

    records: list[AgentRecord] = []
    for name in names:
      r = await mgr.create(profile_id, name)
      records.append(r)

    # 半分を soft_delete
    half = len(records) // 2
    for i in range(half):
      await mgr.soft_delete(records[i].agent_id)

    active = await mgr.list_active(profile_id)

    # 全件 is_active=True
    for agent in active:
      assert agent.is_active is True, (
        f"list_active should only contain active agents, "
        f"got agent_id={agent.agent_id} with is_active={agent.is_active}"
      )

    # 件数が正しい
    assert len(active) == len(names) - half, (
      f"Expected {len(names) - half} active agents after deleting {half}, got {len(active)}"
    )
