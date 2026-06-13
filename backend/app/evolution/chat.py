"""1対1チャットサービス

スレッド管理・会話履歴・推論パイプライン統合を担う。
SSE ストリーミングレスポンスをサポートする。
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import aiosqlite

from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.routing_engine import RoutingEngine

logger = logging.getLogger(__name__)


class ChatService:
  """1対1チャットサービス

  スレッド管理・会話履歴・推論パイプライン統合を担う。
  SSE ストリーミングレスポンスをサポート。
  """

  DEFAULT_CONTEXT_WINDOW: int = 20

  def __init__(
    self,
    db_path: str,
    routing_engine: RoutingEngine,
    context_layer_manager: ContextLayerManager,
    context_window: int = 20,
  ):
    """ChatService を初期化する。

    Args:
      db_path: SQLite DB ファイルパス (evolution.db)
      routing_engine: LLM ルーティングエンジン
      context_layer_manager: 3層コンテキスト管理
      context_window: LLM コンテキストに含む直近ターン数（デフォルト20）
    """
    self._db_path = db_path
    self._routing_engine = routing_engine
    self._clm = context_layer_manager
    self._context_window = context_window

  async def init_db(self) -> None:
    """threads テーブルとインデックスを初期化する。"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS threads (
          turn_id TEXT PRIMARY KEY,
          thread_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_threads_thread
        ON threads(thread_id, created_at)
      """)
      await db.commit()
    logger.info("ChatService: threads table initialized at %s", self._db_path)

  async def send_message(
    self,
    agent_id: str,
    message: str,
    thread_id: str | None = None,
  ) -> dict:
    """メッセージを送信し、エージェントのレスポンスを返す。

    thread_id が None の場合、新規スレッドを作成する。
    直近 context_window ターンを LLM コンテキストに含む。

    Args:
      agent_id: 対象エージェントの ID
      message: ユーザーのメッセージテキスト
      thread_id: 既存スレッド ID（None で新規作成）

    Returns:
      {thread_id, agent_id, response, created_at} の辞書
    """
    thread_id = thread_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # 直近の会話履歴を取得（コンテキストウィンドウ分）
    history = await self._get_recent_history(thread_id, self._context_window)

    # Base OS からシステムプロンプトを構築
    system_prompt = self._build_system_prompt(agent_id)

    # RoutingEngine 経由で LLM にリクエスト
    response = await self._routing_engine.route(
      utterance=message,
      system_prompt=system_prompt,
    )

    # ユーザーメッセージとアシスタントレスポンスを保存
    await self._store_turn(thread_id, agent_id, "user", message, now)
    response_time = datetime.now(timezone.utc).isoformat()
    await self._store_turn(thread_id, agent_id, "assistant", response, response_time)

    return {
      "thread_id": thread_id,
      "agent_id": agent_id,
      "response": response,
      "created_at": response_time,
    }

  async def stream_response(
    self,
    agent_id: str,
    message: str,
    thread_id: str | None = None,
  ) -> AsyncGenerator[str, None]:
    """SSE ストリーミングレスポンスを生成する。

    PoC 段階: フルレスポンスを1チャンクで yield する。
    将来的にはトークン単位のストリーミングに拡張予定。

    Args:
      agent_id: 対象エージェントの ID
      message: ユーザーのメッセージテキスト
      thread_id: 既存スレッド ID（None で新規作成）

    Yields:
      "data: {json_chunk}\\n\\n" 形式の SSE イベント文字列
    """
    # send_message を呼び出してフルレスポンスを取得
    result = await self.send_message(agent_id, message, thread_id)

    # SSE 形式で1チャンクとして送出
    chunk = json.dumps({
      "thread_id": result["thread_id"],
      "agent_id": result["agent_id"],
      "content": result["response"],
      "done": True,
    }, ensure_ascii=False)

    yield f"data: {chunk}\n\n"

  async def get_history(
    self,
    thread_id: str,
    limit: int | None = None,
  ) -> list[dict]:
    """スレッドの会話履歴を取得する。

    Args:
      thread_id: 取得対象のスレッド ID
      limit: 取得件数上限（None で全件）

    Returns:
      [{turn_id, role, content, created_at}, ...] のリスト（時系列昇順）
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      if limit is not None:
        # 最新 limit 件を取得するために降順で取得後、昇順に戻す
        async with db.execute(
          "SELECT turn_id, role, content, created_at "
          "FROM threads WHERE thread_id = ? "
          "ORDER BY created_at DESC LIMIT ?",
          (thread_id, limit),
        ) as cursor:
          rows = await cursor.fetchall()
        # 時系列昇順に並べ替え
        rows = list(reversed(rows))
      else:
        async with db.execute(
          "SELECT turn_id, role, content, created_at "
          "FROM threads WHERE thread_id = ? "
          "ORDER BY created_at ASC",
          (thread_id,),
        ) as cursor:
          rows = await cursor.fetchall()

    return [
      {
        "turn_id": row["turn_id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
      }
      for row in rows
    ]

  def _build_system_prompt(self, agent_id: str) -> str:
    """エージェントの Base OS からシステムプロンプトを構築する。

    ContextLayerManager から Base OS を取得し、
    パーソナリティ特性をシステムプロンプトに組み込む。

    Args:
      agent_id: 対象エージェント ID

    Returns:
      システムプロンプト文字列。Base OS 取得失敗時はデフォルトプロンプト。
    """
    try:
      # agent_id に対応する profile_id を特定する必要があるが、
      # ChatService は agent_id を直接 profile_id として扱わず、
      # CLM の全キャッシュから検索する。
      # PoC 段階: agent_id をそのまま profile_id として試行する。
      # 実運用では AgentManager 経由で profile_id を解決する。
      base_os = self._clm.get_base_os(agent_id)
      parts = [
        "You are an AI assistant with the following personality:",
        f"Decision style: {base_os.decision_style}",
      ]
      # axes をテキストに変換
      if base_os.axes:
        parts.append("Personality axes:")
        for axis_name, score in base_os.axes.items():
          parts.append(f"  - {axis_name}: {score}")
      # do_not_list をガードレールに
      if base_os.do_not_list:
        parts.append("You MUST NOT:")
        for item in base_os.do_not_list:
          parts.append(f"  - {item}")
      return "\n".join(parts)
    except (KeyError, AttributeError):
      # Base OS が取得できない場合はデフォルトプロンプトを使用
      logger.warning(
        "Failed to build system prompt for agent_id=%s, using default",
        agent_id,
      )
      return "You are a helpful AI assistant."

  async def _get_recent_history(
    self, thread_id: str, limit: int
  ) -> list[dict]:
    """直近 limit 件の会話履歴を取得する（内部用）。

    Args:
      thread_id: スレッド ID
      limit: 取得件数上限

    Returns:
      [{role, content}, ...] のリスト（時系列昇順）
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
        "SELECT role, content FROM threads "
        "WHERE thread_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (thread_id, limit),
      ) as cursor:
        rows = await cursor.fetchall()
    # 時系列昇順に並べ替え
    return [
      {"role": row["role"], "content": row["content"]}
      for row in reversed(rows)
    ]

  async def _store_turn(
    self,
    thread_id: str,
    agent_id: str,
    role: str,
    content: str,
    created_at: str,
  ) -> None:
    """1ターンを DB に保存する。

    Args:
      thread_id: スレッド ID
      agent_id: エージェント ID
      role: "user" or "assistant"
      content: メッセージ内容
      created_at: ISO 8601 タイムスタンプ
    """
    turn_id = str(uuid.uuid4())
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        """
        INSERT INTO threads (turn_id, thread_id, agent_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (turn_id, thread_id, agent_id, role, content, created_at),
      )
      await db.commit()
    logger.debug(
      "Turn stored: turn_id=%s, thread_id=%s, role=%s",
      turn_id, thread_id, role,
    )
