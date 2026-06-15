"""1対1チャットサービス

スレッド管理・会話履歴・推論パイプライン統合を担う。
SSE ストリーミングレスポンスをサポートする。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, AsyncGenerator

import aiosqlite

from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.memory_utils import (
  build_rich_system_prompt,
  execute_search_memory,
  get_answer_summaries,
)
from app.evolution.routing_engine import RoutingEngine

if TYPE_CHECKING:
  from app.decision_engine.mode_detector import ModeDetector
  from app.models.profile import ProfileOutput

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
    agent_manager=None,
    context_window: int = 20,
    mode_detector: ModeDetector | None = None,
  ):
    """ChatService を初期化する。

    Args:
      db_path: SQLite DB ファイルパス (evolution.db)
      routing_engine: LLM ルーティングエンジン
      context_layer_manager: 3層コンテキスト管理
      agent_manager: agent_id → profile_id 解決用 AgentManager
      context_window: LLM コンテキストに含む直近ターン数（デフォルト20）
      mode_detector: コンテキスト適応モード検出エンジン（None の場合モード検出スキップ）
    """
    self._db_path = db_path
    self._routing_engine = routing_engine
    self._clm = context_layer_manager
    self._agent_manager = agent_manager
    self._context_window = context_window
    self._mode_detector = mode_detector
    # agent_id → profile_id のインメモリキャッシュ（DB アクセス削減）
    self._profile_id_cache: dict[str, str] = {}
    # failure_patterns インデックス済みフラグ（agent_id → indexed）
    self._failure_indexed: dict[str, bool] = {}

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

    # agent_id → profile_id を事前に解決してキャッシュ
    await self._resolve_profile_id(agent_id)

    # failure_patterns のインデックス（初回のみ）
    if not self._failure_indexed.get(agent_id):
      await self._try_index_failure_patterns(agent_id)

    # 直近の会話履歴を取得（コンテキストウィンドウ分）
    history = await self._get_recent_history(thread_id, self._context_window)

    # Base OS からシステムプロンプトを構築
    system_prompt = self._build_system_prompt(agent_id)

    # コンテキスト適応モード検出 → システムプロンプト追記
    system_prompt = self._detect_and_apply_mode(agent_id, message, system_prompt, history)

    # Responses API + function calling でツール付き推論
    # search_memory ツールでペルソナの記憶/経験を検索可能にする
    from app.evolution.routing_engine import MEMORY_SEARCH_TOOL

    profile_id = self._profile_id_cache.get(agent_id)

    async def tool_executor(name: str, args: dict) -> str:
      """search_memory ツールの実行（共用ユーティリティに委譲）"""
      if profile_id:
        return await execute_search_memory(name, args, profile_id, self._clm)
      return "記憶データにアクセスできません。"

    # 会話履歴を含む発話を構築
    utterance_parts = []
    if history:
      utterance_parts.append("これまでの会話:")
      for h in history[-10:]:  # 最新10ターンのみ
        utterance_parts.append(f"  {h['role']}: {h['content']}")
      utterance_parts.append("")
    utterance_parts.append(f"user: {message}")
    full_utterance = "\n".join(utterance_parts)

    response = await self._routing_engine.route_with_tools(
      utterance=full_utterance,
      system_prompt=system_prompt,
      tools=[MEMORY_SEARCH_TOOL],
      tool_executor=tool_executor,
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
    """エージェントの全プロファイル情報からリッチなシステムプロンプトを構築する。

    共用ユーティリティ build_rich_system_prompt を使用。

    Args:
      agent_id: 対象エージェント ID

    Returns:
      システムプロンプト文字列。プロファイル取得失敗時はデフォルトプロンプト。
    """
    try:
      profile_id = self._profile_id_cache.get(agent_id)
      lookup_key = profile_id or agent_id
      profile = self._clm.get_profile(lookup_key)
      display_name = profile.persona.nickname if profile.persona.nickname else agent_id
      return build_rich_system_prompt(profile=profile, agent_display_name=display_name)
    except (KeyError, AttributeError) as e:
      logger.warning(
        "Failed to build system prompt for agent_id=%s: %s",
        agent_id, e,
      )
      return "You are a helpful AI assistant."

  def _detect_and_apply_mode(
    self,
    agent_id: str,
    message: str,
    system_prompt: str,
    recent_history: list[dict] | None = None,
  ) -> str:
    """モード検出 → システムプロンプト追記。

    ModeDetector が未設定またはプロファイルに context_adaptation がない場合は
    スキップし、性能ペナルティなしで元のプロンプトをそのまま返す。

    Args:
      agent_id: 対象エージェント ID
      message: ユーザーメッセージ
      system_prompt: 現在のシステムプロンプト
      recent_history: 直近の会話履歴（ターンリスト）

    Returns:
      モード適用後のシステムプロンプト（変更なしの場合は元のまま）
    """
    if self._mode_detector is None:
      return system_prompt

    recent_turns = recent_history or []
    mode_name = self._mode_detector.detect_mode(message, recent_turns)
    if mode_name is None:
      return system_prompt

    mode_prompt = self._mode_detector.format_mode_prompt(mode_name)
    if not mode_prompt:
      return system_prompt

    # モード設定をシステムプロンプト末尾に追記
    return f"{system_prompt}\n\n{mode_prompt}"

  async def _try_index_failure_patterns(self, agent_id: str) -> None:
    """failure_patterns のインデックスを試行する（エラー時はスキップ）。

    Args:
      agent_id: 対象エージェント ID
    """
    try:
      profile_id = self._profile_id_cache.get(agent_id)
      lookup_key = profile_id or agent_id
      profile = self._clm.get_profile(lookup_key)
      await self._index_failure_patterns(profile)
      self._failure_indexed[agent_id] = True
    except (KeyError, AttributeError) as e:
      # プロファイル未ロード時はスキップ
      logger.debug(
        "Skipping failure_patterns indexing for agent_id=%s: %s",
        agent_id, e,
      )
      self._failure_indexed[agent_id] = True

  async def _index_failure_patterns(self, profile: ProfileOutput) -> None:
    """failure_patterns を search_memory 用にインデックスする。

    degradation_triggers と recurring_mistakes を
    semantic_contexts として登録し、検索可能にする。
    プロファイルに failure_patterns がない場合はスキップ。

    Args:
      profile: ProfileOutput インスタンス
    """
    if not hasattr(profile, "failure_patterns") or profile.failure_patterns is None:
      return

    fp = profile.failure_patterns
    entries: dict[str, str] = {}

    # degradation_triggers をインデックス
    if fp.degradation_triggers:
      entries["degradation_triggers"] = (
        "パフォーマンス劣化の引き金: " + "; ".join(fp.degradation_triggers)
      )

    # recurring_mistakes をインデックス
    if fp.recurring_mistakes:
      entries["recurring_mistakes"] = (
        "繰り返しがちなミス: " + "; ".join(fp.recurring_mistakes)
      )

    if not entries:
      return

    # SemanticRetriever にインデックス（semantic_contexts と同様の方式）
    semantic_retriever = getattr(self._clm, "_semantic_retriever", None)
    if semantic_retriever is not None:
      # 既存の semantic_contexts に追加する形でインデックス
      await semantic_retriever.index_profile(
        profile.profile_id, entries
      )
      logger.info(
        "Indexed %d failure_patterns entries for profile_id=%s",
        len(entries), profile.profile_id,
      )
    else:
      # SemanticRetriever がない場合はローカルキャッシュに追加
      local_contexts = getattr(self._clm, "_semantic_contexts_local", {})
      if profile.profile_id in local_contexts:
        local_contexts[profile.profile_id].update(entries)
      else:
        local_contexts[profile.profile_id] = entries
      logger.info(
        "Indexed %d failure_patterns entries locally for profile_id=%s",
        len(entries), profile.profile_id,
      )

  async def _resolve_profile_id(self, agent_id: str) -> str | None:
    """agent_id → profile_id を解決してキャッシュする。

    AgentManager が設定されている場合は DB から取得する。
    未設定の場合は None を返す。
    """
    if agent_id in self._profile_id_cache:
      return self._profile_id_cache[agent_id]

    if self._agent_manager is not None:
      record = await self._agent_manager.get(agent_id)
      if record is not None:
        self._profile_id_cache[agent_id] = record.profile_id
        return record.profile_id
    return None

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
