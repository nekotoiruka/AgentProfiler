"""AnswerPipeline ユニットテスト"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest

from app.decision_engine.answer_pipeline import AnswerPipeline
from app.decision_engine.models import AnswerMetadata, Permanence
from app.decision_engine.normalizer_llm import NormalizationResult


@pytest.fixture
def tmp_db_path():
  """一時 DB ファイルパスを生成し、テスト後に削除する"""
  fd, path = tempfile.mkstemp(suffix=".db")
  os.close(fd)
  yield path
  if os.path.exists(path):
    os.unlink(path)


@pytest.fixture
def mock_normalizer():
  """LLMNormalizer のモック"""
  normalizer = MagicMock()
  normalizer.normalize = AsyncMock(return_value=None)
  return normalizer


@pytest.fixture
def pipeline(tmp_db_path, mock_normalizer):
  """テスト用 AnswerPipeline インスタンス"""
  return AnswerPipeline(db_path=tmp_db_path, llm_normalizer=mock_normalizer)


class TestInitDb:
  """init_db() のテスト"""

  @pytest.mark.asyncio
  async def test_creates_answer_layers_table(self, pipeline, tmp_db_path):
    """answer_layers テーブルが作成される"""
    await pipeline.init_db()

    async with aiosqlite.connect(tmp_db_path) as db:
      cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='answer_layers'"
      )
      row = await cursor.fetchone()
      assert row is not None
      assert row[0] == "answer_layers"

  @pytest.mark.asyncio
  async def test_creates_session_index(self, pipeline, tmp_db_path):
    """session_id + question_id のインデックスが作成される"""
    await pipeline.init_db()

    async with aiosqlite.connect(tmp_db_path) as db:
      cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_answer_layers_session'"
      )
      row = await cursor.fetchone()
      assert row is not None

  @pytest.mark.asyncio
  async def test_idempotent_creation(self, pipeline, tmp_db_path):
    """2回呼んでもエラーにならない（IF NOT EXISTS）"""
    await pipeline.init_db()
    await pipeline.init_db()  # 2回目もエラーなし

    async with aiosqlite.connect(tmp_db_path) as db:
      cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='answer_layers'"
      )
      row = await cursor.fetchone()
      assert row is not None


class TestProcessPredefined:
  """process_predefined() のテスト"""

  @pytest.mark.asyncio
  async def test_stores_and_returns_correctly(self, pipeline, tmp_db_path):
    """定義済み選択肢が正しく保存・返却される"""
    await pipeline.init_db()

    result = await pipeline.process_predefined(
      session_id="sess_001",
      question_id="dm_001",
      choice_id="a",
      choice_label="根本原因を特定する",
      policy_text="when_incident: 根本原因分析を最優先する",
      normalized_tags=[{"type": "behavior_tag", "value": "根本原因分析"}],
    )

    assert result["is_pending"] is False
    assert result["policy"] == "when_incident: 根本原因分析を最優先する"
    assert result["raw"]["choice_id"] == "a"
    assert result["raw"]["choice_label"] == "根本原因を特定する"
    assert result["normalized"]["tags"] == [{"type": "behavior_tag", "value": "根本原因分析"}]

  @pytest.mark.asyncio
  async def test_persisted_in_db(self, pipeline, tmp_db_path):
    """DB に正しく永続化される"""
    await pipeline.init_db()

    await pipeline.process_predefined(
      session_id="sess_001",
      question_id="dm_002",
      choice_id="b",
      choice_label="顧客対応を優先",
      policy_text="when_conflict: 顧客満足度を最優先する",
    )

    async with aiosqlite.connect(tmp_db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute("SELECT * FROM answer_layers WHERE session_id = 'sess_001'")
      row = await cursor.fetchone()

      assert row is not None
      assert row["session_id"] == "sess_001"
      assert row["question_id"] == "dm_002"
      assert row["policy_text"] == "when_conflict: 顧客満足度を最優先する"
      assert row["permanence"] == "permanent"
      assert row["confidence"] == 0.6

  @pytest.mark.asyncio
  async def test_with_custom_metadata(self, pipeline, tmp_db_path):
    """カスタムメタデータが反映される"""
    await pipeline.init_db()

    meta = AnswerMetadata(
      permanence=Permanence.CONTEXTUAL,
      confidence=0.9,
      exception_note="緊急時を除く",
      is_core_rule=True,
      ambiguity=0.3,
    )

    await pipeline.process_predefined(
      session_id="sess_001",
      question_id="dm_003",
      choice_id="c",
      choice_label="スピード優先",
      policy_text="when_normal: 速度を重視する",
      metadata=meta,
    )

    async with aiosqlite.connect(tmp_db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute("SELECT * FROM answer_layers WHERE question_id = 'dm_003'")
      row = await cursor.fetchone()

      assert row["permanence"] == "contextual"
      assert row["confidence"] == 0.9
      assert row["exception_note"] == "緊急時を除く"
      assert row["is_core_rule"] == 1
      assert row["ambiguity"] == 0.3

  @pytest.mark.asyncio
  async def test_without_normalized_tags(self, pipeline, tmp_db_path):
    """normalized_tags なしでも正常に動作する"""
    await pipeline.init_db()

    result = await pipeline.process_predefined(
      session_id="sess_001",
      question_id="dm_004",
      choice_id="d",
      choice_label="長期的視点",
      policy_text="when_planning: 長期的影響を考慮する",
    )

    assert result["normalized"] is None
    assert result["policy"] == "when_planning: 長期的影響を考慮する"


class TestProcessFreeText:
  """process_free_text() のテスト"""

  @pytest.mark.asyncio
  async def test_successful_normalization(self, pipeline, tmp_db_path, mock_normalizer):
    """LLM 正規化成功時: 3層すべてが格納される"""
    await pipeline.init_db()

    mock_normalizer.normalize = AsyncMock(
      return_value=NormalizationResult(
        tags=[{"type": "value_tag", "value": "品質重視"}],
        policy_text="when_development: 品質基準を維持する",
      )
    )

    result = await pipeline.process_free_text(
      session_id="sess_002",
      question_id="dm_001",
      text="私は品質を最も重視しています",
      question_text="あなたの優先事項は？",
    )

    assert result["is_pending"] is False
    assert result["policy"] == "when_development: 品質基準を維持する"
    assert result["normalized"]["tags"] == [{"type": "value_tag", "value": "品質重視"}]
    assert result["raw"]["free_text"] == "私は品質を最も重視しています"

  @pytest.mark.asyncio
  async def test_normalization_failure_marks_pending(self, pipeline, tmp_db_path, mock_normalizer):
    """LLM 正規化失敗時: pending としてマークされる"""
    await pipeline.init_db()

    # normalizer が None を返す（失敗シミュレーション）
    mock_normalizer.normalize = AsyncMock(return_value=None)

    result = await pipeline.process_free_text(
      session_id="sess_002",
      question_id="dm_002",
      text="複雑な回答テキスト",
    )

    assert result["is_pending"] is True
    assert result["policy"] is None
    assert result["normalized"] is None

  @pytest.mark.asyncio
  async def test_pending_entry_has_null_policy_in_db(self, pipeline, tmp_db_path, mock_normalizer):
    """pending エントリは DB で policy_text が NULL"""
    await pipeline.init_db()
    mock_normalizer.normalize = AsyncMock(return_value=None)

    await pipeline.process_free_text(
      session_id="sess_002",
      question_id="dm_003",
      text="テスト回答",
    )

    async with aiosqlite.connect(tmp_db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute("SELECT * FROM answer_layers WHERE question_id = 'dm_003'")
      row = await cursor.fetchone()

      assert row["policy_text"] is None
      assert row["normalized_json"] is None

  @pytest.mark.asyncio
  async def test_normalizer_called_with_correct_args(self, pipeline, tmp_db_path, mock_normalizer):
    """LLMNormalizer に正しい引数が渡される"""
    await pipeline.init_db()
    mock_normalizer.normalize = AsyncMock(return_value=None)

    await pipeline.process_free_text(
      session_id="sess_002",
      question_id="dm_004",
      text="回答テキスト",
      question_text="質問テキスト",
    )

    mock_normalizer.normalize.assert_called_once_with("質問テキスト", "回答テキスト")


class TestReNormalizePending:
  """re_normalize_pending() のテスト"""

  @pytest.mark.asyncio
  async def test_re_normalizes_pending_entries(self, pipeline, tmp_db_path, mock_normalizer):
    """pending エントリが正常に再正規化される"""
    await pipeline.init_db()

    # まず pending エントリを作成
    mock_normalizer.normalize = AsyncMock(return_value=None)
    await pipeline.process_free_text(
      session_id="sess_003",
      question_id="q_001",
      text="再正規化対象テキスト",
    )

    # 再正規化時は成功するように設定
    mock_normalizer.normalize = AsyncMock(
      return_value=NormalizationResult(
        tags=[{"type": "behavior_tag", "value": "計画的"}],
        policy_text="when_task: 計画を立ててから実行する",
      )
    )

    count = await pipeline.re_normalize_pending("sess_003")

    assert count == 1

    # DB が更新されていることを確認
    async with aiosqlite.connect(tmp_db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute("SELECT * FROM answer_layers WHERE question_id = 'q_001'")
      row = await cursor.fetchone()

      assert row["policy_text"] == "when_task: 計画を立ててから実行する"
      assert row["normalized_json"] is not None

  @pytest.mark.asyncio
  async def test_skips_non_pending_entries(self, pipeline, tmp_db_path, mock_normalizer):
    """既に正規化済みのエントリはスキップされる"""
    await pipeline.init_db()

    # 正規化済みエントリを作成
    await pipeline.process_predefined(
      session_id="sess_003",
      question_id="q_002",
      choice_id="a",
      choice_label="テスト",
      policy_text="when_test: テスト",
    )

    mock_normalizer.normalize = AsyncMock(return_value=None)
    count = await pipeline.re_normalize_pending("sess_003")

    assert count == 0
    # normalizer は呼ばれない（policy_text が NULL のエントリがないため）
    mock_normalizer.normalize.assert_not_called()

  @pytest.mark.asyncio
  async def test_partial_success(self, pipeline, tmp_db_path, mock_normalizer):
    """一部のみ再正規化に成功するケース"""
    await pipeline.init_db()

    # 2つの pending エントリを作成
    mock_normalizer.normalize = AsyncMock(return_value=None)
    await pipeline.process_free_text(session_id="sess_003", question_id="q_a", text="テキストA")
    await pipeline.process_free_text(session_id="sess_003", question_id="q_b", text="テキストB")

    # 再正規化: 1回目成功、2回目失敗
    mock_normalizer.normalize = AsyncMock(
      side_effect=[
        NormalizationResult(
          tags=[{"type": "value_tag", "value": "成功"}],
          policy_text="when_a: 成功ルール",
        ),
        None,  # 2回目は失敗
      ]
    )

    count = await pipeline.re_normalize_pending("sess_003")

    assert count == 1

  @pytest.mark.asyncio
  async def test_returns_zero_for_empty_session(self, pipeline, tmp_db_path):
    """存在しないセッションでは 0 を返す"""
    await pipeline.init_db()

    count = await pipeline.re_normalize_pending("nonexistent_session")

    assert count == 0


class TestGetAllPolicies:
  """get_all_policies() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_policies_in_creation_order(self, pipeline, tmp_db_path):
    """作成順でポリシーが返される"""
    await pipeline.init_db()

    # 3つのエントリを順に作成
    await pipeline.process_predefined(
      session_id="sess_004",
      question_id="q_first",
      choice_id="a",
      choice_label="最初",
      policy_text="when_first: 最初のルール",
    )
    await pipeline.process_predefined(
      session_id="sess_004",
      question_id="q_second",
      choice_id="b",
      choice_label="2番目",
      policy_text="when_second: 2番目のルール",
    )
    await pipeline.process_predefined(
      session_id="sess_004",
      question_id="q_third",
      choice_id="c",
      choice_label="3番目",
      policy_text="when_third: 3番目のルール",
    )

    policies = await pipeline.get_all_policies("sess_004")

    assert len(policies) == 3
    assert policies[0]["rule"] == "when_first: 最初のルール"
    assert policies[1]["rule"] == "when_second: 2番目のルール"
    assert policies[2]["rule"] == "when_third: 3番目のルール"

  @pytest.mark.asyncio
  async def test_excludes_pending_entries(self, pipeline, tmp_db_path, mock_normalizer):
    """pending（policy_text が NULL）のエントリは除外される"""
    await pipeline.init_db()

    # 正規化済みエントリ
    await pipeline.process_predefined(
      session_id="sess_004",
      question_id="q_done",
      choice_id="a",
      choice_label="完了",
      policy_text="when_done: 完了ルール",
    )

    # pending エントリ
    mock_normalizer.normalize = AsyncMock(return_value=None)
    await pipeline.process_free_text(
      session_id="sess_004",
      question_id="q_pending",
      text="未処理テキスト",
    )

    policies = await pipeline.get_all_policies("sess_004")

    assert len(policies) == 1
    assert policies[0]["question_id"] == "q_done"

  @pytest.mark.asyncio
  async def test_returns_correct_fields(self, pipeline, tmp_db_path):
    """返却される各フィールドが正しい"""
    await pipeline.init_db()

    meta = AnswerMetadata(
      permanence=Permanence.CONTEXTUAL,
      confidence=0.8,
      is_core_rule=True,
    )
    await pipeline.process_predefined(
      session_id="sess_004",
      question_id="q_fields",
      choice_id="a",
      choice_label="テスト",
      policy_text="when_test: フィールド確認",
      normalized_tags=[{"type": "value_tag", "value": "テスト"}],
      metadata=meta,
    )

    policies = await pipeline.get_all_policies("sess_004")

    assert len(policies) == 1
    p = policies[0]
    assert p["question_id"] == "q_fields"
    assert p["rule"] == "when_test: フィールド確認"
    assert p["confidence"] == 0.8
    assert p["is_core"] is True
    assert p["permanence"] == "contextual"
    assert p["normalization_tags"] == [{"type": "value_tag", "value": "テスト"}]

  @pytest.mark.asyncio
  async def test_isolates_sessions(self, pipeline, tmp_db_path):
    """異なるセッションのデータは混在しない"""
    await pipeline.init_db()

    await pipeline.process_predefined(
      session_id="sess_A",
      question_id="q_001",
      choice_id="a",
      choice_label="A",
      policy_text="when_a: セッションA",
    )
    await pipeline.process_predefined(
      session_id="sess_B",
      question_id="q_001",
      choice_id="b",
      choice_label="B",
      policy_text="when_b: セッションB",
    )

    policies_a = await pipeline.get_all_policies("sess_A")
    policies_b = await pipeline.get_all_policies("sess_B")

    assert len(policies_a) == 1
    assert policies_a[0]["rule"] == "when_a: セッションA"
    assert len(policies_b) == 1
    assert policies_b[0]["rule"] == "when_b: セッションB"

  @pytest.mark.asyncio
  async def test_empty_session_returns_empty_list(self, pipeline, tmp_db_path):
    """エントリがないセッションでは空リストを返す"""
    await pipeline.init_db()

    policies = await pipeline.get_all_policies("nonexistent")

    assert policies == []
