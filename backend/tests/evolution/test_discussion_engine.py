"""DiscussionEngine のユニットテスト

マルチエージェント・ターン制議論の
セッション管理・ターン実行・SSE ストリーミング・永続化を検証する。
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.evolution.agent_manager import AgentManager, AgentRecord
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.discussion_engine import DiscussionEngine, DiscussionTurn
from app.evolution.routing_engine import RoutingEngine


@pytest_asyncio.fixture
async def db_path(tmp_path) -> str:
  """テスト用の一時 DB パスを返す。"""
  return str(tmp_path / "test_discussion.db")


@pytest_asyncio.fixture
async def mock_routing_engine() -> RoutingEngine:
  """RoutingEngine のモック。route() が固定レスポンスを返す。"""
  engine = MagicMock(spec=RoutingEngine)
  engine.route = AsyncMock(return_value="I think this is interesting.")
  return engine


@pytest_asyncio.fixture
async def mock_clm() -> ContextLayerManager:
  """ContextLayerManager のモック。get_base_os が正常に返る。"""
  clm = MagicMock(spec=ContextLayerManager)
  base_os = MagicMock()
  base_os.decision_style = "analytical"
  base_os.axes = {"extroverted_introverted": 0.7, "thinking_feeling": 0.3}
  base_os.do_not_list = ["Be rude"]
  clm.get_base_os = MagicMock(return_value=base_os)
  return clm


@pytest_asyncio.fixture
async def mock_agent_manager() -> AgentManager:
  """AgentManager のモック。get() がアクティブなレコードを返す。"""
  mgr = MagicMock(spec=AgentManager)

  def make_record(agent_id: str) -> AgentRecord:
    return AgentRecord(
      agent_id=agent_id,
      profile_id="prof_000001",
      display_name=f"Agent-{agent_id[:4]}",
      created_at="2024-01-01T00:00:00+00:00",
      is_active=True,
    )

  mgr.get = AsyncMock(side_effect=lambda aid: make_record(aid))
  return mgr


@pytest_asyncio.fixture
async def mock_agent_manager_with_inactive() -> AgentManager:
  """AgentManager のモック。一部エージェントが非アクティブ。"""
  mgr = MagicMock(spec=AgentManager)

  def side_effect(agent_id: str):
    if agent_id == "inactive-agent":
      return AgentRecord(
        agent_id=agent_id,
        profile_id="prof_000001",
        display_name="Inactive",
        created_at="2024-01-01T00:00:00+00:00",
        is_active=False,
      )
    return AgentRecord(
      agent_id=agent_id,
      profile_id="prof_000001",
      display_name=f"Agent-{agent_id[:4]}",
      created_at="2024-01-01T00:00:00+00:00",
      is_active=True,
    )

  mgr.get = AsyncMock(side_effect=side_effect)
  return mgr


@pytest_asyncio.fixture
async def discussion_engine(
  db_path: str,
  mock_routing_engine: RoutingEngine,
  mock_clm: ContextLayerManager,
  mock_agent_manager: AgentManager,
) -> DiscussionEngine:
  """初期化済み DiscussionEngine を返す。"""
  engine = DiscussionEngine(
    db_path=db_path,
    routing_engine=mock_routing_engine,
    context_layer_manager=mock_clm,
    agent_manager=mock_agent_manager,
  )
  await engine.init_db()
  return engine


class TestInitDb:
  """init_db() のテスト"""

  @pytest.mark.asyncio
  async def test_creates_discussions_table(self, db_path: str) -> None:
    """discussions テーブルが正常に作成されること。"""
    engine = DiscussionEngine(
      db_path=db_path,
      routing_engine=MagicMock(spec=RoutingEngine),
      context_layer_manager=MagicMock(spec=ContextLayerManager),
      agent_manager=MagicMock(spec=AgentManager),
    )
    await engine.init_db()
    # 2回目の呼び出しもエラーにならない (IF NOT EXISTS)
    await engine.init_db()

  @pytest.mark.asyncio
  async def test_idempotent_init(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """init_db() を複数回呼んでもエラーにならないこと。"""
    await discussion_engine.init_db()
    await discussion_engine.init_db()


class TestStartDiscussion:
  """start_discussion() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_discussion_id(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """有効なエージェントで discussion_id (UUID) が返ること。"""
    discussion_id = await discussion_engine.start_discussion(
      agent_ids=["agent-1", "agent-2"],
      theme="AI の未来",
    )
    assert discussion_id is not None
    assert len(discussion_id) == 36  # UUID形式

  @pytest.mark.asyncio
  async def test_rejects_less_than_2_agents(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """エージェント数が2未満の場合 ValueError が発生すること。"""
    with pytest.raises(ValueError, match="2 to 6"):
      await discussion_engine.start_discussion(
        agent_ids=["agent-1"],
        theme="テスト",
      )

  @pytest.mark.asyncio
  async def test_rejects_more_than_6_agents(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """エージェント数が6超の場合 ValueError が発生すること。"""
    ids = [f"agent-{i}" for i in range(7)]
    with pytest.raises(ValueError, match="2 to 6"):
      await discussion_engine.start_discussion(
        agent_ids=ids,
        theme="テスト",
      )

  @pytest.mark.asyncio
  async def test_accepts_boundary_2_agents(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """ちょうど2エージェントで成功すること。"""
    discussion_id = await discussion_engine.start_discussion(
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
    )
    assert discussion_id is not None

  @pytest.mark.asyncio
  async def test_accepts_boundary_6_agents(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """ちょうど6エージェントで成功すること。"""
    ids = [f"agent-{i}" for i in range(6)]
    discussion_id = await discussion_engine.start_discussion(
      agent_ids=ids,
      theme="テスト",
    )
    assert discussion_id is not None

  @pytest.mark.asyncio
  async def test_rejects_inactive_agents(
    self,
    db_path: str,
    mock_routing_engine: RoutingEngine,
    mock_clm: ContextLayerManager,
    mock_agent_manager_with_inactive: AgentManager,
  ) -> None:
    """非アクティブなエージェントが含まれる場合 ValueError が発生すること。"""
    engine = DiscussionEngine(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
      agent_manager=mock_agent_manager_with_inactive,
    )
    await engine.init_db()
    with pytest.raises(ValueError, match="inactive-agent"):
      await engine.start_discussion(
        agent_ids=["agent-1", "inactive-agent"],
        theme="テスト",
      )

  @pytest.mark.asyncio
  async def test_rejects_nonexistent_agents(
    self,
    db_path: str,
    mock_routing_engine: RoutingEngine,
    mock_clm: ContextLayerManager,
  ) -> None:
    """存在しないエージェントが含まれる場合 ValueError が発生すること。"""
    mgr = MagicMock(spec=AgentManager)
    mgr.get = AsyncMock(return_value=None)
    engine = DiscussionEngine(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=mock_clm,
      agent_manager=mgr,
    )
    await engine.init_db()
    with pytest.raises(ValueError, match="Invalid or inactive"):
      await engine.start_discussion(
        agent_ids=["nonexistent-1", "nonexistent-2"],
        theme="テスト",
      )


class TestRunTurns:
  """run_turns() のテスト"""

  @pytest.mark.asyncio
  async def test_yields_correct_number_of_turns(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """max_turns_per_agent × agent_count のターンが生成されること。"""
    agent_ids = ["agent-1", "agent-2"]
    max_turns = 3
    turns: list[DiscussionTurn] = []
    async for turn in discussion_engine.run_turns(
      discussion_id="test-disc-001",
      agent_ids=agent_ids,
      theme="テスト",
      max_turns_per_agent=max_turns,
    ):
      turns.append(turn)

    expected_count = max_turns * len(agent_ids)
    assert len(turns) == expected_count

  @pytest.mark.asyncio
  async def test_round_robin_agent_selection(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """エージェントがラウンドロビンで選択されること。"""
    agent_ids = ["agent-1", "agent-2", "agent-3"]
    turns: list[DiscussionTurn] = []
    async for turn in discussion_engine.run_turns(
      discussion_id="test-disc-002",
      agent_ids=agent_ids,
      theme="テスト",
      max_turns_per_agent=2,
    ):
      turns.append(turn)

    # 期待: agent-1, agent-2, agent-3, agent-1, agent-2, agent-3
    expected_ids = agent_ids * 2
    actual_ids = [t.agent_id for t in turns]
    assert actual_ids == expected_ids

  @pytest.mark.asyncio
  async def test_turn_numbers_are_sequential(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """turn_number が1から連番であること。"""
    turns: list[DiscussionTurn] = []
    async for turn in discussion_engine.run_turns(
      discussion_id="test-disc-003",
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=2,
    ):
      turns.append(turn)

    turn_numbers = [t.turn_number for t in turns]
    assert turn_numbers == [1, 2, 3, 4]

  @pytest.mark.asyncio
  async def test_turns_contain_display_name(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """各ターンに display_name が含まれること。"""
    turns: list[DiscussionTurn] = []
    async for turn in discussion_engine.run_turns(
      discussion_id="test-disc-004",
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=1,
    ):
      turns.append(turn)

    for turn in turns:
      assert turn.display_name != ""
      assert turn.display_name is not None

  @pytest.mark.asyncio
  async def test_turns_contain_content(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """各ターンにコンテンツが含まれること。"""
    turns: list[DiscussionTurn] = []
    async for turn in discussion_engine.run_turns(
      discussion_id="test-disc-005",
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=1,
    ):
      turns.append(turn)

    for turn in turns:
      assert turn.content == "I think this is interesting."

  @pytest.mark.asyncio
  async def test_turns_persisted_to_db(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """各ターンが DB に永続化されること。"""
    disc_id = "test-disc-006"
    async for _ in discussion_engine.run_turns(
      discussion_id=disc_id,
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=2,
    ):
      pass

    history = await discussion_engine.get_history(disc_id)
    assert len(history) == 4

  @pytest.mark.asyncio
  async def test_routing_engine_called_per_turn(
    self,
    discussion_engine: DiscussionEngine,
    mock_routing_engine: RoutingEngine,
  ) -> None:
    """各ターンで RoutingEngine.route() が呼ばれること。"""
    async for _ in discussion_engine.run_turns(
      discussion_id="test-disc-007",
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=2,
    ):
      pass

    assert mock_routing_engine.route.call_count == 4


class TestStreamDiscussion:
  """stream_discussion() のテスト"""

  @pytest.mark.asyncio
  async def test_yields_sse_events(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """SSE 形式のイベントが yield されること。"""
    events: list[str] = []
    async for event in discussion_engine.stream_discussion(
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=1,
    ):
      events.append(event)

    assert len(events) == 2
    for event in events:
      assert event.startswith("data: ")
      assert event.endswith("\n\n")

  @pytest.mark.asyncio
  async def test_sse_payload_structure(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """SSE ペイロードに必須フィールドが含まれること。"""
    events: list[str] = []
    async for event in discussion_engine.stream_discussion(
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=1,
    ):
      events.append(event)

    for event in events:
      payload_str = event[len("data: "):-2]
      payload = json.loads(payload_str)
      assert "discussion_id" in payload
      assert "turn_number" in payload
      assert "agent_id" in payload
      assert "display_name" in payload
      assert "content" in payload
      assert "timestamp" in payload

  @pytest.mark.asyncio
  async def test_sse_discussion_id_consistent(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """全イベントで discussion_id が一致すること。"""
    events: list[str] = []
    async for event in discussion_engine.stream_discussion(
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=2,
    ):
      events.append(event)

    discussion_ids = set()
    for event in events:
      payload_str = event[len("data: "):-2]
      payload = json.loads(payload_str)
      discussion_ids.add(payload["discussion_id"])

    assert len(discussion_ids) == 1


class TestGetHistory:
  """get_history() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_empty_for_nonexistent(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """存在しない discussion_id では空リストが返ること。"""
    history = await discussion_engine.get_history("nonexistent")
    assert history == []

  @pytest.mark.asyncio
  async def test_returns_all_turns_ordered(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """全ターンが turn_number 昇順で返ること。"""
    disc_id = "test-history-001"
    async for _ in discussion_engine.run_turns(
      discussion_id=disc_id,
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=3,
    ):
      pass

    history = await discussion_engine.get_history(disc_id)
    assert len(history) == 6
    turn_numbers = [h["turn_number"] for h in history]
    assert turn_numbers == [1, 2, 3, 4, 5, 6]

  @pytest.mark.asyncio
  async def test_history_contains_required_fields(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """各ターンに必須フィールドが含まれること。"""
    disc_id = "test-history-002"
    async for _ in discussion_engine.run_turns(
      discussion_id=disc_id,
      agent_ids=["agent-1", "agent-2"],
      theme="テスト",
      max_turns_per_agent=1,
    ):
      pass

    history = await discussion_engine.get_history(disc_id)
    for turn in history:
      assert "turn_id" in turn
      assert "turn_number" in turn
      assert "agent_id" in turn
      assert "display_name" in turn
      assert "content" in turn
      assert "created_at" in turn


class TestBuildSystemPrompt:
  """_build_system_prompt() のテスト"""

  @pytest.mark.asyncio
  async def test_includes_theme(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """システムプロンプトにテーマが含まれること。"""
    prompt = discussion_engine._build_system_prompt(
      agent_id="agent-1",
      theme="AI の未来",
      agent_ids=["agent-1", "agent-2"],
      agent_display_names={"agent-1": "Alice", "agent-2": "Bob"},
    )
    assert "AI の未来" in prompt

  @pytest.mark.asyncio
  async def test_includes_agent_display_name(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """システムプロンプトにエージェント表示名が含まれること。"""
    prompt = discussion_engine._build_system_prompt(
      agent_id="agent-1",
      theme="テスト",
      agent_ids=["agent-1", "agent-2"],
      agent_display_names={"agent-1": "Alice", "agent-2": "Bob"},
    )
    assert "Alice" in prompt

  @pytest.mark.asyncio
  async def test_includes_other_participants(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """システムプロンプトに他の参加者名が含まれること。"""
    prompt = discussion_engine._build_system_prompt(
      agent_id="agent-1",
      theme="テスト",
      agent_ids=["agent-1", "agent-2", "agent-3"],
      agent_display_names={"agent-1": "Alice", "agent-2": "Bob", "agent-3": "Charlie"},
    )
    assert "Bob" in prompt
    assert "Charlie" in prompt

  @pytest.mark.asyncio
  async def test_includes_personality_traits(
    self, discussion_engine: DiscussionEngine
  ) -> None:
    """システムプロンプトにパーソナリティ特性が含まれること。"""
    prompt = discussion_engine._build_system_prompt(
      agent_id="agent-1",
      theme="テスト",
      agent_ids=["agent-1", "agent-2"],
      agent_display_names={"agent-1": "Alice", "agent-2": "Bob"},
    )
    assert "analytical" in prompt

  @pytest.mark.asyncio
  async def test_fallback_on_missing_profile(
    self,
    db_path: str,
    mock_routing_engine: RoutingEngine,
    mock_agent_manager: AgentManager,
  ) -> None:
    """Base OS 取得失敗時にデフォルトプロンプトが返ること。"""
    clm = MagicMock(spec=ContextLayerManager)
    clm.get_base_os = MagicMock(side_effect=KeyError("not loaded"))
    engine = DiscussionEngine(
      db_path=db_path,
      routing_engine=mock_routing_engine,
      context_layer_manager=clm,
      agent_manager=mock_agent_manager,
    )
    prompt = engine._build_system_prompt(
      agent_id="agent-1",
      theme="テスト",
      agent_ids=["agent-1", "agent-2"],
      agent_display_names={"agent-1": "Alice", "agent-2": "Bob"},
    )
    assert "Alice" in prompt
    assert "テスト" in prompt
