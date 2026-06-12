"""Mapping Dictionary Loader & Question Data Loader ユニットテスト

ロード成功、ホットリロード、不正エントリ除外、ファイル不在エラーを検証。
"""

import json
import os
import time
from pathlib import Path

import pytest
import yaml

from app.services.data_loader import (
  MappingDictionaryLoader,
  MappingDictionaryLoadError,
  QuestionDataLoader,
  QuestionDataLoadError,
)


@pytest.fixture
def valid_mapping_data():
  """有効なMapping Dictionaryデータ"""
  return {
    "metadata": {
      "version": "1.0",
      "theoretical_bounds": {
        "extroverted_introverted": {"min": -30, "max": 30},
        "sensing_intuition": {"min": -25, "max": 25},
        "thinking_feeling": {"min": -28, "max": 28},
        "judging_perceiving": {"min": -26, "max": 26},
      },
    },
    "mappings": [
      {
        "question_id": "q1",
        "choice_id": "a",
        "scores": {
          "extroverted_introverted": 5,
          "sensing_intuition": -3,
          "thinking_feeling": 2,
          "judging_perceiving": 0,
        },
      },
      {
        "question_id": "q1",
        "choice_id": "b",
        "scores": {
          "extroverted_introverted": -5,
          "sensing_intuition": 3,
          "thinking_feeling": -2,
          "judging_perceiving": 1,
        },
      },
    ],
  }


@pytest.fixture
def mapping_file(tmp_path, valid_mapping_data):
  """一時ファイルに有効なMapping Dictionaryを書き出す"""
  file_path = tmp_path / "mapping_dictionary.json"
  file_path.write_text(json.dumps(valid_mapping_data), encoding="utf-8")
  return file_path


class TestLoad:
  """load() メソッドのテスト"""

  def test_load_success(self, mapping_file, valid_mapping_data):
    """有効なJSONファイルを正常にロードできる"""
    loader = MappingDictionaryLoader(mapping_file)
    result = loader.load()

    assert result.metadata.version == "1.0"
    assert len(result.mappings) == 2
    assert result.mappings[0].question_id == "q1"
    assert result.mappings[0].choice_id == "a"
    assert result.mappings[0].scores.extroverted_introverted == 5

  def test_load_file_not_found(self, tmp_path):
    """ファイル不在時はMappingDictionaryLoadErrorを送出"""
    loader = MappingDictionaryLoader(tmp_path / "nonexistent.json")

    with pytest.raises(MappingDictionaryLoadError, match="not found"):
      loader.load()

  def test_load_invalid_json(self, tmp_path):
    """JSON構文エラー時はMappingDictionaryLoadErrorを送出"""
    file_path = tmp_path / "bad.json"
    file_path.write_text("{invalid json content", encoding="utf-8")
    loader = MappingDictionaryLoader(file_path)

    with pytest.raises(MappingDictionaryLoadError, match="Failed to parse"):
      loader.load()

  def test_load_not_object(self, tmp_path):
    """JSONがオブジェクトでない場合はエラー"""
    file_path = tmp_path / "array.json"
    file_path.write_text("[1, 2, 3]", encoding="utf-8")
    loader = MappingDictionaryLoader(file_path)

    with pytest.raises(MappingDictionaryLoadError, match="must be a JSON object"):
      loader.load()

  def test_load_invalid_metadata(self, tmp_path):
    """metadata構造が不正な場合はエラー"""
    data = {"metadata": {"version": "1.0"}, "mappings": []}
    file_path = tmp_path / "bad_meta.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")
    loader = MappingDictionaryLoader(file_path)

    with pytest.raises(MappingDictionaryLoadError, match="Invalid metadata"):
      loader.load()

  def test_load_invalid_entries_excluded(self, tmp_path, valid_mapping_data):
    """不正エントリはログ出力して除外、有効エントリのみ残る"""
    # スコアが範囲外のエントリを追加
    valid_mapping_data["mappings"].append(
      {
        "question_id": "q2",
        "choice_id": "a",
        "scores": {
          "extroverted_introverted": 15,  # 範囲外
          "sensing_intuition": 0,
          "thinking_feeling": 0,
          "judging_perceiving": 0,
        },
      }
    )
    # 必須フィールド欠落エントリを追加
    valid_mapping_data["mappings"].append(
      {
        "question_id": "q3",
        # choice_id が無い
        "scores": {
          "extroverted_introverted": 1,
          "sensing_intuition": 0,
          "thinking_feeling": 0,
          "judging_perceiving": 0,
        },
      }
    )

    file_path = tmp_path / "partial.json"
    file_path.write_text(json.dumps(valid_mapping_data), encoding="utf-8")
    loader = MappingDictionaryLoader(file_path)
    result = loader.load()

    # 元の2件のみが有効
    assert len(result.mappings) == 2

  def test_load_mappings_not_list(self, tmp_path):
    """mappingsがリストでない場合はエラー"""
    data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": "not a list",
    }
    file_path = tmp_path / "bad_mappings.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")
    loader = MappingDictionaryLoader(file_path)

    with pytest.raises(MappingDictionaryLoadError, match="must be a list"):
      loader.load()


class TestGet:
  """get() メソッドのテスト"""

  def test_get_auto_loads_on_first_call(self, mapping_file):
    """get()初回呼び出し時に自動ロードされる"""
    loader = MappingDictionaryLoader(mapping_file)
    result = loader.get()

    assert len(result.mappings) == 2

  def test_get_returns_cached(self, mapping_file):
    """ファイル未変更時はキャッシュを返す"""
    loader = MappingDictionaryLoader(mapping_file)
    first = loader.get()
    second = loader.get()

    # 同一オブジェクト（再ロードなし）
    assert first is second

  def test_get_hot_reload_on_file_change(self, tmp_path, valid_mapping_data):
    """ファイル変更時にホットリロードされる"""
    file_path = tmp_path / "mapping_dictionary.json"
    file_path.write_text(json.dumps(valid_mapping_data), encoding="utf-8")

    loader = MappingDictionaryLoader(file_path)
    first = loader.get()
    assert len(first.mappings) == 2

    # ファイルを変更（エントリ追加）
    # mtime変更を確実にするため少し待機
    time.sleep(0.05)
    valid_mapping_data["mappings"].append(
      {
        "question_id": "q2",
        "choice_id": "a",
        "scores": {
          "extroverted_introverted": 3,
          "sensing_intuition": -1,
          "thinking_feeling": 4,
          "judging_perceiving": -2,
        },
      }
    )
    file_path.write_text(json.dumps(valid_mapping_data), encoding="utf-8")

    # mtimeが同一になる可能性があるため、手動で変更
    # os.utime で確実にmtimeを変える
    new_mtime = loader._last_mtime + 1.0
    os.utime(file_path, (new_mtime, new_mtime))

    second = loader.get()
    assert len(second.mappings) == 3
    assert first is not second

  def test_get_file_deleted_uses_cache(self, mapping_file):
    """ファイル削除後もキャッシュを使い続ける"""
    loader = MappingDictionaryLoader(mapping_file)
    cached = loader.get()

    # ファイルを削除
    mapping_file.unlink()

    # キャッシュが返る
    result = loader.get()
    assert result is cached


class TestEdgeCases:
  """エッジケーステスト"""

  def test_empty_mappings_is_valid(self, tmp_path):
    """mappingsが空リストでも正常ロードされる"""
    data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": [],
    }
    file_path = tmp_path / "empty_mappings.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    loader = MappingDictionaryLoader(file_path)
    result = loader.load()
    assert len(result.mappings) == 0

  def test_score_boundary_values(self, tmp_path):
    """スコア境界値(-10, +10)は有効"""
    data = {
      "metadata": {
        "version": "1.0",
        "theoretical_bounds": {
          "extroverted_introverted": {"min": -30, "max": 30},
          "sensing_intuition": {"min": -25, "max": 25},
          "thinking_feeling": {"min": -28, "max": 28},
          "judging_perceiving": {"min": -26, "max": 26},
        },
      },
      "mappings": [
        {
          "question_id": "q1",
          "choice_id": "a",
          "scores": {
            "extroverted_introverted": -10,
            "sensing_intuition": 10,
            "thinking_feeling": -10,
            "judging_perceiving": 10,
          },
        }
      ],
    }
    file_path = tmp_path / "boundary.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    loader = MappingDictionaryLoader(file_path)
    result = loader.load()
    assert len(result.mappings) == 1
    assert result.mappings[0].scores.extroverted_introverted == -10
    assert result.mappings[0].scores.sensing_intuition == 10



# ========== QuestionDataLoader テスト ==========


@pytest.fixture
def mapping_data_for_questions():
  """質問テスト用のMapping Dictionaryデータ"""
  return {
    "metadata": {
      "version": "1.0",
      "theoretical_bounds": {
        "extroverted_introverted": {"min": -30, "max": 30},
        "sensing_intuition": {"min": -25, "max": 25},
        "thinking_feeling": {"min": -28, "max": 28},
        "judging_perceiving": {"min": -26, "max": 26},
      },
    },
    "mappings": [
      # q1: 4軸中3軸が活性化
      {"question_id": "q1", "choice_id": "a", "scores": {"extroverted_introverted": 5, "sensing_intuition": -3, "thinking_feeling": 2, "judging_perceiving": 0}},
      {"question_id": "q1", "choice_id": "b", "scores": {"extroverted_introverted": -5, "sensing_intuition": 3, "thinking_feeling": -2, "judging_perceiving": 0}},
      {"question_id": "q1", "choice_id": "c", "scores": {"extroverted_introverted": 3, "sensing_intuition": 0, "thinking_feeling": 4, "judging_perceiving": 0}},
      {"question_id": "q1", "choice_id": "d", "scores": {"extroverted_introverted": -3, "sensing_intuition": 0, "thinking_feeling": -4, "judging_perceiving": 0}},
      # q2: 2軸活性化
      {"question_id": "q2", "choice_id": "a", "scores": {"extroverted_introverted": 7, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": -4}},
      {"question_id": "q2", "choice_id": "b", "scores": {"extroverted_introverted": -7, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 4}},
      {"question_id": "q2", "choice_id": "c", "scores": {"extroverted_introverted": 3, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": -2}},
      {"question_id": "q2", "choice_id": "d", "scores": {"extroverted_introverted": -3, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 2}},
      # q3: 1軸のみ活性化（バリデーションで弾かれる）
      {"question_id": "q3", "choice_id": "a", "scores": {"extroverted_introverted": 5, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 0}},
      {"question_id": "q3", "choice_id": "b", "scores": {"extroverted_introverted": -5, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 0}},
      {"question_id": "q3", "choice_id": "c", "scores": {"extroverted_introverted": 3, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 0}},
      {"question_id": "q3", "choice_id": "d", "scores": {"extroverted_introverted": -3, "sensing_intuition": 0, "thinking_feeling": 0, "judging_perceiving": 0}},
      # q4: 4軸活性化（別カテゴリ用）
      {"question_id": "q4", "choice_id": "a", "scores": {"extroverted_introverted": 3, "sensing_intuition": -2, "thinking_feeling": 5, "judging_perceiving": -1}},
      {"question_id": "q4", "choice_id": "b", "scores": {"extroverted_introverted": -3, "sensing_intuition": 2, "thinking_feeling": -5, "judging_perceiving": 1}},
      {"question_id": "q4", "choice_id": "c", "scores": {"extroverted_introverted": 1, "sensing_intuition": -4, "thinking_feeling": 3, "judging_perceiving": -2}},
      {"question_id": "q4", "choice_id": "d", "scores": {"extroverted_introverted": -1, "sensing_intuition": 4, "thinking_feeling": -3, "judging_perceiving": 2}},
    ],
  }


@pytest.fixture
def valid_question_data():
  """有効な質問データ"""
  return {
    "categories": [
      {
        "id": "cat_a",
        "name": "Category A",
        "order": 1,
        "questions": [
          {
            "id": "q1",
            "text": "テスト質問1",
            "category_id": "cat_a",
            "choices": [
              {"id": "a", "label": "選択肢A"},
              {"id": "b", "label": "選択肢B"},
              {"id": "c", "label": "選択肢C"},
              {"id": "d", "label": "選択肢D"},
            ],
            "source_reference": "TEST_SOURCE_1",
          },
          {
            "id": "q2",
            "text": "テスト質問2",
            "category_id": "cat_a",
            "choices": [
              {"id": "a", "label": "選択肢A"},
              {"id": "b", "label": "選択肢B"},
              {"id": "c", "label": "選択肢C"},
              {"id": "d", "label": "選択肢D"},
            ],
            "source_reference": "TEST_SOURCE_2",
          },
        ],
      },
      {
        "id": "cat_b",
        "name": "Category B",
        "order": 2,
        "questions": [
          {
            "id": "q4",
            "text": "テスト質問4",
            "category_id": "cat_b",
            "choices": [
              {"id": "a", "label": "選択肢A"},
              {"id": "b", "label": "選択肢B"},
              {"id": "c", "label": "選択肢C"},
              {"id": "d", "label": "選択肢D"},
            ],
            "source_reference": "TEST_SOURCE_4",
          },
        ],
      },
    ]
  }


@pytest.fixture
def question_file(tmp_path, valid_question_data):
  """一時ファイルに有効な質問データを書き出す"""
  file_path = tmp_path / "questions.yaml"
  file_path.write_text(yaml.dump(valid_question_data, allow_unicode=True), encoding="utf-8")
  return file_path


@pytest.fixture
def mapping_loader_for_questions(tmp_path, mapping_data_for_questions):
  """質問テスト用MappingDictionaryLoaderを準備"""
  file_path = tmp_path / "mapping_dictionary.json"
  file_path.write_text(json.dumps(mapping_data_for_questions), encoding="utf-8")
  loader = MappingDictionaryLoader(file_path)
  loader.load()
  return loader


class TestQuestionDataLoaderLoad:
  """QuestionDataLoader.load() のテスト"""

  def test_load_success(self, question_file, mapping_loader_for_questions):
    """有効なYAMLファイルを正常にロードできる"""
    loader = QuestionDataLoader(question_file, mapping_loader_for_questions)
    result = loader.load()

    assert len(result) == 2
    assert result[0].id == "cat_a"
    assert result[0].order == 1
    assert len(result[0].questions) == 2
    assert result[0].questions[0].id == "q1"
    assert result[0].questions[0].text == "テスト質問1"
    assert len(result[0].questions[0].choices) == 4
    assert result[1].id == "cat_b"
    assert result[1].order == 2

  def test_load_file_not_found(self, tmp_path, mapping_loader_for_questions):
    """ファイル不在時はQuestionDataLoadErrorを送出"""
    loader = QuestionDataLoader(
      tmp_path / "nonexistent.yaml", mapping_loader_for_questions
    )

    with pytest.raises(QuestionDataLoadError, match="not found"):
      loader.load()

  def test_load_invalid_yaml(self, tmp_path, mapping_loader_for_questions):
    """YAML構文エラー時はQuestionDataLoadErrorを送出"""
    file_path = tmp_path / "bad.yaml"
    file_path.write_text("{{invalid yaml:", encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)

    with pytest.raises(QuestionDataLoadError, match="Failed to parse"):
      loader.load()

  def test_load_not_mapping(self, tmp_path, mapping_loader_for_questions):
    """YAMLがマッピングでない場合はエラー"""
    file_path = tmp_path / "array.yaml"
    file_path.write_text("- item1\n- item2\n", encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)

    with pytest.raises(QuestionDataLoadError, match="must be a YAML mapping"):
      loader.load()

  def test_load_categories_not_list(self, tmp_path, mapping_loader_for_questions):
    """categoriesがリストでない場合はエラー"""
    file_path = tmp_path / "bad_categories.yaml"
    file_path.write_text("categories: not_a_list\n", encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)

    with pytest.raises(QuestionDataLoadError, match="must be a list"):
      loader.load()

  def test_load_category_order_sorting(self, tmp_path, mapping_loader_for_questions):
    """カテゴリがorder順にソートされる"""
    data = {
      "categories": [
        {
          "id": "cat_b",
          "name": "Category B",
          "order": 2,
          "questions": [
            {
              "id": "q4",
              "text": "テスト質問",
              "category_id": "cat_b",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
          ],
        },
        {
          "id": "cat_a",
          "name": "Category A",
          "order": 1,
          "questions": [
            {
              "id": "q1",
              "text": "テスト質問",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
          ],
        },
      ]
    }
    file_path = tmp_path / "unordered.yaml"
    file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    result = loader.load()

    assert result[0].id == "cat_a"
    assert result[0].order == 1
    assert result[1].id == "cat_b"
    assert result[1].order == 2


class TestQuestionDataLoaderValidation:
  """QuestionDataLoader バリデーションのテスト"""

  def test_duplicate_id_excluded(self, tmp_path, mapping_loader_for_questions):
    """重複IDの質問は除外される"""
    data = {
      "categories": [
        {
          "id": "cat_a",
          "name": "Category A",
          "order": 1,
          "questions": [
            {
              "id": "q1",
              "text": "質問1 オリジナル",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
            {
              "id": "q1",
              "text": "質問1 重複",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
          ],
        },
      ]
    }
    file_path = tmp_path / "dup.yaml"
    file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    result = loader.load()

    assert len(result[0].questions) == 1
    assert result[0].questions[0].text == "質問1 オリジナル"

  def test_missing_mapping_excluded(self, tmp_path, mapping_loader_for_questions):
    """Mapping Dictionaryにマッピングがない質問はsource_referenceがあれば許可される
    （persona等の直接マッピング質問として扱われる）"""
    data = {
      "categories": [
        {
          "id": "cat_a",
          "name": "Category A",
          "order": 1,
          "questions": [
            {
              "id": "q_no_mapping",
              "text": "マッピング無し質問",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
            {
              "id": "q1",
              "text": "有効な質問",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
          ],
        },
      ]
    }
    file_path = tmp_path / "no_mapping.yaml"
    file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    result = loader.load()

    # マッピングなし質問もsource_referenceがあれば許可される（直接マッピング扱い）
    assert len(result[0].questions) == 2

  def test_single_axis_excluded(self, tmp_path, mapping_loader_for_questions):
    """1軸のみ活性化する質問は除外される"""
    data = {
      "categories": [
        {
          "id": "cat_a",
          "name": "Category A",
          "order": 1,
          "questions": [
            {
              "id": "q3",
              "text": "1軸のみ活性化",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
            {
              "id": "q1",
              "text": "有効な質問",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
          ],
        },
      ]
    }
    file_path = tmp_path / "single_axis.yaml"
    file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    result = loader.load()

    assert len(result[0].questions) == 1
    assert result[0].questions[0].id == "q1"

  def test_text_exceeds_max_length(self, tmp_path, mapping_loader_for_questions):
    """textが200文字超過の質問は除外される"""
    data = {
      "categories": [
        {
          "id": "cat_a",
          "name": "Category A",
          "order": 1,
          "questions": [
            {
              "id": "q1",
              "text": "あ" * 201,
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
          ],
        },
      ]
    }
    file_path = tmp_path / "long_text.yaml"
    file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    result = loader.load()

    assert len(result[0].questions) == 0

  def test_choice_label_exceeds_max_length(self, tmp_path, mapping_loader_for_questions):
    """choice labelが100文字超過の質問は除外される"""
    data = {
      "categories": [
        {
          "id": "cat_a",
          "name": "Category A",
          "order": 1,
          "questions": [
            {
              "id": "q1",
              "text": "テスト質問",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "あ" * 101},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "SRC",
            },
          ],
        },
      ]
    }
    file_path = tmp_path / "long_label.yaml"
    file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    result = loader.load()

    assert len(result[0].questions) == 0

  def test_not_exactly_4_choices(self, tmp_path, mapping_loader_for_questions):
    """選択肢が4つでない質問は除外される"""
    data = {
      "categories": [
        {
          "id": "cat_a",
          "name": "Category A",
          "order": 1,
          "questions": [
            {
              "id": "q1",
              "text": "テスト質問",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
              ],
              "source_reference": "SRC",
            },
          ],
        },
      ]
    }
    file_path = tmp_path / "three_choices.yaml"
    file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    result = loader.load()

    assert len(result[0].questions) == 0

  def test_missing_source_reference(self, tmp_path, mapping_loader_for_questions):
    """source_referenceが空の質問は除外される"""
    data = {
      "categories": [
        {
          "id": "cat_a",
          "name": "Category A",
          "order": 1,
          "questions": [
            {
              "id": "q1",
              "text": "テスト質問",
              "category_id": "cat_a",
              "choices": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
                {"id": "d", "label": "D"},
              ],
              "source_reference": "",
            },
          ],
        },
      ]
    }
    file_path = tmp_path / "no_src.yaml"
    file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    result = loader.load()

    assert len(result[0].questions) == 0


class TestQuestionDataLoaderGet:
  """QuestionDataLoader.get() のテスト"""

  def test_get_auto_loads(self, question_file, mapping_loader_for_questions):
    """get()初回呼び出し時に自動ロードされる"""
    loader = QuestionDataLoader(question_file, mapping_loader_for_questions)
    result = loader.get()

    assert len(result) == 2

  def test_get_returns_cached(self, question_file, mapping_loader_for_questions):
    """ファイル未変更時はキャッシュを返す"""
    loader = QuestionDataLoader(question_file, mapping_loader_for_questions)
    first = loader.get()
    second = loader.get()

    assert first is second

  def test_get_hot_reload_on_file_change(
    self, tmp_path, valid_question_data, mapping_loader_for_questions
  ):
    """ファイル変更時にホットリロードされる"""
    file_path = tmp_path / "questions.yaml"
    file_path.write_text(
      yaml.dump(valid_question_data, allow_unicode=True), encoding="utf-8"
    )

    loader = QuestionDataLoader(file_path, mapping_loader_for_questions)
    first = loader.get()
    initial_count = sum(len(c.questions) for c in first)

    # ファイルを変更（質問追加）
    valid_question_data["categories"][0]["questions"].append(
      {
        "id": "q2",
        "text": "追加質問",
        "category_id": "cat_a",
        "choices": [
          {"id": "a", "label": "A"},
          {"id": "b", "label": "B"},
          {"id": "c", "label": "C"},
          {"id": "d", "label": "D"},
        ],
        "source_reference": "SRC",
      }
    )
    file_path.write_text(
      yaml.dump(valid_question_data, allow_unicode=True), encoding="utf-8"
    )

    # mtimeを確実に変更
    new_mtime = loader._last_mtime + 1.0
    os.utime(file_path, (new_mtime, new_mtime))

    second = loader.get()
    assert first is not second

  def test_get_file_deleted_uses_cache(
    self, question_file, mapping_loader_for_questions
  ):
    """ファイル削除後もキャッシュを使い続ける"""
    loader = QuestionDataLoader(question_file, mapping_loader_for_questions)
    cached = loader.get()

    question_file.unlink()

    result = loader.get()
    assert result is cached
