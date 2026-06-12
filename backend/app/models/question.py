"""質問データモデル: 選択肢・質問・カテゴリ"""

from typing import Literal

from pydantic import BaseModel, Field


class Choice(BaseModel):
  """質問の選択肢（4択のうちの1つ）"""

  id: str
  label: str = Field(..., max_length=100)


class MultiSelectOption(BaseModel):
  """チェックボックス型質問の選択肢"""

  id: str
  label: str = Field(..., max_length=100)
  tags: list[str] = Field(default_factory=list)
  """選択時にlexical_tagsに追加されるタグ群"""


class Question(BaseModel):
  """個別質問定義

  question_type:
    - "single_choice": 従来の4択+Other（スコアリング対象）
    - "multi_select": チェックボックス複数選択（タグ収集用、スコアリング非対象）

  single_choice 型: choices フィールドを使用
  multi_select 型: options フィールドを使用
  """

  id: str
  text: str = Field(..., max_length=200)
  category_id: str
  question_type: Literal["single_choice", "multi_select"] = "single_choice"
  choices: list[Choice] = Field(default_factory=list)
  """single_choice型の選択肢（4つ固定）"""
  options: list[MultiSelectOption] = Field(default_factory=list)
  """multi_select型の選択肢（5〜15個、複数選択可）"""
  min_select: int = 0
  """multi_select型: 最低選択数（0=制限なし）"""
  max_select: int = 0
  """multi_select型: 最大選択数（0=制限なし）"""
  source_reference: str = ""


class Category(BaseModel):
  """質問カテゴリ

  Business OS → Communication → Lifestyle/Hobbies → Interests & Preferences の
  固定順序で質問をグルーピングする。
  """

  id: str
  name: str
  order: int
  questions: list[Question] = Field(default_factory=list)

