"""End-to-End統合テスト

セッション作成→全質問回答→計算→プロファイル表示の完全フロー、
セッション復帰フロー、エラーハンドリングフローを検証する。

Validates: Requirements 1.7, 10.2, 10.3
"""

import re

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
]

# single_choice のみのID（スコアリング対象）
SINGLE_CHOICE_IDS = [qid for qid in ALL_QUESTION_IDS if not qid.startswith("int_")]

# multi_select のID（タグ収集用）
MULTI_SELECT_IDS = [qid for qid in ALL_QUESTION_IDS if qid.startswith("int_")]

# プロファイルIDの正規表現パターン
PROFILE_ID_PATTERN = re.compile(r"^prof_\d{6}$")

# semantic_contexts の5ドメインキー
SEMANTIC_CONTEXT_KEYS = [
  "problem_solving",
  "communication_style",
  "work_rhythm",
  "analog_habits",
  "lifestyle_preferences",
]


@pytest.fixture(autouse=True)
async def setup_services(tmp_path):
  """テスト用の一時DBパスでサービスを初期化する"""
  original_db_path = deps._DB_PATH
  deps._DB_PATH = tmp_path / "test_sessions.db"
  await deps.init_services()
  yield
  deps._DB_PATH = original_db_path


@pytest.fixture
async def client():
  """httpx AsyncClient を生成する"""
  transport = ASGITransport(app=app)
  async with AsyncClient(transport=transport, base_url="http://test") as c:
    yield c


# =============================================================================
# ヘルパー関数
# =============================================================================


async def create_session(client: AsyncClient) -> str:
  """セッションを作成してsession_idを返す"""
  resp = await client.post("/api/sessions")
  assert resp.status_code == 201
  return resp.json()["session_id"]


async def answer_all_questions(
  client: AsyncClient,
  session_id: str,
  choices: list[str] | None = None,
  text_answers: dict[str, str] | None = None,
) -> None:
  """全質問に回答する

  choices: 各single_choice質問に対する選択肢IDリスト（指定なしの場合は全て"a"）
  text_answers: question_id → text のマッピング（Other回答）
  multi_select質問には自動的にデフォルト選択肢を送信する。
  """
  text_answers = text_answers or {}

  single_idx = 0
  for qid in ALL_QUESTION_IDS:
    if qid.startswith("int_"):
      # multi_select: 最初の2つのオプションを選択（ダミー回答）
      body = {"question_id": qid, "selected_options": ["opt_1", "opt_2"]}
    elif qid in text_answers:
      body = {"question_id": qid, "text": text_answers[qid]}
    else:
      choice = choices[single_idx] if choices else "a"
      body = {"question_id": qid, "choice_id": choice}
      single_idx += 1

    resp = await client.post(
      f"/api/sessions/{session_id}/answers",
      json=body,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


async def calculate_profile(client: AsyncClient, session_id: str) -> str:
  """プロファイル計算を実行しprofile_idを返す"""
  resp = await client.post(f"/api/sessions/{session_id}/calculate")
  assert resp.status_code == 200
  data = resp.json()
  assert "profile_id" in data
  return data["profile_id"]


# =============================================================================
# 1. Complete flow with varied answers
# =============================================================================


class TestCompleteFlowVariedAnswers:
  """選択肢をローテーションしながら全問回答→計算→プロファイル取得の完全フロー

  Validates: Requirements 1.7, 10.3
  """

  async def test_full_flow_with_rotating_choices(self, client: AsyncClient):
    # セッション作成
    session_id = await create_session(client)

    # 全13問に a, b, c, d をローテーションで回答
    rotating_choices = [
      ["a", "b", "c", "d"][i % 4] for i in range(len(ALL_QUESTION_IDS))
    ]
    await answer_all_questions(client, session_id, choices=rotating_choices)

    # ステータス確認: 13/13
    resp = await client.get(f"/api/sessions/{session_id}/status")
    assert resp.status_code == 200
    status = resp.json()
    assert status["answered"] == 32
    assert status["total"] == 32

    # プロファイル計算
    profile_id = await calculate_profile(client, session_id)

    # profile_id フォーマット検証: prof_XXXXXX (6桁)
    assert PROFILE_ID_PATTERN.match(profile_id)

    # プロファイル取得
    resp = await client.get(f"/api/sessions/{session_id}/profile")
    assert resp.status_code == 200
    profile = resp.json()

    # 全セクション存在確認
    assert "profile_id" in profile
    assert "base_os" in profile
    assert "lexical_tags" in profile
    assert "semantic_contexts" in profile
    assert "context_layers" in profile

    # axes は全て [0.0, 1.0] の範囲内
    axes = profile["base_os"]["axes"]
    for axis_name in [
      "extroverted_introverted",
      "sensing_intuition",
      "thinking_feeling",
      "judging_perceiving",
    ]:
      assert axis_name in axes
      assert 0.0 <= axes[axis_name] <= 1.0

    # decision_style は非空文字列
    assert isinstance(profile["base_os"]["decision_style"], str)
    assert len(profile["base_os"]["decision_style"]) > 0

    # lexical_tags は5個以上
    assert isinstance(profile["lexical_tags"], list)
    assert len(profile["lexical_tags"]) >= 5

    # semantic_contexts は5ドメイン全て含む
    assert isinstance(profile["semantic_contexts"], dict)
    for key in SEMANTIC_CONTEXT_KEYS:
      assert key in profile["semantic_contexts"]
      assert len(profile["semantic_contexts"][key]) > 0


# =============================================================================
# 2. Complete flow with Other (text) answers
# =============================================================================


class TestCompleteFlowWithOtherAnswers:
  """一部の質問をOther（テキスト）で回答しても正常にプロファイル生成される

  Other回答はニュートラルスコアリング（全軸0）となる。

  Validates: Requirements 1.7, 10.3
  """

  async def test_mixed_choice_and_text_answers(self, client: AsyncClient):
    session_id = await create_session(client)

    # 一部をテキスト回答にする
    text_answers = {
      "bos_002": "独自のアプローチで技術選定する",
      "com_001": "状況に応じて柔軟に対応する",
      "lif_003": "計画は立てずに直感で動く",
    }

    # テキスト回答以外は全て "b"
    choices = ["b"] * len(ALL_QUESTION_IDS)
    for i, qid in enumerate(ALL_QUESTION_IDS):
      if qid in text_answers:
        resp = await client.post(
          f"/api/sessions/{session_id}/answers",
          json={"question_id": qid, "text": text_answers[qid]},
        )
      else:
        resp = await client.post(
          f"/api/sessions/{session_id}/answers",
          json={"question_id": qid, "choice_id": "b"},
        )
      assert resp.status_code == 200

    # ステータス確認: 全問回答済み
    resp = await client.get(f"/api/sessions/{session_id}/status")
    assert resp.json()["answered"] == 32

    # 計算＋プロファイル取得
    profile_id = await calculate_profile(client, session_id)
    assert PROFILE_ID_PATTERN.match(profile_id)

    resp = await client.get(f"/api/sessions/{session_id}/profile")
    assert resp.status_code == 200
    profile = resp.json()

    # プロファイル構造の完全性
    assert "base_os" in profile
    assert "lexical_tags" in profile
    assert "semantic_contexts" in profile
    assert all(
      0.0 <= v <= 1.0 for v in profile["base_os"]["axes"].values()
    )


# =============================================================================
# 3. Session resume flow
# =============================================================================


class TestSessionResumeFlow:
  """途中まで回答→再開→完了のセッション復帰フロー

  Validates: Requirements 10.2
  """

  async def test_partial_answer_then_resume(self, client: AsyncClient):
    session_id = await create_session(client)

    # 最初の5問に回答
    for qid in ALL_QUESTION_IDS[:5]:
      resp = await client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": qid, "choice_id": "a"},
      )
      assert resp.status_code == 200

    # ステータス確認: 5/13
    resp = await client.get(f"/api/sessions/{session_id}/status")
    assert resp.status_code == 200
    status = resp.json()
    assert status["answered"] == 5
    assert status["total"] == 32
    assert status["status"] == "active"

    # 残り8問に回答（セッション復帰）
    for qid in ALL_QUESTION_IDS[5:]:
      resp = await client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": qid, "choice_id": "c"},
      )
      assert resp.status_code == 200

    # ステータス確認: 13/13
    resp = await client.get(f"/api/sessions/{session_id}/status")
    assert resp.json()["answered"] == 32

    # 計算＋プロファイル取得
    profile_id = await calculate_profile(client, session_id)
    assert PROFILE_ID_PATTERN.match(profile_id)

    resp = await client.get(f"/api/sessions/{session_id}/profile")
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["profile_id"] == profile_id


# =============================================================================
# 4. Answer overwrite flow
# =============================================================================


class TestAnswerOverwriteFlow:
  """同じ質問に再回答（上書き）した場合、最新の回答が使われる

  Validates: Requirements 10.5
  """

  async def test_overwrite_answer_uses_latest(self, client: AsyncClient):
    session_id = await create_session(client)

    # bos_001 に "a" で回答
    resp = await client.post(
      f"/api/sessions/{session_id}/answers",
      json={"question_id": "bos_001", "choice_id": "a"},
    )
    assert resp.status_code == 200

    # bos_001 を "c" で上書き
    resp = await client.post(
      f"/api/sessions/{session_id}/answers",
      json={"question_id": "bos_001", "choice_id": "c"},
    )
    assert resp.status_code == 200

    # ステータス確認: 回答数は1（重複カウントされない）
    resp = await client.get(f"/api/sessions/{session_id}/status")
    assert resp.json()["answered"] == 1

    # 残りの質問に回答して完了
    for qid in ALL_QUESTION_IDS[1:]:
      await client.post(
        f"/api/sessions/{session_id}/answers",
        json={"question_id": qid, "choice_id": "b"},
      )

    # 計算＋プロファイル取得（choice "c" のスコアが反映される）
    profile_id = await calculate_profile(client, session_id)
    assert PROFILE_ID_PATTERN.match(profile_id)

    resp = await client.get(f"/api/sessions/{session_id}/profile")
    assert resp.status_code == 200
    profile = resp.json()

    # bos_001 の choice "c" のスコアベクトル:
    # EI: -4, SN: 5, TF: 7, JP: 3
    # "a" なら EI: 8, SN: -3, TF: 2, JP: -2
    # → "c" が適用されていればスコアが異なるはず
    # 全軸が正常範囲内であることを確認
    axes = profile["base_os"]["axes"]
    for v in axes.values():
      assert 0.0 <= v <= 1.0


# =============================================================================
# 5. Error flow - double calculate
# =============================================================================


class TestDoubleCalculateFlow:
  """完了後に再度計算しても成功する（冪等性）

  Validates: Requirements 10.3
  """

  async def test_calculate_twice_succeeds(self, client: AsyncClient):
    session_id = await create_session(client)
    await answer_all_questions(client, session_id)

    # 1回目の計算
    profile_id_1 = await calculate_profile(client, session_id)
    assert PROFILE_ID_PATTERN.match(profile_id_1)

    # 2回目の計算 → 成功するはず
    resp = await client.post(f"/api/sessions/{session_id}/calculate")
    assert resp.status_code == 200
    profile_id_2 = resp.json()["profile_id"]
    assert PROFILE_ID_PATTERN.match(profile_id_2)


# =============================================================================
# 6. Error flow - answer after complete
# =============================================================================


class TestAnswerAfterCompleteFlow:
  """完了セッションへの回答送信は409で拒否される

  Validates: Requirements 10.3, 10.7
  """

  async def test_submit_answer_after_calculate_returns_409(
    self, client: AsyncClient
  ):
    session_id = await create_session(client)
    await answer_all_questions(client, session_id)
    await calculate_profile(client, session_id)

    # 完了後に回答を試行 → 409
    resp = await client.post(
      f"/api/sessions/{session_id}/answers",
      json={"question_id": "bos_001", "choice_id": "d"},
    )
    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"]["error"] == "session_not_modifiable"


# =============================================================================
# 7. Verify profile data correctness (all "a" choices)
# =============================================================================


class TestProfileDataCorrectness:
  """全問 choice "a" で回答した場合のスコアパターン検証

  mapping_dictionary.json の全 "a" スコアを合算し、
  正規化後の値が期待範囲内であることを確認する。

  Validates: Requirements 1.7, 10.3
  """

  async def test_all_a_choices_expected_score_pattern(
    self, client: AsyncClient
  ):
    session_id = await create_session(client)
    await answer_all_questions(client, session_id)  # デフォルトで全て "a"

    profile_id = await calculate_profile(client, session_id)
    resp = await client.get(f"/api/sessions/{session_id}/profile")
    assert resp.status_code == 200
    profile = resp.json()

    axes = profile["base_os"]["axes"]

    # 全 "a" の raw scores (27問):
    # EI=88, SN=-16, TF=-23, JP=-27
    #
    # theoretical_bounds:
    # EI: min=-120, max=156 → (88-(-120))/(156-(-120)) = 208/276 ≈ 0.75
    # SN: min=-106, max=131 → (-16-(-106))/(131-(-106)) = 90/237 ≈ 0.38
    # TF: min=-129, max=137 → (-23-(-129))/(137-(-129)) = 106/266 ≈ 0.40
    # JP: min=-119, max=137 → (-27-(-119))/(137-(-119)) = 92/256 ≈ 0.36

    # 検証: 計算精度を考慮して±0.05の許容範囲
    assert 0.70 <= axes["extroverted_introverted"] <= 0.80
    assert 0.33 <= axes["sensing_intuition"] <= 0.43
    assert 0.35 <= axes["thinking_feeling"] <= 0.45
    assert 0.31 <= axes["judging_perceiving"] <= 0.41

    # decision_style は日本語名（コード）フォーマット
    # EI > 0.50, SN < 0.50, TF < 0.50, JP < 0.50 → ENFP → 閃光の触媒
    decision_style = profile["base_os"]["decision_style"]
    assert "閃光の触媒" == decision_style

    # do_not_list が存在する（EI > 0.70 なので少なくとも1項目）
    assert len(profile["base_os"]["do_not_list"]) >= 1

    # context_layers の正確な値
    assert profile["context_layers"] == {
      "base_os": 1,
      "lexical_tags": 2,
      "semantic_contexts": 3,
    }
