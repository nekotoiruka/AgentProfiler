"""ProfileGenerator ユニットテスト"""

import re
import threading

import pytest

from app.models.scores import NormalizedScores
from app.models.session import Answer
from app.models.question import Question, Choice
from app.models.profile import ProfileOutput, ContextLayers
from app.core.profile_generator import ProfileGenerator


@pytest.fixture(autouse=True)
def reset_counter() -> None:
  """各テスト前にカウンターをリセット"""
  ProfileGenerator.reset_counter()


@pytest.fixture
def generator() -> ProfileGenerator:
  return ProfileGenerator()


@pytest.fixture
def sample_scores() -> NormalizedScores:
  return NormalizedScores(
    extroverted_introverted=0.72,
    sensing_intuition=0.35,
    thinking_feeling=0.68,
    judging_perceiving=0.51,
  )


@pytest.fixture
def sample_questions() -> list[Question]:
  return [
    Question(
      id="bos_001",
      text="プロジェクトが危機的状況に陥った時、最初に取る行動は？",
      category_id="business_os",
      choices=[
        Choice(id="a", label="チーム全員を集めて即座にブレインストーミングを開始する"),
        Choice(id="b", label="一人で状況を整理し、解決策を練ってから共有する"),
        Choice(id="c", label="データを集めて根本原因を特定してから対策を立てる"),
        Choice(id="d", label="過去の類似事例を参照し、実績ある手法を適用する"),
      ],
      source_reference="OEJTS_E/I_adapted",
    ),
    Question(
      id="bos_002",
      text="新しいプロジェクトのアサインについて、あなたの好みに最も近いものは？",
      category_id="business_os",
      choices=[
        Choice(id="a", label="未経験の技術領域に挑戦する案件を選ぶ"),
        Choice(id="b", label="これまでの専門性を深掘りできる案件を選ぶ"),
        Choice(id="c", label="チームメンバーとの相性を重視して選ぶ"),
        Choice(id="d", label="成果が明確に測定できる案件を選ぶ"),
      ],
      source_reference="IPIP-NEO_Openness_adapted",
    ),
    Question(
      id="com_001",
      text="チームメンバーからの相談への対応として、最も自然に取る行動は？",
      category_id="communication",
      choices=[
        Choice(id="a", label="まず相手の気持ちに寄り添い、話を最後まで聞く"),
        Choice(id="b", label="問題を構造化し、具体的な解決策を提示する"),
        Choice(id="c", label="関連する人を巻き込んで、チームで解決策を議論する"),
        Choice(id="d", label="類似の過去事例や参考資料を探して共有する"),
      ],
      source_reference="OEJTS_T/F_adapted",
    ),
    Question(
      id="lif_001",
      text="休日の過ごし方として、最もリフレッシュできるのは？",
      category_id="lifestyle",
      choices=[
        Choice(id="a", label="友人や仲間と集まってアクティビティを楽しむ"),
        Choice(id="b", label="一人で読書や映画鑑賞など静かに過ごす"),
        Choice(id="c", label="新しい場所を探索し、未知の体験をする"),
        Choice(id="d", label="自宅で趣味の制作や学習に没頭する"),
      ],
      source_reference="OEJTS_E/I_adapted",
    ),
  ]


@pytest.fixture
def sample_answers() -> list[Answer]:
  return [
    Answer(question_id="bos_001", choice_id="a"),
    Answer(question_id="bos_002", choice_id="a"),
    Answer(question_id="com_001", choice_id="b"),
    Answer(question_id="lif_001", choice_id="c"),
  ]


class TestProfileId:
  """profile_id の生成テスト"""

  def test_first_id_format(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """最初のIDは prof_000001"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    assert result.profile_id == "prof_000001"

  def test_sequential_ids(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """連続呼び出しで連番になる"""
    r1 = generator.generate(sample_scores, sample_answers, sample_questions)
    r2 = generator.generate(sample_scores, sample_answers, sample_questions)
    r3 = generator.generate(sample_scores, sample_answers, sample_questions)
    assert r1.profile_id == "prof_000001"
    assert r2.profile_id == "prof_000002"
    assert r3.profile_id == "prof_000003"

  def test_id_regex_pattern(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """profile_id は ^prof_\\d{6}$ にマッチ"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    assert re.match(r"^prof_\d{6}$", result.profile_id)

  def test_thread_safety(self, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """マルチスレッドでも重複しない"""
    results: list[str] = []
    lock = threading.Lock()

    def gen_profile() -> None:
      g = ProfileGenerator()
      r = g.generate(sample_scores, sample_answers, sample_questions)
      with lock:
        results.append(r.profile_id)

    threads = [threading.Thread(target=gen_profile) for _ in range(10)]
    for t in threads:
      t.start()
    for t in threads:
      t.join()

    assert len(results) == 10
    assert len(set(results)) == 10  # 全てユニーク


class TestDecisionStyle:
  """decision_style の導出テスト"""

  def test_all_high(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """全軸 > 0.50 → 全て第1極"""
    scores = NormalizedScores(
      extroverted_introverted=0.80,
      sensing_intuition=0.70,
      thinking_feeling=0.60,
      judging_perceiving=0.90,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert result.base_os.decision_style == "extroverted_sensing_thinking_judging"

  def test_all_low(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """全軸 < 0.50 → 全て第2極"""
    scores = NormalizedScores(
      extroverted_introverted=0.20,
      sensing_intuition=0.30,
      thinking_feeling=0.10,
      judging_perceiving=0.40,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert result.base_os.decision_style == "introverted_intuitive_feeling_perceiving"

  def test_mixed_poles(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """混合パターン"""
    scores = NormalizedScores(
      extroverted_introverted=0.72,
      sensing_intuition=0.35,
      thinking_feeling=0.68,
      judging_perceiving=0.51,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert result.base_os.decision_style == "extroverted_intuitive_thinking_judging"

  def test_balanced_axis(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """0.50の軸は balanced"""
    scores = NormalizedScores(
      extroverted_introverted=0.50,
      sensing_intuition=0.50,
      thinking_feeling=0.50,
      judging_perceiving=0.50,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert result.base_os.decision_style == "balanced_balanced_balanced_balanced"

  def test_partial_balanced(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """一部だけ balanced"""
    scores = NormalizedScores(
      extroverted_introverted=0.80,
      sensing_intuition=0.50,
      thinking_feeling=0.30,
      judging_perceiving=0.50,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert result.base_os.decision_style == "extroverted_balanced_feeling_balanced"


class TestDoNotList:
  """do_not_list の生成テスト"""

  def test_strong_high_polarity(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """スコア > 0.70 で項目生成"""
    scores = NormalizedScores(
      extroverted_introverted=0.85,
      sensing_intuition=0.50,
      thinking_feeling=0.50,
      judging_perceiving=0.50,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert len(result.base_os.do_not_list) >= 1
    assert any("外向" in item for item in result.base_os.do_not_list)

  def test_strong_low_polarity(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """スコア < 0.30 で項目生成"""
    scores = NormalizedScores(
      extroverted_introverted=0.20,
      sensing_intuition=0.50,
      thinking_feeling=0.50,
      judging_perceiving=0.50,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert len(result.base_os.do_not_list) >= 1
    assert any("内向" in item for item in result.base_os.do_not_list)

  def test_no_strong_polarity_generic(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """強い偏りなし → 汎用メッセージ1件"""
    scores = NormalizedScores(
      extroverted_introverted=0.50,
      sensing_intuition=0.50,
      thinking_feeling=0.50,
      judging_perceiving=0.50,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert len(result.base_os.do_not_list) == 1
    assert "バランス" in result.base_os.do_not_list[0]

  def test_max_four_items(self, generator: ProfileGenerator, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """最大4項目"""
    scores = NormalizedScores(
      extroverted_introverted=0.90,
      sensing_intuition=0.10,
      thinking_feeling=0.85,
      judging_perceiving=0.05,
    )
    result = generator.generate(scores, sample_answers, sample_questions)
    assert 1 <= len(result.base_os.do_not_list) <= 4

  def test_items_are_nonempty_strings(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """全項目が非空文字列"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    for item in result.base_os.do_not_list:
      assert isinstance(item, str)
      assert len(item) > 0


class TestLexicalTags:
  """lexical_tags のテスト"""

  def test_minimum_five_tags(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """最小5件保証"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    assert len(result.lexical_tags) >= 5

  def test_maximum_fifty_tags(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """最大50件"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    assert len(result.lexical_tags) <= 50

  def test_no_duplicates(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """重複なし"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    assert len(result.lexical_tags) == len(set(result.lexical_tags))

  def test_tag_pattern_format(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """全タグが [a-z0-9\\-./]+ にマッチ"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    pattern = re.compile(r"^[a-z0-9\-./]+$")
    for tag in result.lexical_tags:
      assert pattern.match(tag), f"Tag '{tag}' does not match pattern"

  def test_tags_from_brainstorming_choice(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question]) -> None:
    """ブレインストーミング選択肢を選んだ場合、関連タグが含まれる"""
    answers = [Answer(question_id="bos_001", choice_id="a")]
    result = generator.generate(sample_scores, answers, sample_questions)
    assert "brainstorming" in result.lexical_tags

  def test_tags_lowercase(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """全タグが小文字"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    for tag in result.lexical_tags:
      assert tag == tag.lower()


class TestSemanticContexts:
  """semantic_contexts のテスト"""

  def test_fixed_domain_keys(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """固定ドメインキーを全て含む"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    expected_keys = {
      "problem_solving", "communication_style",
      "work_rhythm", "analog_habits", "lifestyle_preferences",
    }
    assert set(result.semantic_contexts.keys()) == expected_keys

  def test_paragraph_minimum_length(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """各段落が50語（日本語は50文字）以上"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    for key, paragraph in result.semantic_contexts.items():
      # 日本語なので文字数でチェック（50文字以上）
      assert len(paragraph) >= 50, f"{key}: too short ({len(paragraph)} chars)"

  def test_paragraph_maximum_length(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """各段落が500語（日本語は妥当な上限）以下"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    for key, paragraph in result.semantic_contexts.items():
      # 日本語では1000文字程度を上限とする
      assert len(paragraph) <= 1000, f"{key}: too long ({len(paragraph)} chars)"

  def test_paragraphs_are_nonempty(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """全段落が非空"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    for paragraph in result.semantic_contexts.values():
      assert len(paragraph.strip()) > 0


class TestDataSeparation:
  """lexical_tags と semantic_contexts のデータ分離テスト"""

  def test_tags_not_in_contexts(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """lexical_tagsのキーワードがsemantic_contextsに出現しない"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    tag_pattern = re.compile(r"^[a-z0-9\-./]+$")
    for tag in result.lexical_tags:
      if tag_pattern.match(tag):
        for context_text in result.semantic_contexts.values():
          assert tag not in context_text, (
            f"Tag '{tag}' found in semantic_contexts"
          )


class TestContextLayers:
  """context_layers のテスト"""

  def test_fixed_layer_values(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """context_layers は固定値"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    assert result.context_layers.base_os == 1
    assert result.context_layers.lexical_tags == 2
    assert result.context_layers.semantic_contexts == 3


class TestProfileOutputStructure:
  """ProfileOutput全体の構造テスト"""

  def test_output_is_profile_output(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """戻り値がProfileOutput型"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    assert isinstance(result, ProfileOutput)

  def test_axes_match_input_scores(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question], sample_answers: list[Answer]) -> None:
    """base_os.axes が入力スコアと一致"""
    result = generator.generate(sample_scores, sample_answers, sample_questions)
    assert result.base_os.axes.extroverted_introverted == sample_scores.extroverted_introverted
    assert result.base_os.axes.sensing_intuition == sample_scores.sensing_intuition
    assert result.base_os.axes.thinking_feeling == sample_scores.thinking_feeling
    assert result.base_os.axes.judging_perceiving == sample_scores.judging_perceiving

  def test_empty_answers(self, generator: ProfileGenerator, sample_scores: NormalizedScores, sample_questions: list[Question]) -> None:
    """回答が空でも最低限のプロファイルが生成される"""
    result = generator.generate(sample_scores, [], sample_questions)
    assert result.profile_id == "prof_000001"
    assert len(result.lexical_tags) >= 5
    assert len(result.semantic_contexts) == 5
