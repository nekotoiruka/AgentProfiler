"""全質問統一パイプライン E2E テスト

全88問回答 → 3層変換 → Rule Hierarchy 集約 → ProfileOutput 生成の完全フロー
既存カテゴリ（BOS/COM/LIF）の回答から policy_text が正しく生成されることを検証

Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.7, 12.8
"""

import json
from pathlib import Path

import pytest

from app.core.profile_generator import ProfileGenerator
from app.decision_engine.rule_aggregator import RuleAggregator
from app.decision_engine.scorer import DecisionScorer
from app.evolution.prompt_engine import PromptEngine
from app.models.scores import NormalizedScores
from app.models.session import Answer
from app.services.data_loader import MappingDictionaryLoader, QuestionDataLoader


@pytest.fixture
def scorer():
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  return DecisionScorer(loader)


@pytest.fixture
def aggregator():
  return RuleAggregator()


@pytest.fixture
def question_loader(scorer):
  data_dir = Path(__file__).resolve().parent.parent.parent / "data"
  mapping_loader = MappingDictionaryLoader(data_dir / "mapping_dictionary.json")
  return QuestionDataLoader(data_dir / "questions.yaml", mapping_loader)


@pytest.fixture
def all_questions(question_loader):
  categories = question_loader.get()
  return [q for cat in categories for q in cat.questions]


@pytest.fixture
def full_answers():
  """全カテゴリの回答を生成する（choice 'a' で統一）"""
  answers = []

  # BOS (9 questions)
  for i in range(1, 10):
    answers.append(Answer(question_id=f"bos_{i:03d}", choice_id="a"))

  # COM (9 questions)
  for i in range(1, 10):
    answers.append(Answer(question_id=f"com_{i:03d}", choice_id="a"))

  # LIF (9 questions)
  for i in range(1, 10):
    answers.append(Answer(question_id=f"lif_{i:03d}", choice_id="a"))

  # DM (10 questions)
  for i in range(1, 11):
    answers.append(Answer(question_id=f"dm_{i:03d}", choice_id="a"))

  # TS (8 questions)
  for i in range(1, 9):
    answers.append(Answer(question_id=f"ts_{i:03d}", choice_id="a"))

  # FP (7 questions)
  for i in range(1, 8):
    answers.append(Answer(question_id=f"fp_{i:03d}", choice_id="a"))

  # CA (5 questions)
  for i in range(1, 6):
    answers.append(Answer(question_id=f"ca_{i:03d}", choice_id="a"))

  # RF (5 questions - ordering uses JSON array in choice_id)
  answers.append(Answer(
    question_id="rf_001",
    choice_id=json.dumps(
      ["step_gather", "step_define", "step_generate", "step_evaluate", "step_decide", "step_execute"]
    ),
  ))
  answers.append(Answer(
    question_id="rf_002",
    choice_id=json.dumps(["step_overview", "step_logic", "step_edge", "step_style"]),
  ))
  for i in range(3, 6):
    answers.append(Answer(question_id=f"rf_{i:03d}", choice_id="a"))

  return answers


class TestFullPipelineE2E:
  """全88問 → ProfileOutput 生成の統合テスト"""

  def test_profile_with_all_decision_sections(
    self, full_answers, all_questions, scorer, aggregator
  ):
    """全質問回答後、全 decision engine セクションが populated される"""
    pg = ProfileGenerator()
    pg.reset_counter()

    normalized = NormalizedScores(
      extroverted_introverted=0.6,
      sensing_intuition=0.4,
      thinking_feeling=0.7,
      judging_perceiving=0.5,
    )

    profile = pg.generate(
      normalized, full_answers, all_questions,
      scorer=scorer, aggregator=aggregator,
    )

    # 全 decision engine セクションが非 None
    assert profile.decision_model is not None
    assert profile.failure_patterns is not None
    assert profile.context_adaptation is not None
    assert profile.reasoning_flow is not None
    assert profile.decision_rules is not None
    assert profile.rule_hierarchy is not None
    assert profile.answer_metadata_summary is not None

    # base_os も正常に生成されている
    assert profile.base_os is not None
    assert profile.base_os.axes is not None
    assert len(profile.base_os.do_not_list) >= 1

  def test_decision_model_has_priorities_and_tradeoffs(
    self, full_answers, all_questions, scorer, aggregator
  ):
    """decision_model に priorities と tradeoff_tendencies が含まれる"""
    pg = ProfileGenerator()
    pg.reset_counter()

    normalized = NormalizedScores(
      extroverted_introverted=0.5, sensing_intuition=0.5,
      thinking_feeling=0.5, judging_perceiving=0.5,
    )

    profile = pg.generate(normalized, full_answers, all_questions, scorer=scorer, aggregator=aggregator)

    dm = profile.decision_model
    assert len(dm.priorities) > 0
    assert len(dm.priority_weights) > 0
    assert any(w == 1.0 for w in dm.priority_weights.values())
    assert len(dm.tradeoff_tendencies) == 8

  def test_existing_categories_produce_decision_rules(
    self, full_answers, all_questions, scorer, aggregator
  ):
    """既存カテゴリ（BOS/COM/LIF）の回答から decision_rules にルールが含まれる"""
    pg = ProfileGenerator()
    pg.reset_counter()

    normalized = NormalizedScores(
      extroverted_introverted=0.5, sensing_intuition=0.5,
      thinking_feeling=0.5, judging_perceiving=0.5,
    )

    profile = pg.generate(normalized, full_answers, all_questions, scorer=scorer, aggregator=aggregator)

    rules = profile.decision_rules
    assert rules is not None
    # 既存カテゴリの質問IDからルールが生成されている
    bos_rules = [r for r in rules if r["question_id"].startswith("bos_")]
    com_rules = [r for r in rules if r["question_id"].startswith("com_")]
    lif_rules = [r for r in rules if r["question_id"].startswith("lif_")]

    assert len(bos_rules) > 0, "BOS answers should produce rules"
    assert len(com_rules) > 0, "COM answers should produce rules"
    assert len(lif_rules) > 0, "LIF answers should produce rules"

  def test_rule_hierarchy_aggregation(
    self, full_answers, all_questions, scorer, aggregator
  ):
    """Rule Hierarchy に全カテゴリのルールが分類されている"""
    pg = ProfileGenerator()
    pg.reset_counter()

    normalized = NormalizedScores(
      extroverted_introverted=0.5, sensing_intuition=0.5,
      thinking_feeling=0.5, judging_perceiving=0.5,
    )

    profile = pg.generate(normalized, full_answers, all_questions, scorer=scorer, aggregator=aggregator)

    rh = profile.rule_hierarchy
    assert rh is not None
    total_rules = (
      len(rh.core_invariants)
      + len(rh.context_rules)
      + len(rh.exceptions)
      + len(rh.preferences)
    )
    # 全回答に対応するルールが集約されている
    assert total_rules > 0
    assert total_rules == len(profile.decision_rules)

  def test_prompt_engine_includes_decision_framework(
    self, full_answers, all_questions, scorer, aggregator
  ):
    """PromptEngine が Decision Framework をプロンプトに含める"""
    pg = ProfileGenerator()
    pg.reset_counter()

    normalized = NormalizedScores(
      extroverted_introverted=0.5, sensing_intuition=0.5,
      thinking_feeling=0.5, judging_perceiving=0.5,
    )

    profile = pg.generate(normalized, full_answers, all_questions, scorer=scorer, aggregator=aggregator)

    engine = PromptEngine(max_tokens=8000)
    result = engine.generate(profile)

    assert "## Decision Framework" in result.prompt
    assert "## Known Weaknesses & Guardrails" in result.prompt

  def test_base_os_unaffected_by_decision_engine(
    self, full_answers, all_questions, scorer, aggregator
  ):
    """4軸スコアの base_os 計算が decision engine に影響されない"""
    pg = ProfileGenerator()

    normalized = NormalizedScores(
      extroverted_introverted=0.7, sensing_intuition=0.3,
      thinking_feeling=0.8, judging_perceiving=0.4,
    )

    # scorer なし（従来）
    pg._counter = 0
    profile_without = pg.generate(normalized, full_answers, all_questions)

    # scorer あり（新規）
    pg._counter = 0
    profile_with = pg.generate(normalized, full_answers, all_questions, scorer=scorer, aggregator=aggregator)

    # base_os は完全に同一
    assert profile_without.base_os.axes == profile_with.base_os.axes
    assert profile_without.base_os.decision_style == profile_with.base_os.decision_style
    assert profile_without.base_os.do_not_list == profile_with.base_os.do_not_list
