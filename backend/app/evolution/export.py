"""会話ログエクスポートサービス

チャットスレッドおよびマルチエージェント議論の履歴を
JSON または Markdown 形式でエクスポートする。
"""

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from app.evolution.chat import ChatService
  from app.evolution.discussion_engine import DiscussionEngine

logger = logging.getLogger(__name__)


class ExportService:
  """会話ログエクスポートサービス

  ChatService / DiscussionEngine の履歴データを
  構造化された JSON または Markdown 文字列に変換する。
  """

  SUPPORTED_FORMATS = ("json", "markdown")

  def __init__(
    self,
    chat_service: "ChatService",
    discussion_engine: "DiscussionEngine",
  ):
    """ExportService を初期化する。

    Args:
      chat_service: 1対1チャットサービスインスタンス
      discussion_engine: マルチエージェント議論エンジンインスタンス
    """
    self._chat_service = chat_service
    self._discussion_engine = discussion_engine

  async def export_thread(
    self,
    thread_id: str,
    format: str = "json",
  ) -> str:
    """チャットスレッドをエクスポートする。

    全ターンを時系列昇順で取得し、指定フォーマットで文字列化する。

    Args:
      thread_id: エクスポート対象のスレッド ID
      format: "json" または "markdown"

    Returns:
      フォーマット済みの文字列

    Raises:
      ValueError: サポート外のフォーマットが指定された場合
    """
    self._validate_format(format)

    turns = await self._chat_service.get_history(thread_id)
    # created_at で昇順ソート（通常は既にソート済みだが保証する）
    turns = sorted(turns, key=lambda t: t["created_at"])

    if format == "json":
      return self._thread_to_json(thread_id, turns)
    return self._thread_to_markdown(thread_id, turns)

  async def export_discussion(
    self,
    discussion_id: str,
    format: str = "json",
  ) -> str:
    """マルチエージェント議論をエクスポートする。

    全ターンを turn_number 昇順で取得し、指定フォーマットで文字列化する。

    Args:
      discussion_id: エクスポート対象の議論セッション ID
      format: "json" または "markdown"

    Returns:
      フォーマット済みの文字列

    Raises:
      ValueError: サポート外のフォーマットが指定された場合
    """
    self._validate_format(format)

    turns = await self._discussion_engine.get_history(discussion_id)
    # turn_number で昇順ソート（通常は既にソート済みだが保証する）
    turns = sorted(turns, key=lambda t: t["turn_number"])

    if format == "json":
      return self._discussion_to_json(discussion_id, turns)
    return self._discussion_to_markdown(discussion_id, turns)

  def _validate_format(self, format: str) -> None:
    """フォーマット文字列を検証する。

    Args:
      format: 検証対象のフォーマット文字列

    Raises:
      ValueError: サポート外のフォーマットが指定された場合
    """
    if format not in self.SUPPORTED_FORMATS:
      raise ValueError(
        f"Unsupported format: '{format}'. "
        f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
      )

  def _thread_to_json(self, thread_id: str, turns: list[dict]) -> str:
    """チャットスレッドを JSON 文字列に変換する。

    Args:
      thread_id: スレッド ID
      turns: ターンデータのリスト

    Returns:
      JSON 文字列（メタデータ + ターン一覧）
    """
    # タイムスタンプ範囲を算出
    first_at = turns[0]["created_at"] if turns else None
    last_at = turns[-1]["created_at"] if turns else None

    payload = {
      "thread_id": thread_id,
      "turns_count": len(turns),
      "first_timestamp": first_at,
      "last_timestamp": last_at,
      "turns": [
        {
          "turn_id": t["turn_id"],
          "role": t["role"],
          "content": t["content"],
          "created_at": t["created_at"],
        }
        for t in turns
      ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

  def _thread_to_markdown(self, thread_id: str, turns: list[dict]) -> str:
    """チャットスレッドを Markdown 文字列に変換する。

    Args:
      thread_id: スレッド ID
      turns: ターンデータのリスト

    Returns:
      Markdown フォーマットの文字列
    """
    first_at = turns[0]["created_at"] if turns else "N/A"
    last_at = turns[-1]["created_at"] if turns else "N/A"

    # 日付部分のみ抽出（ISO 8601 の先頭10文字）
    first_date = first_at[:10] if first_at != "N/A" else "N/A"
    last_date = last_at[:10] if last_at != "N/A" else "N/A"

    lines = [
      f"# Chat Export: {thread_id}",
      "",
      "## Metadata",
      f"- **Thread ID**: {thread_id}",
      f"- **Turns**: {len(turns)}",
      f"- **Period**: {first_date} — {last_date}",
      "",
      "## Conversation",
      "",
    ]

    for turn in turns:
      # ロール名を表示用に変換
      role_label = turn["role"].capitalize()
      timestamp = turn["created_at"]
      content = turn["content"]
      lines.append(f"**{role_label}** ({timestamp}):")
      lines.append(f"> {content}")
      lines.append("")

    return "\n".join(lines)

  def _discussion_to_json(
    self, discussion_id: str, turns: list[dict]
  ) -> str:
    """マルチエージェント議論を JSON 文字列に変換する。

    Args:
      discussion_id: 議論セッション ID
      turns: ターンデータのリスト

    Returns:
      JSON 文字列（メタデータ + 参加者 + ターン一覧）
    """
    # 参加者の display_name を重複なく抽出（登場順を保持）
    participants: list[str] = []
    seen: set[str] = set()
    for t in turns:
      name = t["display_name"]
      if name not in seen:
        participants.append(name)
        seen.add(name)

    payload = {
      "discussion_id": discussion_id,
      "participants": participants,
      "turns_count": len(turns),
      "turns": [
        {
          "turn_id": t["turn_id"],
          "turn_number": t["turn_number"],
          "agent_id": t["agent_id"],
          "display_name": t["display_name"],
          "content": t["content"],
          "created_at": t["created_at"],
        }
        for t in turns
      ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

  def _discussion_to_markdown(
    self, discussion_id: str, turns: list[dict]
  ) -> str:
    """マルチエージェント議論を Markdown 文字列に変換する。

    Args:
      discussion_id: 議論セッション ID
      turns: ターンデータのリスト

    Returns:
      Markdown フォーマットの文字列
    """
    # 参加者リストを構築（登場順）
    participants: list[str] = []
    seen: set[str] = set()
    for t in turns:
      name = t["display_name"]
      if name not in seen:
        participants.append(name)
        seen.add(name)

    lines = [
      f"# Discussion Export: {discussion_id}",
      "",
      "## Metadata",
      f"- **Discussion ID**: {discussion_id}",
      f"- **Participants**: {', '.join(participants)}",
      f"- **Turns**: {len(turns)}",
      "",
      "## Discussion",
      "",
    ]

    for turn in turns:
      display_name = turn["display_name"]
      turn_number = turn["turn_number"]
      content = turn["content"]
      lines.append(f"**{display_name}** (turn {turn_number}):")
      lines.append(f"> {content}")
      lines.append("")

    return "\n".join(lines)
