"""ExportService プロパティベーステスト

Feature: agent-evolution
Property 35: Export completeness and ordering
Property 36: Export format equivalence
Validates: Requirements 23.2, 23.3, 23.4, 23.5
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.evolution.export import ExportService


# --- Hypothesis ストラテジー ---

# ロール: user または assistant
_role_st = st.sampled_from(["user", "assistant"])

# コンテンツ: 印刷可能テキスト（1〜80文字）
_content_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
  min_size=1,
  max_size=80,
).filter(lambda s: s.strip() != "")

# thread_id / discussion_id: 英数字 + ハイフン
_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
  min_size=1,
  max_size=30,
).filter(lambda s: s.strip() != "")

# display_name: 英字のみ（1〜15文字）
_display_name_st = st.text(
  alphabet=st.characters(whitelist_categories=("L",)),
  min_size=1,
  max_size=15,
).filter(lambda s: s.strip() != "")


def _make_timestamp(index: int) -> str:
  """index に基づく一意なタイムスタンプ文字列を生成する。"""
  base = datetime(2024, 1, 1, tzinfo=timezone.utc)
  dt = base + timedelta(seconds=index)
  return dt.isoformat()


# チャットターン1件を生成するストラテジー
@st.composite
def _chat_turn_st(draw, index: int = 0):
  """1件のチャットターン dict を生成する。"""
  return {
    "turn_id": f"turn-{draw(st.uuids())}",
    "role": draw(_role_st),
    "content": draw(_content_st),
    "created_at": _make_timestamp(index),
  }


# チャットターンリスト（0〜10件、各ターンに一意タイムスタンプ）
@st.composite
def _chat_turns_st(draw):
  """ランダムな順番のチャットターンリストを生成する。"""
  n = draw(st.integers(min_value=0, max_value=10))
  turns = []
  for i in range(n):
    turn = {
      "turn_id": f"turn-{draw(st.uuids())}",
      "role": draw(_role_st),
      "content": draw(_content_st),
      "created_at": _make_timestamp(i),
    }
    turns.append(turn)
  # シャッフルして返す（ソート保証を検証するため）
  shuffled = draw(st.permutations(turns))
  return list(shuffled)


# ディスカッションターンリスト（0〜10件）
@st.composite
def _discussion_turns_st(draw):
  """ランダムな順番のディスカッションターンリストを生成する。"""
  n = draw(st.integers(min_value=0, max_value=10))
  turns = []
  for i in range(n):
    turn = {
      "turn_id": f"dturn-{draw(st.uuids())}",
      "turn_number": i + 1,
      "agent_id": f"agent-{draw(st.uuids()).hex[:8]}",
      "display_name": draw(_display_name_st),
      "content": draw(_content_st),
      "created_at": _make_timestamp(i),
    }
    turns.append(turn)
  # シャッフルして返す（ソート保証を検証するため）
  shuffled = draw(st.permutations(turns))
  return list(shuffled)


# --- ヘルパー ---


def _build_export_service(
  chat_turns: list[dict],
  discussion_turns: list[dict],
) -> ExportService:
  """モックされた依存を持つ ExportService を構築する。"""
  chat_svc = MagicMock()
  chat_svc.get_history = AsyncMock(return_value=chat_turns)

  disc_engine = MagicMock()
  disc_engine.get_history = AsyncMock(return_value=discussion_turns)

  return ExportService(
    chat_service=chat_svc,
    discussion_engine=disc_engine,
  )


# =============================================================================
# Property 35: Export completeness and ordering
# Feature: agent-evolution
# =============================================================================


class TestExportCompletenessAndOrdering:
  """Property 35: Export completeness and ordering.

  任意の会話（スレッドまたはディスカッション）に対し、
  エクスポート結果が全ターンを時系列順に含むことを保証する。

  **Validates: Requirements 23.2, 23.3, 23.4**
  """

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    thread_id=_id_st,
    turns=_chat_turns_st(),
  )
  async def test_export_thread_json_turns_count(
    self,
    thread_id: str,
    turns: list[dict],
  ) -> None:
    """export_thread JSON の turns_count が実際のターン数と一致すること。

    **Validates: Requirements 23.2**
    """
    svc = _build_export_service(chat_turns=turns, discussion_turns=[])
    result = await svc.export_thread(thread_id, format="json")
    data = json.loads(result)

    assert data["turns_count"] == len(turns), (
      f"turns_count={data['turns_count']} but expected {len(turns)}"
    )
    assert len(data["turns"]) == len(turns), (
      f"turns array length={len(data['turns'])} but expected {len(turns)}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    thread_id=_id_st,
    turns=_chat_turns_st(),
  )
  async def test_export_thread_turns_ordered_by_created_at(
    self,
    thread_id: str,
    turns: list[dict],
  ) -> None:
    """export_thread のターンが created_at 昇順であること。

    **Validates: Requirements 23.4**
    """
    svc = _build_export_service(chat_turns=turns, discussion_turns=[])
    result = await svc.export_thread(thread_id, format="json")
    data = json.loads(result)

    timestamps = [t["created_at"] for t in data["turns"]]
    assert timestamps == sorted(timestamps), (
      f"Turns are not sorted by created_at: {timestamps}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    discussion_id=_id_st,
    turns=_discussion_turns_st(),
  )
  async def test_export_discussion_turns_ordered_by_turn_number(
    self,
    discussion_id: str,
    turns: list[dict],
  ) -> None:
    """export_discussion のターンが turn_number 昇順であること。

    **Validates: Requirements 23.3**
    """
    svc = _build_export_service(chat_turns=[], discussion_turns=turns)
    result = await svc.export_discussion(discussion_id, format="json")
    data = json.loads(result)

    turn_numbers = [t["turn_number"] for t in data["turns"]]
    assert turn_numbers == sorted(turn_numbers), (
      f"Turns are not sorted by turn_number: {turn_numbers}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    discussion_id=_id_st,
    turns=_discussion_turns_st(),
  )
  async def test_export_discussion_json_turns_count(
    self,
    discussion_id: str,
    turns: list[dict],
  ) -> None:
    """export_discussion JSON の turns_count が実際のターン数と一致すること。

    **Validates: Requirements 23.3**
    """
    svc = _build_export_service(chat_turns=[], discussion_turns=turns)
    result = await svc.export_discussion(discussion_id, format="json")
    data = json.loads(result)

    assert data["turns_count"] == len(turns), (
      f"turns_count={data['turns_count']} but expected {len(turns)}"
    )
    assert len(data["turns"]) == len(turns), (
      f"turns array length={len(data['turns'])} but expected {len(turns)}"
    )


# =============================================================================
# Property 36: Export format equivalence
# Feature: agent-evolution
# =============================================================================


class TestExportFormatEquivalence:
  """Property 36: Export format equivalence.

  任意の会話に対し、JSON と Markdown の両エクスポートが
  同一のターン数・同一の内容を含むことを保証する。

  **Validates: Requirements 23.5**
  """

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    thread_id=_id_st,
    turns=_chat_turns_st(),
  )
  async def test_thread_json_and_markdown_same_turn_count(
    self,
    thread_id: str,
    turns: list[dict],
  ) -> None:
    """JSON と Markdown エクスポートのターン数が一致すること。

    **Validates: Requirements 23.5**
    """
    svc = _build_export_service(chat_turns=turns, discussion_turns=[])

    json_result = await svc.export_thread(thread_id, format="json")
    md_result = await svc.export_thread(thread_id, format="markdown")

    json_data = json.loads(json_result)
    json_count = json_data["turns_count"]

    # Markdown のメタデータから Turns 数を抽出
    md_count = None
    for line in md_result.split("\n"):
      if line.startswith("- **Turns**:"):
        md_count = int(line.split(":")[1].strip())
        break

    assert json_count == md_count, (
      f"JSON turns_count={json_count} != Markdown Turns={md_count}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    thread_id=_id_st,
    turns=_chat_turns_st(),
  )
  async def test_thread_all_contents_appear_in_both_formats(
    self,
    thread_id: str,
    turns: list[dict],
  ) -> None:
    """全ターンのコンテンツが JSON と Markdown の両方に存在すること。

    **Validates: Requirements 23.5**
    """
    svc = _build_export_service(chat_turns=turns, discussion_turns=[])

    json_result = await svc.export_thread(thread_id, format="json")
    md_result = await svc.export_thread(thread_id, format="markdown")

    json_data = json.loads(json_result)

    # JSON 内の各ターンの content が Markdown にも含まれること
    for turn in json_data["turns"]:
      content = turn["content"]
      assert content in md_result, (
        f"Content '{content[:50]}...' found in JSON but missing from Markdown"
      )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    discussion_id=_id_st,
    turns=_discussion_turns_st(),
  )
  async def test_discussion_json_and_markdown_same_turn_count(
    self,
    discussion_id: str,
    turns: list[dict],
  ) -> None:
    """ディスカッションの JSON と Markdown のターン数が一致すること。

    **Validates: Requirements 23.5**
    """
    svc = _build_export_service(chat_turns=[], discussion_turns=turns)

    json_result = await svc.export_discussion(discussion_id, format="json")
    md_result = await svc.export_discussion(discussion_id, format="markdown")

    json_data = json.loads(json_result)
    json_count = json_data["turns_count"]

    # Markdown のメタデータから Turns 数を抽出
    md_count = None
    for line in md_result.split("\n"):
      if line.startswith("- **Turns**:"):
        md_count = int(line.split(":")[1].strip())
        break

    assert json_count == md_count, (
      f"JSON turns_count={json_count} != Markdown Turns={md_count}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    discussion_id=_id_st,
    turns=_discussion_turns_st(),
  )
  async def test_discussion_all_contents_appear_in_both_formats(
    self,
    discussion_id: str,
    turns: list[dict],
  ) -> None:
    """全ディスカッションターンのコンテンツが両フォーマットに存在すること。

    **Validates: Requirements 23.5**
    """
    svc = _build_export_service(chat_turns=[], discussion_turns=turns)

    json_result = await svc.export_discussion(discussion_id, format="json")
    md_result = await svc.export_discussion(discussion_id, format="markdown")

    json_data = json.loads(json_result)

    # JSON 内の各ターンの content が Markdown にも含まれること
    for turn in json_data["turns"]:
      content = turn["content"]
      assert content in md_result, (
        f"Content '{content[:50]}...' found in JSON but missing from Markdown"
      )
