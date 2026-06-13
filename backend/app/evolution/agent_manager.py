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
    """agents テーブルと profile_id インデックスを初期化する。"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS agents (
          agent_id TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          created_at TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agents_profile
        ON agents(profile_id)
      """)
      await db.commit()
    logger.info("AgentManager: agents table initialized at %s", self._db_path)

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
        "SELECT agent_id, profile_id, display_name, created_at, is_active "
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
        "SELECT agent_id, profile_id, display_name, created_at, is_active "
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
