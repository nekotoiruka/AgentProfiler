"""データローダー

Mapping Dictionary と Question Data のロード・バリデーション・ホットリロードを管理。

Mapping Dictionary:
  起動時にJSONファイルをロードし、Pydanticモデルでバリデーション。
  不正エントリはログ出力して除外し、有効エントリのみ使用する。
  ファイル不在/パース不能時は起動失敗（例外送出）。

Question Data:
  YAMLファイルからカテゴリ順にロードし、必須フィールド・文字数制限・
  選択肢数・重複ID・Mapping整合性・2軸活性化を検証。
  不正質問はログ出力して除外。

共通:
  リクエスト毎にファイル変更時刻を検知し、変更があれば再ロード。
"""

import json
import logging
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.models.mapping import (
  MappingDictionary,
  MappingEntry,
  MappingMetadata,
)
from app.models.question import Category, Choice, Question

logger = logging.getLogger(__name__)


class MappingDictionaryLoadError(Exception):
  """Mapping Dictionary のロード失敗を表す例外"""

  pass


class MappingDictionaryLoader:
  """Mapping Dictionary のロードとホットリロードを管理するクラス

  - 起動時に load() でファイルをロード・バリデーション
  - get() で現在のキャッシュを返すか、ファイル変更時は再ロード
  """

  def __init__(self, file_path: Path) -> None:
    self._file_path = file_path
    self._cached: MappingDictionary | None = None
    self._last_mtime: float = 0.0

  def load(self) -> MappingDictionary:
    """JSONファイルをロードしてバリデーション済みMappingDictionaryを返す

    Raises:
      MappingDictionaryLoadError: ファイル不在またはJSON全体のパースに失敗した場合
    """
    # ファイル存在チェック
    if not self._file_path.exists():
      msg = f"Mapping Dictionary file not found: {self._file_path}"
      logger.error(msg)
      raise MappingDictionaryLoadError(msg)

    # JSONパース
    try:
      raw_text = self._file_path.read_text(encoding="utf-8")
      raw_data = json.loads(raw_text)
    except (json.JSONDecodeError, OSError) as e:
      msg = f"Failed to parse Mapping Dictionary: {self._file_path} - {e}"
      logger.error(msg)
      raise MappingDictionaryLoadError(msg) from e

    # トップレベル構造: metadata は必須（パース不能として扱う）
    if not isinstance(raw_data, dict):
      msg = f"Mapping Dictionary must be a JSON object: {self._file_path}"
      logger.error(msg)
      raise MappingDictionaryLoadError(msg)

    # metadata バリデーション
    try:
      metadata = MappingMetadata(**raw_data.get("metadata", {}))
    except (ValidationError, TypeError) as e:
      msg = f"Invalid metadata in Mapping Dictionary: {self._file_path} - {e}"
      logger.error(msg)
      raise MappingDictionaryLoadError(msg) from e

    # 個別エントリのバリデーション: 不正エントリは除外
    raw_mappings = raw_data.get("mappings", [])
    if not isinstance(raw_mappings, list):
      msg = f"'mappings' must be a list in Mapping Dictionary: {self._file_path}"
      logger.error(msg)
      raise MappingDictionaryLoadError(msg)

    valid_entries: list[MappingEntry] = []
    for i, entry_data in enumerate(raw_mappings):
      try:
        entry = MappingEntry(**entry_data)
        valid_entries.append(entry)
      except (ValidationError, TypeError) as e:
        # 不正エントリはログ出力して除外
        logger.warning(
          "Skipping invalid mapping entry at index %d: %s - %s",
          i,
          entry_data,
          e,
        )

    logger.info(
      "Loaded Mapping Dictionary: %d valid entries, %d skipped from %s",
      len(valid_entries),
      len(raw_mappings) - len(valid_entries),
      self._file_path,
    )

    # キャッシュ更新
    result = MappingDictionary(metadata=metadata, mappings=valid_entries)
    self._cached = result
    self._last_mtime = os.path.getmtime(self._file_path)
    return result

  def get(self) -> MappingDictionary:
    """キャッシュ済みMappingDictionaryを返す。ファイル変更時は再ロード。

    初回呼び出し時（load未実行）は自動的にloadを実行する。

    Raises:
      MappingDictionaryLoadError: ロードに失敗した場合
    """
    if self._cached is None:
      return self.load()

    # ファイル変更検知: mtime比較でホットリロード
    try:
      current_mtime = os.path.getmtime(self._file_path)
    except OSError as e:
      # ファイルが消えた場合はキャッシュを維持しつつ警告
      logger.warning(
        "Cannot stat Mapping Dictionary file: %s - %s. Using cached data.",
        self._file_path,
        e,
      )
      return self._cached

    if current_mtime != self._last_mtime:
      logger.info(
        "Mapping Dictionary file changed (mtime: %f -> %f), reloading.",
        self._last_mtime,
        current_mtime,
      )
      return self.load()

    return self._cached


class QuestionDataLoadError(Exception):
  """Question Data のロード失敗を表す例外"""

  pass


class QuestionDataLoader:
  """Question Data のロードとバリデーション・ホットリロードを管理するクラス

  - load() でYAMLファイルからカテゴリ順に質問をロード・バリデーション
  - get() でキャッシュを返すか、ファイル変更時に再ロード
  - Mapping Dictionary との整合性チェックを実施
  """

  def __init__(self, file_path: Path, mapping_loader: MappingDictionaryLoader) -> None:
    self._file_path = file_path
    self._mapping_loader = mapping_loader
    self._cached: list[Category] | None = None
    self._last_mtime: float = 0.0

  def load(self) -> list[Category]:
    """YAMLファイルをロードしてバリデーション済みCategory一覧を返す

    バリデーション:
      1. 必須フィールド（id, text, category_id, 4 choices, source_reference）
      2. text最大200文字、choice label最大100文字
      3. 正確に4選択肢
      4. 重複質問IDの排除
      5. Mapping Dictionaryとの整合性（全4選択肢のマッピング存在）
      6. 各質問が2軸以上を活性化

    Raises:
      QuestionDataLoadError: ファイル不在またはYAMLパースに失敗した場合
    """
    # ファイル存在チェック
    if not self._file_path.exists():
      msg = f"Question data file not found: {self._file_path}"
      logger.error(msg)
      raise QuestionDataLoadError(msg)

    # YAMLパース
    try:
      raw_text = self._file_path.read_text(encoding="utf-8")
      raw_data = yaml.safe_load(raw_text)
    except (yaml.YAMLError, OSError) as e:
      msg = f"Failed to parse question data: {self._file_path} - {e}"
      logger.error(msg)
      raise QuestionDataLoadError(msg) from e

    # トップレベル構造チェック
    if not isinstance(raw_data, dict):
      msg = f"Question data must be a YAML mapping: {self._file_path}"
      logger.error(msg)
      raise QuestionDataLoadError(msg)

    raw_categories = raw_data.get("categories")
    if not isinstance(raw_categories, list):
      msg = f"'categories' must be a list in question data: {self._file_path}"
      logger.error(msg)
      raise QuestionDataLoadError(msg)

    # Mapping Dictionary を取得してルックアップ構築
    mapping_dict = self._mapping_loader.get()
    mapping_lookup = self._build_mapping_lookup(mapping_dict)

    # カテゴリ・質問のバリデーション
    seen_question_ids: set[str] = set()
    categories: list[Category] = []

    for cat_data in raw_categories:
      category = self._validate_category(
        cat_data, mapping_lookup, seen_question_ids
      )
      if category is not None:
        categories.append(category)

    # カテゴリをorder順にソート
    categories.sort(key=lambda c: c.order)

    logger.info(
      "Loaded question data: %d categories, %d total questions from %s",
      len(categories),
      sum(len(c.questions) for c in categories),
      self._file_path,
    )

    # キャッシュ更新
    self._cached = categories
    self._last_mtime = os.path.getmtime(self._file_path)
    return categories

  def get(self) -> list[Category]:
    """キャッシュ済みCategory一覧を返す。ファイル変更時は再ロード。

    初回呼び出し時（load未実行）は自動的にloadを実行する。

    Raises:
      QuestionDataLoadError: ロードに失敗した場合
    """
    if self._cached is None:
      return self.load()

    # ファイル変更検知: mtime比較でホットリロード
    try:
      current_mtime = os.path.getmtime(self._file_path)
    except OSError as e:
      logger.warning(
        "Cannot stat question data file: %s - %s. Using cached data.",
        self._file_path,
        e,
      )
      return self._cached

    if current_mtime != self._last_mtime:
      logger.info(
        "Question data file changed (mtime: %f -> %f), reloading.",
        self._last_mtime,
        current_mtime,
      )
      return self.load()

    return self._cached

  def _build_mapping_lookup(
    self, mapping_dict: MappingDictionary
  ) -> dict[tuple[str, str], list[int]]:
    """Mapping Dictionary から (question_id, choice_id) → 4軸スコアリスト を構築"""
    lookup: dict[tuple[str, str], list[int]] = {}
    for entry in mapping_dict.mappings:
      scores = [
        entry.scores.extroverted_introverted,
        entry.scores.sensing_intuition,
        entry.scores.thinking_feeling,
        entry.scores.judging_perceiving,
      ]
      lookup[(entry.question_id, entry.choice_id)] = scores
    return lookup

  def _validate_category(
    self,
    cat_data: dict,
    mapping_lookup: dict[tuple[str, str], list[int]],
    seen_question_ids: set[str],
  ) -> Category | None:
    """カテゴリデータをバリデーションし、Categoryモデルを返す"""
    if not isinstance(cat_data, dict):
      logger.warning("Skipping non-dict category entry: %s", cat_data)
      return None

    cat_id = cat_data.get("id")
    cat_name = cat_data.get("name")
    cat_order = cat_data.get("order")

    if not cat_id or not cat_name or cat_order is None:
      logger.warning(
        "Skipping category with missing required fields: %s", cat_data
      )
      return None

    raw_questions = cat_data.get("questions", [])
    if not isinstance(raw_questions, list):
      logger.warning(
        "Category '%s' has invalid 'questions' field, skipping", cat_id
      )
      return None

    valid_questions: list[Question] = []
    for q_data in raw_questions:
      question = self._validate_question(
        q_data, cat_id, mapping_lookup, seen_question_ids
      )
      if question is not None:
        valid_questions.append(question)

    return Category(
      id=cat_id,
      name=cat_name,
      order=cat_order,
      questions=valid_questions,
    )

  def _validate_question(
    self,
    q_data: dict,
    category_id: str,
    mapping_lookup: dict[tuple[str, str], list[int]],
    seen_question_ids: set[str],
  ) -> Question | None:
    """質問データをバリデーションし、Questionモデルを返す

    検証項目:
      - 必須フィールド存在
      - Pydanticモデルバリデーション（文字数制限、選択肢数）
      - 重複IDチェック
      - Mapping Dictionary整合性（single_choice型のみ）
      - 2軸以上の活性化（single_choice型のみ）
    """
    if not isinstance(q_data, dict):
      logger.warning("Skipping non-dict question entry: %s", q_data)
      return None

    q_id = q_data.get("id")
    q_type = q_data.get("question_type", "single_choice")

    # 重複IDチェック
    if q_id and q_id in seen_question_ids:
      logger.warning(
        "Skipping duplicate question ID: %s", q_id
      )
      return None

    # multi_select 型の場合は別ルートでバリデーション
    if q_type == "multi_select":
      return self._validate_multi_select_question(q_data, category_id, seen_question_ids)

    # Pydanticモデルでバリデーション（必須フィールド・文字数・選択肢数）
    try:
      question = Question(
        id=q_data.get("id", ""),
        text=q_data.get("text", ""),
        category_id=q_data.get("category_id", category_id),
        question_type="single_choice",
        choices=[
          Choice(id=c.get("id", ""), label=c.get("label", ""))
          for c in q_data.get("choices", [])
          if isinstance(c, dict)
        ],
        source_reference=q_data.get("source_reference", ""),
      )
    except (ValidationError, TypeError, AttributeError) as e:
      logger.warning(
        "Skipping invalid question entry '%s': %s", q_id or "unknown", e
      )
      return None

    # 空の必須フィールドチェック
    if not question.id or not question.text:
      logger.warning(
        "Skipping question with empty required fields: %s", question.id
      )
      return None

    # single_choice型: 正確に4選択肢が必要
    if len(question.choices) != 4:
      logger.warning(
        "Skipping question '%s': requires exactly 4 choices, got %d",
        question.id,
        len(question.choices),
      )
      return None

    # Mapping Dictionary整合性チェック: マッピングが存在する質問のみスコアリング対象
    has_mapping = all(
      (question.id, choice.id) in mapping_lookup
      for choice in question.choices
    )

    if has_mapping:
      # スコアリング対象質問: source_reference必須 + 2軸以上活性化チェック
      if not question.source_reference:
        logger.warning(
          "Skipping question '%s': missing source_reference", question.id
        )
        return None

      # 2軸以上の活性化チェック
      activated_axes = set()
      for choice in question.choices:
        scores = mapping_lookup[(question.id, choice.id)]
        for axis_idx, score in enumerate(scores):
          if score != 0:
            activated_axes.add(axis_idx)

      if len(activated_axes) < 2:
        logger.warning(
          "Skipping question '%s': activates only %d axis (requires >= 2)",
          question.id,
          len(activated_axes),
        )
        return None
    # else: マッピングなし = persona/tone/values等の直接マッピング質問 → スキップしない

    # すべてパス → 登録
    seen_question_ids.add(question.id)
    return question

  def _validate_multi_select_question(
    self,
    q_data: dict,
    category_id: str,
    seen_question_ids: set[str],
  ) -> Question | None:
    """multi_select型質問のバリデーション

    検証項目:
      - 必須フィールド（id, text）
      - options が1件以上存在
      - 各optionにid, label, tagsが存在
    """
    from app.models.question import MultiSelectOption

    q_id = q_data.get("id", "")
    q_text = q_data.get("text", "")

    if not q_id or not q_text:
      logger.warning(
        "Skipping multi_select question with empty id or text: %s", q_data
      )
      return None

    raw_options = q_data.get("options", [])
    if not isinstance(raw_options, list) or len(raw_options) == 0:
      logger.warning(
        "Skipping multi_select question '%s': no options defined", q_id
      )
      return None

    # options のバリデーション
    valid_options: list[MultiSelectOption] = []
    for opt_data in raw_options:
      if not isinstance(opt_data, dict):
        continue
      try:
        option = MultiSelectOption(
          id=opt_data.get("id", ""),
          label=opt_data.get("label", ""),
          tags=opt_data.get("tags", []),
        )
        if option.id and option.label:
          valid_options.append(option)
      except (ValidationError, TypeError):
        continue

    if len(valid_options) == 0:
      logger.warning(
        "Skipping multi_select question '%s': no valid options", q_id
      )
      return None

    question = Question(
      id=q_id,
      text=q_text,
      category_id=q_data.get("category_id", category_id),
      question_type="multi_select",
      options=valid_options,
      min_select=q_data.get("min_select", 0),
      max_select=q_data.get("max_select", 0),
      source_reference=q_data.get("source_reference", ""),
    )

    seen_question_ids.add(question.id)
    return question
