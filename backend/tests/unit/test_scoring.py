"""ScoringEngine ユニットテスト"""

import pytest

from app.core.scoring import MappingNotFoundError, ScoringEngine
from app.models.mapping import (
  AxisBound,
  MappingDictionary,
  MappingEntry,
  MappingMetadata,
  MappingScores,
  TheoreticalBounds,
)
from app.models.scores import AxisScores


# --- Fixtures ---


@pytest.fixture
def sample_mapping_dict() -> MappingDictionary:
  """テスト用のマッピング辞書"""
  return MappingDictionary(
    metadata=MappingMetadata(
      version="1.0",
      theoretical_bounds=TheoreticalBounds(
        extroverted_introverted=AxisBound(min=-30, max=30),
        sensing_intuition=AxisBound(min=-25, max=25),
        thinking_feeling=AxisBound(min=-28, max=28),
        judging_perceiving=AxisBound(min=-26, max=26),
      ),
    ),
    mappings=[
      MappingEntry(
        question_id="q1",
        choice_id="a",
        scores=MappingScores(
          extroverted_introverted=5,
          sensing_intuition=-3,
          thinking_feeling=2,
          judging_perceiving=0,
        ),
      ),
      MappingEntry(
        question_id="q1",
        choice_id="b",
        scores=MappingScores(
          extroverted_introverted=-5,
          sensing_intuition=3,
          thinking_feeling=-2,
          judging_perceiving=1,
        ),
      ),
      MappingEntry(
        question_id="q2",
        choice_id="a",
        scores=MappingScores(
          extroverted_introverted=3,
          sensing_intuition=0,
          thinking_feeling=-4,
          judging_perceiving=7,
        ),
      ),
    ],
  )


@pytest.fixture
def engine(sample_mapping_dict: MappingDictionary) -> ScoringEngine:
  """テスト用のScoringEngineインスタンス"""
  return ScoringEngine(sample_mapping_dict)


@pytest.fixture
def zero_scores() -> AxisScores:
  """初期スコア（全軸0）"""
  return AxisScores()


# --- apply_score tests ---


class TestApplyScore:
  """apply_score メソッドのテスト"""

  def test_applies_score_from_mapping(
    self, engine: ScoringEngine, zero_scores: AxisScores
  ) -> None:
    """マッピングに存在する組み合わせで正しくスコアが加算される"""
    result = engine.apply_score(zero_scores, "q1", "a")

    assert result.extroverted_introverted == 5
    assert result.sensing_intuition == -3
    assert result.thinking_feeling == 2
    assert result.judging_perceiving == 0

  def test_accumulates_scores(
    self, engine: ScoringEngine, zero_scores: AxisScores
  ) -> None:
    """複数回の適用でスコアが累積加算される"""
    after_q1a = engine.apply_score(zero_scores, "q1", "a")
    after_q2a = engine.apply_score(after_q1a, "q2", "a")

    assert after_q2a.extroverted_introverted == 5 + 3
    assert after_q2a.sensing_intuition == -3 + 0
    assert after_q2a.thinking_feeling == 2 + (-4)
    assert after_q2a.judging_perceiving == 0 + 7

  def test_returns_new_instance(
    self, engine: ScoringEngine, zero_scores: AxisScores
  ) -> None:
    """元のスコアオブジェクトを変更せず、新しいインスタンスを返す"""
    result = engine.apply_score(zero_scores, "q1", "a")

    # 元のスコアは変更されていない
    assert zero_scores.extroverted_introverted == 0
    assert zero_scores.sensing_intuition == 0
    assert zero_scores.thinking_feeling == 0
    assert zero_scores.judging_perceiving == 0

    # 結果は異なるオブジェクト
    assert result is not zero_scores

  def test_with_non_zero_initial_scores(self, engine: ScoringEngine) -> None:
    """初期スコアが0でない場合にも正しく加算される"""
    initial = AxisScores(
      extroverted_introverted=10,
      sensing_intuition=-5,
      thinking_feeling=3,
      judging_perceiving=-2,
    )
    result = engine.apply_score(initial, "q1", "b")

    assert result.extroverted_introverted == 10 + (-5)
    assert result.sensing_intuition == -5 + 3
    assert result.thinking_feeling == 3 + (-2)
    assert result.judging_perceiving == -2 + 1

  def test_raises_error_for_missing_mapping(
    self, engine: ScoringEngine, zero_scores: AxisScores
  ) -> None:
    """マッピングに存在しない組み合わせで MappingNotFoundError を発生"""
    with pytest.raises(MappingNotFoundError) as exc_info:
      engine.apply_score(zero_scores, "q99", "z")

    assert exc_info.value.question_id == "q99"
    assert exc_info.value.choice_id == "z"

  def test_missing_mapping_does_not_modify_scores(
    self, engine: ScoringEngine, zero_scores: AxisScores
  ) -> None:
    """マッピング不在時にスコアが変更されないことを確認"""
    original_ei = zero_scores.extroverted_introverted
    original_sn = zero_scores.sensing_intuition
    original_tf = zero_scores.thinking_feeling
    original_jp = zero_scores.judging_perceiving

    with pytest.raises(MappingNotFoundError):
      engine.apply_score(zero_scores, "nonexistent", "x")

    # スコアが変更されていない
    assert zero_scores.extroverted_introverted == original_ei
    assert zero_scores.sensing_intuition == original_sn
    assert zero_scores.thinking_feeling == original_tf
    assert zero_scores.judging_perceiving == original_jp

  def test_valid_question_invalid_choice_raises_error(
    self, engine: ScoringEngine, zero_scores: AxisScores
  ) -> None:
    """有効な question_id でも無効な choice_id ならエラー"""
    with pytest.raises(MappingNotFoundError) as exc_info:
      engine.apply_score(zero_scores, "q1", "z")

    assert exc_info.value.question_id == "q1"
    assert exc_info.value.choice_id == "z"


# --- apply_neutral tests ---


class TestApplyNeutral:
  """apply_neutral メソッドのテスト"""

  def test_returns_same_scores(
    self, engine: ScoringEngine, zero_scores: AxisScores
  ) -> None:
    """ゼロスコアが変更されずに返る"""
    result = engine.apply_neutral(zero_scores)

    assert result.extroverted_introverted == 0
    assert result.sensing_intuition == 0
    assert result.thinking_feeling == 0
    assert result.judging_perceiving == 0

  def test_returns_same_instance(
    self, engine: ScoringEngine, zero_scores: AxisScores
  ) -> None:
    """同一オブジェクトが返る（identity operation）"""
    result = engine.apply_neutral(zero_scores)
    assert result is zero_scores

  def test_preserves_non_zero_scores(self, engine: ScoringEngine) -> None:
    """非ゼロスコアも変更されない"""
    scores = AxisScores(
      extroverted_introverted=15,
      sensing_intuition=-8,
      thinking_feeling=22,
      judging_perceiving=-3,
    )
    result = engine.apply_neutral(scores)

    assert result.extroverted_introverted == 15
    assert result.sensing_intuition == -8
    assert result.thinking_feeling == 22
    assert result.judging_perceiving == -3
    assert result is scores


# --- MappingNotFoundError tests ---


class TestMappingNotFoundError:
  """MappingNotFoundError のテスト"""

  def test_error_message_format(self) -> None:
    """エラーメッセージにquestion_idとchoice_idが含まれる"""
    error = MappingNotFoundError("q1", "x")
    assert "q1" in str(error)
    assert "x" in str(error)

  def test_error_attributes(self) -> None:
    """question_id と choice_id 属性が正しくセットされる"""
    error = MappingNotFoundError("test_q", "test_c")
    assert error.question_id == "test_q"
    assert error.choice_id == "test_c"

  def test_is_exception(self) -> None:
    """Exception のサブクラスであること"""
    assert issubclass(MappingNotFoundError, Exception)


# --- ScoringEngine constructor tests ---


class TestScoringEngineInit:
  """ScoringEngine 初期化のテスト"""

  def test_builds_lookup_from_mapping(
    self, engine: ScoringEngine, sample_mapping_dict: MappingDictionary
  ) -> None:
    """全マッピングエントリがルックアップに含まれる"""
    assert len(engine._lookup) == len(sample_mapping_dict.mappings)

  def test_empty_mappings(self) -> None:
    """空のマッピングでも正常に初期化される"""
    empty_dict = MappingDictionary(
      metadata=MappingMetadata(
        version="1.0",
        theoretical_bounds=TheoreticalBounds(
          extroverted_introverted=AxisBound(min=-30, max=30),
          sensing_intuition=AxisBound(min=-25, max=25),
          thinking_feeling=AxisBound(min=-28, max=28),
          judging_perceiving=AxisBound(min=-26, max=26),
        ),
      ),
      mappings=[],
    )
    engine = ScoringEngine(empty_dict)
    assert len(engine._lookup) == 0
