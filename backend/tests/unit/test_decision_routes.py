"""Decision Engine API エンドポイントのユニットテスト

Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.decision_engine.answer_pipeline import AnswerPipeline
from app.decision_engine.feedback_service import FeedbackService
from app.main import app


@pytest.fixture(autouse=True)
async def _override_db_path(tmp_path):
  """テスト用の一時ディレクトリを data_dir として使用する

  routes.py の _get_db_path() と dependencies.py のファクトリ関数が
  参照する DB パスを一時ディレクトリにオーバーライドする。
  テーブルも事前に初期化する。
  """
  tmp_db = str(tmp_path / "decision_engine.db")

  # FeedbackService を一時 DB で生成しテーブル初期化
  service = FeedbackService(db_path=tmp_db, threshold=10, step=0.1)
  await service.init_db()

  # AnswerPipeline を一時 DB で生成（LLMNormalizer はモック）
  mock_normalizer = MagicMock()
  mock_normalizer.normalize = AsyncMock(return_value=None)
  pipeline = AnswerPipeline(db_path=tmp_db, llm_normalizer=mock_normalizer)
  await pipeline.init_db()

  # routes.py 内の _get_db_path と dependencies のファクトリをオーバーライド
  with patch(
    "app.decision_engine.routes._get_db_path",
    return_value=tmp_db,
  ), patch(
    "app.decision_engine.routes.get_feedback_service",
    return_value=service,
  ), patch(
    "app.decision_engine.routes.get_answer_pipeline",
    return_value=pipeline,
  ):
    yield tmp_db


@pytest.fixture
async def client():
  """非同期テストクライアント"""
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as ac:
    yield ac


class TestPostFeedback:
  """POST /api/feedback のテスト"""

  @pytest.mark.asyncio
  async def test_creates_feedback_201(self, client):
    """正常なフィードバック送信で 201 を返す"""
    response = await client.post("/api/feedback", json={
      "agent_id": "12345678-1234-4123-8123-123456789012",
      "thread_id": "12345678-1234-4123-8123-123456789012",
      "turn_id": "12345678-1234-4123-8123-123456789012",
      "feedback_type": "approve",
    })
    assert response.status_code == 201
    data = response.json()
    assert "feedback_id" in data
    assert "created_at" in data

  @pytest.mark.asyncio
  async def test_reject_without_correction_422(self, client):
    """reject で user_correction なしは 422"""
    response = await client.post("/api/feedback", json={
      "agent_id": "12345678-1234-4123-8123-123456789012",
      "thread_id": "12345678-1234-4123-8123-123456789012",
      "turn_id": "12345678-1234-4123-8123-123456789012",
      "feedback_type": "reject",
    })
    assert response.status_code == 422

  @pytest.mark.asyncio
  async def test_reject_with_correction_201(self, client):
    """reject で user_correction ありは 201"""
    response = await client.post("/api/feedback", json={
      "agent_id": "12345678-1234-4123-8123-123456789012",
      "thread_id": "12345678-1234-4123-8123-123456789012",
      "turn_id": "12345678-1234-4123-8123-123456789012",
      "feedback_type": "reject",
      "user_correction": "もっと丁寧に",
    })
    assert response.status_code == 201

  @pytest.mark.asyncio
  async def test_invalid_agent_id_422(self, client):
    """不正な UUID 形式で 422 を返す"""
    response = await client.post("/api/feedback", json={
      "agent_id": "not-a-valid-uuid",
      "thread_id": "12345678-1234-4123-8123-123456789012",
      "turn_id": "12345678-1234-4123-8123-123456789012",
      "feedback_type": "approve",
    })
    assert response.status_code == 422


class TestGetFeedback:
  """GET /api/feedback/{agent_id} のテスト"""

  @pytest.mark.asyncio
  async def test_returns_feedback_list(self, client):
    """フィードバック一覧取得が成功する"""
    agent_id = "12345678-1234-4123-8123-123456789012"
    response = await client.get(f"/api/feedback/{agent_id}")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data

  @pytest.mark.asyncio
  async def test_pagination_params(self, client):
    """ページネーションパラメータが反映される"""
    agent_id = "12345678-1234-4123-8123-123456789012"
    response = await client.get(f"/api/feedback/{agent_id}?limit=5&offset=10")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 10

  @pytest.mark.asyncio
  async def test_default_pagination(self, client):
    """デフォルトのページネーション値が適用される"""
    agent_id = "12345678-1234-4123-8123-123456789012"
    response = await client.get(f"/api/feedback/{agent_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 20
    assert data["offset"] == 0

  @pytest.mark.asyncio
  async def test_returns_created_feedback(self, client):
    """投稿したフィードバックが一覧に含まれる"""
    agent_id = "12345678-1234-4123-8123-123456789012"

    # フィードバックを作成
    await client.post("/api/feedback", json={
      "agent_id": agent_id,
      "thread_id": "12345678-1234-4123-8123-123456789012",
      "turn_id": "12345678-1234-4123-8123-123456789012",
      "feedback_type": "approve",
    })

    # 一覧を取得
    response = await client.get(f"/api/feedback/{agent_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


class TestGetDecisionEngine:
  """GET /api/profiles/{profile_id}/decision-engine のテスト"""

  @pytest.mark.asyncio
  async def test_returns_placeholder_data(self, client):
    """decision-engine データ取得が成功する"""
    response = await client.get("/api/profiles/prof_000001/decision-engine")
    assert response.status_code == 200
    data = response.json()
    assert "profile_id" in data
    assert data["profile_id"] == "prof_000001"

  @pytest.mark.asyncio
  async def test_returns_expected_fields(self, client):
    """レスポンスに必要なフィールドが含まれる"""
    response = await client.get("/api/profiles/prof_000001/decision-engine")
    assert response.status_code == 200
    data = response.json()
    assert "decision_model" in data
    assert "failure_patterns" in data
    assert "context_adaptation" in data
    assert "reasoning_flow" in data
    assert "rule_hierarchy" in data


class TestGetModificationHistory:
  """GET /api/profiles/{profile_id}/modification-history のテスト"""

  @pytest.mark.asyncio
  async def test_returns_empty_history(self, client):
    """変更履歴取得が成功する（空リスト）"""
    response = await client.get("/api/profiles/prof_000001/modification-history")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 0

  @pytest.mark.asyncio
  async def test_different_profile_ids(self, client):
    """異なる profile_id で問題なく取得できる"""
    response = await client.get("/api/profiles/any_profile_id/modification-history")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


class TestReNormalize:
  """POST /api/sessions/{session_id}/re-normalize のテスト"""

  @pytest.mark.asyncio
  async def test_re_normalize_returns_count(self, client):
    """re-normalize が成功し、処理件数を返す"""
    response = await client.post("/api/sessions/test_session/re-normalize")
    assert response.status_code == 200
    data = response.json()
    assert "re_normalized_count" in data
    assert "session_id" in data

  @pytest.mark.asyncio
  async def test_re_normalize_session_id_matches(self, client):
    """レスポンスの session_id がリクエストと一致する"""
    session_id = "my_custom_session"
    response = await client.post(f"/api/sessions/{session_id}/re-normalize")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id

  @pytest.mark.asyncio
  async def test_re_normalize_empty_session(self, client):
    """pending エントリなしの場合 0 を返す"""
    response = await client.post("/api/sessions/empty_session/re-normalize")
    assert response.status_code == 200
    data = response.json()
    assert data["re_normalized_count"] == 0
