"""マルチエージェント・ターン制議論エンジン

複数の分身エージェントがテーマに基づいてターン制で自律的に議論する
対話セッションを管理する。SQLite 永続化と SSE ストリーミングをサポート。
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator

import aiosqlite

from app.evolution.agent_manager import AgentManager
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.routing_engine import RoutingEngine

logger = logging.getLogger(__name__)


@dataclass
class DiscussionTurn:
  """議論の1ターン（1エージェントの1発話）を表すデータクラス"""

  turn_number: int
  agent_id: str
  display_name: str
  content: str
  timestamp: str


class DiscussionEngine:
  """マルチエージェント・ターン制議論エンジン

  2〜6のエージェントがテーマに基づき順番に発話する議論セッションを管理する。
  各ターンは SQLite に永続化され、SSE ストリーミングで逐次配信可能。
  """

  def __init__(
    self,
    db_path: str,
    routing_engine: RoutingEngine,
    context_layer_manager: ContextLayerManager,
    agent_manager: AgentManager,
  ):
    """DiscussionEngine を初期化する。

    Args:
      db_path: SQLite DB ファイルパス (evolution.db)
      routing_engine: LLM ルーティングエンジン
      context_layer_manager: 3層コンテキスト管理
      agent_manager: 分身プロファイル管理
    """
    self._db_path = db_path
    self._routing_engine = routing_engine
    self._clm = context_layer_manager
    self._agent_manager = agent_manager

  async def init_db(self) -> None:
    """discussions テーブルとインデックスを初期化する。"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS discussions (
          turn_id TEXT PRIMARY KEY,
          discussion_id TEXT NOT NULL,
          turn_number INTEGER NOT NULL,
          agent_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_discussions_id
        ON discussions(discussion_id, turn_number)
      """)
      await db.commit()
    logger.info(
      "DiscussionEngine: discussions table initialized at %s",
      self._db_path,
    )

  async def start_discussion(
    self,
    agent_ids: list[str],
    theme: str,
  ) -> str:
    """議論セッションを開始する。

    エージェント数のバリデーション (2〜6) と
    全エージェントの存在・アクティブ状態を検証する。

    Args:
      agent_ids: 参加エージェントの ID リスト (2〜6)
      theme: 議論テーマ

    Returns:
      生成された discussion_id (UUID v4)

    Raises:
      ValueError: agent_ids の数が範囲外、または無効な agent_id が含まれる場合
    """
    # エージェント数バリデーション
    if len(agent_ids) < 2 or len(agent_ids) > 6:
      raise ValueError(
        f"agent_ids must contain 2 to 6 agents, got {len(agent_ids)}"
      )

    # 全エージェントの存在・アクティブ状態を確認
    invalid_ids: list[str] = []
    for agent_id in agent_ids:
      record = await self._agent_manager.get(agent_id)
      if record is None or not record.is_active:
        invalid_ids.append(agent_id)

    if invalid_ids:
      raise ValueError(
        f"Invalid or inactive agent_ids: {invalid_ids}"
      )

    discussion_id = str(uuid.uuid4())
    logger.info(
      "Discussion started: discussion_id=%s, agents=%s, theme=%s",
      discussion_id,
      agent_ids,
      theme,
    )
    return discussion_id

  async def run_turns(
    self,
    discussion_id: str,
    agent_ids: list[str],
    theme: str,
    max_turns_per_agent: int = 10,
  ) -> AsyncGenerator[DiscussionTurn, None]:
    """議論ターンを順次実行し、各ターンを yield する。

    各エージェントが順番に発話する。前ターンまでの全履歴を
    コンテキストに含め、RoutingEngine 経由で LLM にリクエストする。

    Args:
      discussion_id: 議論セッション ID
      agent_ids: 参加エージェントの ID リスト
      theme: 議論テーマ
      max_turns_per_agent: エージェント当たりの最大ターン数 (デフォルト10)

    Yields:
      各ターンの DiscussionTurn
    """
    total_turns = max_turns_per_agent * len(agent_ids)
    # エージェント表示名を事前に取得
    agent_display_names: dict[str, str] = {}
    for agent_id in agent_ids:
      record = await self._agent_manager.get(agent_id)
      if record:
        agent_display_names[agent_id] = record.display_name
      else:
        agent_display_names[agent_id] = agent_id

    # 議論の累積履歴（全ターンのテキスト）
    history: list[dict[str, str]] = []

    for turn_number in range(1, total_turns + 1):
      # ラウンドロビンでエージェントを選択
      agent_idx = (turn_number - 1) % len(agent_ids)
      agent_id = agent_ids[agent_idx]
      display_name = agent_display_names[agent_id]

      # エージェント固有のシステムプロンプトを構築
      system_prompt = self._build_system_prompt(agent_id, theme, agent_ids, agent_display_names)

      # ユーザーメッセージ: テーマ + これまでの会話履歴
      utterance = self._build_utterance(theme, history, display_name)

      # RoutingEngine 経由で LLM にリクエスト
      response = await self._routing_engine.route(
        utterance=utterance,
        system_prompt=system_prompt,
      )

      timestamp = datetime.now(timezone.utc).isoformat()

      # DB に永続化
      await self._store_turn(
        discussion_id=discussion_id,
        turn_number=turn_number,
        agent_id=agent_id,
        display_name=display_name,
        content=response,
        created_at=timestamp,
      )

      # 累積履歴に追加
      history.append({
        "agent_id": agent_id,
        "display_name": display_name,
        "content": response,
      })

      turn = DiscussionTurn(
        turn_number=turn_number,
        agent_id=agent_id,
        display_name=display_name,
        content=response,
        timestamp=timestamp,
      )

      yield turn

  async def stream_discussion(
    self,
    agent_ids: list[str],
    theme: str,
    max_turns_per_agent: int = 10,
  ) -> AsyncGenerator[str, None]:
    """SSE ストリーミングで議論ターンを逐次配信する。

    start_discussion() でセッションを開始し、run_turns() の各ターンを
    SSE イベント形式で yield する。

    Args:
      agent_ids: 参加エージェントの ID リスト
      theme: 議論テーマ
      max_turns_per_agent: エージェント当たりの最大ターン数

    Yields:
      "data: {json_turn}\\n\\n" 形式の SSE イベント文字列
    """
    discussion_id = await self.start_discussion(agent_ids, theme)

    async for turn in self.run_turns(
      discussion_id=discussion_id,
      agent_ids=agent_ids,
      theme=theme,
      max_turns_per_agent=max_turns_per_agent,
    ):
      payload = json.dumps({
        "discussion_id": discussion_id,
        "turn_number": turn.turn_number,
        "agent_id": turn.agent_id,
        "display_name": turn.display_name,
        "content": turn.content,
        "timestamp": turn.timestamp,
      }, ensure_ascii=False)
      yield f"data: {payload}\n\n"

  async def get_history(self, discussion_id: str) -> list[dict]:
    """議論の全ターン履歴を取得する。

    Args:
      discussion_id: 取得対象の議論セッション ID

    Returns:
      [{turn_id, turn_number, agent_id, display_name, content, created_at}, ...]
      のリスト（turn_number 昇順）
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
        "SELECT turn_id, turn_number, agent_id, display_name, content, created_at "
        "FROM discussions WHERE discussion_id = ? "
        "ORDER BY turn_number ASC",
        (discussion_id,),
      ) as cursor:
        rows = await cursor.fetchall()

    return [
      {
        "turn_id": row["turn_id"],
        "turn_number": row["turn_number"],
        "agent_id": row["agent_id"],
        "display_name": row["display_name"],
        "content": row["content"],
        "created_at": row["created_at"],
      }
      for row in rows
    ]

  def _build_system_prompt(
    self,
    agent_id: str,
    theme: str,
    agent_ids: list[str],
    agent_display_names: dict[str, str],
  ) -> str:
    """エージェント固有のシステムプロンプトを構築する。

    Base OS からパーソナリティ特性を取得し、
    議論コンテキスト（テーマ・参加者）を含むプロンプトを生成する。

    Args:
      agent_id: 現在発話するエージェント ID
      theme: 議論テーマ
      agent_ids: 全参加エージェント ID
      agent_display_names: エージェント ID → 表示名のマッピング

    Returns:
      システムプロンプト文字列
    """
    try:
      # AgentManager から profile_id を取得する代わりに、
      # PoC 段階では agent_id をそのまま CLM に渡す
      # (ChatService と同じパターン)
      base_os = self._clm.get_base_os(agent_id)
      parts = [
        f"You are {agent_display_names.get(agent_id, agent_id)}, "
        f"participating in a group discussion about: {theme}",
        "",
        "Your personality:",
        f"  Decision style: {base_os.decision_style}",
      ]
      if base_os.axes:
        parts.append("  Personality axes:")
        for axis_name, score in base_os.axes.items():
          parts.append(f"    - {axis_name}: {score}")
      if base_os.do_not_list:
        parts.append("  You MUST NOT:")
        for item in base_os.do_not_list:
          parts.append(f"    - {item}")

      # 他の参加者情報を追加
      other_agents = [
        agent_display_names.get(aid, aid)
        for aid in agent_ids
        if aid != agent_id
      ]
      parts.append("")
      parts.append(f"Other participants: {', '.join(other_agents)}")
      parts.append("")
      parts.append(
        "Respond naturally as your character. Be concise and engaging. "
        "Build on what others have said."
      )
      return "\n".join(parts)
    except (KeyError, AttributeError):
      # Base OS が取得できない場合はデフォルトプロンプト
      logger.warning(
        "Failed to build system prompt for agent_id=%s, using default",
        agent_id,
      )
      return (
        f"You are {agent_display_names.get(agent_id, agent_id)}, "
        f"participating in a group discussion about: {theme}. "
        "Respond naturally and concisely."
      )

  def _build_utterance(
    self,
    theme: str,
    history: list[dict[str, str]],
    current_display_name: str,
  ) -> str:
    """LLM に送るユーザーメッセージ（会話コンテキスト）を構築する。

    テーマと過去の全発話履歴を含め、現在のエージェントに
    次の発言を促すメッセージを生成する。

    Args:
      theme: 議論テーマ
      history: これまでの発話履歴
      current_display_name: 現在発話するエージェントの表示名

    Returns:
      LLM に送信するメッセージ文字列
    """
    parts = [f"Discussion theme: {theme}"]

    if history:
      parts.append("")
      parts.append("Conversation so far:")
      for entry in history:
        parts.append(f"  {entry['display_name']}: {entry['content']}")

    parts.append("")
    parts.append(
      f"Now it's your turn, {current_display_name}. "
      "Please share your thoughts."
    )
    return "\n".join(parts)

  async def _store_turn(
    self,
    discussion_id: str,
    turn_number: int,
    agent_id: str,
    display_name: str,
    content: str,
    created_at: str,
  ) -> None:
    """1ターンを DB に永続化する。

    Args:
      discussion_id: 議論セッション ID
      turn_number: ターン番号
      agent_id: 発話エージェント ID
      display_name: エージェント表示名
      content: 発話内容
      created_at: ISO 8601 タイムスタンプ
    """
    turn_id = str(uuid.uuid4())
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        """
        INSERT INTO discussions
          (turn_id, discussion_id, turn_number, agent_id, display_name, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (turn_id, discussion_id, turn_number, agent_id, display_name, content, created_at),
      )
      await db.commit()
    logger.debug(
      "Discussion turn stored: turn_id=%s, discussion_id=%s, turn=%d, agent=%s",
      turn_id,
      discussion_id,
      turn_number,
      agent_id,
    )
