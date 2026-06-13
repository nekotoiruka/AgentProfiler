"""EvolutionMCPServer のユニットテスト

MCP Tool 登録・呼び出し・エラーハンドリング・ロギングを検証する。
"""

import logging

import pytest

from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.mcp_server import EvolutionMCPServer
from app.models.profile import (
  BaseOS,
  ContextLayers,
  ProfileOutput,
)
from app.models.scores import NormalizedScores


def _make_profile(
  profile_id: str = "prof_000001",
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
      "analog_habits": "毎朝モーニングページを3ページ書く",
    },
    context_layers=ContextLayers(base_os=1, lexical_tags=2, semantic_contexts=3),
  )


@pytest.fixture
async def loaded_manager() -> ContextLayerManager:
  """プロファイルロード済みの ContextLayerManager。"""
  mgr = ContextLayerManager()
  await mgr.load_profile(_make_profile())
  return mgr


@pytest.fixture
async def mcp_server(loaded_manager: ContextLayerManager) -> EvolutionMCPServer:
  """テスト用 EvolutionMCPServer インスタンス。"""
  return EvolutionMCPServer(
    context_layer_manager=loaded_manager,
    transport="stdio",
  )


class TestMCPServerInit:
  """初期化テスト"""

  def test_default_transport_is_stdio(self) -> None:
    """デフォルトトランスポートが stdio であること。"""
    mgr = ContextLayerManager()
    server = EvolutionMCPServer(context_layer_manager=mgr)
    assert server.transport == "stdio"

  def test_sse_transport_configured(self) -> None:
    """SSE トランスポートが設定可能であること。"""
    mgr = ContextLayerManager()
    server = EvolutionMCPServer(
      context_layer_manager=mgr,
      transport="sse",
      sse_host="0.0.0.0",
      sse_port=9090,
    )
    assert server.transport == "sse"

  def test_server_name(self) -> None:
    """FastMCP サーバー名が "agent-evolution" であること。"""
    mgr = ContextLayerManager()
    server = EvolutionMCPServer(context_layer_manager=mgr)
    assert server.server.name == "agent-evolution"


class TestToolRegistration:
  """ツール登録テスト"""

  @pytest.mark.asyncio
  async def test_get_semantic_context_tool_registered(
    self, mcp_server: EvolutionMCPServer
  ) -> None:
    """get_semantic_context ツールが登録されていること。"""
    tools = await mcp_server.server.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_semantic_context" in tool_names

  @pytest.mark.asyncio
  async def test_tool_has_description(
    self, mcp_server: EvolutionMCPServer
  ) -> None:
    """登録ツールに説明文が設定されていること。"""
    tools = await mcp_server.server.list_tools()
    tool = next(t for t in tools if t.name == "get_semantic_context")
    assert tool.description is not None
    assert "semantic context" in tool.description.lower()


class TestHandleToolCall:
  """ツール呼び出しテスト"""

  @pytest.mark.asyncio
  async def test_successful_domain_retrieval(
    self, mcp_server: EvolutionMCPServer
  ) -> None:
    """存在するドメインのコンテキストを正常に取得できること。"""
    result = await mcp_server.handle_tool_call(
      "get_semantic_context",
      {"profile_id": "prof_000001", "domain": "problem_solving"},
    )
    assert result.type == "text"
    assert "分析的にアプローチし段階的に解決する" in result.text

  @pytest.mark.asyncio
  async def test_retrieval_communication_style(
    self, mcp_server: EvolutionMCPServer
  ) -> None:
    """communication_style ドメインを取得できること。"""
    result = await mcp_server.handle_tool_call(
      "get_semantic_context",
      {"profile_id": "prof_000001", "domain": "communication_style"},
    )
    assert "論理的で簡潔な表現を好む" in result.text

  @pytest.mark.asyncio
  async def test_error_for_nonexistent_domain(
    self, mcp_server: EvolutionMCPServer
  ) -> None:
    """存在しないドメインでエラーレスポンスが返ること。"""
    result = await mcp_server.handle_tool_call(
      "get_semantic_context",
      {"profile_id": "prof_000001", "domain": "nonexistent_domain"},
    )
    assert result.type == "text"
    assert "Error" in result.text
    assert "nonexistent_domain" in result.text

  @pytest.mark.asyncio
  async def test_error_for_unloaded_profile(
    self, mcp_server: EvolutionMCPServer
  ) -> None:
    """未ロードの profile_id でエラーレスポンスが返ること。"""
    result = await mcp_server.handle_tool_call(
      "get_semantic_context",
      {"profile_id": "prof_999999", "domain": "problem_solving"},
    )
    assert result.type == "text"
    assert "Error" in result.text
    assert "prof_999999" in result.text

  @pytest.mark.asyncio
  async def test_multiple_profiles_isolation(self) -> None:
    """複数プロファイル間でデータが隔離されていること。"""
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

    server = EvolutionMCPServer(context_layer_manager=mgr)

    # prof_000001 のドメインは prof_000002 で取得不可
    result = await server.handle_tool_call(
      "get_semantic_context",
      {"profile_id": "prof_000002", "domain": "problem_solving"},
    )
    assert "Error" in result.text

    # prof_000002 固有のドメインは取得可能
    result = await server.handle_tool_call(
      "get_semantic_context",
      {"profile_id": "prof_000002", "domain": "creativity"},
    )
    assert "直感的に発想し実験を重ねる" in result.text


class TestLogging:
  """ロギングテスト"""

  @pytest.mark.asyncio
  async def test_successful_call_logs_invocation(
    self, mcp_server: EvolutionMCPServer, caplog: pytest.LogCaptureFixture
  ) -> None:
    """成功した呼び出しがログに記録されること。"""
    with caplog.at_level(logging.INFO, logger="app.evolution.mcp_server"):
      await mcp_server.handle_tool_call(
        "get_semantic_context",
        {"profile_id": "prof_000001", "domain": "problem_solving"},
      )

    assert any("MCP tool invocation" in r.message for r in caplog.records)
    assert any("status=success" in r.message for r in caplog.records)
    assert any("prof_000001" in r.message for r in caplog.records)
    assert any("problem_solving" in r.message for r in caplog.records)

  @pytest.mark.asyncio
  async def test_error_call_logs_invocation(
    self, mcp_server: EvolutionMCPServer, caplog: pytest.LogCaptureFixture
  ) -> None:
    """エラー呼び出しがログに記録されること。"""
    with caplog.at_level(logging.INFO, logger="app.evolution.mcp_server"):
      await mcp_server.handle_tool_call(
        "get_semantic_context",
        {"profile_id": "prof_000001", "domain": "nonexistent"},
      )

    assert any("status=error" in r.message for r in caplog.records)

  @pytest.mark.asyncio
  async def test_log_contains_timestamp(
    self, mcp_server: EvolutionMCPServer, caplog: pytest.LogCaptureFixture
  ) -> None:
    """ログにタイムスタンプが含まれること。"""
    with caplog.at_level(logging.INFO, logger="app.evolution.mcp_server"):
      await mcp_server.handle_tool_call(
        "get_semantic_context",
        {"profile_id": "prof_000001", "domain": "problem_solving"},
      )

    # ISO 8601 タイムスタンプの部分文字列で確認
    assert any("timestamp=" in r.message for r in caplog.records)


class TestTransportProperty:
  """トランスポート設定プロパティテスト"""

  def test_stdio_transport(self) -> None:
    """stdio トランスポートが正しく返されること。"""
    mgr = ContextLayerManager()
    server = EvolutionMCPServer(context_layer_manager=mgr, transport="stdio")
    assert server.transport == "stdio"

  def test_sse_transport(self) -> None:
    """sse トランスポートが正しく返されること。"""
    mgr = ContextLayerManager()
    server = EvolutionMCPServer(context_layer_manager=mgr, transport="sse")
    assert server.transport == "sse"
