"""セッション管理サービス

SQLite (aiosqlite) によるセッション永続化と状態管理。

ライフサイクル:
  active → complete（全問回答完了時）
  active → expired（30日間非アクティブ時）

主な責務:
  - セッション作成（UUID生成）
  - 回答保存（上書き対応）
  - 完了判定・ステータス遷移
  - 30日超非活動セッションの自動失効
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import aiosqlite

from app.models.scores import AxisScores, NormalizedScores
from app.models.session import Answer, Session

logger = logging.getLogger(__name__)

# 非アクティブ閾値: 30日
EXPIRATION_DAYS = 30


class SessionNotFoundError(Exception):
  """セッションIDが存在しない場合に送出される例外"""

  pass


class SessionNotModifiableError(Exception):
  """完了/期限切れセッションへの変更操作時に送出される例外"""

  pass


class SessionManager:
  """セッションのCRUD、永続化、有効期限管理

  SQLiteデータベースを使用してセッションと回答を永続化する。
  init_db() でテーブルを自動作成する。
  """

  def __init__(self, db_path: Path, total_questions: int) -> None:
    self._db_path = db_path
    self._total_questions = total_questions

  async def init_db(self) -> None:
    """データベースとテーブルを初期化する

    テーブルが存在しない場合のみ作成（IF NOT EXISTS）。
    """
    # ディレクトリが存在しない場合は作成
    self._db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
          session_id TEXT PRIMARY KEY,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          raw_scores TEXT,
          normalized_scores TEXT,
          profile_id TEXT
        )
      """)
      await db.execute("""
        CREATE TABLE IF NOT EXISTS answers (
          session_id TEXT NOT NULL,
          question_id TEXT NOT NULL,
          choice_id TEXT,
          text TEXT,
          selected_options TEXT,
          submitted_at TEXT NOT NULL,
          PRIMARY KEY (session_id, question_id),
          FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
      """)
      await db.commit()

  async def create_session(self) -> str:
    """新規セッションを作成し、セッションIDを返す

    UUID4でセッションIDを生成し、ステータス"active"で永続化する。
    """
    session_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        """
        INSERT INTO sessions (session_id, status, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, "active", now, now),
      )
      await db.commit()

    logger.info("Created new session: %s", session_id)
    return session_id

  async def get_session(self, session_id: str) -> Session:
    """セッションを取得する

    30日超非アクティブの場合、自動的に"expired"に遷移する。

    Raises:
      SessionNotFoundError: セッションIDが存在しない場合
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (session_id,),
      )
      row = await cursor.fetchone()

      if row is None:
        raise SessionNotFoundError(
          f"Session not found: {session_id}"
        )

      # 30日超非アクティブチェック
      if row["status"] == "active":
        updated_at = datetime.fromisoformat(row["updated_at"])
        if self._is_expired(updated_at):
          await db.execute(
            "UPDATE sessions SET status = 'expired' WHERE session_id = ?",
            (session_id,),
          )
          await db.commit()
          logger.info(
            "Session expired due to inactivity: %s", session_id
          )
          # 再取得
          cursor = await db.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
          )
          row = await cursor.fetchone()

      # 回答を取得
      answers_cursor = await db.execute(
        "SELECT * FROM answers WHERE session_id = ?",
        (session_id,),
      )
      answer_rows = await answers_cursor.fetchall()

    # Sessionモデルを構築
    answers: dict[str, Answer] = {}
    for a_row in answer_rows:
      # selected_options のデシリアライズ
      selected_opts = None
      if a_row["selected_options"]:
        selected_opts = json.loads(a_row["selected_options"])

      answers[a_row["question_id"]] = Answer(
        question_id=a_row["question_id"],
        choice_id=a_row["choice_id"],
        text=a_row["text"],
        selected_options=selected_opts,
        submitted_at=datetime.fromisoformat(a_row["submitted_at"]),
      )

    # raw_scores / normalized_scores のデシリアライズ
    raw_scores = None
    if row["raw_scores"]:
      raw_scores = AxisScores(**json.loads(row["raw_scores"]))

    normalized_scores = None
    if row["normalized_scores"]:
      normalized_scores = NormalizedScores(
        **json.loads(row["normalized_scores"])
      )

    return Session(
      session_id=row["session_id"],
      status=row["status"],
      created_at=datetime.fromisoformat(row["created_at"]),
      updated_at=datetime.fromisoformat(row["updated_at"]),
      answers=answers,
      raw_scores=raw_scores,
      normalized_scores=normalized_scores,
      profile_id=row["profile_id"],
    )

  async def submit_answer(
    self,
    session_id: str,
    question_id: str,
    choice_id: str | None = None,
    text: str | None = None,
    selected_options: list[str] | None = None,
  ) -> None:
    """回答を保存する（上書き対応）

    同一question_idへの再回答は上書きされ、タイムスタンプが更新される。

    Raises:
      SessionNotFoundError: セッションIDが存在しない場合
      SessionNotModifiableError: セッションが完了/期限切れの場合
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row

      # セッション存在・ステータスチェック
      cursor = await db.execute(
        "SELECT status, updated_at FROM sessions WHERE session_id = ?",
        (session_id,),
      )
      row = await cursor.fetchone()

      if row is None:
        raise SessionNotFoundError(
          f"Session not found: {session_id}"
        )

      status = row["status"]

      # active セッションの有効期限チェック
      if status == "active":
        updated_at = datetime.fromisoformat(row["updated_at"])
        if self._is_expired(updated_at):
          await db.execute(
            "UPDATE sessions SET status = 'expired' WHERE session_id = ?",
            (session_id,),
          )
          await db.commit()
          raise SessionNotModifiableError(
            f"Session expired due to inactivity: {session_id}"
          )
      elif status in ("complete", "expired"):
        raise SessionNotModifiableError(
          f"Session is not modifiable (status: {status}): {session_id}"
        )

      # selected_options を JSON 文字列にシリアライズ
      selected_options_json = (
        json.dumps(selected_options) if selected_options else None
      )

      # 回答の保存（UPSERT: 上書き対応）
      now = datetime.now(timezone.utc).isoformat()
      await db.execute(
        """
        INSERT INTO answers (session_id, question_id, choice_id, text, selected_options, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (session_id, question_id)
        DO UPDATE SET choice_id = excluded.choice_id,
                      text = excluded.text,
                      selected_options = excluded.selected_options,
                      submitted_at = excluded.submitted_at
        """,
        (session_id, question_id, choice_id, text, selected_options_json, now),
      )

      # セッションの updated_at を更新
      await db.execute(
        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
        (now, session_id),
      )
      await db.commit()

  async def is_complete(self, session_id: str) -> bool:
    """全質問が回答済みかチェックする

    Raises:
      SessionNotFoundError: セッションIDが存在しない場合
    """
    async with aiosqlite.connect(self._db_path) as db:
      # セッション存在チェック
      cursor = await db.execute(
        "SELECT session_id FROM sessions WHERE session_id = ?",
        (session_id,),
      )
      if await cursor.fetchone() is None:
        raise SessionNotFoundError(
          f"Session not found: {session_id}"
        )

      # 回答数カウント
      cursor = await db.execute(
        "SELECT COUNT(*) FROM answers WHERE session_id = ?",
        (session_id,),
      )
      row = await cursor.fetchone()
      answer_count = row[0]

    return answer_count >= self._total_questions

  async def mark_complete(self, session_id: str) -> None:
    """セッションを完了状態に変更する

    以降の回答送信は拒否される。

    Raises:
      SessionNotFoundError: セッションIDが存在しない場合
      SessionNotModifiableError: セッションが既に完了/期限切れの場合
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row

      cursor = await db.execute(
        "SELECT status FROM sessions WHERE session_id = ?",
        (session_id,),
      )
      row = await cursor.fetchone()

      if row is None:
        raise SessionNotFoundError(
          f"Session not found: {session_id}"
        )

      if row["status"] != "active":
        raise SessionNotModifiableError(
          f"Session is not modifiable (status: {row['status']}): {session_id}"
        )

      now = datetime.now(timezone.utc).isoformat()
      await db.execute(
        """
        UPDATE sessions SET status = 'complete', updated_at = ?
        WHERE session_id = ?
        """,
        (now, session_id),
      )
      await db.commit()

    logger.info("Session marked complete: %s", session_id)

  async def update_scores(
    self,
    session_id: str,
    raw_scores: AxisScores,
    normalized_scores: NormalizedScores,
    profile_id: str,
  ) -> None:
    """セッションにスコアとプロファイルIDを保存する

    Raises:
      SessionNotFoundError: セッションIDが存在しない場合
    """
    async with aiosqlite.connect(self._db_path) as db:
      cursor = await db.execute(
        "SELECT session_id FROM sessions WHERE session_id = ?",
        (session_id,),
      )
      if await cursor.fetchone() is None:
        raise SessionNotFoundError(
          f"Session not found: {session_id}"
        )

      now = datetime.now(timezone.utc).isoformat()
      await db.execute(
        """
        UPDATE sessions
        SET raw_scores = ?, normalized_scores = ?, profile_id = ?, updated_at = ?
        WHERE session_id = ?
        """,
        (
          raw_scores.model_dump_json(),
          normalized_scores.model_dump_json(),
          profile_id,
          now,
          session_id,
        ),
      )
      await db.commit()

  def _is_expired(self, updated_at: datetime) -> bool:
    """updated_at から30日超経過しているかチェック"""
    now = datetime.now(timezone.utc)
    # updated_at が naive な場合は UTC として扱う
    if updated_at.tzinfo is None:
      updated_at = updated_at.replace(tzinfo=timezone.utc)
    return (now - updated_at) > timedelta(days=EXPIRATION_DAYS)
