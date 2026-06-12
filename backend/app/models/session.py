"""セッション関連モデル: 回答およびセッション状態管理"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.scores import AxisScores, NormalizedScores


class Answer(BaseModel):
  """個別回答データ

  single_choice型: choice_id または text を設定。
  multi_select型: selected_options を設定。
  """

  question_id: str
  choice_id: str | None = None
  text: str | None = None
  selected_options: list[str] | None = None
  """multi_select型の回答: 選択されたoption_idのリスト"""
  free_texts: list[str] | None = None
  """multi_select型の自由入力テキスト"""
  submitted_at: datetime = Field(default_factory=datetime.now)


class Session(BaseModel):
  """サーベイセッション

  セッションのライフサイクル:
  active → complete（全問回答完了時）
  active → expired（30日間非アクティブ時）
  """

  session_id: str
  created_at: datetime = Field(default_factory=datetime.now)
  updated_at: datetime = Field(default_factory=datetime.now)
  status: Literal["active", "complete", "expired"] = "active"
  answers: dict[str, Answer] = Field(default_factory=dict)  # question_id -> Answer
  raw_scores: AxisScores | None = None
  normalized_scores: NormalizedScores | None = None
  profile_id: str | None = None
