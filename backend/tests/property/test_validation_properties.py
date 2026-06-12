"""データバリデーション プロパティベーステスト

Feature: agent-profiler
Validates: Requirements 3.2, 3.7, 4.2, 4.4, 9.5, 9.6, 9.7
"""

import json
import tempfile
from pathlib import Path

import yaml
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models.mapping import (
  MappingDictionary,
  MappingEntry,
  MappingMetadata,
  MappingScores,
  TheoreticalBounds,
  AxisBound,
)
from app.models.question import Category, Choice, Question
from app.services.data_loader import (
  MappingDictionaryLoader,
  QuestionDataLoader,
)


# --- 共通ヘルパー ---

def _default_metadata() -> MappingMetadata:
  """テスト用デフォルトメタデータ"""
  return MappingMetadata(
    version="1.0",
    theoretical_bounds=TheoreticalBounds(
      extroverted_introverted=AxisBound(min=-30, max=30),
      sensing_intuition=AxisBound(min=-25, max=25),
      thinking_feeling=AxisBound(min=-28, max=28),
      judging_perceiving=AxisBound(min=-26, max=26),
    ),
  )


def _build_mapping_dictionary(
  entries: list[MappingEntry],
) -> MappingDictionary:
  """テスト用 MappingDictionary を構築"""
  return MappingDictionary(
    metadata=_default_metadata(),
    mappings=entries,
  )


def _create_mapping_file(mapping_dict: dict, tmp_dir: Path) -> Path:
  """一時ディレクトリにマッピングJSONファイルを作成"""
  file_path = tmp_dir / "mapping_dictionary.json"
  file_path.write_text(json.dumps(mapping_dict), encoding="utf-8")
  return file_path


def _create_questions_file(questions_data: dict, tmp_dir: Path) -> Path:
  """一時ディレクトリに質問YAMLファイルを作成"""
  file_path = tmp_dir / "questions.yaml"
  file_path.write_text(yaml.dump(questions_data, allow_unicode=True), encoding="utf-8")
  return file_path


# --- Hypothesis ストラテジー ---

# 有効な軸スコア (-10 〜 +10)
_valid_axis_score_st = st.integers(min_value=-10, max_value=10)

# 範囲外の軸スコア
_out_of_range_score_st = st.one_of(
  st.integers(min_value=-1000, max_value=-11),
  st.integers(min_value=11, max_value=1000),
)

# 有効な MappingScores 辞書
_valid_scores_dict_st = st.fixed_dictionaries({
  "extroverted_introverted": _valid_axis_score_st,
  "sensing_intuition": _valid_axis_score_st,
  "thinking_feeling": _valid_axis_score_st,
  "judging_perceiving": _valid_axis_score_st,
})

# 有効な question_id / choice_id
_question_id_st = st.from_regex(r"[a-z]{2,4}_\d{3}", fullmatch=True)
_choice_id_st = st.sampled_from(["a", "b", "c", "d"])

# カテゴリID・名前
_category_ids = ["business_os", "communication", "lifestyle"]
_category_names = ["Business OS", "Communication", "Lifestyle/Hobbies"]
_category_orders = [1, 2, 3]

# 有効な短い文字列ストラテジー（質問テキスト用）
_short_text_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
  min_size=1,
  max_size=200,
)

# 有効なラベルストラテジー（選択肢ラベル用）
_label_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
  min_size=1,
  max_size=100,
)


# =============================================================================
# Property 3: Mapping entry schema validation
# Feature: agent-profiler, Property 3: Mapping entry schema validation
# =============================================================================


@settings(max_examples=200)
@given(
  question_id=_question_id_st,
  choice_id=_choice_id_st,
  scores=_valid_scores_dict_st,
)
def test_valid_mapping_entry_accepted(
  question_id: str, choice_id: str, scores: dict
) -> None:
  """有効なマッピングエントリ（全フィールド存在、スコア範囲内）は
  Pydanticバリデーションを通過する。

  **Validates: Requirements 3.2, 4.2**
  """
  # 有効なエントリは例外なく構築可能
  entry = MappingEntry(
    question_id=question_id,
    choice_id=choice_id,
    scores=MappingScores(**scores),
  )

  # 全フィールドが正しく設定される
  assert entry.question_id == question_id
  assert entry.choice_id == choice_id
  assert entry.scores.extroverted_introverted == scores["extroverted_introverted"]
  assert entry.scores.sensing_intuition == scores["sensing_intuition"]
  assert entry.scores.thinking_feeling == scores["thinking_feeling"]
  assert entry.scores.judging_perceiving == scores["judging_perceiving"]


@settings(max_examples=200)
@given(
  question_id=_question_id_st,
  choice_id=_choice_id_st,
  valid_scores=_valid_scores_dict_st,
  out_of_range=_out_of_range_score_st,
  axis_to_break=st.sampled_from([
    "extroverted_introverted",
    "sensing_intuition",
    "thinking_feeling",
    "judging_perceiving",
  ]),
)
def test_out_of_range_score_rejected(
  question_id: str,
  choice_id: str,
  valid_scores: dict,
  out_of_range: int,
  axis_to_break: str,
) -> None:
  """範囲外スコア値（-10〜+10 外）を含むエントリはバリデーションで拒否される。

  **Validates: Requirements 3.2, 4.4**
  """
  # 1軸を範囲外値に差し替え
  invalid_scores = {**valid_scores, axis_to_break: out_of_range}

  try:
    MappingScores(**invalid_scores)
    # ここに到達してはならない
    assert False, f"Score {out_of_range} for {axis_to_break} should be rejected"
  except ValidationError:
    pass  # 期待通り拒否


@settings(max_examples=200)
@given(
  question_id=_question_id_st,
  choice_id=_choice_id_st,
  valid_scores=_valid_scores_dict_st,
  axis_to_remove=st.sampled_from([
    "extroverted_introverted",
    "sensing_intuition",
    "thinking_feeling",
    "judging_perceiving",
  ]),
)
def test_missing_axis_rejected(
  question_id: str,
  choice_id: str,
  valid_scores: dict,
  axis_to_remove: str,
) -> None:
  """軸が欠損しているエントリはバリデーションで拒否される。

  **Validates: Requirements 3.7, 4.4**
  """
  # 1軸を削除
  incomplete_scores = {k: v for k, v in valid_scores.items() if k != axis_to_remove}

  try:
    MappingScores(**incomplete_scores)
    assert False, f"Missing axis '{axis_to_remove}' should be rejected"
  except ValidationError:
    pass  # 期待通り拒否


# =============================================================================
# Property 14: Question ordering invariant
# Feature: agent-profiler, Property 14: Question ordering invariant
# =============================================================================


# カテゴリ順序のシャッフル用ストラテジー
_category_permutation_st = st.permutations(list(range(3)))


@settings(max_examples=200)
@given(category_order=_category_permutation_st)
def test_question_ordering_by_category(category_order: list[int]) -> None:
  """任意の順序でカテゴリデータを与えても、ロード後は固定カテゴリ順
  (Business OS → Communication → Lifestyle/Hobbies) でソートされる。

  **Validates: Requirements 1.5, 9.3**
  """
  # カテゴリ定義（固定順序: order=1, 2, 3）
  category_defs = [
    {"id": "business_os", "name": "Business OS", "order": 1},
    {"id": "communication", "name": "Communication", "order": 2},
    {"id": "lifestyle", "name": "Lifestyle/Hobbies", "order": 3},
  ]

  # 2軸以上活性化するスコアパターン
  scores_pattern = {
    "extroverted_introverted": 5,
    "sensing_intuition": -3,
    "thinking_feeling": 2,
    "judging_perceiving": 0,
  }

  # 質問IDプレフィックスとカテゴリの対応
  prefixes = ["bos", "com", "lif"]

  # マッピングエントリを構築
  mapping_entries = []
  for cat_idx in range(3):
    prefix = prefixes[cat_idx]
    for q_num in range(1, 4):
      q_id = f"{prefix}_{q_num:03d}"
      for c_id in ["a", "b", "c", "d"]:
        # 少なくとも2軸を活性化するスコアを各選択肢に設定
        mapping_entries.append({
          "question_id": q_id,
          "choice_id": c_id,
          "scores": scores_pattern,
        })

  # 質問データをカテゴリ順序をシャッフルして構築
  shuffled_categories = [category_defs[i] for i in category_order]
  categories_data = []

  for cat_def in shuffled_categories:
    cat_id = cat_def["id"]
    prefix = prefixes[_category_ids.index(cat_id)]
    questions = []
    for q_num in range(1, 4):
      q_id = f"{prefix}_{q_num:03d}"
      questions.append({
        "id": q_id,
        "text": f"質問テスト {q_id}",
        "category_id": cat_id,
        "choices": [
          {"id": c, "label": f"選択肢 {c} for {q_id}"}
          for c in ["a", "b", "c", "d"]
        ],
        "source_reference": "test_source",
      })
    categories_data.append({**cat_def, "questions": questions})

  # 一時ファイルにデータを書き込み、ロード
  with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    # マッピングファイル作成
    mapping_data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": mapping_entries,
    }
    mapping_file = _create_mapping_file(mapping_data, tmp_path)

    # 質問ファイル作成（シャッフル済みカテゴリ順）
    questions_data = {"categories": categories_data}
    questions_file = _create_questions_file(questions_data, tmp_path)

    # ローダーでロード
    mapping_loader = MappingDictionaryLoader(mapping_file)
    mapping_loader.load()
    question_loader = QuestionDataLoader(questions_file, mapping_loader)
    loaded_categories = question_loader.load()

  # カテゴリが固定順序でソートされていること
  assert len(loaded_categories) == 3
  assert loaded_categories[0].id == "business_os"
  assert loaded_categories[0].order == 1
  assert loaded_categories[1].id == "communication"
  assert loaded_categories[1].order == 2
  assert loaded_categories[2].id == "lifestyle"
  assert loaded_categories[2].order == 3

  # 各カテゴリ内の質問が連続していること
  # （あるカテゴリの質問が別カテゴリに紛れ込んでいない）
  for cat in loaded_categories:
    for question in cat.questions:
      assert question.category_id == cat.id


# =============================================================================
# Property 16: Question data validation
# Feature: agent-profiler, Property 16: Question data validation
# =============================================================================


def _make_valid_question_data(
  q_id: str, category_id: str
) -> dict:
  """有効な質問データを生成するヘルパー"""
  return {
    "id": q_id,
    "text": f"テスト質問 {q_id}",
    "category_id": category_id,
    "choices": [
      {"id": c, "label": f"選択肢{c}のラベル"}
      for c in ["a", "b", "c", "d"]
    ],
    "source_reference": "test_source_ref",
  }


def _make_mapping_entries_for_question(
  q_id: str, activate_axes: int = 4
) -> list[dict]:
  """指定質問のマッピングエントリを生成（activate_axes軸を活性化）"""
  # 4軸活性化パターン: 全軸に非ゼロスコア
  full_scores = [
    {"extroverted_introverted": 5, "sensing_intuition": -3, "thinking_feeling": 4, "judging_perceiving": -2},
    {"extroverted_introverted": -5, "sensing_intuition": 3, "thinking_feeling": -4, "judging_perceiving": 2},
    {"extroverted_introverted": 3, "sensing_intuition": 6, "thinking_feeling": -2, "judging_perceiving": 4},
    {"extroverted_introverted": -3, "sensing_intuition": -6, "thinking_feeling": 2, "judging_perceiving": -4},
  ]
  # 1軸のみ活性化パターン（2軸未満 → 拒否されるべき）
  single_axis_scores = [
    {"extroverted_introverted": 5, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 0},
    {"extroverted_introverted": -5, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 0},
    {"extroverted_introverted": 3, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 0},
    {"extroverted_introverted": -3, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 0},
  ]

  scores_list = full_scores if activate_axes >= 2 else single_axis_scores
  entries = []
  for i, c_id in enumerate(["a", "b", "c", "d"]):
    entries.append({
      "question_id": q_id,
      "choice_id": c_id,
      "scores": scores_list[i],
    })
  return entries


@settings(max_examples=200)
@given(
  text_length=st.integers(min_value=1, max_value=200),
  label_length=st.integers(min_value=1, max_value=100),
)
def test_valid_question_accepted(text_length: int, label_length: int) -> None:
  """全ての必須フィールドを持ち、文字数制限内の質問はバリデーションを通過する。

  **Validates: Requirements 9.5**
  """
  q_id = "val_001"
  cat_id = "business_os"

  # 有効な文字数のテキストとラベル
  text = "あ" * text_length
  label = "い" * label_length

  question_data = {
    "id": q_id,
    "text": text,
    "category_id": cat_id,
    "choices": [
      {"id": c, "label": label} for c in ["a", "b", "c", "d"]
    ],
    "source_reference": "test_ref",
  }

  mapping_entries = _make_mapping_entries_for_question(q_id)

  with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    mapping_data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": mapping_entries,
    }
    mapping_file = _create_mapping_file(mapping_data, tmp_path)

    questions_data = {
      "categories": [{
        "id": cat_id,
        "name": "Business OS",
        "order": 1,
        "questions": [question_data],
      }],
    }
    questions_file = _create_questions_file(questions_data, tmp_path)

    mapping_loader = MappingDictionaryLoader(mapping_file)
    mapping_loader.load()
    question_loader = QuestionDataLoader(questions_file, mapping_loader)
    loaded = question_loader.load()

  # 有効な質問は1件ロードされる
  assert len(loaded) == 1
  assert len(loaded[0].questions) == 1
  assert loaded[0].questions[0].id == q_id


@settings(max_examples=200)
@given(
  missing_field=st.sampled_from(["id", "text", "choices", "source_reference"]),
)
def test_missing_required_field_rejected(missing_field: str) -> None:
  """必須フィールドが欠損している質問は除外される。

  **Validates: Requirements 9.5**
  """
  q_id = "inv_001"
  cat_id = "business_os"

  question_data = _make_valid_question_data(q_id, cat_id)
  # 必須フィールドを削除
  del question_data[missing_field]

  mapping_entries = _make_mapping_entries_for_question(q_id)

  with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    mapping_data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": mapping_entries,
    }
    mapping_file = _create_mapping_file(mapping_data, tmp_path)

    questions_data = {
      "categories": [{
        "id": cat_id,
        "name": "Business OS",
        "order": 1,
        "questions": [question_data],
      }],
    }
    questions_file = _create_questions_file(questions_data, tmp_path)

    mapping_loader = MappingDictionaryLoader(mapping_file)
    mapping_loader.load()
    question_loader = QuestionDataLoader(questions_file, mapping_loader)
    loaded = question_loader.load()

  # 不正な質問は除外され、カテゴリ内に0件
  total_questions = sum(len(c.questions) for c in loaded)
  assert total_questions == 0


@settings(max_examples=200)
@given(data=st.data())
def test_duplicate_question_id_rejected(data) -> None:
  """重複した質問IDを持つエントリは2件目以降が除外される。

  **Validates: Requirements 9.5**
  """
  q_id = "dup_001"
  cat_id = "business_os"

  # 同一IDの質問を2件作成
  question1 = _make_valid_question_data(q_id, cat_id)
  question2 = _make_valid_question_data(q_id, cat_id)
  question2["text"] = "重複質問テスト"

  mapping_entries = _make_mapping_entries_for_question(q_id)

  with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    mapping_data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": mapping_entries,
    }
    mapping_file = _create_mapping_file(mapping_data, tmp_path)

    questions_data = {
      "categories": [{
        "id": cat_id,
        "name": "Business OS",
        "order": 1,
        "questions": [question1, question2],
      }],
    }
    questions_file = _create_questions_file(questions_data, tmp_path)

    mapping_loader = MappingDictionaryLoader(mapping_file)
    mapping_loader.load()
    question_loader = QuestionDataLoader(questions_file, mapping_loader)
    loaded = question_loader.load()

  # 重複は除外され、1件のみロードされる
  total_questions = sum(len(c.questions) for c in loaded)
  assert total_questions == 1
  assert loaded[0].questions[0].id == q_id


@settings(max_examples=200)
@given(
  num_valid=st.integers(min_value=1, max_value=3),
)
def test_question_without_mapping_rejected(num_valid: int) -> None:
  """対応するマッピングエントリがない質問は除外される。

  **Validates: Requirements 9.7**
  """
  cat_id = "business_os"

  # 有効な質問（マッピングあり）
  valid_questions = []
  all_mapping_entries = []
  for i in range(num_valid):
    q_id = f"map_{i + 1:03d}"
    valid_questions.append(_make_valid_question_data(q_id, cat_id))
    all_mapping_entries.extend(_make_mapping_entries_for_question(q_id))

  # 無効な質問（マッピングなし）
  orphan_q_id = "orphan_001"
  orphan_question = _make_valid_question_data(orphan_q_id, cat_id)
  # orphan_q_id のマッピングは作らない

  all_questions = valid_questions + [orphan_question]

  with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    mapping_data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": all_mapping_entries,
    }
    mapping_file = _create_mapping_file(mapping_data, tmp_path)

    questions_data = {
      "categories": [{
        "id": cat_id,
        "name": "Business OS",
        "order": 1,
        "questions": all_questions,
      }],
    }
    questions_file = _create_questions_file(questions_data, tmp_path)

    mapping_loader = MappingDictionaryLoader(mapping_file)
    mapping_loader.load()
    question_loader = QuestionDataLoader(questions_file, mapping_loader)
    loaded = question_loader.load()

  # 新ロジック: マッピングなし質問は直接マッピング質問として許可される
  total_questions = sum(len(c.questions) for c in loaded)
  assert total_questions == num_valid + 1  # orphan も含めて全てロードされる

  # orphan_q_id も含まれている（マッピングなし=直接マッピング質問扱い）
  all_loaded_ids = [
    q.id for cat in loaded for q in cat.questions
  ]
  assert orphan_q_id in all_loaded_ids


@settings(max_examples=200)
@given(data=st.data())
def test_question_fewer_than_2_axes_rejected(data) -> None:
  """2軸未満しか活性化しない質問は除外される。

  **Validates: Requirements 9.6**
  """
  q_id = "axis_001"
  cat_id = "business_os"

  question_data = _make_valid_question_data(q_id, cat_id)

  # 1軸のみ活性化するマッピング（拒否されるべき）
  mapping_entries = _make_mapping_entries_for_question(q_id, activate_axes=1)

  with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    mapping_data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": mapping_entries,
    }
    mapping_file = _create_mapping_file(mapping_data, tmp_path)

    questions_data = {
      "categories": [{
        "id": cat_id,
        "name": "Business OS",
        "order": 1,
        "questions": [question_data],
      }],
    }
    questions_file = _create_questions_file(questions_data, tmp_path)

    mapping_loader = MappingDictionaryLoader(mapping_file)
    mapping_loader.load()
    question_loader = QuestionDataLoader(questions_file, mapping_loader)
    loaded = question_loader.load()

  # 2軸未満の質問は除外される
  total_questions = sum(len(c.questions) for c in loaded)
  assert total_questions == 0
