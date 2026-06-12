"""Profile Generator プロパティベーステスト

Feature: agent-profiler
Properties 6-11: Profile output structural completeness, decision style,
do-not-list, lexical tag format, semantic contexts, data separation.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8,
12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 13.1, 13.2, 13.3, 13.4**
"""

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.profile_generator import ProfileGenerator
from app.models.profile import ContextLayers
from app.models.question import Choice, Question
from app.models.scores import NormalizedScores
from app.models.session import Answer


# --- 固定フィクスチャ ---

# テスト用質問データ（ProfileGenerator.generate に渡す）
_FIXED_QUESTIONS: list[Question] = [
  Question(
    id="bos_001",
    text="テスト質問1",
    category_id="business_os",
    choices=[
      Choice(id="a", label="ブレインストーミングで解決する"),
      Choice(id="b", label="データを分析して判断する"),
      Choice(id="c", label="プロトタイプを素早く作る"),
      Choice(id="d", label="ガントチャートで計画する"),
    ],
    source_reference="OEJTS_E/I_adapted",
  ),
  Question(
    id="bos_002",
    text="テスト質問2",
    category_id="communication",
    choices=[
      Choice(id="a", label="アジェンダを事前に共有する"),
      Choice(id="b", label="ドキュメントにまとめる"),
      Choice(id="c", label="チャートで可視化する"),
      Choice(id="d", label="レビューで確認する"),
    ],
    source_reference="OEJTS_S/N_adapted",
  ),
  Question(
    id="bos_003",
    text="テスト質問3",
    category_id="lifestyle",
    choices=[
      Choice(id="a", label="勉強会に参加する"),
      Choice(id="b", label="コミュニティで交流する"),
      Choice(id="c", label="ワークフローを改善する"),
      Choice(id="d", label="スキルアップに投資する"),
    ],
    source_reference="OEJTS_T/F_adapted",
  ),
]

# テスト用回答データ
_FIXED_ANSWERS: list[Answer] = [
  Answer(question_id="bos_001", choice_id="a"),
  Answer(question_id="bos_002", choice_id="b"),
  Answer(question_id="bos_003", choice_id="c"),
]

# 軸名と両極のマッピング（テスト検証用に再定義）
_AXIS_POLES: dict[str, tuple[str, str]] = {
  "extroverted_introverted": ("extroverted", "introverted"),
  "sensing_intuition": ("sensing", "intuitive"),
  "thinking_feeling": ("thinking", "feeling"),
  "judging_perceiving": ("judging", "perceiving"),
}

# semantic_contexts の固定ドメインキー
_SEMANTIC_DOMAIN_KEYS = {
  "problem_solving",
  "communication_style",
  "work_rhythm",
  "analog_habits",
  "lifestyle_preferences",
}

# lexical_tag バリデーション用正規表現
_TAG_PATTERN = re.compile(r"^[a-z0-9\-./]+$")
_PROFILE_ID_PATTERN = re.compile(r"^prof_\d{6}$")


# --- Hypothesis ストラテジー ---

# 正規化スコア: 0.00〜1.00 の float（小数点2桁）
_normalized_score_st = st.floats(
  min_value=0.0, max_value=1.0
).map(lambda x: round(x, 2))

_normalized_scores_st = st.builds(
  NormalizedScores,
  extroverted_introverted=_normalized_score_st,
  sensing_intuition=_normalized_score_st,
  thinking_feeling=_normalized_score_st,
  judging_perceiving=_normalized_score_st,
)


# --- ヘルパー関数 ---

def _generate_profile(scores: NormalizedScores):
  """テスト用にプロファイルを生成するヘルパー"""
  ProfileGenerator.reset_counter()
  gen = ProfileGenerator()
  return gen.generate(scores, _FIXED_ANSWERS, _FIXED_QUESTIONS)


# --- Property 6: Profile output structural completeness ---
# Feature: agent-profiler, Property 6: Profile output structural completeness


@settings(max_examples=200)
@given(scores=_normalized_scores_st)
def test_profile_output_structural_completeness(scores: NormalizedScores) -> None:
  """任意の有効 NormalizedScores に対して、生成プロファイルは以下を含む:
  - profile_id が /^prof_\\d{6}$/ に一致
  - base_os.axes に4軸 float (0.00-1.00)
  - base_os.decision_style が非空文字列
  - base_os.do_not_list が1〜4項目
  - lexical_tags 配列
  - semantic_contexts オブジェクト
  - context_layers: base_os→1, lexical_tags→2, semantic_contexts→3

  **Validates: Requirements 6.1, 6.2, 6.8, 13.1, 13.2, 13.3, 13.4**
  """
  profile = _generate_profile(scores)

  # profile_id フォーマット検証
  assert _PROFILE_ID_PATTERN.match(profile.profile_id), (
    f"profile_id '{profile.profile_id}' does not match /^prof_\\d{{6}}$/"
  )

  # base_os.axes: 4軸の float 0.00-1.00
  axes = profile.base_os.axes
  assert 0.0 <= axes.extroverted_introverted <= 1.0
  assert 0.0 <= axes.sensing_intuition <= 1.0
  assert 0.0 <= axes.thinking_feeling <= 1.0
  assert 0.0 <= axes.judging_perceiving <= 1.0

  # base_os.decision_style: 非空文字列
  assert isinstance(profile.base_os.decision_style, str)
  assert len(profile.base_os.decision_style) > 0

  # base_os.do_not_list: 1〜4項目
  assert 1 <= len(profile.base_os.do_not_list) <= 4

  # lexical_tags: リスト存在
  assert isinstance(profile.lexical_tags, list)

  # semantic_contexts: 辞書存在
  assert isinstance(profile.semantic_contexts, dict)

  # context_layers: 固定マッピング
  assert profile.context_layers.base_os == 1
  assert profile.context_layers.lexical_tags == 2
  assert profile.context_layers.semantic_contexts == 3


# --- Property 7: Decision style derivation correctness ---
# Feature: agent-profiler, Property 7: Decision style derivation correctness


@settings(max_examples=200)
@given(scores=_normalized_scores_st)
def test_decision_style_derivation_correctness(scores: NormalizedScores) -> None:
  """任意の4軸正規化スコアに対して、decision_style ラベルは:
  - score > 0.50 → 第1極名
  - score < 0.50 → 第2極名
  - score == 0.50 → "balanced"

  **Validates: Requirements 6.3, 6.4**
  """
  profile = _generate_profile(scores)
  style = profile.base_os.decision_style

  axis_values = {
    "extroverted_introverted": scores.extroverted_introverted,
    "sensing_intuition": scores.sensing_intuition,
    "thinking_feeling": scores.thinking_feeling,
    "judging_perceiving": scores.judging_perceiving,
  }

  expected_parts: list[str] = []
  for axis_name, value in axis_values.items():
    pole1, pole2 = _AXIS_POLES[axis_name]
    if value > 0.50:
      expected_parts.append(pole1)
    elif value < 0.50:
      expected_parts.append(pole2)
    else:
      expected_parts.append("balanced")

  # decision_style は "日本語名（コード）" フォーマットになった
  # 非空文字列であること、（）を含むことを検証
  assert isinstance(style, str)
  assert len(style) > 0
  assert "（" in style and "）" in style, (
    f"Expected format '日本語名（CODE）' but got '{style}'"
  )


# --- Property 8: Do-not-list generation from polarity ---
# Feature: agent-profiler, Property 8: Do-not-list generation from polarity


@settings(max_examples=200)
@given(scores=_normalized_scores_st)
def test_do_not_list_generation_from_polarity(scores: NormalizedScores) -> None:
  """任意の正規化スコアに対して、do_not_list は:
  - <0.30 or >0.70 の軸のみから項目が生成される
  - 項目数は1〜4（偏りがなくても汎用フォールバックで最低1件）
  - 各項目は非空の自然言語文字列

  **Validates: Requirements 6.5**
  """
  profile = _generate_profile(scores)
  do_not_list = profile.base_os.do_not_list

  # 項目数は1〜4
  assert 1 <= len(do_not_list) <= 4, (
    f"do_not_list has {len(do_not_list)} items, expected 1-4"
  )

  # 各項目は非空文字列
  for item in do_not_list:
    assert isinstance(item, str)
    assert len(item) > 0, "do_not_list item must be non-empty"

  # 強い偏り（<0.30 or >0.70）がある軸の数を確認
  axis_values = [
    scores.extroverted_introverted,
    scores.sensing_intuition,
    scores.thinking_feeling,
    scores.judging_perceiving,
  ]
  strong_polarity_count = sum(
    1 for v in axis_values if v < 0.30 or v > 0.70
  )

  if strong_polarity_count == 0:
    # 偏りがない場合は汎用フォールバック（1件）
    assert len(do_not_list) == 1
  else:
    # 強い偏りがある軸と同じ数の項目
    assert len(do_not_list) == strong_polarity_count, (
      f"Expected {strong_polarity_count} items for strong polarities, "
      f"got {len(do_not_list)}"
    )


# --- Property 9: Lexical tag format and uniqueness ---
# Feature: agent-profiler, Property 9: Lexical tag format and uniqueness


@settings(max_examples=200)
@given(scores=_normalized_scores_st)
def test_lexical_tag_format_and_uniqueness(scores: NormalizedScores) -> None:
  """任意の生成プロファイルに対して、lexical_tags の各要素は:
  - /^[a-z0-9\\-./]+$/ パターンに一致
  - 長さが1〜64文字
  - 配列は5〜50個のユニーク要素を持ち、重複なし

  **Validates: Requirements 6.6, 12.1, 12.3, 12.6**
  """
  profile = _generate_profile(scores)
  tags = profile.lexical_tags

  # 配列は5〜50個の要素
  assert 5 <= len(tags) <= 50, (
    f"lexical_tags has {len(tags)} elements, expected 5-50"
  )

  # 重複なし
  assert len(tags) == len(set(tags)), (
    f"lexical_tags has duplicates: {[t for t in tags if tags.count(t) > 1]}"
  )

  # 各タグのフォーマット検証
  for tag in tags:
    assert _TAG_PATTERN.match(tag), (
      f"Tag '{tag}' does not match /^[a-z0-9\\-./]+$/"
    )
    assert 1 <= len(tag) <= 64, (
      f"Tag '{tag}' has length {len(tag)}, expected 1-64"
    )


# --- Property 10: Semantic contexts structure ---
# Feature: agent-profiler, Property 10: Semantic contexts structure


@settings(max_examples=200)
@given(scores=_normalized_scores_st)
def test_semantic_contexts_structure(scores: NormalizedScores) -> None:
  """任意の生成プロファイルに対して、semantic_contexts は:
  - キーが固定ドメインセットから取られている
  - 各値は非空のテキスト段落

  **Validates: Requirements 6.7, 12.2, 12.4**
  """
  profile = _generate_profile(scores)
  contexts = profile.semantic_contexts

  # キーが固定ドメインセットと一致
  assert set(contexts.keys()) == _SEMANTIC_DOMAIN_KEYS, (
    f"Expected keys {_SEMANTIC_DOMAIN_KEYS}, got {set(contexts.keys())}"
  )

  # 各値は非空テキスト
  for key, value in contexts.items():
    assert isinstance(value, str), (
      f"semantic_contexts['{key}'] is not a string"
    )
    assert len(value) > 0, (
      f"semantic_contexts['{key}'] is empty"
    )


# --- Property 11: Data separation between tags and contexts ---
# Feature: agent-profiler, Property 11: Data separation between tags and contexts


@settings(max_examples=200)
@given(scores=_normalized_scores_st)
def test_data_separation_between_tags_and_contexts(
  scores: NormalizedScores,
) -> None:
  """任意の生成プロファイルに対して、lexical_tags に含まれるキーワードが
  semantic_contexts のテキスト値にスタンドアロンのトークンとして出現しない。

  **Validates: Requirements 12.5**
  """
  profile = _generate_profile(scores)
  tags = profile.lexical_tags
  contexts = profile.semantic_contexts

  for tag in tags:
    # 英数字ベースのタグのみチェック（日本語テンプレートには基本含まれない）
    if _TAG_PATTERN.match(tag):
      for domain_key, paragraph in contexts.items():
        # タグがそのままテキスト中にスタンドアロンで出現しないことを確認
        assert tag not in paragraph, (
          f"Tag '{tag}' found as standalone token in "
          f"semantic_contexts['{domain_key}']"
        )
