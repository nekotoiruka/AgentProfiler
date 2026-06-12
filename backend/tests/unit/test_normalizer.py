"""Normalizer ユニットテスト"""

import logging

import pytest

from app.models import AxisScores, NormalizedScores, TheoreticalBounds, AxisBound
from app.core.normalizer import Normalizer


@pytest.fixture
def bounds() -> TheoreticalBounds:
  """標準的な理論的境界値"""
  return TheoreticalBounds(
    extroverted_introverted=AxisBound(min=-30, max=30),
    sensing_intuition=AxisBound(min=-25, max=25),
    thinking_feeling=AxisBound(min=-28, max=28),
    judging_perceiving=AxisBound(min=-26, max=26),
  )


@pytest.fixture
def normalizer(bounds: TheoreticalBounds) -> Normalizer:
  return Normalizer(bounds)


class TestNormalizeBasic:
  """基本的な正規化動作"""

  def test_midpoint_returns_half(self, normalizer: Normalizer) -> None:
    """rawがmin-maxの中間値 → 0.5"""
    raw = AxisScores(
      extroverted_introverted=0,
      sensing_intuition=0,
      thinking_feeling=0,
      judging_perceiving=0,
    )
    result = normalizer.normalize(raw)
    assert result.extroverted_introverted == 0.5
    assert result.sensing_intuition == 0.5
    assert result.thinking_feeling == 0.5
    assert result.judging_perceiving == 0.5

  def test_min_returns_zero(self, normalizer: Normalizer) -> None:
    """rawがmin値 → 0.0"""
    raw = AxisScores(
      extroverted_introverted=-30,
      sensing_intuition=-25,
      thinking_feeling=-28,
      judging_perceiving=-26,
    )
    result = normalizer.normalize(raw)
    assert result.extroverted_introverted == 0.0
    assert result.sensing_intuition == 0.0
    assert result.thinking_feeling == 0.0
    assert result.judging_perceiving == 0.0

  def test_max_returns_one(self, normalizer: Normalizer) -> None:
    """rawがmax値 → 1.0"""
    raw = AxisScores(
      extroverted_introverted=30,
      sensing_intuition=25,
      thinking_feeling=28,
      judging_perceiving=26,
    )
    result = normalizer.normalize(raw)
    assert result.extroverted_introverted == 1.0
    assert result.sensing_intuition == 1.0
    assert result.thinking_feeling == 1.0
    assert result.judging_perceiving == 1.0

  def test_arbitrary_value(self, normalizer: Normalizer) -> None:
    """具体的なスコア値の正規化検証"""
    # E/I: (15 - (-30)) / (30 - (-30)) = 45/60 = 0.75
    raw = AxisScores(
      extroverted_introverted=15,
      sensing_intuition=-10,
      thinking_feeling=14,
      judging_perceiving=0,
    )
    result = normalizer.normalize(raw)
    assert result.extroverted_introverted == 0.75
    # S/N: (-10 - (-25)) / (25 - (-25)) = 15/50 = 0.30
    assert result.sensing_intuition == 0.30
    # T/F: (14 - (-28)) / (28 - (-28)) = 42/56 = 0.75
    assert result.thinking_feeling == 0.75
    # J/P: (0 - (-26)) / (26 - (-26)) = 26/52 = 0.50
    assert result.judging_perceiving == 0.50


class TestClamp:
  """クランプ: 範囲外スコアの制限"""

  def test_below_min_clamps_to_zero(self, normalizer: Normalizer) -> None:
    """rawがmin未満 → 0.0にクランプ"""
    raw = AxisScores(
      extroverted_introverted=-50,
      sensing_intuition=0,
      thinking_feeling=0,
      judging_perceiving=0,
    )
    result = normalizer.normalize(raw)
    assert result.extroverted_introverted == 0.0

  def test_above_max_clamps_to_one(self, normalizer: Normalizer) -> None:
    """rawがmax超 → 1.0にクランプ"""
    raw = AxisScores(
      extroverted_introverted=100,
      sensing_intuition=0,
      thinking_feeling=0,
      judging_perceiving=0,
    )
    result = normalizer.normalize(raw)
    assert result.extroverted_introverted == 1.0


class TestRoundHalfUp:
  """round-half-up 小数点2桁の丸め検証"""

  def test_round_half_up_rounds_up(self) -> None:
    """0.5の端数はround-half-upで切り上げ

    bounds (0, 1000) で raw=5 → 5/1000 = 0.005 → round-half-up → 0.01
    """
    bounds = TheoreticalBounds(
      extroverted_introverted=AxisBound(min=0, max=1000),
      sensing_intuition=AxisBound(min=0, max=1000),
      thinking_feeling=AxisBound(min=0, max=1000),
      judging_perceiving=AxisBound(min=0, max=1000),
    )
    normalizer = Normalizer(bounds)
    raw = AxisScores(
      extroverted_introverted=5,
      sensing_intuition=0,
      thinking_feeling=0,
      judging_perceiving=0,
    )
    result = normalizer.normalize(raw)
    # 5/1000 = 0.005 → round-half-up → 0.01
    assert result.extroverted_introverted == 0.01

  def test_two_decimal_places(self) -> None:
    """結果が常に小数点2桁"""
    bounds = TheoreticalBounds(
      extroverted_introverted=AxisBound(min=0, max=3),
      sensing_intuition=AxisBound(min=0, max=3),
      thinking_feeling=AxisBound(min=0, max=3),
      judging_perceiving=AxisBound(min=0, max=3),
    )
    normalizer = Normalizer(bounds)
    # 1/3 = 0.3333... → round-half-up → 0.33
    raw = AxisScores(
      extroverted_introverted=1,
      sensing_intuition=2,
      thinking_feeling=0,
      judging_perceiving=3,
    )
    result = normalizer.normalize(raw)
    assert result.extroverted_introverted == 0.33
    # 2/3 = 0.6666... → round-half-up → 0.67
    assert result.sensing_intuition == 0.67


class TestMinEqualsMax:
  """min == max の場合のフォールバック動作"""

  def test_returns_half_when_min_equals_max(self) -> None:
    """min == max → 0.5を返す"""
    bounds = TheoreticalBounds(
      extroverted_introverted=AxisBound(min=10, max=10),
      sensing_intuition=AxisBound(min=-5, max=25),
      thinking_feeling=AxisBound(min=-5, max=25),
      judging_perceiving=AxisBound(min=-5, max=25),
    )
    normalizer = Normalizer(bounds)
    raw = AxisScores(
      extroverted_introverted=10,
      sensing_intuition=0,
      thinking_feeling=0,
      judging_perceiving=0,
    )
    result = normalizer.normalize(raw)
    assert result.extroverted_introverted == 0.5

  def test_logs_warning_when_min_equals_max(self, caplog: pytest.LogCaptureFixture) -> None:
    """min == max → warningログが出力される"""
    bounds = TheoreticalBounds(
      extroverted_introverted=AxisBound(min=0, max=0),
      sensing_intuition=AxisBound(min=-5, max=25),
      thinking_feeling=AxisBound(min=-5, max=25),
      judging_perceiving=AxisBound(min=-5, max=25),
    )
    normalizer = Normalizer(bounds)
    raw = AxisScores(
      extroverted_introverted=5,
      sensing_intuition=0,
      thinking_feeling=0,
      judging_perceiving=0,
    )

    with caplog.at_level(logging.WARNING):
      normalizer.normalize(raw)

    assert any(
      "extroverted_introverted" in record.message and "min == max" in record.message
      for record in caplog.records
    )


class TestReturnType:
  """返り値の型チェック"""

  def test_returns_normalized_scores(self, normalizer: Normalizer) -> None:
    """normalize()はNormalizedScoresを返す"""
    raw = AxisScores(
      extroverted_introverted=0,
      sensing_intuition=0,
      thinking_feeling=0,
      judging_perceiving=0,
    )
    result = normalizer.normalize(raw)
    assert isinstance(result, NormalizedScores)

  def test_all_values_are_floats(self, normalizer: Normalizer) -> None:
    """全軸の値がfloat"""
    raw = AxisScores(
      extroverted_introverted=10,
      sensing_intuition=-5,
      thinking_feeling=20,
      judging_perceiving=-15,
    )
    result = normalizer.normalize(raw)
    assert isinstance(result.extroverted_introverted, float)
    assert isinstance(result.sensing_intuition, float)
    assert isinstance(result.thinking_feeling, float)
    assert isinstance(result.judging_perceiving, float)
