"""DecisionScorer ユニットテスト"""

from unittest.mock import MagicMock

import pytest

from app.decision_engine.scorer import DecisionScorer, MappingNotFoundError
from app.models.mapping import (
  AxisBound,
  MappingDictionary,
  MappingEntry,
  MappingMetadata,
  MappingScores,
  ModeConfig,
  TheoreticalBounds,
)


# --- Fixtures ---

ZERO_SCORES = MappingScores(
  extroverted_introverted=0,
  sensing_intuition=0,
  thinking_feeling=0,
  judging_perceiving=0,
)

METADATA = MappingMetadata(
  version="3.0",
  theoretical_bounds=TheoreticalBounds(
    extroverted_introverted=AxisBound(min=-120, max=156),
    sensing_intuition=AxisBound(min=-106, max=131),
    thinking_feeling=AxisBound(min=-129, max=137),
    judging_perceiving=AxisBound(min=-119, max=137),
  ),
)


@pytest.fixture
def mapping_loader() -> MagicMock:
  """テスト用 MappingDictionaryLoader モック"""
  loader = MagicMock()
  loader.get.return_value = MappingDictionary(
    metadata=METADATA,
    mappings=[
      # decision_model エントリ
      MappingEntry(
        question_id="dm_001",
        choice_id="a",
        scores=ZERO_SCORES,
        priority_labels=["root_cause_first"],
        weights={"root_cause_first": 8},
        policy_text="when_decision: 根本原因の特定を最優先する",
      ),
      MappingEntry(
        question_id="dm_001",
        choice_id="b",
        scores=ZERO_SCORES,
        priority_labels=["customer_first"],
        weights={"customer_first": 7},
        policy_text="when_decision: 顧客への影響を最小化する",
      ),
      # tradeoff_scenarios エントリ
      MappingEntry(
        question_id="ts_001",
        choice_id="a",
        scores=ZERO_SCORES,
        conflict_pair="speed_vs_quality",
        tendency_score=0.2,
        policy_text="when_speed_quality_conflict: スピードを優先する",
      ),
      MappingEntry(
        question_id="ts_001",
        choice_id="b",
        scores=ZERO_SCORES,
        conflict_pair="speed_vs_quality",
        tendency_score=0.8,
        policy_text="when_speed_quality_conflict: 品質を確保する",
      ),
      # failure_patterns エントリ
      MappingEntry(
        question_id="fp_001",
        choice_id="a",
        scores=ZERO_SCORES,
        subcategory="degradation_triggers",
        label="睡眠不足時に判断力が著しく低下する",
        policy_text="when_degradation: 睡眠不足時は重要判断を避ける",
      ),
      MappingEntry(
        question_id="fp_001",
        choice_id="b",
        scores=ZERO_SCORES,
        subcategory="procrastination_patterns",
        label="大きなタスクを前に手を付けられなくなる",
        policy_text="when_procrastination: タスクを小分けにする",
      ),
      # context_adaptation エントリ
      MappingEntry(
        question_id="ca_001",
        choice_id="a",
        scores=ZERO_SCORES,
        mode_name="executive_report",
        mode_config=ModeConfig(
          tone="formal", detail="minimal", focus="結論とインパクト"
        ),
        trigger="経営層への報告時",
        policy_text="when_executive_audience: 結論ファーストで要点のみ伝える",
      ),
      MappingEntry(
        question_id="ca_001",
        choice_id="b",
        scores=ZERO_SCORES,
        mode_name="team_direction",
        mode_config=ModeConfig(
          tone="supportive", detail="standard", focus="背景と期待する行動"
        ),
        trigger="チームメンバーへの指示時",
        policy_text="when_team_audience: 背景を説明し期待する行動を明示する",
      ),
      # 既存エントリ（decision engine 固有フィールドなし）
      MappingEntry(
        question_id="bos_001",
        choice_id="a",
        scores=MappingScores(
          extroverted_introverted=8,
          sensing_intuition=0,
          thinking_feeling=-2,
          judging_perceiving=-3,
        ),
        policy_text="when_crisis: 即座にチームを集め協働解決を試みる",
      ),
    ],
  )
  return loader


@pytest.fixture
def scorer(mapping_loader: MagicMock) -> DecisionScorer:
  """テスト用 DecisionScorer"""
  return DecisionScorer(mapping_loader)


# --- score_decision_model ---


class TestScoreDecisionModel:
  def test_valid_entry(self, scorer: DecisionScorer) -> None:
    """正常なマッピングで priority_label → weight を返す"""
    result = scorer.score_decision_model("dm_001", "a")
    assert result == {"root_cause_first": 8}

  def test_valid_entry_choice_b(self, scorer: DecisionScorer) -> None:
    """別の選択肢でも正しく返す"""
    result = scorer.score_decision_model("dm_001", "b")
    assert result == {"customer_first": 7}

  def test_not_found_raises(self, scorer: DecisionScorer) -> None:
    """存在しないペアで MappingNotFoundError を送出"""
    with pytest.raises(MappingNotFoundError) as exc_info:
      scorer.score_decision_model("dm_999", "a")
    assert exc_info.value.question_id == "dm_999"
    assert exc_info.value.choice_id == "a"

  def test_entry_without_priority_labels_raises(self, scorer: DecisionScorer) -> None:
    """decision engine フィールドを持たないエントリでエラー"""
    with pytest.raises(MappingNotFoundError):
      scorer.score_decision_model("bos_001", "a")


# --- score_tradeoff ---


class TestScoreTradeoff:
  def test_valid_choice_a(self, scorer: DecisionScorer) -> None:
    """choice "a" で conflict_pair と低 tendency_score を返す"""
    pair, score = scorer.score_tradeoff("ts_001", "a")
    assert pair == "speed_vs_quality"
    assert score == 0.2

  def test_valid_choice_b(self, scorer: DecisionScorer) -> None:
    """choice "b" で conflict_pair と高 tendency_score を返す"""
    pair, score = scorer.score_tradeoff("ts_001", "b")
    assert pair == "speed_vs_quality"
    assert score == 0.8

  def test_not_found_raises(self, scorer: DecisionScorer) -> None:
    """存在しないペアで MappingNotFoundError を送出"""
    with pytest.raises(MappingNotFoundError):
      scorer.score_tradeoff("ts_999", "a")

  def test_entry_without_conflict_pair_raises(self, scorer: DecisionScorer) -> None:
    """tradeoff フィールドを持たないエントリでエラー"""
    with pytest.raises(MappingNotFoundError):
      scorer.score_tradeoff("dm_001", "a")


# --- score_failure_pattern ---


class TestScoreFailurePattern:
  def test_degradation_triggers(self, scorer: DecisionScorer) -> None:
    """degradation_triggers サブカテゴリに分類される"""
    subcategory, label = scorer.score_failure_pattern("fp_001", "a")
    assert subcategory == "degradation_triggers"
    assert label == "睡眠不足時に判断力が著しく低下する"

  def test_procrastination_patterns(self, scorer: DecisionScorer) -> None:
    """procrastination_patterns サブカテゴリに分類される"""
    subcategory, label = scorer.score_failure_pattern("fp_001", "b")
    assert subcategory == "procrastination_patterns"
    assert label == "大きなタスクを前に手を付けられなくなる"

  def test_not_found_raises(self, scorer: DecisionScorer) -> None:
    """存在しないペアで MappingNotFoundError を送出"""
    with pytest.raises(MappingNotFoundError):
      scorer.score_failure_pattern("fp_999", "a")

  def test_entry_without_subcategory_raises(self, scorer: DecisionScorer) -> None:
    """failure パターンフィールドを持たないエントリでエラー"""
    with pytest.raises(MappingNotFoundError):
      scorer.score_failure_pattern("dm_001", "a")


# --- score_context_adaptation ---


class TestScoreContextAdaptation:
  def test_executive_report_mode(self, scorer: DecisionScorer) -> None:
    """executive_report モードの設定を返す"""
    result = scorer.score_context_adaptation("ca_001", "a")
    assert result == {
      "executive_report": {
        "tone": "formal",
        "detail": "minimal",
        "focus": "結論とインパクト",
      }
    }

  def test_team_direction_mode(self, scorer: DecisionScorer) -> None:
    """team_direction モードの設定を返す"""
    result = scorer.score_context_adaptation("ca_001", "b")
    assert result == {
      "team_direction": {
        "tone": "supportive",
        "detail": "standard",
        "focus": "背景と期待する行動",
      }
    }

  def test_not_found_raises(self, scorer: DecisionScorer) -> None:
    """存在しないペアで MappingNotFoundError を送出"""
    with pytest.raises(MappingNotFoundError):
      scorer.score_context_adaptation("ca_999", "a")

  def test_entry_without_mode_config_raises(self, scorer: DecisionScorer) -> None:
    """context_adaptation フィールドを持たないエントリでエラー"""
    with pytest.raises(MappingNotFoundError):
      scorer.score_context_adaptation("dm_001", "a")


# --- normalize_weights ---


class TestNormalizeWeights:
  def test_empty_dict(self, scorer: DecisionScorer) -> None:
    """空辞書は空辞書を返す"""
    assert scorer.normalize_weights({}) == {}

  def test_all_same_values(self, scorer: DecisionScorer) -> None:
    """全値が同一なら全て 1.0"""
    result = scorer.normalize_weights({"a": 5, "b": 5, "c": 5})
    assert result == {"a": 1.0, "b": 1.0, "c": 1.0}

  def test_normal_case(self, scorer: DecisionScorer) -> None:
    """通常の正規化計算"""
    result = scorer.normalize_weights({"low": 2, "mid": 6, "high": 10})
    # (2-2)/(10-2) = 0.0, (6-2)/(10-2) = 0.5, (10-2)/(10-2) = 1.0
    assert result == {"low": 0.0, "mid": 0.5, "high": 1.0}

  def test_max_is_always_one(self, scorer: DecisionScorer) -> None:
    """最大値は常に 1.0"""
    result = scorer.normalize_weights({"x": 3, "y": 7, "z": 15})
    assert result["z"] == 1.0

  def test_min_is_always_zero(self, scorer: DecisionScorer) -> None:
    """最小値は常に 0.0"""
    result = scorer.normalize_weights({"x": 1, "y": 5, "z": 10})
    assert result["x"] == 0.0

  def test_single_entry(self, scorer: DecisionScorer) -> None:
    """1エントリの場合は 1.0"""
    result = scorer.normalize_weights({"only": 42})
    assert result == {"only": 1.0}

  def test_two_entries(self, scorer: DecisionScorer) -> None:
    """2エントリの場合"""
    result = scorer.normalize_weights({"a": 0, "b": 10})
    assert result == {"a": 0.0, "b": 1.0}

  def test_rounded_to_two_decimal_places(self, scorer: DecisionScorer) -> None:
    """結果は小数点2桁に丸められる"""
    # (1-0)/(3-0) = 0.333... → 0.33
    result = scorer.normalize_weights({"a": 0, "b": 1, "c": 3})
    assert result["b"] == 0.33


# --- MappingNotFoundError ---


class TestMappingNotFoundError:
  def test_attributes(self) -> None:
    """例外が question_id と choice_id を保持する"""
    err = MappingNotFoundError("q1", "x")
    assert err.question_id == "q1"
    assert err.choice_id == "x"

  def test_message(self) -> None:
    """例外メッセージのフォーマット"""
    err = MappingNotFoundError("q1", "x")
    assert str(err) == "No mapping found for (q1, x)"
