"""ExportService のユニットテスト

チャットスレッド・マルチエージェント議論のエクスポートを
JSON / Markdown 両フォーマットで検証する。
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.evolution.export import ExportService


@pytest.fixture
def mock_chat_service():
  """ChatService のモック。get_history() が固定データを返す。"""
  svc = MagicMock()
  svc.get_history = AsyncMock(return_value=[
    {
      "turn_id": "turn-001",
      "role": "user",
      "content": "Hello!",
      "created_at": "2024-01-01T00:00:00+00:00",
    },
    {
      "turn_id": "turn-002",
      "role": "assistant",
      "content": "Hi there! How can I help?",
      "created_at": "2024-01-01T00:00:01+00:00",
    },
    {
      "turn_id": "turn-003",
      "role": "user",
      "content": "Tell me a joke.",
      "created_at": "2024-01-01T00:00:02+00:00",
    },
    {
      "turn_id": "turn-004",
      "role": "assistant",
      "content": "Why did the chicken cross the road?",
      "created_at": "2024-01-01T00:00:03+00:00",
    },
  ])
  return svc


@pytest.fixture
def mock_discussion_engine():
  """DiscussionEngine のモック。get_history() が固定データを返す。"""
  engine = MagicMock()
  engine.get_history = AsyncMock(return_value=[
    {
      "turn_id": "dturn-001",
      "turn_number": 1,
      "agent_id": "agent-alice",
      "display_name": "Alice",
      "content": "I think we should focus on quality.",
      "created_at": "2024-01-01T10:00:00+00:00",
    },
    {
      "turn_id": "dturn-002",
      "turn_number": 2,
      "agent_id": "agent-bob",
      "display_name": "Bob",
      "content": "Speed is more important in a startup.",
      "created_at": "2024-01-01T10:00:05+00:00",
    },
    {
      "turn_id": "dturn-003",
      "turn_number": 3,
      "agent_id": "agent-alice",
      "display_name": "Alice",
      "content": "But technical debt will slow us down later.",
      "created_at": "2024-01-01T10:00:10+00:00",
    },
  ])
  return engine


@pytest.fixture
def mock_empty_chat_service():
  """空の履歴を返す ChatService モック。"""
  svc = MagicMock()
  svc.get_history = AsyncMock(return_value=[])
  return svc


@pytest.fixture
def mock_empty_discussion_engine():
  """空の履歴を返す DiscussionEngine モック。"""
  engine = MagicMock()
  engine.get_history = AsyncMock(return_value=[])
  return engine


@pytest.fixture
def export_service(mock_chat_service, mock_discussion_engine):
  """ExportService インスタンスを返す。"""
  return ExportService(
    chat_service=mock_chat_service,
    discussion_engine=mock_discussion_engine,
  )


@pytest.fixture
def export_service_empty(mock_empty_chat_service, mock_empty_discussion_engine):
  """空データの ExportService インスタンスを返す。"""
  return ExportService(
    chat_service=mock_empty_chat_service,
    discussion_engine=mock_empty_discussion_engine,
  )


class TestExportThreadJson:
  """export_thread() の JSON フォーマットテスト"""

  @pytest.mark.asyncio
  async def test_returns_valid_json(self, export_service):
    """有効な JSON 文字列が返ること。"""
    result = await export_service.export_thread("thread-123", format="json")
    data = json.loads(result)
    assert isinstance(data, dict)

  @pytest.mark.asyncio
  async def test_contains_thread_metadata(self, export_service):
    """thread_id と turns_count がメタデータに含まれること。"""
    result = await export_service.export_thread("thread-123", format="json")
    data = json.loads(result)
    assert data["thread_id"] == "thread-123"
    assert data["turns_count"] == 4

  @pytest.mark.asyncio
  async def test_contains_timestamps(self, export_service):
    """first_timestamp と last_timestamp が含まれること。"""
    result = await export_service.export_thread("thread-123", format="json")
    data = json.loads(result)
    assert data["first_timestamp"] == "2024-01-01T00:00:00+00:00"
    assert data["last_timestamp"] == "2024-01-01T00:00:03+00:00"

  @pytest.mark.asyncio
  async def test_turns_chronological_order(self, export_service):
    """ターンが時系列昇順で並ぶこと。"""
    result = await export_service.export_thread("thread-123", format="json")
    data = json.loads(result)
    timestamps = [t["created_at"] for t in data["turns"]]
    assert timestamps == sorted(timestamps)

  @pytest.mark.asyncio
  async def test_turn_fields(self, export_service):
    """各ターンに必須フィールドが含まれること。"""
    result = await export_service.export_thread("thread-123", format="json")
    data = json.loads(result)
    for turn in data["turns"]:
      assert "turn_id" in turn
      assert "role" in turn
      assert "content" in turn
      assert "created_at" in turn

  @pytest.mark.asyncio
  async def test_empty_thread(self, export_service_empty):
    """空スレッドでも正常に JSON を返すこと。"""
    result = await export_service_empty.export_thread("empty-thread", format="json")
    data = json.loads(result)
    assert data["thread_id"] == "empty-thread"
    assert data["turns_count"] == 0
    assert data["turns"] == []


class TestExportThreadMarkdown:
  """export_thread() の Markdown フォーマットテスト"""

  @pytest.mark.asyncio
  async def test_contains_header(self, export_service):
    """Markdown ヘッダーにスレッド ID が含まれること。"""
    result = await export_service.export_thread("thread-123", format="markdown")
    assert "# Chat Export: thread-123" in result

  @pytest.mark.asyncio
  async def test_contains_metadata_section(self, export_service):
    """メタデータセクションが正しいこと。"""
    result = await export_service.export_thread("thread-123", format="markdown")
    assert "## Metadata" in result
    assert "- **Thread ID**: thread-123" in result
    assert "- **Turns**: 4" in result
    assert "- **Period**: 2024-01-01 — 2024-01-01" in result

  @pytest.mark.asyncio
  async def test_contains_conversation_section(self, export_service):
    """会話セクションにメッセージが含まれること。"""
    result = await export_service.export_thread("thread-123", format="markdown")
    assert "## Conversation" in result
    assert "**User** (2024-01-01T00:00:00+00:00):" in result
    assert "> Hello!" in result
    assert "**Assistant** (2024-01-01T00:00:01+00:00):" in result
    assert "> Hi there! How can I help?" in result

  @pytest.mark.asyncio
  async def test_empty_thread_markdown(self, export_service_empty):
    """空スレッドでも正常に Markdown を返すこと。"""
    result = await export_service_empty.export_thread("empty", format="markdown")
    assert "# Chat Export: empty" in result
    assert "- **Turns**: 0" in result


class TestExportDiscussionJson:
  """export_discussion() の JSON フォーマットテスト"""

  @pytest.mark.asyncio
  async def test_returns_valid_json(self, export_service):
    """有効な JSON 文字列が返ること。"""
    result = await export_service.export_discussion("disc-456", format="json")
    data = json.loads(result)
    assert isinstance(data, dict)

  @pytest.mark.asyncio
  async def test_contains_discussion_metadata(self, export_service):
    """discussion_id と turns_count が含まれること。"""
    result = await export_service.export_discussion("disc-456", format="json")
    data = json.loads(result)
    assert data["discussion_id"] == "disc-456"
    assert data["turns_count"] == 3

  @pytest.mark.asyncio
  async def test_contains_participants(self, export_service):
    """参加者リストが重複なく登場順で含まれること。"""
    result = await export_service.export_discussion("disc-456", format="json")
    data = json.loads(result)
    assert data["participants"] == ["Alice", "Bob"]

  @pytest.mark.asyncio
  async def test_turns_ordered_by_turn_number(self, export_service):
    """ターンが turn_number 昇順で並ぶこと。"""
    result = await export_service.export_discussion("disc-456", format="json")
    data = json.loads(result)
    numbers = [t["turn_number"] for t in data["turns"]]
    assert numbers == sorted(numbers)

  @pytest.mark.asyncio
  async def test_turn_fields(self, export_service):
    """各ターンに必須フィールドが含まれること。"""
    result = await export_service.export_discussion("disc-456", format="json")
    data = json.loads(result)
    for turn in data["turns"]:
      assert "turn_id" in turn
      assert "turn_number" in turn
      assert "agent_id" in turn
      assert "display_name" in turn
      assert "content" in turn
      assert "created_at" in turn

  @pytest.mark.asyncio
  async def test_empty_discussion(self, export_service_empty):
    """空議論でも正常に JSON を返すこと。"""
    result = await export_service_empty.export_discussion("empty-disc", format="json")
    data = json.loads(result)
    assert data["discussion_id"] == "empty-disc"
    assert data["turns_count"] == 0
    assert data["participants"] == []
    assert data["turns"] == []


class TestExportDiscussionMarkdown:
  """export_discussion() の Markdown フォーマットテスト"""

  @pytest.mark.asyncio
  async def test_contains_header(self, export_service):
    """Markdown ヘッダーに議論 ID が含まれること。"""
    result = await export_service.export_discussion("disc-456", format="markdown")
    assert "# Discussion Export: disc-456" in result

  @pytest.mark.asyncio
  async def test_contains_metadata_section(self, export_service):
    """メタデータセクションが正しいこと。"""
    result = await export_service.export_discussion("disc-456", format="markdown")
    assert "## Metadata" in result
    assert "- **Discussion ID**: disc-456" in result
    assert "- **Participants**: Alice, Bob" in result
    assert "- **Turns**: 3" in result

  @pytest.mark.asyncio
  async def test_contains_discussion_section(self, export_service):
    """議論セクションにターンが含まれること。"""
    result = await export_service.export_discussion("disc-456", format="markdown")
    assert "## Discussion" in result
    assert "**Alice** (turn 1):" in result
    assert "> I think we should focus on quality." in result
    assert "**Bob** (turn 2):" in result
    assert "> Speed is more important in a startup." in result

  @pytest.mark.asyncio
  async def test_empty_discussion_markdown(self, export_service_empty):
    """空議論でも正常に Markdown を返すこと。"""
    result = await export_service_empty.export_discussion("empty", format="markdown")
    assert "# Discussion Export: empty" in result
    assert "- **Turns**: 0" in result


class TestFormatValidation:
  """フォーマットバリデーションのテスト"""

  @pytest.mark.asyncio
  async def test_invalid_format_thread(self, export_service):
    """不正なフォーマットで ValueError が発生すること。"""
    with pytest.raises(ValueError, match="Unsupported format"):
      await export_service.export_thread("thread-1", format="xml")

  @pytest.mark.asyncio
  async def test_invalid_format_discussion(self, export_service):
    """不正なフォーマットで ValueError が発生すること。"""
    with pytest.raises(ValueError, match="Unsupported format"):
      await export_service.export_discussion("disc-1", format="csv")

  @pytest.mark.asyncio
  async def test_default_format_is_json(self, export_service):
    """デフォルトフォーマットが JSON であること。"""
    result = await export_service.export_thread("thread-123")
    # JSON としてパースできれば OK
    data = json.loads(result)
    assert "thread_id" in data


class TestSortGuarantee:
  """ソート保証のテスト"""

  @pytest.mark.asyncio
  async def test_unsorted_thread_turns_are_sorted(self):
    """未ソートのターンが created_at 昇順にソートされること。"""
    chat_svc = MagicMock()
    # 意図的に逆順のデータを返す
    chat_svc.get_history = AsyncMock(return_value=[
      {
        "turn_id": "t2",
        "role": "assistant",
        "content": "Response",
        "created_at": "2024-01-01T00:00:02+00:00",
      },
      {
        "turn_id": "t1",
        "role": "user",
        "content": "Hello",
        "created_at": "2024-01-01T00:00:01+00:00",
      },
    ])
    disc_engine = MagicMock()
    disc_engine.get_history = AsyncMock(return_value=[])

    svc = ExportService(chat_service=chat_svc, discussion_engine=disc_engine)
    result = await svc.export_thread("thread-x", format="json")
    data = json.loads(result)
    assert data["turns"][0]["turn_id"] == "t1"
    assert data["turns"][1]["turn_id"] == "t2"

  @pytest.mark.asyncio
  async def test_unsorted_discussion_turns_are_sorted(self):
    """未ソートのターンが turn_number 昇順にソートされること。"""
    chat_svc = MagicMock()
    chat_svc.get_history = AsyncMock(return_value=[])
    disc_engine = MagicMock()
    # 意図的に逆順のデータを返す
    disc_engine.get_history = AsyncMock(return_value=[
      {
        "turn_id": "d2",
        "turn_number": 2,
        "agent_id": "a2",
        "display_name": "Bob",
        "content": "Second",
        "created_at": "2024-01-01T10:00:05+00:00",
      },
      {
        "turn_id": "d1",
        "turn_number": 1,
        "agent_id": "a1",
        "display_name": "Alice",
        "content": "First",
        "created_at": "2024-01-01T10:00:00+00:00",
      },
    ])

    svc = ExportService(chat_service=chat_svc, discussion_engine=disc_engine)
    result = await svc.export_discussion("disc-x", format="json")
    data = json.loads(result)
    assert data["turns"][0]["turn_number"] == 1
    assert data["turns"][1]["turn_number"] == 2
