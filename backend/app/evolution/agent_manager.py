"""Agent Manager: 分身プロファイルの CRUD 管理

SQLite agents テーブルを操作し、agent_id (UUID v4) による
複数分身の作成・管理を提供する。
DB ファイルは evolution.db に集約する。
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite

from app.evolution.context_layer_manager import ContextLayerManager

logger = logging.getLogger(__name__)


@dataclass
class AgentRecord:
  """エージェントペルソナのデータレコード"""

  agent_id: str  # UUID v4
  profile_id: str
  display_name: str
  created_at: str  # ISO 8601
  is_active: bool
  visibility: str = "private"  # "private" | "published"


class AgentManager:
  """分身プロファイルの CRUD 管理

  SQLite agents テーブルを操作し、
  agent_id による複数分身の作成・管理を提供する。
  作成時に ContextLayerManager を介して Base_OS + コンテキスト層を初期化する。
  """

  def __init__(
    self,
    db_path: str,
    context_layer_manager: ContextLayerManager | None = None,
  ):
    """AgentManager を初期化する。

    Args:
      db_path: SQLite DB ファイルパス (evolution.db)
      context_layer_manager: エージェント作成時に Base_OS + コンテキスト層を
        初期化するための ContextLayerManager インスタンス
    """
    self._db_path = db_path
    self._clm = context_layer_manager

  async def init_db(self) -> None:
    """agents テーブル + profiles テーブルとインデックスを初期化する。"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS agents (
          agent_id TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          created_at TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1,
          visibility TEXT NOT NULL DEFAULT 'private'
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agents_profile
        ON agents(profile_id)
      """)
      # 既存テーブルに visibility カラムがない場合のマイグレーション
      # (CREATE TABLE IF NOT EXISTS は既存テーブルを変更しないため)
      try:
        await db.execute(
          "ALTER TABLE agents ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'"
        )
      except Exception:
        # カラム既存の場合は無視
        pass
      # visibility カラム確保後にインデックスを作成
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agents_visibility
        ON agents(visibility)
      """)
      # プロファイル永続化テーブル（サーバー再起動時に自動復元するため）
      await db.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
          profile_id TEXT PRIMARY KEY,
          profile_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
      """)
      await db.commit()
    logger.info("AgentManager: tables initialized at %s", self._db_path)

  async def save_profile(self, profile_id: str, profile_json: str) -> None:
    """ProfileOutput JSON を DB に永続化する（UPSERT）。

    Args:
      profile_id: プロファイル識別子
      profile_json: ProfileOutput の JSON 文字列
    """
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        """
        INSERT INTO profiles (profile_id, profile_json, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(profile_id) DO UPDATE SET profile_json = excluded.profile_json
        """,
        (profile_id, profile_json, now),
      )
      await db.commit()
    logger.debug("Profile saved to DB: profile_id=%s", profile_id)

  async def get_profile_json(self, profile_id: str) -> str | None:
    """DB からプロファイル JSON を取得する。

    Args:
      profile_id: 取得対象のプロファイル ID

    Returns:
      JSON 文字列。存在しない場合は None。
    """
    async with aiosqlite.connect(self._db_path) as db:
      async with db.execute(
        "SELECT profile_json FROM profiles WHERE profile_id = ?",
        (profile_id,),
      ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None

  async def list_profile_ids(self) -> list[str]:
    """DB に保存されている全プロファイル ID を返す。"""
    async with aiosqlite.connect(self._db_path) as db:
      async with db.execute("SELECT profile_id FROM profiles") as cursor:
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

  async def create(self, profile_id: str, display_name: str) -> AgentRecord:
    """新規エージェントペルソナを作成する。

    UUID v4 を生成し、profile_id が ContextLayerManager にロード済みか検証した上で
    agents テーブルにレコードを挿入する。

    Args:
      profile_id: 関連付けるプロファイル ID (prof_XXXXXX 形式)
      display_name: エージェントの表示名

    Returns:
      作成された AgentRecord

    Raises:
      ValueError: profile_id が ContextLayerManager に未ロードの場合
    """
    # profile_id 存在チェック: ContextLayerManager にロード済みか確認
    if self._clm is not None:
      try:
        self._clm.get_base_os(profile_id)
      except KeyError:
        raise ValueError(
          f"Profile '{profile_id}' is not loaded. "
          "Load the profile before creating an agent."
        )

    agent_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        """
        INSERT INTO agents (agent_id, profile_id, display_name, created_at, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        (agent_id, profile_id, display_name, created_at),
      )
      await db.commit()

    record = AgentRecord(
      agent_id=agent_id,
      profile_id=profile_id,
      display_name=display_name,
      created_at=created_at,
      is_active=True,
      visibility="private",
    )
    logger.info(
      "Agent created: agent_id=%s, profile_id=%s, display_name=%s",
      agent_id,
      profile_id,
      display_name,
    )
    return record

  async def get(self, agent_id: str) -> AgentRecord | None:
    """agent_id でレコードを取得する。

    Args:
      agent_id: 取得対象のエージェント ID (UUID v4)

    Returns:
      該当する AgentRecord。存在しない場合は None。
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
        "SELECT agent_id, profile_id, display_name, created_at, is_active, "
        "COALESCE(visibility, 'private') as visibility "
        "FROM agents WHERE agent_id = ?",
        (agent_id,),
      ) as cursor:
        row = await cursor.fetchone()
        if row is None:
          return None
        return AgentRecord(
          agent_id=row["agent_id"],
          profile_id=row["profile_id"],
          display_name=row["display_name"],
          created_at=row["created_at"],
          is_active=bool(row["is_active"]),
          visibility=row["visibility"],
        )

  async def list_active(self, profile_id: str) -> list[AgentRecord]:
    """指定 profile_id の有効なエージェント一覧を返す。

    Args:
      profile_id: 対象のプロファイル ID

    Returns:
      is_active=True のエージェントレコードのリスト（作成日時昇順）
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
        "SELECT agent_id, profile_id, display_name, created_at, is_active, "
        "COALESCE(visibility, 'private') as visibility "
        "FROM agents WHERE profile_id = ? AND is_active = 1 "
        "ORDER BY created_at ASC",
        (profile_id,),
      ) as cursor:
        rows = await cursor.fetchall()
        return [
          AgentRecord(
            agent_id=row["agent_id"],
            profile_id=row["profile_id"],
            display_name=row["display_name"],
            created_at=row["created_at"],
            is_active=bool(row["is_active"]),
            visibility=row["visibility"],
          )
          for row in rows
        ]

  async def list_all_active(self) -> list[AgentRecord]:
    """全プロファイルの有効なエージェント一覧を返す。

    Returns:
      is_active=True の全エージェントレコードのリスト（作成日時昇順）
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
        "SELECT agent_id, profile_id, display_name, created_at, is_active, "
        "COALESCE(visibility, 'private') as visibility "
        "FROM agents WHERE is_active = 1 "
        "ORDER BY created_at ASC",
      ) as cursor:
        rows = await cursor.fetchall()
        return [
          AgentRecord(
            agent_id=row["agent_id"],
            profile_id=row["profile_id"],
            display_name=row["display_name"],
            created_at=row["created_at"],
            is_active=bool(row["is_active"]),
            visibility=row["visibility"],
          )
          for row in rows
        ]

  async def update_display_name(
    self, agent_id: str, display_name: str
  ) -> AgentRecord:
    """表示名を更新する。

    Args:
      agent_id: 更新対象のエージェント ID
      display_name: 新しい表示名

    Returns:
      更新後の AgentRecord

    Raises:
      ValueError: agent_id が存在しない場合
    """
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        "UPDATE agents SET display_name = ? WHERE agent_id = ?",
        (display_name, agent_id),
      )
      await db.commit()

    record = await self.get(agent_id)
    if record is None:
      raise ValueError(f"Agent '{agent_id}' not found")
    logger.info(
      "Agent display_name updated: agent_id=%s, new_name=%s",
      agent_id,
      display_name,
    )
    return record

  async def soft_delete(self, agent_id: str) -> None:
    """is_active = 0 にソフトデリートする。

    Args:
      agent_id: 削除対象のエージェント ID

    Raises:
      ValueError: agent_id が存在しない場合
    """
    record = await self.get(agent_id)
    if record is None:
      raise ValueError(f"Agent '{agent_id}' not found")

    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        "UPDATE agents SET is_active = 0 WHERE agent_id = ?",
        (agent_id,),
      )
      await db.commit()
    logger.info("Agent soft-deleted: agent_id=%s", agent_id)

  async def publish(self, agent_id: str) -> AgentRecord:
    """エージェントを公開状態に変更する（明示的 opt-in）。

    公開されたエージェントは他ユーザーからチャット・議論の
    相手として選択可能になる。

    Args:
      agent_id: 公開対象のエージェント ID

    Returns:
      更新後の AgentRecord

    Raises:
      ValueError: agent_id が存在しない / 非アクティブの場合
    """
    record = await self.get(agent_id)
    if record is None or not record.is_active:
      raise ValueError(f"Agent '{agent_id}' not found or not active")

    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        "UPDATE agents SET visibility = 'published' WHERE agent_id = ?",
        (agent_id,),
      )
      await db.commit()

    logger.info("Agent published: agent_id=%s", agent_id)
    record.visibility = "published"
    return record

  async def unpublish(self, agent_id: str) -> AgentRecord:
    """エージェントを非公開に戻す。

    Args:
      agent_id: 非公開にするエージェント ID

    Returns:
      更新後の AgentRecord

    Raises:
      ValueError: agent_id が存在しない / 非アクティブの場合
    """
    record = await self.get(agent_id)
    if record is None or not record.is_active:
      raise ValueError(f"Agent '{agent_id}' not found or not active")

    async with aiosqlite.connect(self._db_path) as db:
      await db.execute(
        "UPDATE agents SET visibility = 'private' WHERE agent_id = ?",
        (agent_id,),
      )
      await db.commit()

    logger.info("Agent unpublished: agent_id=%s", agent_id)
    record.visibility = "private"
    return record

  async def list_published(self) -> list[AgentRecord]:
    """公開済みの全エージェントを返す（全ユーザー横断）。

    チャット・議論のパートナー選択に使用する。

    Returns:
      visibility='published' かつ is_active=1 の全レコード（作成日時昇順）
    """
    async with aiosqlite.connect(self._db_path) as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
        "SELECT agent_id, profile_id, display_name, created_at, is_active, "
        "COALESCE(visibility, 'private') as visibility "
        "FROM agents WHERE visibility = 'published' AND is_active = 1 "
        "ORDER BY created_at ASC",
      ) as cursor:
        rows = await cursor.fetchall()
        return [
          AgentRecord(
            agent_id=row["agent_id"],
            profile_id=row["profile_id"],
            display_name=row["display_name"],
            created_at=row["created_at"],
            is_active=bool(row["is_active"]),
            visibility=row["visibility"],
          )
          for row in rows
        ]
