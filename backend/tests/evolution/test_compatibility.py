"""CompatibilityEngine のユニットテスト

4軸コサイン類似度・相補性スコア・分類・レコメンドの
動作を検証する。
"""

import pytest

from app.evolution.compatibility import (
  CompatibilityEngine,
  CompatibilityReport,
  Recommendation,
  SimilarityClassification,
)


@pytest.fixture
def engine() -> CompatibilityEngine:
  """デフォルト重みの CompatibilityEngine を返す。"""
  return CompatibilityEngine()


@pytest.fixture
def custom_engine() -> CompatibilityEngine:
  """カスタム重みの CompatibilityEngine を返す。"""
  return CompatibilityEngine(
    similarity_weight=0.5, complementarity_weight=0.5
  )


class TestComputeSimilarity:
  """compute_similarity() のテスト"""

  def test_identical_vectors(self, engine: CompatibilityEngine) -> None:
    """同一ベクトルの類似度は 1.0 であること。"""
    axes = [0.8, 0.3, 0.6, 0.5]
    result = engine.compute_similarity(axes, axes)
    assert result == pytest.approx(1.0, abs=1e-6)

  def test_orthogonal_vectors(self, engine: CompatibilityEngine) -> None:
    """直交ベクトルの類似度は 0.0 であること。"""
    # [1, 0, 0, 0] と [0, 1, 0, 0] は直交
    axes_a = [1.0, 0.0, 0.0, 0.0]
    axes_b = [0.0, 1.0, 0.0, 0.0]
    result = engine.compute_similarity(axes_a, axes_b)
    assert result == pytest.approx(0.0, abs=1e-6)

  def test_zero_vector(self, engine: CompatibilityEngine) -> None:
    """ゼロベクトルが含まれる場合は 0.0 を返すこと。"""
    axes_a = [0.0, 0.0, 0.0, 0.0]
    axes_b = [0.5, 0.5, 0.5, 0.5]
    result = engine.compute_similarity(axes_a, axes_b)
    assert result == 0.0

  def test_similar_vectors(self, engine: CompatibilityEngine) -> None:
    """類似ベクトルは高い類似度を示すこと。"""
    axes_a = [0.8, 0.7, 0.6, 0.9]
    axes_b = [0.75, 0.72, 0.58, 0.88]
    result = engine.compute_similarity(axes_a, axes_b)
    assert result > 0.99

  def test_dissimilar_vectors(self, engine: CompatibilityEngine) -> None:
    """異なる方向のベクトルは低い類似度を示すこと。"""
    axes_a = [0.9, 0.1, 0.9, 0.1]
    axes_b = [0.1, 0.9, 0.1, 0.9]
    result = engine.compute_similarity(axes_a, axes_b)
    assert result < 0.5

  def test_result_in_range(self, engine: CompatibilityEngine) -> None:
    """結果が 0.0〜1.0 の範囲内であること。"""
    axes_a = [0.3, 0.7, 0.2, 0.9]
    axes_b = [0.8, 0.1, 0.6, 0.4]
    result = engine.compute_similarity(axes_a, axes_b)
    assert 0.0 <= result <= 1.0


class TestComputeComplementarity:
  """compute_complementarity() のテスト"""

  def test_identical_vectors(self, engine: CompatibilityEngine) -> None:
    """同一ベクトルの相補性は 0.0 であること。"""
    axes = [0.5, 0.5, 0.5, 0.5]
    result = engine.compute_complementarity(axes, axes)
    assert result == pytest.approx(0.0, abs=1e-6)

  def test_maximum_difference(self, engine: CompatibilityEngine) -> None:
    """最大差 (全軸 1.0 差) の相補性は 1.0 であること。"""
    axes_a = [0.0, 0.0, 0.0, 0.0]
    axes_b = [1.0, 1.0, 1.0, 1.0]
    result = engine.compute_complementarity(axes_a, axes_b)
    assert result == pytest.approx(1.0, abs=1e-6)

  def test_partial_difference(self, engine: CompatibilityEngine) -> None:
    """部分的な差の相補性が正しく計算されること。"""
    axes_a = [0.2, 0.8, 0.3, 0.7]
    axes_b = [0.7, 0.3, 0.8, 0.2]
    # diff = [0.5, 0.5, 0.5, 0.5] → average = 0.5
    result = engine.compute_complementarity(axes_a, axes_b)
    assert result == pytest.approx(0.5, abs=1e-6)

  def test_result_in_range(self, engine: CompatibilityEngine) -> None:
    """結果が 0.0〜1.0 の範囲内であること。"""
    axes_a = [0.1, 0.9, 0.4, 0.6]
    axes_b = [0.6, 0.2, 0.7, 0.3]
    result = engine.compute_complementarity(axes_a, axes_b)
    assert 0.0 <= result <= 1.0


class TestClassify:
  """classify() のテスト"""

  def test_highly_similar(self, engine: CompatibilityEngine) -> None:
    """similarity >= 0.9 で HIGHLY_SIMILAR に分類されること。"""
    result = engine.classify(0.95, 0.1)
    assert result == SimilarityClassification.HIGHLY_SIMILAR

  def test_highly_similar_boundary(self, engine: CompatibilityEngine) -> None:
    """similarity == 0.9 で HIGHLY_SIMILAR に分類されること。"""
    result = engine.classify(0.9, 0.3)
    assert result == SimilarityClassification.HIGHLY_SIMILAR

  def test_moderately_similar(self, engine: CompatibilityEngine) -> None:
    """0.7 <= similarity < 0.9 で MODERATELY_SIMILAR に分類されること。"""
    result = engine.classify(0.8, 0.2)
    assert result == SimilarityClassification.MODERATELY_SIMILAR

  def test_moderately_similar_boundary(
    self, engine: CompatibilityEngine
  ) -> None:
    """similarity == 0.7 で MODERATELY_SIMILAR に分類されること。"""
    result = engine.classify(0.7, 0.3)
    assert result == SimilarityClassification.MODERATELY_SIMILAR

  def test_complementary(self, engine: CompatibilityEngine) -> None:
    """complementarity >= 0.5 かつ similarity < 0.7 で COMPLEMENTARY。"""
    result = engine.classify(0.5, 0.6)
    assert result == SimilarityClassification.COMPLEMENTARY

  def test_complementary_boundary(self, engine: CompatibilityEngine) -> None:
    """complementarity == 0.5 で COMPLEMENTARY に分類されること。"""
    result = engine.classify(0.4, 0.5)
    assert result == SimilarityClassification.COMPLEMENTARY

  def test_contrasting(self, engine: CompatibilityEngine) -> None:
    """どの条件にも該当しない場合に CONTRASTING に分類されること。"""
    result = engine.classify(0.3, 0.3)
    assert result == SimilarityClassification.CONTRASTING

  def test_similarity_priority_over_complementarity(
    self, engine: CompatibilityEngine
  ) -> None:
    """similarity が高い場合は complementarity に関わらず similarity 優先。"""
    # sim >= 0.9 なら comp がどんなに高くても HIGHLY_SIMILAR
    result = engine.classify(0.95, 0.9)
    assert result == SimilarityClassification.HIGHLY_SIMILAR


class TestComputeCompatibility:
  """compute_compatibility() のテスト"""

  def test_returns_compatibility_report(
    self, engine: CompatibilityEngine
  ) -> None:
    """CompatibilityReport が返されること。"""
    axes_a = [0.8, 0.7, 0.6, 0.9]
    axes_b = [0.75, 0.72, 0.58, 0.88]
    result = engine.compute_compatibility(axes_a, axes_b)
    assert isinstance(result, CompatibilityReport)

  def test_overall_score_range(self, engine: CompatibilityEngine) -> None:
    """overall_score が 0〜100 の範囲内であること。"""
    axes_a = [0.3, 0.7, 0.2, 0.9]
    axes_b = [0.8, 0.1, 0.6, 0.4]
    result = engine.compute_compatibility(axes_a, axes_b)
    assert 0.0 <= result.overall_score <= 100.0

  def test_per_axis_comparison_structure(
    self, engine: CompatibilityEngine
  ) -> None:
    """per_axis_comparison が正しい構造であること。"""
    axes_a = [0.8, 0.3, 0.6, 0.5]
    axes_b = [0.2, 0.9, 0.4, 0.7]
    result = engine.compute_compatibility(axes_a, axes_b)

    assert len(result.per_axis_comparison) == 4
    for axis_name in [
      "extroverted_introverted",
      "sensing_intuition",
      "thinking_feeling",
      "judging_perceiving",
    ]:
      assert axis_name in result.per_axis_comparison
      axis_data = result.per_axis_comparison[axis_name]
      assert "agent_1" in axis_data
      assert "agent_2" in axis_data
      assert "diff" in axis_data

  def test_per_axis_diff_values(self, engine: CompatibilityEngine) -> None:
    """per_axis_comparison の diff が正しく計算されていること。"""
    axes_a = [0.8, 0.3, 0.6, 0.5]
    axes_b = [0.2, 0.9, 0.4, 0.7]
    result = engine.compute_compatibility(axes_a, axes_b)

    assert result.per_axis_comparison["extroverted_introverted"]["diff"] == pytest.approx(0.6, abs=1e-6)
    assert result.per_axis_comparison["sensing_intuition"]["diff"] == pytest.approx(0.6, abs=1e-6)
    assert result.per_axis_comparison["thinking_feeling"]["diff"] == pytest.approx(0.2, abs=1e-6)
    assert result.per_axis_comparison["judging_perceiving"]["diff"] == pytest.approx(0.2, abs=1e-6)

  def test_classification_included(self, engine: CompatibilityEngine) -> None:
    """分類が含まれること。"""
    axes_a = [0.8, 0.8, 0.8, 0.8]
    axes_b = [0.79, 0.81, 0.78, 0.82]
    result = engine.compute_compatibility(axes_a, axes_b)
    assert isinstance(result.classification, SimilarityClassification)

  def test_relationship_type_included(
    self, engine: CompatibilityEngine
  ) -> None:
    """relationship_type が日本語ラベルであること。"""
    axes_a = [0.8, 0.8, 0.8, 0.8]
    axes_b = [0.79, 0.81, 0.78, 0.82]
    result = engine.compute_compatibility(axes_a, axes_b)
    assert result.relationship_type != ""
    assert isinstance(result.relationship_type, str)

  def test_identical_vectors_high_score(
    self, engine: CompatibilityEngine
  ) -> None:
    """同一ベクトルでは高いスコアが得られること。"""
    axes = [0.7, 0.5, 0.8, 0.3]
    result = engine.compute_compatibility(axes, axes)
    # sim=1.0, comp=0.0 → overall = 0.6 * 1.0 * 100 = 60.0
    assert result.overall_score == pytest.approx(60.0, abs=0.1)
    assert result.classification == SimilarityClassification.HIGHLY_SIMILAR

  def test_custom_weights(self, custom_engine: CompatibilityEngine) -> None:
    """カスタム重みが正しく適用されること。"""
    axes_a = [0.9, 0.9, 0.9, 0.9]
    axes_b = [0.9, 0.9, 0.9, 0.9]
    result = custom_engine.compute_compatibility(axes_a, axes_b)
    # sim=1.0, comp=0.0 → overall = 0.5 * 1.0 * 100 = 50.0
    assert result.overall_score == pytest.approx(50.0, abs=0.1)


class TestRecommend:
  """recommend() のテスト"""

  @pytest.fixture
  def sample_agents(self) -> list[dict]:
    """テスト用エージェントリスト。"""
    return [
      {
        "agent_id": "agent-source",
        "display_name": "Source",
        "axes": [0.8, 0.7, 0.6, 0.9],
      },
      {
        "agent_id": "agent-similar",
        "display_name": "Similar",
        "axes": [0.78, 0.72, 0.58, 0.88],
      },
      {
        "agent_id": "agent-opposite",
        "display_name": "Opposite",
        "axes": [0.2, 0.3, 0.4, 0.1],
      },
      {
        "agent_id": "agent-mixed",
        "display_name": "Mixed",
        "axes": [0.5, 0.5, 0.5, 0.5],
      },
    ]

  @pytest.mark.asyncio
  async def test_returns_two_categories(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """2カテゴリが返されること。"""
    result = await engine.recommend("agent-source", sample_agents)
    assert "most_heated_debate" in result
    assert "business_partner" in result

  @pytest.mark.asyncio
  async def test_max_3_per_category(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """各カテゴリ最大3件であること。"""
    result = await engine.recommend("agent-source", sample_agents)
    assert len(result["most_heated_debate"]) <= 3
    assert len(result["business_partner"]) <= 3

  @pytest.mark.asyncio
  async def test_excludes_source_agent(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """ソースエージェント自身はレコメンドに含まれないこと。"""
    result = await engine.recommend("agent-source", sample_agents)
    for rec in result["most_heated_debate"]:
      assert rec.agent_id != "agent-source"
    for rec in result["business_partner"]:
      assert rec.agent_id != "agent-source"

  @pytest.mark.asyncio
  async def test_debate_ranked_by_complementarity(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """most_heated_debate が相補性降順でランクされること。"""
    result = await engine.recommend("agent-source", sample_agents)
    scores = [rec.score for rec in result["most_heated_debate"]]
    assert scores == sorted(scores, reverse=True)

  @pytest.mark.asyncio
  async def test_partner_ranked_by_similarity(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """business_partner が類似度降順でランクされること。"""
    result = await engine.recommend("agent-source", sample_agents)
    scores = [rec.score for rec in result["business_partner"]]
    assert scores == sorted(scores, reverse=True)

  @pytest.mark.asyncio
  async def test_opposite_is_top_debate(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """対極的なエージェントが most_heated_debate の上位に来ること。"""
    result = await engine.recommend("agent-source", sample_agents)
    top_debate = result["most_heated_debate"][0]
    assert top_debate.agent_id == "agent-opposite"

  @pytest.mark.asyncio
  async def test_similar_is_top_partner(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """類似エージェントが business_partner の上位に来ること。"""
    result = await engine.recommend("agent-source", sample_agents)
    top_partner = result["business_partner"][0]
    assert top_partner.agent_id == "agent-similar"

  @pytest.mark.asyncio
  async def test_recommendation_structure(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """Recommendation の構造が正しいこと。"""
    result = await engine.recommend("agent-source", sample_agents)
    for rec in result["most_heated_debate"]:
      assert isinstance(rec, Recommendation)
      assert rec.agent_id != ""
      assert rec.display_name != ""
      assert rec.score >= 0
      assert rec.explanation != ""

  @pytest.mark.asyncio
  async def test_source_not_found(
    self, engine: CompatibilityEngine, sample_agents: list[dict]
  ) -> None:
    """存在しない source_agent_id で空結果が返ること。"""
    result = await engine.recommend("nonexistent", sample_agents)
    assert result["most_heated_debate"] == []
    assert result["business_partner"] == []

  @pytest.mark.asyncio
  async def test_single_agent_returns_empty(
    self, engine: CompatibilityEngine
  ) -> None:
    """エージェントが1人の場合は空結果が返ること。"""
    agents = [
      {"agent_id": "only-one", "display_name": "Solo", "axes": [0.5, 0.5, 0.5, 0.5]}
    ]
    result = await engine.recommend("only-one", agents)
    assert result["most_heated_debate"] == []
    assert result["business_partner"] == []
