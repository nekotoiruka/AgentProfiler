"""APIルートハンドラー: 6エンドポイントの実装

Endpoints:
  POST /api/sessions          → 新規セッション作成
  POST /api/sessions/{id}/answers  → 回答送信
  GET  /api/sessions/{id}/status   → ステータス取得
  GET  /api/questions          → 質問一覧（カテゴリ別）
  POST /api/sessions/{id}/calculate → スコア計算 + プロファイル生成
  GET  /api/sessions/{id}/profile   → プロファイルJSON取得
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
  get_mapping_loader,
  get_normalizer,
  get_profile_generator,
  get_question_loader,
  get_scoring_engine,
  get_session_manager,
  get_llm_client,
)
from app.core.normalizer import Normalizer
from app.core.profile_generator import ProfileGenerator
from app.core.scoring import MappingNotFoundError, ScoringEngine
from app.models.api import (
  AnswerSubmission,
  AnswerSubmittedResponse,
  CalculateResponse,
  ErrorResponse,
  QuestionsResponse,
  SessionCreatedResponse,
  SessionStatusResponse,
)
from app.models.profile import ProfileOutput
from app.models.scores import AxisScores
from app.services.data_loader import MappingDictionaryLoader, QuestionDataLoader
from app.services.session_manager import (
  SessionManager,
  SessionNotFoundError,
  SessionNotModifiableError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post(
  "/sessions",
  response_model=SessionCreatedResponse,
  status_code=201,
)
async def create_session(
  sm: SessionManager = Depends(get_session_manager),
) -> SessionCreatedResponse:
  """新規セッションを作成し、セッションIDを返す"""
  session_id = await sm.create_session()
  return SessionCreatedResponse(session_id=session_id)


@router.post(
  "/sessions/{session_id}/answers",
  response_model=AnswerSubmittedResponse,
  responses={
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
  },
)
async def submit_answer(
  session_id: str,
  body: AnswerSubmission,
  sm: SessionManager = Depends(get_session_manager),
) -> AnswerSubmittedResponse:
  """回答を送信する

  single_choice型: choice_id または text のいずれかが必須。text は最大500文字。
  multi_select型: selected_options が必須。
  """
  # バリデーション: choice_id, text, selected_options のいずれかが必要
  if body.choice_id is None and body.text is None and body.selected_options is None:
    raise HTTPException(
      status_code=422,
      detail={
        "error": "validation_error",
        "details": [
          {
            "field": "choice_id/text/selected_options",
            "message": "Either choice_id, text, or selected_options must be provided",
          }
        ],
      },
    )

  try:
    await sm.submit_answer(
      session_id=session_id,
      question_id=body.question_id,
      choice_id=body.choice_id,
      text=body.text,
      selected_options=body.selected_options,
      free_texts=body.free_texts,
    )
  except SessionNotFoundError:
    raise HTTPException(
      status_code=404,
      detail={
        "error": "session_not_found",
        "message": f"Session not found: {session_id}",
      },
    )
  except SessionNotModifiableError:
    raise HTTPException(
      status_code=409,
      detail={
        "error": "session_not_modifiable",
        "message": f"Session is not modifiable: {session_id}",
      },
    )

  return AnswerSubmittedResponse(status="accepted")


@router.get(
  "/sessions/{session_id}/status",
  response_model=SessionStatusResponse,
  responses={404: {"model": ErrorResponse}},
)
async def get_session_status(
  session_id: str,
  sm: SessionManager = Depends(get_session_manager),
  ql: QuestionDataLoader = Depends(get_question_loader),
) -> SessionStatusResponse:
  """セッションの進捗ステータスを取得する"""
  try:
    session = await sm.get_session(session_id)
  except SessionNotFoundError:
    raise HTTPException(
      status_code=404,
      detail={
        "error": "session_not_found",
        "message": f"Session not found: {session_id}",
      },
    )

  # 質問データからカテゴリ情報を取得
  categories = ql.get()
  total = sum(len(cat.questions) for cat in categories)
  answered = len(session.answers)

  # 現在のカテゴリを特定（次に未回答の質問があるカテゴリ）
  current_category: str | None = None
  for cat in categories:
    for question in cat.questions:
      if question.id not in session.answers:
        current_category = cat.name
        break
    if current_category is not None:
      break

  # 全問回答済みの場合は最後のカテゴリを表示
  if current_category is None and categories:
    current_category = categories[-1].name

  return SessionStatusResponse(
    session_id=session.session_id,
    status=session.status,
    answered=answered,
    total=total,
    category=current_category,
  )


@router.get(
  "/questions",
  response_model=QuestionsResponse,
)
async def get_questions(
  ql: QuestionDataLoader = Depends(get_question_loader),
) -> QuestionsResponse:
  """質問一覧をカテゴリ別に取得する"""
  categories = ql.get()
  return QuestionsResponse(categories=categories)


@router.post(
  "/sessions/{session_id}/calculate",
  response_model=CalculateResponse,
  responses={
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
  },
)
async def calculate_profile(
  session_id: str,
  sm: SessionManager = Depends(get_session_manager),
  se: ScoringEngine = Depends(get_scoring_engine),
  normalizer: Normalizer = Depends(get_normalizer),
  pg: ProfileGenerator = Depends(get_profile_generator),
  ql: QuestionDataLoader = Depends(get_question_loader),
) -> CalculateResponse:
  """スコア計算 + プロファイル生成を実行する

  手順:
  1. セッション取得（完了チェック）
  2. 全回答に対してスコアを累積（Other回答はLLMスコアリング）
  3. 正規化
  4. プロファイル生成
  5. セッションにスコアとprofile_idを保存
  """
  from app.services.llm_client import LLMClient

  # セッション取得
  try:
    session = await sm.get_session(session_id)
  except SessionNotFoundError:
    raise HTTPException(
      status_code=404,
      detail={
        "error": "session_not_found",
        "message": f"Session not found: {session_id}",
      },
    )

  # 完了チェック: 全問回答済みか確認
  is_complete = await sm.is_complete(session_id)
  if not is_complete:
    raise HTTPException(
      status_code=409,
      detail={
        "error": "session_incomplete",
        "message": f"Session has unanswered questions: {session_id}",
      },
    )

  # セッションを complete に遷移（まだ active の場合）
  if session.status == "active":
    await sm.mark_complete(session_id)

  # 質問マップを構築（LLMスコアリングで質問テキストが必要）
  categories = ql.get()
  question_map = {q.id: q for cat in categories for q in cat.questions}

  # LLMクライアント取得
  llm = get_llm_client()

  # スコア累積計算
  accumulated = AxisScores()
  for answer in session.answers.values():
    if answer.choice_id:
      # 定義済み選択肢 → マッピングスコア適用
      try:
        accumulated = se.apply_score(
          accumulated, answer.question_id, answer.choice_id
        )
      except MappingNotFoundError as e:
        logger.warning("Mapping not found during calculation: %s", e)
        accumulated = se.apply_neutral(accumulated)
    elif answer.text:
      # Other（自由記述） → LLMスコアリング
      question = question_map.get(answer.question_id)
      q_text = question.text if question else ""

      if llm and llm.enabled:
        result = llm.score_free_text(q_text, answer.text)
        if result:
          accumulated = se.apply_llm_scores(
            accumulated,
            result.extroverted_introverted,
            result.sensing_intuition,
            result.thinking_feeling,
            result.judging_perceiving,
          )
        else:
          # LLM失敗 → ニュートラルフォールバック
          accumulated = se.apply_neutral(accumulated)
      else:
        # LLM無効 → ニュートラルフォールバック
        accumulated = se.apply_neutral(accumulated)
    else:
      # multi_select回答等 → スコアリング対象外
      accumulated = se.apply_neutral(accumulated)

  # 正規化
  normalized = normalizer.normalize(accumulated)

  # プロファイル生成
  # 質問リストを取得してProfile Generatorに渡す
  categories = ql.get()
  all_questions = [q for cat in categories for q in cat.questions]
  answers_list = list(session.answers.values())

  profile = pg.generate(normalized, answers_list, all_questions)

  # セッションにスコアとprofile_idを保存
  await sm.update_scores(
    session_id=session_id,
    raw_scores=accumulated,
    normalized_scores=normalized,
    profile_id=profile.profile_id,
  )

  return CalculateResponse(profile_id=profile.profile_id)


@router.get(
  "/sessions/{session_id}/profile",
  response_model=ProfileOutput,
  responses={404: {"model": ErrorResponse}},
)
async def get_profile(
  session_id: str,
  sm: SessionManager = Depends(get_session_manager),
  pg: ProfileGenerator = Depends(get_profile_generator),
  ql: QuestionDataLoader = Depends(get_question_loader),
  normalizer: Normalizer = Depends(get_normalizer),
) -> ProfileOutput:
  """生成済みプロファイルJSONを取得する"""
  try:
    session = await sm.get_session(session_id)
  except SessionNotFoundError:
    raise HTTPException(
      status_code=404,
      detail={
        "error": "session_not_found",
        "message": f"Session not found: {session_id}",
      },
    )

  # プロファイル未生成チェック
  if session.profile_id is None or session.normalized_scores is None:
    raise HTTPException(
      status_code=404,
      detail={
        "error": "profile_not_available",
        "message": f"Profile has not been generated for session: {session_id}",
      },
    )

  # 保存済みスコアからプロファイルを再生成
  categories = ql.get()
  all_questions = [q for cat in categories for q in cat.questions]
  answers_list = list(session.answers.values())

  profile = pg.generate(
    session.normalized_scores, answers_list, all_questions
  )

  # profile_id は保存済みのものを使用（連番の一貫性のため）
  profile.profile_id = session.profile_id

  return profile
