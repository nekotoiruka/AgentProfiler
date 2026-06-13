"""Evolution 固有データモデル: API リクエスト/レスポンス定義"""

import re
from enum import Enum

from pydantic import BaseModel, Field

from app.models.profile import ProfileOutput


class ResultSource(str, Enum):
  """検索結果のソースタイプ"""

  LEXICAL = "lexical"
  SEMANTIC = "semantic"


class SearchResultItem(BaseModel):
  """ハイブリッド検索の個別結果アイテム

  content: マッチしたテキスト内容
  source: 検索ソース (lexical / semantic)
  score: 関連度スコア (0.0–1.0)
  domain: semantic 結果の場合のドメインキー（lexical 結果は None）
  """

  content: str
  source: ResultSource
  score: float = Field(..., ge=0.0, le=1.0)
  domain: str | None = None


class HybridSearchRequest(BaseModel):
  """ハイブリッド検索リクエスト

  query: 検索文字列
  profile_id: 対象プロファイル ID
  weight: lexical/semantic の重み (0.0 = lexical only, 1.0 = semantic only)
  """

  query: str = Field(..., min_length=1)
  profile_id: str = Field(..., pattern=r"^prof_\d{6}$")
  weight: float = Field(default=0.5, ge=0.0, le=1.0)


class HybridSearchResponse(BaseModel):
  """ハイブリッド検索レスポンス

  results: スコア降順でソートされた検索結果リスト
  """

  results: list[SearchResultItem] = Field(default_factory=list)


class InferRequest(BaseModel):
  """推論パイプラインリクエスト

  profile_id: 対象プロファイル ID
  utterance: ユーザー発話テキスト
  routing_hint: ルーティング制御ヒント (light / deep)
  thread_id: 会話スレッド ID（既存スレッド継続時に指定）
  """

  profile_id: str = Field(..., pattern=r"^prof_\d{6}$")
  utterance: str = Field(..., min_length=1)
  routing_hint: str | None = None
  thread_id: str | None = None


class InferResponse(BaseModel):
  """推論パイプラインレスポンス

  response: LLM が生成したレスポンステキスト
  complexity: ルーティングで使用された複雑度分類 (light / deep)
  cache_hit: セマンティックキャッシュヒットの有無
  """

  response: str
  complexity: str
  cache_hit: bool


class CacheStats(BaseModel):
  """セマンティックキャッシュ統計情報

  total_entries: キャッシュエントリ総数
  hit_rate: ヒット率 (0.0–1.0)
  avg_similarity: 平均類似度スコア
  """

  total_entries: int = Field(..., ge=0)
  hit_rate: float = Field(..., ge=0.0, le=1.0)
  avg_similarity: float = Field(..., ge=0.0, le=1.0)


class ProfileLoadResponse(BaseModel):
  """プロファイルロード成功レスポンス

  profile_id: ロードされたプロファイル ID
  timestamp: ロード完了時刻 (ISO 8601)
  status: ステータスメッセージ
  """

  profile_id: str = Field(..., pattern=r"^prof_\d{6}$")
  timestamp: str
  status: str



# --- Evolution プロファイルバリデーション ---

# profile_id パターン: "prof_" + 6桁ゼロパディング
_PROFILE_ID_PATTERN = re.compile(r"^prof_\d{6}$")


class ProfileValidationError(Exception):
  """Evolution プロファイルバリデーションエラー

  errors: バリデーション違反メッセージのリスト
  """

  def __init__(self, errors: list[str]):
    self.errors = errors
    super().__init__(f"Validation failed: {'; '.join(errors)}")


def validate_profile_for_evolution(profile: ProfileOutput) -> None:
  """ProfileOutput を Evolution システム用に厳密バリデーションする

  Pydantic レベルの制約に加え、Evolution 固有の追加検証を実施する。
  全ルールを一括チェックし、違反があればまとめて例外を送出する。

  Raises:
    ProfileValidationError: バリデーション違反が1件以上ある場合
  """
  errors: list[str] = []

  # 1. profile_id パターン検証 (prof_ + 6桁)
  if not _PROFILE_ID_PATTERN.match(profile.profile_id):
    errors.append(
      f"profile_id must match 'prof_' + 6 digits, got '{profile.profile_id}'"
    )

  # 2. base_os.axes 値域チェック (0.0–1.0)
  axes = profile.base_os.axes
  for axis_name in (
    "extroverted_introverted",
    "sensing_intuition",
    "thinking_feeling",
    "judging_perceiving",
  ):
    value = getattr(axes, axis_name)
    if not (0.0 <= value <= 1.0):
      errors.append(
        f"base_os.axes.{axis_name} must be 0.0–1.0, got {value}"
      )

  # 3. lexical_tags 件数チェック (5–500)
  tag_count = len(profile.lexical_tags)
  if tag_count < 5:
    errors.append(
      f"lexical_tags must have at least 5 entries, got {tag_count}"
    )
  elif tag_count > 500:
    errors.append(
      f"lexical_tags must have at most 500 entries, got {tag_count}"
    )

  # 4. semantic_contexts 文字数チェック (各 10–2000 文字)
  for domain, text in profile.semantic_contexts.items():
    text_len = len(text)
    if text_len < 10:
      errors.append(
        f"semantic_contexts['{domain}'] is shorter than 10 characters ({text_len})"
      )
    elif text_len > 2000:
      errors.append(
        f"semantic_contexts['{domain}'] exceeds 2000 characters ({text_len})"
      )

  # 5. do_not_list 件数チェック (1–4)
  dnl_count = len(profile.base_os.do_not_list)
  if dnl_count < 1:
    errors.append(
      f"do_not_list must have at least 1 entry, got {dnl_count}"
    )
  elif dnl_count > 4:
    errors.append(
      f"do_not_list must have at most 4 entries, got {dnl_count}"
    )

  # 6. context_layers バリデーション (base_os=1, lexical_tags=2, semantic_contexts=3)
  layers = profile.context_layers
  if layers.base_os != 1:
    errors.append(
      f"context_layers.base_os must be 1, got {layers.base_os}"
    )
  if layers.lexical_tags != 2:
    errors.append(
      f"context_layers.lexical_tags must be 2, got {layers.lexical_tags}"
    )
  if layers.semantic_contexts != 3:
    errors.append(
      f"context_layers.semantic_contexts must be 3, got {layers.semantic_contexts}"
    )

  if errors:
    raise ProfileValidationError(errors)
