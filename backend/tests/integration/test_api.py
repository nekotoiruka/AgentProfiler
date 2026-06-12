"""API統合テスト

全6エンドポイントの正常系・異常系テスト、および完全フローテスト。

Validates: Requirements 11.7, 11.8, 11.9, 11.10
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import dependencies as deps
from app.main import app


# 全質問ID一覧（questions.yaml に対応）
ALL_QUESTION_IDS = [
  "bos_001", "bos_002", "bos_003", "bos_004", "bos_005",
  "bos_006", "bos_007", "bos_008", "bos_009",
  "com_001", "com_002", "com_003", "com_004",
  "com_005", "com_006", "com_007", "com_008", "com_009",
  "lif_001", "lif_002", "lif_003", "lif_004",
  "lif_005", "lif_006", "lif_007", "lif_008", "lif_009",
  "int_001", "int_002", "int_003", "int_004", "int_005",
  "per_001", "per_002", "per_003", "per_004", "per_005",
  "ton_001", "ton_002", "ton_003", "ton_004", "ton_005",
  "val_001", "val_002", "val_003", "val_004", "val_005",
]


@pytest.fixture(autouse=True)
async def setup_services(tmp_path):
  """テスト用の一時DBパスでサービスを初期化する"""
  # DBパスを一時ディレクトリにオーバーライド
  original_db_path = deps._DB_PATH
  deps._DB_PATH = tmp_path / "test_sessions.db"

  # サービスを初期化
  await deps.init_services()

  yield

  # クリーンアップ: 元のパスに戻す
  deps._DB_PATH = original_db_path


@pytest.fixture
async def client():
  """httpx AsyncClient を生成する"""
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as c:
    yield c


# =============================================================================
# 正常系テスト
# =============================================================================


class TestCreateSession:
  """POST /api/sessions → 201"""

  async def test_creates_session_returns_201(self, client: AsyncClient):
    resp = await client.post("/api/sessions")
    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data
    assert isinstance(data["session_id"], str)
    assert len(data["session_id"]) > 0


class TestSubmitAnswer:
  """POST /api/sessions/{id}/answers → 200"""

  async def test_submit_choice_answer(self, client: AsyncClient):
    # セッション作成
    resp = await client.post("/api/sessions")
    session_id = resp.json()["session_id"]

    # 選択肢回答を送信
    resp = await client.post(
      f"/api/sessions/{session_id}/answers",
      json={
        "question_id": "bos_001",
        "choice_id": "a",
      },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"

  async def test_submit_text_answer(self, client: AsyncClient):
    # セッション作成
    resp = await client.post("/api/sessions")
    session_id = resp.json()["session_id"]

    # テキスト回答を送信（Other選択）
    resp = await client.post(
      f"/api/sessions/{session_id}/answers",
      json={
        "question_id": "bos_001",
        "text": "独自のアプローチで解決する",
      },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"


class TestGetSessionStatus:
  """GET /api/sessions/{id}/status → 200"""

  async def test_returns_session_status(self, client: AsyncClient):
    # セッション作成
    resp = await client.post("/api/sessions")
    session_id = resp.json()["session_id"]

    # 1問回答
    await client.post(
      f"/api/sessions/{session_id}/answers",
      json={"question_id": "bos_001", "choice_id": "a"},
    )

    # ステータス取得
    resp = await client.get(f"/api/sessions/{session_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["status"] == "active"
    assert data["answered"] == 1
    assert data["total"] == 47
    assert data["category"] is not None


class TestGetQuestions:
  """GET /api/questions → 200"""

  async def test_returns_categories_with_questions(self, client: AsyncClient):
    resp = await client.get("/api/questions")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data

    categories = data["categories"]
    assert len(categories) == 7

    # カテゴリ順序確認
    assert categories[0]["id"] == "business_os"
    assert categories[1]["id"] == "communication"
    assert categories[2]["id"] == "lifestyle"

    # 各カテゴリに質問が含まれている
    for cat in categories:
      assert len(cat["questions"]) >= 3


class TestCalculateProfile:
  """POST /api/sessions/{id}/calculate → 200"""

  async def test_calculate_after_all_answers(self, client: AsyncClient):
    # セッション作成
    resp = await client.post("/api/sessions")
    session_id = resp.json()["session_id"]

    # 全問回答
    for qid in ALL_QUESTION_IDS:
      if qid.startswith("int_"):
        await client.post(
          f"/api/sessions/{session_id}/answers",
          json={"question_id": qid, "selected_options": ["opt_1"]},
        )
      else:
        await client.post(
          f"/api/sessions/{session_id}/answers",
          json={"question_id": qid, "choice_id": "a"},
        )

    # 計算実行
    resp = await client.post(f"/api/sessions/{session_id}/calculate")
    assert resp.status_code == 200
    data = resp.json()
    assert "profile_id" in data
    assert data["profile_id"].startswith("prof_")


class TestGetProfile:
  """GET /api/sessions/{id}/profile → 200"""

  async def test_returns_full_profile_json(self, client: AsyncClient):
    # セッション作成
    resp = await client.post("/api/sessions")
    session_id = resp.json()["session_id"]

    # 全問回答
    for qid in ALL_QUESTION_IDS:
      if qid.startswith("int_"):
        await client.post(
          f"/api/sessions/{session_id}/answers",
          json={"question_id": qid, "selected_options": ["opt_1"]},
        )
      else:
        await client.post(
          f"/api/sessions/{session_id}/answers",
          json={"question_id": qid, "choice_id": "a"},
        )

    # 計算
    await client.post(f"/api/sessions/{session_id}/calculate")

    # プロファイル取得
    resp = await client.get(f"/api/sessions/{session_id}/profile")
    assert resp.status_code == 200
    data = resp.json()

    # 構造検証
    assert "profile_id" in data
    assert "base_os" in data
    assert "lexical_tags" in data
    assert "semantic_contexts" in data
    assert "context_layers" in data

    # base_os 構造
    base_os = data["base_os"]
    assert "axes" in base_os
    assert "decision_style" in base_os
    assert "do_not_list" in base_os

    # axes は4軸すべて 0.00〜1.00
    axes = base_os["axes"]
    for axis_name in [
      "extroverted_introverted",
      "sensing_intuition",
      "thinking_feeling",
      "judging_perceiving",
    ]:
      assert axis_name in axes
      assert 0.0 <= axes[axis_name] <= 1.0

    # context_layers
    layers = data["context_layers"]
    assert layers["base_os"] == 1
    assert layers["lexical_tags"] == 2
    assert layers["semantic_contexts"] == 3


# =============================================================================
# エラー系テスト
# =============================================================================


class TestErrorInvalidSession:
  """不正セッションID → 404

  Validates: Requirement 11.7
  """

  async def test_submit_answer_to_invalid_session(self, client: AsyncClient):
    resp = await client.post(
      "/api/sessions/nonexistent-session-id/answers",
      json={"question_id": "bos_001", "choice_id": "a"},
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"]["error"] == "session_not_found"

  async def test_get_status_of_invalid_session(self, client: AsyncClient):
    resp = await client.get("/api/sessions/nonexistent-session-id/status")
    assert resp.status_code == 404

  async def test_calculate_invalid_session(self, client: AsyncClient):
    resp = await client.post(
      "/api/sessions/nonexistent-session-id/calculate"
    )
    assert resp.status_code == 404

  async def test_get_profile_of_invalid_session(self, client: AsyncClient):
    resp = await client.get("/api/sessions/nonexistent-session-id/profile")
    assert resp.status_code == 404


class TestErrorValidation:
  """不正リクエスト → 422

  Validates: Requirement 11.8
  """

  async def test_submit_answer_without_choice_or_text(
    self, client: AsyncClient
  ):
    # セッション作成
    resp = await client.post("/api/sessions")
    session_id = resp.json()["session_id"]

    # choice_id も text も指定しない
    resp = await client.post(
      f"/api/sessions/{session_id}/answers",
      json={"question_id": "bos_001"},
    )
    assert resp.status_code == 422


class TestErrorIncompleteCalculation:
  """未完了セッションの計算 → 409

  Validates: Requirement 11.9
  """

  async def test_calculate_with_unanswered_questions(
    self, client: AsyncClient
  ):
    # セッション作成
    resp = await client.post("/api/sessions")
    session_id = resp.json()["session_id"]

    # 1問だけ回答（13問中）
    await client.post(
      f"/api/sessions/{session_id}/answers",
      json={"question_id": "bos_001", "choice_id": "a"},
    )

    # 計算を試行 → 409
    resp = await client.post(f"/api/sessions/{session_id}/calculate")
    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"]["error"] == "session_incomplete"


class TestErrorProfileNotGenerated:
  """未生成プロファイルの取得 → 404

  Validates: Requirement 11.10
  """

  async def test_get_profile_before_calculation(self, client: AsyncClient):
    # セッション作成
    resp = await client.post("/api/sessions")
    session_id = resp.json()["session_id"]

    # 計算前にプロファイル取得 → 404
    resp = await client.get(f"/api/sessions/{session_id}/profile")
    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"]["error"] == "profile_not_available"


# =============================================================================
# 完全フローテスト
# =============================================================================


class TestFullFlow:
  """セッション作成→全問回答→計算→プロファイル取得の完全フロー"""

  async def test_complete_survey_flow(self, client: AsyncClient):
    # 1. セッション作成
    resp = await client.post("/api/sessions")
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    # 2. 全32問に回答（single_choiceはローテーション、multi_selectはデフォルト選択）
    choices = ["a", "b", "c", "d"]
    single_idx = 0
    for qid in ALL_QUESTION_IDS:
      if qid.startswith("int_"):
        # multi_select: デフォルト選択肢
        resp = await client.post(
          f"/api/sessions/{session_id}/answers",
          json={"question_id": qid, "selected_options": ["opt_1", "opt_2"]},
        )
      else:
        choice = choices[single_idx % 4]
        resp = await client.post(
          f"/api/sessions/{session_id}/answers",
          json={"question_id": qid, "choice_id": choice},
        )
        single_idx += 1
      assert resp.status_code == 200
      assert resp.json()["status"] == "accepted"

    # 3. ステータス確認: 全問回答済み
    resp = await client.get(f"/api/sessions/{session_id}/status")
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["answered"] == 47
    assert status_data["total"] == 47

    # 4. スコア計算＋プロファイル生成
    resp = await client.post(f"/api/sessions/{session_id}/calculate")
    assert resp.status_code == 200
    profile_id = resp.json()["profile_id"]
    assert profile_id.startswith("prof_")

    # 5. プロファイル取得
    resp = await client.get(f"/api/sessions/{session_id}/profile")
    assert resp.status_code == 200
    profile = resp.json()

    # プロファイル構造の完全性検証
    assert profile["profile_id"] == profile_id
    assert "base_os" in profile
    assert "axes" in profile["base_os"]
    assert "decision_style" in profile["base_os"]
    assert "do_not_list" in profile["base_os"]
    assert "lexical_tags" in profile
    assert isinstance(profile["lexical_tags"], list)
    assert "semantic_contexts" in profile
    assert isinstance(profile["semantic_contexts"], dict)
    assert profile["context_layers"] == {
      "base_os": 1,
      "lexical_tags": 2,
      "semantic_contexts": 3,
    }

    # 6. 完了後セッションのステータス確認
    resp = await client.get(f"/api/sessions/{session_id}/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"
