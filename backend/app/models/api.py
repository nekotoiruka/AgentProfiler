"""APIリクエスト/レスポンススキーマ"""

from pydantic import BaseModel, Field

from app.models.profile import ProfileOutput
from app.models.question import Category


# --- Request Models ---

class AnswerSubmission(BaseModel):
  """回答送信リクエスト

  single_choice型:
    predefined choice: question_id + choice_id
    Other（自由記述）: question_id + text

  multi_select型:
    question_id + selected_options (選択されたoption_idのリスト)
  """

  question_id: str
  choice_id: str | None = None
  text: str | None = Field(None, max_length=500)
  selected_options: list[str] | None = None
  """multi_select型の回答: 選択されたoption_idのリスト"""
  free_texts: list[str] | None = None
  """multi_select型の自由入力テキスト（各最大100文字）"""


# --- Response Models ---

class SessionCreatedResponse(BaseModel):
  """セッション作成レスポンス"""

  session_id: str


class AnswerSubmittedResponse(BaseModel):
  """回答送信成功レスポンス"""

  status: str = "accepted"


class SessionStatusResponse(BaseModel):
  """セッション状態レスポンス"""

  session_id: str
  status: str
  answered: int
  total: int
  category: str | None = None


class QuestionsResponse(BaseModel):
  """質問一覧レスポンス"""

  categories: list[Category]


class CalculateResponse(BaseModel):
  """スコア計算＋プロファイル生成レスポンス"""

  profile_id: str


class ProfileResponse(ProfileOutput):
  """プロファイル取得レスポンス（ProfileOutputをそのまま返す）"""

  pass


class ErrorResponse(BaseModel):
  """エラーレスポンス"""

  error: str
  message: str


class ValidationErrorDetail(BaseModel):
  """バリデーションエラー詳細"""

  field: str
  message: str


class ValidationErrorResponse(BaseModel):
  """バリデーションエラーレスポンス（422）"""

  error: str = "validation_error"
  details: list[ValidationErrorDetail]
