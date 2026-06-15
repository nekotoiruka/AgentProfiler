"""FeedbackService ユニットテスト"""

import os
import tempfile

import aiosqlite
import pytest

from app.decision_engine.feedback_service import (
  DIMENSION_KEYWORDS,
  FeedbackService,
)


@pytest.fixture
def tmp_db_path():
  """一時 DB ファイルパスを生成し、テスト後に削除する"""
  fd, path = tempfile.mkstemp(suffix=".db")
  os.close(fd)
  yield path
  if os.path.exists(path):
    os.unlink(path)


@pytest.fixture
def service(tmp_db_path):
  """テスト用 FeedbackService インスタンス"""
  return FeedbackService(db_path=tmp_db_path, threshold=10, step=0.1)


class TestInitDb:
  """init_db() のテスト"""

  @pytest.mark.asyncio
  async def test_creates_feedback_records_table(self, service, tmp_db_path):
    """feedback_records テーブルが作成される"""
    await service.init_db()

    async with aiosqlite.connect(tmp_db_path) as db:
      cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='feedback_records'"
      )
      row = await cursor.fetchone()
      assert row is not None
      assert row[0] == "feedback_records"

  @pytest.mark.asyncio
  async def test_creates_modification_history_table(self, service, tmp_db_path):
    """modification_history テーブルが作成される"""
    await service.init_db()

    async with aiosqlite.connect(tmp_db_path) as db:
      cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='modification_history'"
      )
      row = await cursor.fetchone()
      assert row is not None
      assert row[0] == "modification_history"

  @pytest.mark.asyncio
  async def test_creates_indexes(self, service, tmp_db_path):
    """全インデックスが作成される"""
    await service.init_db()

    async with aiosqlite.connect(tmp_db_path) as db:
      cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
      )
      rows = await cursor.fetchall()
      index_names = [row[0] for row in rows]

      assert "idx_feedback_agent_date" in index_names
      assert "idx_feedback_agent_type" in index_names
      assert "idx_modification_profile" in index_names

  @pytest.mark.asyncio
  async def test_idempotent_creation(self, service, tmp_db_path):
    """2回呼んでもエラーにならない（IF NOT EXISTS）"""
    await service.init_db()
    await service.init_db()

    async with aiosqlite.connect(tmp_db_path) as db:
      cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='feedback_records'"
      )
      row = await cursor.fetchone()
      assert row is not None


class TestRecordFeedback:
  """record_feedback() のテスト"""

  @pytest.mark.asyncio
  async def test_stores_approve_feedback(self, service, tmp_db_path):
    """approve フィードバックが正しく保存される"""
    await service.init_db()

    result = await service.record_feedback(
      agent_id="agent-001",
      thread_id="thread-001",
      turn_id="turn-001",
      feedback_type="approve",
      user_correction=None,
      original_response="テスト回答です",
    )

    assert "feedback_id" in result
    assert "created_at" in result
    assert result["feedback_id"] == 1

    # DB 確認
    async with aiosqlite.connect(tmp_db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute("SELECT * FROM feedback_records WHERE id = 1")
      row = await cursor.fetchone()

      assert row["agent_id"] == "agent-001"
      assert row["thread_id"] == "thread-001"
      assert row["turn_id"] == "turn-001"
      assert row["feedback_type"] == "approve"
      assert row["user_correction"] is None
      assert row["original_response"] == "テスト回答です"

  @pytest.mark.asyncio
  async def test_stores_reject_feedback_with_correction(self, service, tmp_db_path):
    """reject フィードバックが user_correction 付きで保存される"""
    await service.init_db()

    result = await service.record_feedback(
      agent_id="agent-002",
      thread_id="thread-002",
      turn_id="turn-002",
      feedback_type="reject",
      user_correction="もっと丁寧に言うべき",
      original_response="元の回答",
    )

    assert result["feedback_id"] == 1

    async with aiosqlite.connect(tmp_db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute("SELECT * FROM feedback_records WHERE id = 1")
      row = await cursor.fetchone()

      assert row["feedback_type"] == "reject"
      assert row["user_correction"] == "もっと丁寧に言うべき"

  @pytest.mark.asyncio
  async def test_raises_value_error_for_reject_without_correction(self, service, tmp_db_path):
    """reject で user_correction が None の場合 ValueError を投げる"""
    await service.init_db()

    with pytest.raises(ValueError, match="user_correction is required"):
      await service.record_feedback(
        agent_id="agent-003",
        thread_id="thread-003",
        turn_id="turn-003",
        feedback_type="reject",
        user_correction=None,
        original_response="元の回答",
      )

  @pytest.mark.asyncio
  async def test_raises_value_error_for_reject_with_empty_string(self, service, tmp_db_path):
    """reject で user_correction が空文字の場合 ValueError を投げる"""
    await service.init_db()

    with pytest.raises(ValueError, match="user_correction is required"):
      await service.record_feedback(
        agent_id="agent-003",
        thread_id="thread-003",
        turn_id="turn-003",
        feedback_type="reject",
        user_correction="",
        original_response="元の回答",
      )

  @pytest.mark.asyncio
  async def test_increments_feedback_id(self, service, tmp_db_path):
    """複数のフィードバックを記録すると ID がインクリメントされる"""
    await service.init_db()

    r1 = await service.record_feedback(
      agent_id="a", thread_id="t", turn_id="u1",
      feedback_type="approve", user_correction=None, original_response="res1",
    )
    r2 = await service.record_feedback(
      agent_id="a", thread_id="t", turn_id="u2",
      feedback_type="approve", user_correction=None, original_response="res2",
    )

    assert r2["feedback_id"] == r1["feedback_id"] + 1


class TestCheckAndAdjust:
  """check_and_adjust() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_empty_when_no_weights(self, service, tmp_db_path):
    """current_weights が None の場合空リストを返す"""
    await service.init_db()

    result = await service.check_and_adjust("agent-001", current_weights=None)
    assert result == []

  @pytest.mark.asyncio
  async def test_returns_empty_below_threshold(self, service, tmp_db_path):
    """reject 件数が閾値未満の場合、空リストを返す"""
    await service.init_db()

    # 9件（閾値10未満）の reject を記録
    for i in range(9):
      await service.record_feedback(
        agent_id="agent-t",
        thread_id="thread-t",
        turn_id=f"turn-{i}",
        feedback_type="reject",
        user_correction="根本原因を分析すべき",
        original_response=f"回答{i}",
      )

    weights = {"root_cause_first": 0.8}
    result = await service.check_and_adjust("agent-t", current_weights=weights)

    assert result == []
    # 重みは変更されない
    assert weights["root_cause_first"] == 0.8

  @pytest.mark.asyncio
  async def test_adjusts_when_threshold_met(self, service, tmp_db_path):
    """reject 件数が閾値以上で、キーワードが一致する次元の重みを調整する"""
    await service.init_db()

    # 10件の reject を記録（"根本原因" キーワード含む）
    for i in range(10):
      await service.record_feedback(
        agent_id="agent-adj",
        thread_id="thread-adj",
        turn_id=f"turn-{i}",
        feedback_type="reject",
        user_correction="根本原因よりもスピードを重視してほしい",
        original_response=f"回答{i}",
      )

    weights = {"root_cause_first": 0.8, "speed_first": 0.5}
    result = await service.check_and_adjust("agent-adj", current_weights=weights)

    # root_cause_first と speed_first 両方がマッチ
    field_names = [adj["field_name"] for adj in result]
    assert "root_cause_first" in field_names
    assert "speed_first" in field_names

    # 値が -0.1 されている
    root_adj = next(a for a in result if a["field_name"] == "root_cause_first")
    assert root_adj["previous_value"] == 0.8
    assert root_adj["new_value"] == 0.7
    assert root_adj["feedback_count"] == 10

    # current_weights も更新される
    assert weights["root_cause_first"] == 0.7

  @pytest.mark.asyncio
  async def test_persists_to_modification_history(self, service, tmp_db_path):
    """調整結果が modification_history テーブルに保存される"""
    await service.init_db()

    for i in range(10):
      await service.record_feedback(
        agent_id="agent-hist",
        thread_id="thread-hist",
        turn_id=f"turn-{i}",
        feedback_type="reject",
        user_correction="顧客を優先してほしい",
        original_response=f"回答{i}",
      )

    weights = {"customer_first": 0.6}
    await service.check_and_adjust("agent-hist", current_weights=weights)

    # modification_history に保存されている
    async with aiosqlite.connect(tmp_db_path) as db:
      db.row_factory = aiosqlite.Row
      cursor = await db.execute(
        "SELECT * FROM modification_history WHERE profile_id = 'agent-hist'"
      )
      rows = await cursor.fetchall()

      assert len(rows) == 1
      assert rows[0]["field_name"] == "customer_first"
      assert rows[0]["previous_value"] == 0.6
      assert rows[0]["new_value"] == 0.5

  @pytest.mark.asyncio
  async def test_ignores_dimensions_not_in_weights(self, service, tmp_db_path):
    """current_weights に存在しない次元は調整しない"""
    await service.init_db()

    for i in range(10):
      await service.record_feedback(
        agent_id="agent-miss",
        thread_id="thread-miss",
        turn_id=f"turn-{i}",
        feedback_type="reject",
        user_correction="データを重視してほしい",
        original_response=f"回答{i}",
      )

    # data_driven は weights に含まれていない
    weights = {"root_cause_first": 0.5}
    result = await service.check_and_adjust("agent-miss", current_weights=weights)

    assert result == []


class TestGetModificationHistory:
  """get_modification_history() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_chronological_order(self, service, tmp_db_path):
    """変更履歴が時系列順で返される"""
    await service.init_db()

    # 手動で modification_history に2件挿入
    async with aiosqlite.connect(tmp_db_path) as db:
      await db.execute(
        """INSERT INTO modification_history
        (profile_id, field_name, previous_value, new_value, adjustment_reason, feedback_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("prof-001", "root_cause_first", 0.8, 0.7, "理由A", 10, "2024-01-01T00:00:00+00:00"),
      )
      await db.execute(
        """INSERT INTO modification_history
        (profile_id, field_name, previous_value, new_value, adjustment_reason, feedback_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("prof-001", "speed_first", 0.5, 0.4, "理由B", 12, "2024-01-02T00:00:00+00:00"),
      )
      await db.commit()

    history = await service.get_modification_history("prof-001")

    assert len(history) == 2
    assert history[0]["field_name"] == "root_cause_first"
    assert history[0]["previous_value"] == 0.8
    assert history[0]["new_value"] == 0.7
    assert history[0]["adjustment_reason"] == "理由A"
    assert history[0]["feedback_count"] == 10
    assert history[0]["timestamp"] == "2024-01-01T00:00:00+00:00"

    assert history[1]["field_name"] == "speed_first"
    assert history[1]["timestamp"] == "2024-01-02T00:00:00+00:00"

  @pytest.mark.asyncio
  async def test_returns_empty_for_unknown_profile(self, service, tmp_db_path):
    """存在しないプロファイルでは空リストを返す"""
    await service.init_db()

    history = await service.get_modification_history("nonexistent")
    assert history == []

  @pytest.mark.asyncio
  async def test_isolates_profiles(self, service, tmp_db_path):
    """異なるプロファイルのデータは混在しない"""
    await service.init_db()

    async with aiosqlite.connect(tmp_db_path) as db:
      await db.execute(
        """INSERT INTO modification_history
        (profile_id, field_name, previous_value, new_value, adjustment_reason, feedback_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("prof-A", "dim_a", 0.5, 0.4, "理由", 10, "2024-01-01T00:00:00+00:00"),
      )
      await db.execute(
        """INSERT INTO modification_history
        (profile_id, field_name, previous_value, new_value, adjustment_reason, feedback_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("prof-B", "dim_b", 0.6, 0.5, "理由B", 11, "2024-01-01T00:00:00+00:00"),
      )
      await db.commit()

    history_a = await service.get_modification_history("prof-A")
    history_b = await service.get_modification_history("prof-B")

    assert len(history_a) == 1
    assert history_a[0]["field_name"] == "dim_a"
    assert len(history_b) == 1
    assert history_b[0]["field_name"] == "dim_b"


class TestAdjustWeight:
  """_adjust_weight() のテスト"""

  def test_increase_within_range(self, service):
    """increase で範囲内に収まる"""
    assert service._adjust_weight(0.5, "increase", 0.1) == 0.6

  def test_decrease_within_range(self, service):
    """decrease で範囲内に収まる"""
    assert service._adjust_weight(0.5, "decrease", 0.1) == 0.4

  def test_clamps_to_max(self, service):
    """1.0 を超える場合 1.0 にクランプされる"""
    assert service._adjust_weight(0.95, "increase", 0.1) == 1.0

  def test_clamps_to_min(self, service):
    """0.0 を下回る場合 0.0 にクランプされる"""
    assert service._adjust_weight(0.05, "decrease", 0.1) == 0.0

  def test_exact_boundary_max(self, service):
    """ちょうど 1.0 に到達する"""
    assert service._adjust_weight(0.9, "increase", 0.1) == 1.0

  def test_exact_boundary_min(self, service):
    """ちょうど 0.0 に到達する"""
    assert service._adjust_weight(0.1, "decrease", 0.1) == 0.0

  def test_at_max_increase_stays(self, service):
    """既に 1.0 で increase しても 1.0 のまま"""
    assert service._adjust_weight(1.0, "increase", 0.1) == 1.0

  def test_at_min_decrease_stays(self, service):
    """既に 0.0 で decrease しても 0.0 のまま"""
    assert service._adjust_weight(0.0, "decrease", 0.1) == 0.0

  def test_rounds_to_two_decimals(self, service):
    """浮動小数点の丸めが2桁で行われる"""
    # 0.33 - 0.1 = 0.23
    result = service._adjust_weight(0.33, "decrease", 0.1)
    assert result == 0.23


class TestExtractDimensionKeywords:
  """_extract_dimension_keywords() のテスト"""

  def test_single_keyword_match(self, service):
    """単一キーワードが正しくマッチする"""
    corrections = ["根本原因を分析してほしい"]
    result = service._extract_dimension_keywords(corrections)

    assert "root_cause_first" in result
    assert result["root_cause_first"] == 1

  def test_multiple_corrections_accumulate(self, service):
    """複数の修正テキストでカウントが累積する"""
    corrections = [
      "根本原因を見てください",
      "根本原因分析が足りない",
      "原因分析を優先して",
    ]
    result = service._extract_dimension_keywords(corrections)

    assert result["root_cause_first"] == 3

  def test_one_count_per_correction_per_dimension(self, service):
    """1つの修正テキストにつき各次元1回のみカウント"""
    # "根本原因" と "原因分析" 両方含むが root_cause_first は 1 回
    corrections = ["根本原因を見て原因分析をしてください"]
    result = service._extract_dimension_keywords(corrections)

    assert result["root_cause_first"] == 1

  def test_multiple_dimensions_in_single_text(self, service):
    """1つの修正テキストから複数次元が抽出される"""
    corrections = ["顧客のデータを分析してほしい"]
    result = service._extract_dimension_keywords(corrections)

    assert "customer_first" in result
    assert "data_driven" in result

  def test_case_insensitive_english(self, service):
    """英語キーワードの大文字小文字を無視する"""
    corrections = ["Please focus on ROOT CAUSE analysis"]
    result = service._extract_dimension_keywords(corrections)

    assert "root_cause_first" in result

  def test_empty_corrections(self, service):
    """空リストでは空辞書を返す"""
    result = service._extract_dimension_keywords([])
    assert result == {}

  def test_no_match(self, service):
    """キーワードがマッチしない場合は空辞書を返す"""
    corrections = ["特に問題なし"]
    result = service._extract_dimension_keywords(corrections)

    assert result == {}
