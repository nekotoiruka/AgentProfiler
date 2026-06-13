"""MCP Server: Model Context Protocol サーバー実装

semantic_contexts の各ドメインを MCP Tool として公開し、
外部エージェントが標準プロトコルでコンテキストを取得可能にする。
stdio / SSE トランスポートに対応。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

if TYPE_CHECKING:
  from app.evolution.context_layer_manager import ContextLayerManager

logger = logging.getLogger(__name__)


class EvolutionMCPServer:
  """Model Context Protocol サーバー

  semantic_contexts の各ドメインを MCP Tool として公開し、
  外部エージェントが標準プロトコルでコンテキストを取得可能にする。

  対応トランスポート:
  - stdio: 標準入出力経由（デフォルト）
  - sse: Server-Sent Events 経由（HTTP）
  """

  def __init__(
    self,
    context_layer_manager: ContextLayerManager,
    transport: str = "stdio",
    sse_host: str = "localhost",
    sse_port: int = 8081,
  ):
    """EvolutionMCPServer を初期化する。

    Args:
      context_layer_manager: 3層コンテキスト管理コンポーネント
      transport: トランスポートモード ("stdio" or "sse")
      sse_host: SSE モード時のバインドホスト
      sse_port: SSE モード時のポート番号
    """
    self._clm = context_layer_manager
    self._transport = transport
    self._sse_host = sse_host
    self._sse_port = sse_port
    self._server = FastMCP(
      name="agent-evolution",
      host=sse_host,
      port=sse_port,
    )
    self._register_tools()
    logger.info(
      "EvolutionMCPServer initialized: transport=%s, sse=%s:%d",
      transport,
      sse_host,
      sse_port,
    )

  def _register_tools(self) -> None:
    """semantic_contexts ドメインを MCP Tool として登録する。

    汎用ツール "get_semantic_context" を登録し、
    profile_id と domain パラメータでスコープ付き取得を提供する。
    """

    @self._server.tool(
      name="get_semantic_context",
      description=(
        "Retrieve a semantic context entry for a specific domain and profile. "
        "Available domains depend on the loaded profile "
        "(e.g., problem_solving, communication_style, analog_habits, vacation_planning)."
      ),
    )
    async def get_semantic_context(profile_id: str, domain: str) -> str:
      """profile_id と domain を指定してセマンティックコンテキストを取得する。

      Args:
        profile_id: 対象プロファイルの識別子
        domain: 取得対象のコンテキストドメイン名

      Returns:
        セマンティックコンテキストのテキスト内容
      """
      return await self._handle_get_semantic_context(profile_id, domain)

    logger.debug("Registered MCP tool: get_semantic_context")

  async def _handle_get_semantic_context(
    self, profile_id: str, domain: str
  ) -> str:
    """get_semantic_context ツールの内部ハンドラ。

    ContextLayerManager からローカルの semantic_contexts を参照し、
    指定ドメインのテキストを返却する。

    Args:
      profile_id: 対象プロファイルの識別子
      domain: 取得対象のコンテキストドメイン名

    Returns:
      セマンティックコンテキストのテキスト

    Raises:
      ValueError: profile_id が未ロード、またはドメインが存在しない場合
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # profile_id のローカル semantic_contexts を取得
    # _semantic_contexts_local は profile_id → {domain: text} のマッピング
    local_contexts = self._clm._semantic_contexts_local.get(profile_id)

    if local_contexts is None:
      self._log_invocation(
        timestamp=timestamp,
        profile_id=profile_id,
        domain=domain,
        status="error",
      )
      raise ValueError(
        f"Profile '{profile_id}' is not loaded. "
        "Load the profile first via ContextLayerManager.load_profile()."
      )

    if domain not in local_contexts:
      self._log_invocation(
        timestamp=timestamp,
        profile_id=profile_id,
        domain=domain,
        status="error",
      )
      available = list(local_contexts.keys())
      raise ValueError(
        f"Domain '{domain}' not found for profile '{profile_id}'. "
        f"Available domains: {available}"
      )

    text = local_contexts[domain]
    self._log_invocation(
      timestamp=timestamp,
      profile_id=profile_id,
      domain=domain,
      status="success",
    )
    return text

  async def handle_tool_call(
    self, tool_name: str, arguments: dict
  ) -> TextContent:
    """Tool 呼び出しを処理し、対応する semantic_context を返す。

    FastMCP の call_tool を経由してツールを実行し、
    結果を TextContent として返却する。

    Args:
      tool_name: 呼び出すツール名
      arguments: ツールパラメータ辞書

    Returns:
      TextContent 形式のレスポンス
    """
    try:
      result = await self._server.call_tool(tool_name, arguments)
      # FastMCP.call_tool は Sequence[ContentBlock] を返す
      # 最初の要素からテキストを抽出
      if result and hasattr(result[0], "text"):
        return TextContent(type="text", text=result[0].text)
      # 文字列で返された場合のフォールバック
      return TextContent(type="text", text=str(result))
    except Exception as e:
      return TextContent(type="text", text=f"Error: {e}")

  async def run(self) -> None:
    """設定されたトランスポートで MCP サーバーを起動する。

    transport が "sse" の場合は SSE モードで起動し、
    それ以外は stdio モードで起動する。
    """
    if self._transport == "sse":
      logger.info(
        "Starting MCP server in SSE mode on %s:%d",
        self._sse_host,
        self._sse_port,
      )
      await self._server.run_sse_async()
    else:
      logger.info("Starting MCP server in stdio mode")
      await self._server.run_stdio_async()

  def _log_invocation(
    self,
    *,
    timestamp: str,
    profile_id: str,
    domain: str,
    status: str,
  ) -> None:
    """ツール呼び出しをロギングする。

    Args:
      timestamp: ISO 8601 形式のタイムスタンプ
      profile_id: 対象プロファイル識別子
      domain: リクエストされたドメイン名
      status: レスポンスステータス ("success" or "error")
    """
    logger.info(
      "MCP tool invocation: timestamp=%s, profile_id=%s, domain=%s, status=%s",
      timestamp,
      profile_id,
      domain,
      status,
    )

  @property
  def server(self) -> FastMCP:
    """内部の FastMCP サーバーインスタンスを返す。"""
    return self._server

  @property
  def transport(self) -> str:
    """設定済みのトランスポートモードを返す。"""
    return self._transport
