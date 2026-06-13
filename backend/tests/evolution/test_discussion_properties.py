"""DiscussionEngine プロパティベーステスト

Feature: agent-evolution
Property 28: Discussion prompts reflect individual personalities
Property 29: Discussion turn accumulation
Property 30: Discussion max turns invariant
Property 31: Discussion turn attribution
Property 32: Discussion turn persistence
Validates: Requirements 18.2, 18.3, 18.4, 18.5, 18.6
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.evolution.agent_manager import AgentManager, AgentRecord
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.discussion_engine import DiscussionEngine, DiscussionTurn
from app.evolution.routing_engine import RoutingEngine


# --- Hypothesis ストラテジー ---

# agent_id: 一意性を確保するためプレフィクス + 連番で生成
_agent_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
  min_size=3,
  max_size=20,
).filter(lambda s: s.strip() != "" and len(s.strip()) >= 3)

# agent_ids リスト: 2〜6 の一意な agent_id
_agent_ids_st = st.lists(
  _agent_id_st,
  min_size=2,
  max_size=6,
  unique=True,
)

# max_turns_per_agent: 1〜5
_max_turns_st = st.integers(min_value=1, max_value=5)

# theme: 非空文字列
_theme_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
  min_size=1,
  max_size=30,
).filter(lambda s: s.strip() != "")


# --- ヘルパー ---


def _make_mock_routing_engine(response: str = "This is my response.") -> RoutingEngine:
  """RoutingEngine のモック。route() が固定レスポンスを返す。"""
  engine = MagicMock(spec=RoutingEngine)
  engine.route = AsyncMock(return_value=response)
  return engine


def _make_mock_clm(agent_ids: list[str]) -> ContextLayerManager:
  """ContextLayerManager のモック。各 agent_id ごとに異なる Base OS を返す。"""
  clm = MagicMock(spec=ContextLayerManager)

  def get_base_os_side_effect(agent_id: str):
    # 各エージェントに固有のパーソナリティを割り当て
    base_os = MagicMock()
    idx = agent_ids.index(agent_id) if agent_id in agent_ids else 0
    styles = ["analytical", "intuitive", "pragmatic", "creative", "empathetic", "systematic"]
    base_os.decision_style = styles[idx % len(styles)]
    base_os.axes = {
      "extroverted_introverted": round(0.1 * (idx + 1), 2),
      "thinking_feeling": round(0.9 - 0.1 * idx, 2),
    }
    base_os.do_not_list = [f"Do not rule {idx + 1}"]
    return base_os

  clm.get_base_os = MagicMock(side_effect=get_base_os_side_effect)
  return clm


def _make_mock_agent_manager(agent_ids: list[str]) -> AgentManager:
  """AgentManager のモック。指定 agent_ids に対しアクティブレコードを返す。"""
  mgr = MagicMock(spec=AgentManager)

  async def get_side_effect(agent_id: str):
    if agent_id in agent_ids:
      return AgentRecord(
        agent_id=agent_id,
        profile_id="prof_000001",
        display_name=f"Agent-{agent_id[:8]}",
        created_at="2024-01-01T00:00:00+00:00",
        is_active=True,
      )
    return None

  mgr.get = AsyncMock(side_effect=get_side_effect)
  return mgr


async def _create_discussion_engine(
  tmp_path, agent_ids: list[str]
) -> DiscussionEngine:
  """テスト用 DiscussionEngine を構築する。

  各呼び出しで一意の DB ファイルを使用し、example 間の衝突を回避する。
  """
  db_path = str(tmp_path / f"discussion_{uuid.uuid4().hex}.db")
  engine = DiscussionEngine(
    db_path=db_path,
    routing_engine=_make_mock_routing_engine(),
    context_layer_manager=_make_mock_clm(agent_ids),
    agent_manager=_make_mock_agent_manager(agent_ids),
  )
  await engine.init_db()
  return engine


# =============================================================================
# Property 28: Discussion prompts reflect individual personalities
# Feature: agent-evolution
# =============================================================================


class TestDiscussionPromptsReflectPersonalities:
  """Property 28: Each agent's system prompt is unique.

  各エージェントに対して構築されるシステムプロンプトが、
  他のエージェントとは異なるパーソナリティを反映すること。

  **Validates: Requirements 18.2**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_ids=_agent_ids_st,
    theme=_theme_st,
  )
  async def test_each_agent_has_unique_system_prompt(
    self,
    agent_ids: list[str],
    theme: str,
    tmp_path,
  ) -> None:
    """各エージェントのシステムプロンプトが一意であること。

    **Validates: Requirements 18.2**
    """
    engine = await _create_discussion_engine(tmp_path, agent_ids)

    # display_names を構築
    agent_display_names = {aid: f"Agent-{aid[:8]}" for aid in agent_ids}

    # 各エージェントのシステムプロンプトを生成
    prompts = []
    for agent_id in agent_ids:
      prompt = engine._build_system_prompt(
        agent_id=agent_id,
        theme=theme,
        agent_ids=agent_ids,
        agent_display_names=agent_display_names,
      )
      prompts.append(prompt)

    # 全プロンプトが一意であること
    assert len(set(prompts)) == len(agent_ids), (
      f"Expected {len(agent_ids)} unique prompts, "
      f"got {len(set(prompts))} unique prompts"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_ids=_agent_ids_st,
    theme=_theme_st,
  )
  async def test_each_prompt_contains_agent_name(
    self,
    agent_ids: list[str],
    theme: str,
    tmp_path,
  ) -> None:
    """各プロンプトにそのエージェントの表示名が含まれること。

    **Validates: Requirements 18.2**
    """
    engine = await _create_discussion_engine(tmp_path, agent_ids)
    agent_display_names = {aid: f"Agent-{aid[:8]}" for aid in agent_ids}

    for agent_id in agent_ids:
      prompt = engine._build_system_prompt(
        agent_id=agent_id,
        theme=theme,
        agent_ids=agent_ids,
        agent_display_names=agent_display_names,
      )
      display_name = agent_display_names[agent_id]
      assert display_name in prompt, (
        f"Prompt for {agent_id} should contain display_name '{display_name}'"
      )


# =============================================================================
# Property 29: Discussion turn accumulation
# Feature: agent-evolution
# =============================================================================


class TestDiscussionTurnAccumulation:
  """Property 29: After run_turns, get_history returns correct turn count.

  run_turns 実行後、get_history で取得できるターン数が
  max_turns_per_agent × len(agent_ids) と一致すること。

  **Validates: Requirements 18.3**
  """

  @settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_ids=_agent_ids_st,
    max_turns_per_agent=_max_turns_st,
    theme=_theme_st,
  )
  async def test_history_count_matches_total_turns(
    self,
    agent_ids: list[str],
    max_turns_per_agent: int,
    theme: str,
    tmp_path,
  ) -> None:
    """get_history のターン数が max_turns_per_agent × agent_count と一致すること。

    **Validates: Requirements 18.3**
    """
    engine = await _create_discussion_engine(tmp_path, agent_ids)
    discussion_id = str(uuid.uuid4())
    expected_total = max_turns_per_agent * len(agent_ids)

    # 全ターンを消費
    async for _ in engine.run_turns(
      discussion_id=discussion_id,
      agent_ids=agent_ids,
      theme=theme,
      max_turns_per_agent=max_turns_per_agent,
    ):
      pass

    history = await engine.get_history(discussion_id)
    assert len(history) == expected_total, (
      f"Expected {expected_total} turns "
      f"({max_turns_per_agent} × {len(agent_ids)}), "
      f"got {len(history)}"
    )


# =============================================================================
# Property 30: Discussion max turns invariant
# Feature: agent-evolution
# =============================================================================


class TestDiscussionMaxTurnsInvariant:
  """Property 30: Total turns never exceeds max_turns_per_agent × agent_count.

  run_turns が yield するターン総数が、max_turns_per_agent × len(agent_ids)
  を超えないこと。

  **Validates: Requirements 18.4**
  """

  @settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_ids=_agent_ids_st,
    max_turns_per_agent=_max_turns_st,
    theme=_theme_st,
  )
  async def test_yielded_turns_equals_max(
    self,
    agent_ids: list[str],
    max_turns_per_agent: int,
    theme: str,
    tmp_path,
  ) -> None:
    """yield されるターン数が max_turns_per_agent × agent_count と等しいこと。

    **Validates: Requirements 18.4**
    """
    engine = await _create_discussion_engine(tmp_path, agent_ids)
    discussion_id = str(uuid.uuid4())
    max_allowed = max_turns_per_agent * len(agent_ids)

    turn_count = 0
    async for _ in engine.run_turns(
      discussion_id=discussion_id,
      agent_ids=agent_ids,
      theme=theme,
      max_turns_per_agent=max_turns_per_agent,
    ):
      turn_count += 1

    assert turn_count == max_allowed, (
      f"Expected exactly {max_allowed} turns, got {turn_count}"
    )
    # 不変条件: 超えてはならない
    assert turn_count <= max_allowed, (
      f"Total turns {turn_count} exceeds max {max_allowed}"
    )


# =============================================================================
# Property 31: Discussion turn attribution
# Feature: agent-evolution
# =============================================================================


class TestDiscussionTurnAttribution:
  """Property 31: Each turn's agent_id matches the round-robin pattern.

  各ターンの agent_id がラウンドロビン（agent_ids[0], agent_ids[1], ...
  agent_ids[-1], agent_ids[0], ...）の順序と一致すること。

  **Validates: Requirements 18.5**
  """

  @settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_ids=_agent_ids_st,
    max_turns_per_agent=_max_turns_st,
    theme=_theme_st,
  )
  async def test_agent_ids_follow_round_robin(
    self,
    agent_ids: list[str],
    max_turns_per_agent: int,
    theme: str,
    tmp_path,
  ) -> None:
    """ターンの agent_id がラウンドロビンパターンに従うこと。

    **Validates: Requirements 18.5**
    """
    engine = await _create_discussion_engine(tmp_path, agent_ids)
    discussion_id = str(uuid.uuid4())

    turns: list[DiscussionTurn] = []
    async for turn in engine.run_turns(
      discussion_id=discussion_id,
      agent_ids=agent_ids,
      theme=theme,
      max_turns_per_agent=max_turns_per_agent,
    ):
      turns.append(turn)

    # 期待されるラウンドロビンパターン
    expected_pattern = agent_ids * max_turns_per_agent
    actual_ids = [t.agent_id for t in turns]

    assert actual_ids == expected_pattern, (
      f"Round-robin mismatch.\n"
      f"  Expected: {expected_pattern}\n"
      f"  Actual:   {actual_ids}"
    )

  @settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_ids=_agent_ids_st,
    max_turns_per_agent=_max_turns_st,
    theme=_theme_st,
  )
  async def test_each_turn_has_valid_display_name_and_agent_id(
    self,
    agent_ids: list[str],
    max_turns_per_agent: int,
    theme: str,
    tmp_path,
  ) -> None:
    """各ターンに display_name, agent_id, content, timestamp が含まれること。

    **Validates: Requirements 18.5**
    """
    engine = await _create_discussion_engine(tmp_path, agent_ids)
    discussion_id = str(uuid.uuid4())

    async for turn in engine.run_turns(
      discussion_id=discussion_id,
      agent_ids=agent_ids,
      theme=theme,
      max_turns_per_agent=max_turns_per_agent,
    ):
      # 全必須フィールドが非空であること
      assert turn.agent_id in agent_ids, (
        f"turn.agent_id '{turn.agent_id}' not in agent_ids"
      )
      assert turn.display_name != "", "display_name should not be empty"
      assert turn.content != "", "content should not be empty"
      assert turn.timestamp != "", "timestamp should not be empty"


# =============================================================================
# Property 32: Discussion turn persistence
# Feature: agent-evolution
# =============================================================================


class TestDiscussionTurnPersistence:
  """Property 32: All yielded turns are persisted to DB.

  run_turns で yield された全ターンが get_history で正確に取得でき、
  内容（agent_id, display_name, content）が一致すること。

  **Validates: Requirements 18.6**
  """

  @settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_ids=_agent_ids_st,
    max_turns_per_agent=_max_turns_st,
    theme=_theme_st,
  )
  async def test_all_yielded_turns_in_history(
    self,
    agent_ids: list[str],
    max_turns_per_agent: int,
    theme: str,
    tmp_path,
  ) -> None:
    """yield されたターンが全て get_history で取得できること。

    **Validates: Requirements 18.6**
    """
    engine = await _create_discussion_engine(tmp_path, agent_ids)
    discussion_id = str(uuid.uuid4())

    yielded_turns: list[DiscussionTurn] = []
    async for turn in engine.run_turns(
      discussion_id=discussion_id,
      agent_ids=agent_ids,
      theme=theme,
      max_turns_per_agent=max_turns_per_agent,
    ):
      yielded_turns.append(turn)

    history = await engine.get_history(discussion_id)

    # 件数が一致
    assert len(history) == len(yielded_turns), (
      f"History count {len(history)} != yielded count {len(yielded_turns)}"
    )

    # 各ターンの内容が一致
    for i, (yielded, persisted) in enumerate(zip(yielded_turns, history)):
      assert persisted["agent_id"] == yielded.agent_id, (
        f"Turn {i}: agent_id mismatch"
      )
      assert persisted["display_name"] == yielded.display_name, (
        f"Turn {i}: display_name mismatch"
      )
      assert persisted["content"] == yielded.content, (
        f"Turn {i}: content mismatch"
      )
      assert persisted["turn_number"] == yielded.turn_number, (
        f"Turn {i}: turn_number mismatch"
      )

  @settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    agent_ids=_agent_ids_st,
    max_turns_per_agent=_max_turns_st,
    theme=_theme_st,
  )
  async def test_persisted_turns_have_required_fields(
    self,
    agent_ids: list[str],
    max_turns_per_agent: int,
    theme: str,
    tmp_path,
  ) -> None:
    """永続化されたターンに turn_id, turn_number, agent_id, display_name, content, created_at が含まれること。

    **Validates: Requirements 18.6**
    """
    engine = await _create_discussion_engine(tmp_path, agent_ids)
    discussion_id = str(uuid.uuid4())

    async for _ in engine.run_turns(
      discussion_id=discussion_id,
      agent_ids=agent_ids,
      theme=theme,
      max_turns_per_agent=max_turns_per_agent,
    ):
      pass

    history = await engine.get_history(discussion_id)

    required_fields = {"turn_id", "turn_number", "agent_id", "display_name", "content", "created_at"}
    for i, turn in enumerate(history):
      missing = required_fields - set(turn.keys())
      assert not missing, (
        f"Turn {i} missing fields: {missing}"
      )
      # turn_id は UUID 形式 (36文字)
      assert len(turn["turn_id"]) == 36, (
        f"Turn {i}: turn_id should be UUID format, got '{turn['turn_id']}'"
      )
      # created_at は非空
      assert turn["created_at"], (
        f"Turn {i}: created_at should not be empty"
      )
