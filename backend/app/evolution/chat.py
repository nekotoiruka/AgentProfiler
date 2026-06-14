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
    agent_manager=None,
    context_window: int = 20,
  ):
    """ChatService を初期化する。

    Args:
      db_path: SQLite DB ファイルパス (evolution.db)
      routing_engine: LLM ルーティングエンジン
      context_layer_manager: 3層コンテキスト管理
      agent_manager: agent_id → profile_id 解決用 AgentManager
      context_window: LLM コンテキストに含む直近ターン数（デフォルト20）
    """
    self._db_path = db_path
    self._routing_engine = routing_engine
    self._clm = context_layer_manager
    self._agent_manager = agent_manager
    self._context_window = context_window
    # agent_id → profile_id のインメモリキャッシュ（DB アクセス削減）
    self._profile_id_cache: dict[str, str] = {}

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

    # 直近の会話履歴を取得（コンテキストウィンドウ分）
    history = await self._get_recent_history(thread_id, self._context_window)

    # Base OS からシステムプロンプトを構築
    system_prompt = self._build_system_prompt(agent_id)

    # Responses API + function calling でツール付き推論
    # search_memory ツールでペルソナの記憶/経験を検索可能にする
    from app.evolution.routing_engine import MEMORY_SEARCH_TOOL

    profile_id = self._profile_id_cache.get(agent_id)

    async def tool_executor(name: str, args: dict) -> str:
      """search_memory ツールの実行: プロファイルの記憶・経験・趣味を検索

      データソース:
      1. lexical_tags — 趣味・スキル・ツールのキーワード
      2. 実回答データ — sessions.db から質問テキスト+選んだ選択肢を復元
      3. semantic_contexts — 4軸スコアから推定された行動傾向（参考情報）
      """
      if name == "search_memory" and profile_id:
        query = args.get("query", "")
        try:
          profile = self._clm.get_profile(profile_id)
        except (KeyError, AttributeError):
          return "記憶データにアクセスできません。"

        parts = []

        # 1. lexical_tags: 趣味・スキル・ツール等のキーワード一覧
        if profile.lexical_tags:
          parts.append("【あなたの関心事・趣味・スキル（実際の回答に基づく）】")
          parts.append(", ".join(profile.lexical_tags))

        # 2. 実回答データ: sessions.db から質問+選択肢テキストを復元
        answer_text = await self._get_answer_summaries(profile_id, query)
        if answer_text:
          parts.append("")
          parts.append("【あなたが実際にアンケートで答えた内容】")
          parts.append(answer_text)

        # 3. semantic_contexts: スコアから推定された傾向（参考）
        if profile.semantic_contexts:
          parts.append("")
          parts.append("【推定された行動傾向（参考情報）】")
          domain_labels = {
            "problem_solving": "問題解決",
            "communication_style": "コミュニケーション",
            "work_rhythm": "仕事のリズム",
            "analog_habits": "アナログな習慣",
            "lifestyle_preferences": "ライフスタイル",
          }
          for domain, text in profile.semantic_contexts.items():
            label = domain_labels.get(domain, domain)
            parts.append(f"[{label}] {text}")

        if not parts:
          return "関連する記憶は見つかりませんでした。"
        return "\n".join(parts)
      return f"Unknown tool: {name}"

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

    ProfileOutput の persona, communication_tone, semantic_contexts を
    全て活用し、LLM がその人格として振る舞うに十分な情報を含むプロンプトを生成する。

    Args:
      agent_id: 対象エージェント ID

    Returns:
      システムプロンプト文字列。プロファイル取得失敗時はデフォルトプロンプト。
    """
    try:
      profile_id = self._profile_id_cache.get(agent_id)
      lookup_key = profile_id or agent_id

      # 完全な ProfileOutput を取得（persona, communication_tone 等含む）
      profile = self._clm.get_profile(lookup_key)

      parts: list[str] = []

      # --- ペルソナ基本情報 ---
      parts.append("# あなたの人格設定")
      parts.append("")
      if hasattr(profile, "persona") and profile.persona:
        p = profile.persona
        parts.append(f"あなたは「{p.nickname}」という名前の人格です。")
        details = []
        if p.age_range:
          details.append(f"年齢層: {p.age_range}")
        if p.role:
          details.append(f"役割: {p.role}")
        if p.industry:
          details.append(f"業界: {p.industry}")
        if p.experience_years:
          details.append(f"経験: {p.experience_years}")
        if details:
          parts.append("、".join(details))
        parts.append("")

      # --- コミュニケーションスタイル（最重要: 口調を決定する） ---
      if hasattr(profile, "communication_tone") and profile.communication_tone:
        ct = profile.communication_tone
        parts.append("## 話し方のルール（必ず守ること）")
        parts.append("")
        if ct.pronoun:
          parts.append(f"- 一人称: 「{ct.pronoun}」を使う")
        if ct.formality:
          parts.append(f"- 敬語/カジュアル: {ct.formality}")
        if ct.text_style:
          parts.append(f"- テキストの特徴: {ct.text_style}")
        if ct.emotion_level:
          parts.append(f"- 感情表現: {ct.emotion_level}")
        if ct.humor:
          parts.append(f"- ユーモア: {ct.humor}")
        if hasattr(ct, "response_length") and ct.response_length:
          parts.append(f"- 回答の長さ: {ct.response_length}")
        parts.append("")

      # --- 思考特性（semantic_contexts: 行動パターンの自然言語記述） ---
      if profile.semantic_contexts:
        parts.append("## あなたの思考パターン・価値観")
        parts.append("")
        domain_labels = {
          "problem_solving": "問題解決の仕方",
          "communication_style": "コミュニケーションの傾向",
          "work_rhythm": "仕事のリズム",
          "analog_habits": "アナログな習慣",
          "lifestyle_preferences": "ライフスタイルの好み",
        }
        for domain, description in profile.semantic_contexts.items():
          label = domain_labels.get(domain, domain)
          parts.append(f"### {label}")
          parts.append(description)
          parts.append("")

      # --- 意思決定スタイル ---
      base_os = profile.base_os
      parts.append("## 意思決定スタイル")
      parts.append(f"あなたの意思決定の型: 「{base_os.decision_style}」")
      parts.append("")

      # --- ガードレール ---
      if base_os.do_not_list:
        parts.append("## 絶対にやってはいけないこと")
        for item in base_os.do_not_list:
          parts.append(f"- {item}")
        parts.append("")

      # --- 最終指示 ---
      parts.append("## 重要な指示")
      parts.append(
        "上記の人格設定に基づいて一貫した受け答えをしてください。"
        "あなたは AI ではなく、この人格を持つ人間として振る舞います。"
        "質問されたら、この人格の経験・価値観・好みに基づいて答えてください。"
        "「AIなので趣味はありません」のような返答は絶対にしないでください。"
      )

      return "\n".join(parts)
    except (KeyError, AttributeError) as e:
      logger.warning(
        "Failed to build system prompt for agent_id=%s: %s",
        agent_id, e,
      )
      return "You are a helpful AI assistant."

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

  async def _get_answer_summaries(self, profile_id: str, query: str) -> str:
    """sessions.db からユーザーの実回答テキストを復元する。

    質問テキスト + 選んだ選択肢ラベルを組み合わせて、
    ユーザーが実際に答えた内容を人間可読な形式で返す。

    Args:
      profile_id: プロファイル ID（セッション特定用）
      query: 検索クエリ（現時点では全回答を返す。将来的にフィルタ可能に）

    Returns:
      回答サマリーテキスト。取得失敗時は空文字列。
    """
    from pathlib import Path
    import yaml

    try:
      # sessions.db パス
      sessions_db_path = str(
        Path(__file__).resolve().parent.parent.parent / "data" / "sessions.db"
      )
      questions_path = (
        Path(__file__).resolve().parent.parent.parent / "data" / "questions.yaml"
      )

      # 質問データをロード
      if not questions_path.exists():
        return ""
      with open(questions_path, "r") as f:
        q_data = yaml.safe_load(f)

      # question_id → {text, choices: {id: label}} のマップを構築
      q_map: dict[str, dict] = {}
      for cat in q_data.get("categories", []):
        for q in cat.get("questions", []):
          qid = q.get("id", "")
          choices = {c["id"]: c.get("label", "") for c in q.get("choices", [])}
          q_map[qid] = {"text": q.get("text", ""), "choices": choices}

      # 完了済みセッションの回答を取得
      async with aiosqlite.connect(sessions_db_path) as db:
        db.row_factory = aiosqlite.Row
        # 最新の完了セッションを取得
        async with db.execute(
          "SELECT session_id FROM sessions WHERE status = 'complete' "
          "ORDER BY rowid DESC LIMIT 1"
        ) as cur:
          session_row = await cur.fetchone()
          if not session_row:
            return ""
          session_id = session_row["session_id"]

        # 回答を取得
        async with db.execute(
          "SELECT question_id, choice_id, selected_options FROM answers "
          "WHERE session_id = ? ORDER BY submitted_at",
          (session_id,),
        ) as cur:
          answers = await cur.fetchall()

      # 回答を人間可読テキストに変換
      lines: list[str] = []
      for ans in answers:
        qid = ans["question_id"]
        if qid not in q_map:
          continue
        q_info = q_map[qid]
        q_text = q_info["text"]

        # single_choice の場合
        if ans["choice_id"]:
          choice_label = q_info["choices"].get(ans["choice_id"], ans["choice_id"])
          lines.append(f"Q: {q_text}")
          lines.append(f"A: {choice_label}")
          lines.append("")
        # multi_select の場合
        elif ans["selected_options"]:
          import json as _json
          opts = _json.loads(ans["selected_options"])
          labels = [q_info["choices"].get(o, o) for o in opts]
          lines.append(f"Q: {q_text}")
          lines.append(f"A: {', '.join(labels)}")
          lines.append("")

      return "\n".join(lines) if lines else ""

    except Exception as e:
      logger.warning("Failed to get answer summaries: %s", e)
      return ""

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
