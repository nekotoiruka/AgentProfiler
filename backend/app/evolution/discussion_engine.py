"""マルチエージェント・ターン制議論エンジン

複数の分身エージェントがテーマに基づいてターン制で自律的に議論する
対話セッションを管理する。SQLite 永続化と SSE ストリーミングをサポート。
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator

import aiosqlite

from app.evolution.agent_manager import AgentManager
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.memory_utils import (
  build_rich_system_prompt,
  execute_search_memory,
)
from app.evolution.routing_engine import MEMORY_SEARCH_TOOL, RoutingEngine

logger = logging.getLogger(__name__)


@dataclass
class DiscussionTurn:
  """議論の1ターン（1エージェントの1発話）を表すデータクラス"""

  turn_number: int
  agent_id: str
  display_name: str
  content: str
  timestamp: str


@dataclass
class InsightSummary:
  """議論完了後の発見サマリー"""

  discussion_id: str
  key_insights: list[str]  # 3-5 個の主要な気づき
  disagreements: list[str]  # 対立点
  unexpected_perspectives: list[str]  # 予想外の視点
  actionable_suggestions: list[str]  # 人間への actionable 提案
  generated_at: str  # ISO 8601


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
      # インサイトサマリーテーブル
      await db.execute("""
        CREATE TABLE IF NOT EXISTS discussion_summaries (
          discussion_id TEXT PRIMARY KEY,
          key_insights TEXT NOT NULL,
          disagreements TEXT NOT NULL,
          unexpected_perspectives TEXT NOT NULL,
          actionable_suggestions TEXT NOT NULL,
          generated_at TEXT NOT NULL
        )
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
    # エージェント表示名と profile_id を事前に取得
    agent_display_names: dict[str, str] = {}
    agent_profile_ids: dict[str, str] = {}
    for agent_id in agent_ids:
      record = await self._agent_manager.get(agent_id)
      if record:
        agent_display_names[agent_id] = record.display_name
        agent_profile_ids[agent_id] = record.profile_id
      else:
        agent_display_names[agent_id] = agent_id
        agent_profile_ids[agent_id] = ""

    # 議論の累積履歴（全ターンのテキスト）
    history: list[dict[str, str]] = []

    for turn_number in range(1, total_turns + 1):
      # ラウンドロビンでエージェントを選択
      agent_idx = (turn_number - 1) % len(agent_ids)
      agent_id = agent_ids[agent_idx]
      display_name = agent_display_names[agent_id]
      profile_id = agent_profile_ids[agent_id]

      # エージェント固有のリッチシステムプロンプトを構築
      other_names = [
        agent_display_names.get(aid, aid)
        for aid in agent_ids if aid != agent_id
      ]
      system_prompt = self._build_system_prompt(
        agent_id, profile_id, theme, agent_ids, agent_display_names
      )

      # ユーザーメッセージ: テーマ + これまでの会話履歴
      utterance = self._build_utterance(theme, history, display_name)

      # Responses API + Function Calling でツール付き推論
      # 各エージェントが自分の記憶を検索できる
      async def _make_tool_executor(pid: str):
        """クロージャで profile_id をキャプチャする"""
        async def executor(name: str, args: dict) -> str:
          return await execute_search_memory(
            name, args, pid, self._clm
          )
        return executor

      tool_executor = await _make_tool_executor(profile_id)

      response = await self._routing_engine.route_with_tools(
        utterance=utterance,
        system_prompt=system_prompt,
        tools=[MEMORY_SEARCH_TOOL],
        tool_executor=tool_executor,
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
    profile_id: str,
    theme: str,
    agent_ids: list[str],
    agent_display_names: dict[str, str],
  ) -> str:
    """エージェント固有のリッチなシステムプロンプトを構築する。

    ProfileOutput 全体（persona, communication_tone, semantic_contexts, lexical_tags）
    + 議論コンテキスト（テーマ・他参加者）を含むプロンプトを生成する。

    Args:
      agent_id: 現在発話するエージェント ID
      profile_id: エージェントに紐づく profile_id
      theme: 議論テーマ
      agent_ids: 全参加エージェント ID
      agent_display_names: エージェント ID → 表示名のマッピング

    Returns:
      システムプロンプト文字列
    """
    display_name = agent_display_names.get(agent_id, agent_id)
    other_names = [
      agent_display_names.get(aid, aid)
      for aid in agent_ids if aid != agent_id
    ]

    try:
      profile = self._clm.get_profile(profile_id)
      return build_rich_system_prompt(
        profile=profile,
        agent_display_name=display_name,
        theme=theme,
        other_participants=other_names,
      )
    except (KeyError, AttributeError) as e:
      logger.warning(
        "Failed to build rich system prompt for agent_id=%s: %s, using fallback",
        agent_id, e,
      )
      return (
        f"あなたは「{display_name}」です。"
        f"テーマ「{theme}」について議論しています。"
        f"他の参加者: {', '.join(other_names)}。"
        "自分の人格として自然に発言してください。"
      )

  def _build_utterance(
    self,
    theme: str,
    history: list[dict[str, str]],
    current_display_name: str,
  ) -> str:
    """LLM に送るユーザーメッセージ（会話コンテキスト）を構築する。

    自分の過去発言と他者の発言を明確に区別し、
    モデルが「自分の人格」と「相手の意見」を混同しないようにする。

    Args:
      theme: 議論テーマ
      history: これまでの発話履歴
      current_display_name: 現在発話するエージェントの表示名

    Returns:
      LLM に送信するメッセージ文字列
    """
    parts = [f"議論テーマ: {theme}"]

    if history:
      # 自分の過去発言と他者の発言を分離
      my_past = [e for e in history if e["display_name"] == current_display_name]
      others = [e for e in history if e["display_name"] != current_display_name]

      if others:
        parts.append("")
        parts.append("--- 他の参加者の発言（あなたの発言ではありません） ---")
        for entry in others:
          parts.append(f"[{entry['display_name']}]: {entry['content']}")

      if my_past:
        parts.append("")
        parts.append("--- あなた自身の過去の発言 ---")
        for entry in my_past:
          parts.append(f"[あなた]: {entry['content']}")

    parts.append("")
    parts.append(
      f"あなたは「{current_display_name}」です。"
      "上記の他者の発言を踏まえて、あなた自身の人格設定と経験に基づいて発言してください。"
      "他者の経験や趣味を自分のものとして語らないでください。"
      "1〜3文で簡潔に。"
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

  async def generate_summary(self, discussion_id: str) -> InsightSummary:
    """議論ログ全体を LLM で要約し、インサイトを抽出する。

    全ターンを LLM に投入し、人間にとって actionable な
    発見・気づき・対立点・予想外の視点・提案をまとめる。
    生成結果は DB にキャッシュされ、再生成時は上書きされる。

    Args:
      discussion_id: 対象の議論セッション ID

    Returns:
      InsightSummary

    Raises:
      ValueError: discussion_id が存在しないまたはターンが空の場合
      RuntimeError: LLM が利用不可の場合
    """
    history = await self.get_history(discussion_id)
    if not history:
      raise ValueError(f"Discussion '{discussion_id}' not found or has no turns")

    # 議論ログをテキストに整形
    transcript_lines = []
    for turn in history:
      transcript_lines.append(
        f"[Turn {turn['turn_number']}] {turn['display_name']}: {turn['content']}"
      )
    transcript = "\n".join(transcript_lines)

    # LLM にインサイト抽出を依頼
    system_prompt = (
      "You are an expert discussion analyst. "
      "Analyze the following multi-agent discussion transcript and extract insights "
      "for the human observer. Respond in JSON format with these keys:\n"
      '- "key_insights": array of 3-5 main discoveries or realizations\n'
      '- "disagreements": array of points where agents disagreed\n'
      '- "unexpected_perspectives": array of viewpoints that were surprising '
      "given the agents' personality parameters\n"
      '- "actionable_suggestions": array of concrete suggestions for the human\n'
      "Respond ONLY with valid JSON. Use Japanese for all text content."
    )

    try:
      response = await self._routing_engine.route(
        utterance=f"以下の議論を分析してください:\n\n{transcript}",
        system_prompt=system_prompt,
      )
    except RuntimeError:
      raise RuntimeError("LLM unavailable for summary generation")

    # LLM レスポンスを JSON パース
    try:
      data = json.loads(response)
    except json.JSONDecodeError:
      # JSON 部分を抽出する試み
      import re
      match = re.search(r"\{.*\}", response, re.DOTALL)
      if match:
        data = json.loads(match.group())
      else:
        # フォールバック: レスポンス全体を key_insights に格納
        data = {
          "key_insights": [response],
          "disagreements": [],
          "unexpected_perspectives": [],
          "actionable_suggestions": [],
        }

    generated_at = datetime.now(timezone.utc).isoformat()

    summary = InsightSummary(
      discussion_id=discussion_id,
      key_insights=data.get("key_insights", []),
      disagreements=data.get("disagreements", []),
      unexpected_perspectives=data.get("unexpected_perspectives", []),
      actionable_suggestions=data.get("actionable_suggestions", []),
      generated_at=generated_at,
    )

    # DB にキャッシュ (UPSERT)
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        """
        INSERT INTO discussion_summaries
          (discussion_id, key_insights, disagreements,
           unexpected_perspectives, actionable_suggestions, generated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(discussion_id) DO UPDATE SET
          key_insights = excluded.key_insights,
          disagreements = excluded.disagreements,
          unexpected_perspectives = excluded.unexpected_perspectives,
          actionable_suggestions = excluded.actionable_suggestions,
          generated_at = excluded.generated_at
        """,
        (
          discussion_id,
          json.dumps(summary.key_insights, ensure_ascii=False),
          json.dumps(summary.disagreements, ensure_ascii=False),
          json.dumps(summary.unexpected_perspectives, ensure_ascii=False),
          json.dumps(summary.actionable_suggestions, ensure_ascii=False),
          generated_at,
        ),
      )
      await db.commit()

    logger.info("Discussion summary generated: discussion_id=%s", discussion_id)
    return summary

  async def get_summary(self, discussion_id: str) -> InsightSummary | None:
    """キャッシュ済みのインサイトサマリーを取得する。

    Args:
      discussion_id: 対象の議論セッション ID

    Returns:
      InsightSummary。未生成の場合は None。
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
        "SELECT * FROM discussion_summaries WHERE discussion_id = ?",
        (discussion_id,),
      ) as cursor:
        row = await cursor.fetchone()
        if row is None:
          return None
        return InsightSummary(
          discussion_id=row["discussion_id"],
          key_insights=json.loads(row["key_insights"]),
          disagreements=json.loads(row["disagreements"]),
          unexpected_perspectives=json.loads(row["unexpected_perspectives"]),
          actionable_suggestions=json.loads(row["actionable_suggestions"]),
          generated_at=row["generated_at"],
        )
