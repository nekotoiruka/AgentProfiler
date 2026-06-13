"""CompatibilityEngine プロパティベーステスト

Feature: agent-evolution
Property 33: Compatibility score computation
Property 34: Recommendation ranking
Validates: Requirements 19.1, 19.2, 19.3, 19.4, 20.1, 20.2, 20.3
"""

import uuid

import numpy as np
import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.evolution.compatibility import (
  CompatibilityEngine,
  CompatibilityReport,
  Recommendation,
  SimilarityClassification,
  AXIS_NAMES,
)


# --- Hypothesis ストラテジー ---

# 4軸パラメータベクトル: 各要素が [0.0, 1.0] の4要素リスト
_axes_st = st.lists(
  st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
  min_size=4,
  max_size=4,
)

# ゼロベクトルを除外した4軸パラメータ (cosine similarity が定義できる)
# 極小値 (subnormal) のみのベクトルは norm ≈ 0 として扱われるため除外
_nonzero_axes_st = st.lists(
  st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False, allow_subnormal=False),
  min_size=4,
  max_size=4,
).filter(lambda axes: max(axes) > 1e-10)

# agent_id: ユニークな ID 文字列
_agent_id_st = st.uuids().map(lambda u: str(u))

# display_name: 表示名
_display_name_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_ "),
  min_size=1,
  max_size=20,
).filter(lambda s: s.strip() != "")

# 重み (similarity_weight): 0.0〜1.0
_weight_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


def _make_agent(agent_id: str, axes: list[float], display_name: str) -> dict:
  """テスト用エージェント辞書を構築する。"""
  return {
    "agent_id": agent_id,
    "axes": axes,
    "display_name": display_name,
  }


# =============================================================================
# Property 33: Compatibility score computation
# Feature: agent-evolution
# =============================================================================


class TestCompatibilityScoreComputation:
  """Property 33: Compatibility score is correctly computed.

  任意の2つの有効な4軸パラメータベクトルに対して、CompatibilityEngine は:
  (a) cosine_similarity がベクトルの数学的コサイン類似度と一致
  (b) complementarity_score が各軸の差の絶対値の平均と一致
  (c) overall_score = (sim_weight × similarity + comp_weight × complementarity) × 100 で [0,100] 範囲
  (d) レポートに per_axis_comparison, classification, recommended_interaction_mode を含む

  **Validates: Requirements 19.1, 19.2, 19.3, 19.4**
  """

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_nonzero_axes_st,
    axes_b=_nonzero_axes_st,
  )
  def test_overall_score_in_range(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """overall_score が [0, 100] 範囲内であること。

    **Validates: Requirements 19.3**
    """
    engine = CompatibilityEngine()
    report = engine.compute_compatibility(axes_a, axes_b)

    assert 0 <= report.overall_score <= 100, (
      f"overall_score {report.overall_score} out of [0, 100] range"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_nonzero_axes_st,
    axes_b=_nonzero_axes_st,
  )
  def test_cosine_similarity_in_range(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """cosine_similarity が [0, 1] 範囲内であること。

    **Validates: Requirements 19.1**
    """
    engine = CompatibilityEngine()
    report = engine.compute_compatibility(axes_a, axes_b)

    assert 0.0 <= report.cosine_similarity <= 1.0, (
      f"cosine_similarity {report.cosine_similarity} out of [0.0, 1.0] range"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_nonzero_axes_st,
    axes_b=_nonzero_axes_st,
  )
  def test_complementarity_score_in_range(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """complementarity_score が [0, 1] 範囲内であること。

    **Validates: Requirements 19.2**
    """
    engine = CompatibilityEngine()
    report = engine.compute_compatibility(axes_a, axes_b)

    assert 0.0 <= report.complementarity_score <= 1.0, (
      f"complementarity_score {report.complementarity_score} out of [0.0, 1.0] range"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_nonzero_axes_st,
    axes_b=_nonzero_axes_st,
  )
  def test_cosine_similarity_matches_expected(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """cosine_similarity が数学的コサイン類似度と一致すること。

    **Validates: Requirements 19.1**
    """
    engine = CompatibilityEngine()
    report = engine.compute_compatibility(axes_a, axes_b)

    # 期待値: numpy による計算
    a = np.array(axes_a, dtype=np.float64)
    b = np.array(axes_b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
      expected_sim = 0.0
    else:
      expected_sim = float(np.dot(a, b) / (norm_a * norm_b))
      expected_sim = max(0.0, min(1.0, expected_sim))

    assert abs(report.cosine_similarity - round(expected_sim, 4)) < 1e-4, (
      f"cosine_similarity {report.cosine_similarity} != expected {round(expected_sim, 4)}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_axes_st,
    axes_b=_axes_st,
  )
  def test_complementarity_matches_expected(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """complementarity_score が各軸差の絶対値の平均と一致すること。

    **Validates: Requirements 19.2**
    """
    engine = CompatibilityEngine()
    report = engine.compute_compatibility(axes_a, axes_b)

    # 期待値: 各軸の差の絶対値の平均
    expected_comp = sum(abs(a - b) for a, b in zip(axes_a, axes_b)) / 4
    expected_comp = round(expected_comp, 4)

    assert abs(report.complementarity_score - expected_comp) < 1e-6, (
      f"complementarity_score {report.complementarity_score} != expected {expected_comp}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_nonzero_axes_st,
    axes_b=_nonzero_axes_st,
  )
  def test_overall_score_formula(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """overall_score が (0.6 × similarity + 0.4 × complementarity) × 100 と一致すること。

    **Validates: Requirements 19.3**
    """
    engine = CompatibilityEngine(similarity_weight=0.6, complementarity_weight=0.4)
    report = engine.compute_compatibility(axes_a, axes_b)

    # 丸め前の計算で確認 (二重丸めの影響で最大 0.02 の誤差を許容)
    expected = (0.6 * report.cosine_similarity + 0.4 * report.complementarity_score) * 100
    expected = round(expected, 2)

    assert abs(report.overall_score - expected) < 0.02, (
      f"overall_score {report.overall_score} != expected formula result {expected}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_nonzero_axes_st,
    axes_b=_nonzero_axes_st,
  )
  def test_similarity_is_symmetric(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """similarity は対称: sim(a, b) == sim(b, a)。

    **Validates: Requirements 19.1**
    """
    engine = CompatibilityEngine()
    sim_ab = engine.compute_similarity(axes_a, axes_b)
    sim_ba = engine.compute_similarity(axes_b, axes_a)

    assert abs(sim_ab - sim_ba) < 1e-10, (
      f"Similarity not symmetric: sim(a,b)={sim_ab} != sim(b,a)={sim_ba}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_axes_st,
    axes_b=_axes_st,
  )
  def test_complementarity_is_symmetric(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """complementarity は対称: comp(a, b) == comp(b, a)。

    **Validates: Requirements 19.2**
    """
    engine = CompatibilityEngine()
    comp_ab = engine.compute_complementarity(axes_a, axes_b)
    comp_ba = engine.compute_complementarity(axes_b, axes_a)

    assert abs(comp_ab - comp_ba) < 1e-10, (
      f"Complementarity not symmetric: comp(a,b)={comp_ab} != comp(b,a)={comp_ba}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_nonzero_axes_st,
    axes_b=_nonzero_axes_st,
  )
  def test_classify_is_deterministic(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """同じ入力に対して classify は常に同じ結果を返すこと。

    **Validates: Requirements 19.4**
    """
    engine = CompatibilityEngine()
    sim = engine.compute_similarity(axes_a, axes_b)
    comp = engine.compute_complementarity(axes_a, axes_b)

    result1 = engine.classify(sim, comp)
    result2 = engine.classify(sim, comp)

    assert result1 == result2, (
      f"classify not deterministic: {result1} != {result2}"
    )

  @settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    axes_a=_nonzero_axes_st,
    axes_b=_nonzero_axes_st,
  )
  def test_report_contains_required_fields(
    self,
    axes_a: list[float],
    axes_b: list[float],
  ) -> None:
    """レポートに per_axis_comparison, classification, recommended_interaction_mode が含まれること。

    **Validates: Requirements 19.4**
    """
    engine = CompatibilityEngine()
    report = engine.compute_compatibility(axes_a, axes_b)

    # per_axis_comparison は4軸すべてを含む
    assert set(report.per_axis_comparison.keys()) == set(AXIS_NAMES), (
      f"per_axis_comparison keys mismatch: {set(report.per_axis_comparison.keys())} "
      f"!= {set(AXIS_NAMES)}"
    )

    # 各軸の比較情報に agent_1, agent_2, diff が含まれる
    for axis_name, comparison in report.per_axis_comparison.items():
      assert "agent_1" in comparison, f"Missing 'agent_1' in {axis_name}"
      assert "agent_2" in comparison, f"Missing 'agent_2' in {axis_name}"
      assert "diff" in comparison, f"Missing 'diff' in {axis_name}"
      assert 0.0 <= comparison["diff"] <= 1.0, (
        f"diff for {axis_name} out of range: {comparison['diff']}"
      )

    # classification は有効な列挙値
    assert isinstance(report.classification, SimilarityClassification), (
      f"classification is not SimilarityClassification: {type(report.classification)}"
    )

    # recommended_interaction_mode は非空文字列
    assert report.recommended_interaction_mode != "", (
      "recommended_interaction_mode should not be empty"
    )

    # relationship_type は非空文字列
    assert report.relationship_type != "", (
      "relationship_type should not be empty"
    )

    # reason は非空文字列
    assert report.reason != "", (
      "reason should not be empty"
    )


# =============================================================================
# Property 34: Recommendation ranking
# Feature: agent-evolution
# =============================================================================


class TestRecommendationRanking:
  """Property 34: Recommendations are correctly ranked and limited.

  任意のソースエージェントに対して、recommend() は:
  (a) 各カテゴリ最大3件を返す
  (b) "most_heated_debate" は complementarity_score 降順
  (c) "business_partner" は cosine_similarity 降順
  (d) 各レコメンドに agent_id, display_name, score, explanation が含まれる
  (e) ソースエージェント自身がレコメンドに含まれないこと

  **Validates: Requirements 20.1, 20.2, 20.3**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    data=st.data(),
    num_agents=st.integers(min_value=3, max_value=8),
  )
  async def test_at_most_3_per_category(
    self,
    data: st.DataObject,
    num_agents: int,
  ) -> None:
    """各カテゴリが最大3件であること。

    **Validates: Requirements 20.3**
    """
    # エージェント一覧を生成
    agents = []
    for i in range(num_agents):
      agent_id = data.draw(_agent_id_st, label=f"agent_id_{i}")
      axes = data.draw(_nonzero_axes_st, label=f"axes_{i}")
      display_name = data.draw(_display_name_st, label=f"name_{i}")
      agents.append(_make_agent(agent_id, axes, display_name))

    # agent_id の一意性を保証
    seen_ids = set()
    unique_agents = []
    for agent in agents:
      if agent["agent_id"] not in seen_ids:
        seen_ids.add(agent["agent_id"])
        unique_agents.append(agent)
    assume(len(unique_agents) >= 3)
    agents = unique_agents

    source_agent_id = agents[0]["agent_id"]
    engine = CompatibilityEngine()

    result = await engine.recommend(source_agent_id, agents)

    assert len(result["most_heated_debate"]) <= 3, (
      f"most_heated_debate has {len(result['most_heated_debate'])} items (max 3)"
    )
    assert len(result["business_partner"]) <= 3, (
      f"business_partner has {len(result['business_partner'])} items (max 3)"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    data=st.data(),
    num_agents=st.integers(min_value=3, max_value=8),
  )
  async def test_most_heated_debate_sorted_descending(
    self,
    data: st.DataObject,
    num_agents: int,
  ) -> None:
    """most_heated_debate が score 降順にソートされていること。

    **Validates: Requirements 20.2**
    """
    agents = []
    for i in range(num_agents):
      agent_id = data.draw(_agent_id_st, label=f"agent_id_{i}")
      axes = data.draw(_nonzero_axes_st, label=f"axes_{i}")
      display_name = data.draw(_display_name_st, label=f"name_{i}")
      agents.append(_make_agent(agent_id, axes, display_name))

    seen_ids = set()
    unique_agents = []
    for agent in agents:
      if agent["agent_id"] not in seen_ids:
        seen_ids.add(agent["agent_id"])
        unique_agents.append(agent)
    assume(len(unique_agents) >= 3)
    agents = unique_agents

    source_agent_id = agents[0]["agent_id"]
    engine = CompatibilityEngine()

    result = await engine.recommend(source_agent_id, agents)
    debate_recs = result["most_heated_debate"]

    # スコアが降順であること
    scores = [rec.score for rec in debate_recs]
    assert scores == sorted(scores, reverse=True), (
      f"most_heated_debate not sorted descending: {scores}"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    data=st.data(),
    num_agents=st.integers(min_value=3, max_value=8),
  )
  async def test_business_partner_sorted_descending(
    self,
    data: st.DataObject,
    num_agents: int,
  ) -> None:
    """business_partner が score 降順にソートされていること。

    **Validates: Requirements 20.2**
    """
    agents = []
    for i in range(num_agents):
      agent_id = data.draw(_agent_id_st, label=f"agent_id_{i}")
      axes = data.draw(_nonzero_axes_st, label=f"axes_{i}")
      display_name = data.draw(_display_name_st, label=f"name_{i}")
      agents.append(_make_agent(agent_id, axes, display_name))

    seen_ids = set()
    unique_agents = []
    for agent in agents:
      if agent["agent_id"] not in seen_ids:
        seen_ids.add(agent["agent_id"])
        unique_agents.append(agent)
    assume(len(unique_agents) >= 3)
    agents = unique_agents

    source_agent_id = agents[0]["agent_id"]
    engine = CompatibilityEngine()

    result = await engine.recommend(source_agent_id, agents)
    partner_recs = result["business_partner"]

    # スコアが降順であること
    scores = [rec.score for rec in partner_recs]
    assert scores == sorted(scores, reverse=True), (
      f"business_partner not sorted descending: {scores}"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    data=st.data(),
    num_agents=st.integers(min_value=3, max_value=8),
  )
  async def test_recommendations_exclude_source_agent(
    self,
    data: st.DataObject,
    num_agents: int,
  ) -> None:
    """ソースエージェント自身がレコメンド結果に含まれないこと。

    **Validates: Requirements 20.1**
    """
    agents = []
    for i in range(num_agents):
      agent_id = data.draw(_agent_id_st, label=f"agent_id_{i}")
      axes = data.draw(_nonzero_axes_st, label=f"axes_{i}")
      display_name = data.draw(_display_name_st, label=f"name_{i}")
      agents.append(_make_agent(agent_id, axes, display_name))

    seen_ids = set()
    unique_agents = []
    for agent in agents:
      if agent["agent_id"] not in seen_ids:
        seen_ids.add(agent["agent_id"])
        unique_agents.append(agent)
    assume(len(unique_agents) >= 3)
    agents = unique_agents

    source_agent_id = agents[0]["agent_id"]
    engine = CompatibilityEngine()

    result = await engine.recommend(source_agent_id, agents)

    # 全カテゴリでソースエージェントが含まれないこと
    for category, recs in result.items():
      for rec in recs:
        assert rec.agent_id != source_agent_id, (
          f"Source agent '{source_agent_id}' found in '{category}' recommendations"
        )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
  )
  @given(
    data=st.data(),
    num_agents=st.integers(min_value=3, max_value=8),
  )
  async def test_recommendations_contain_required_fields(
    self,
    data: st.DataObject,
    num_agents: int,
  ) -> None:
    """各レコメンドに agent_id, display_name, score, explanation が含まれること。

    **Validates: Requirements 20.3**
    """
    agents = []
    for i in range(num_agents):
      agent_id = data.draw(_agent_id_st, label=f"agent_id_{i}")
      axes = data.draw(_nonzero_axes_st, label=f"axes_{i}")
      display_name = data.draw(_display_name_st, label=f"name_{i}")
      agents.append(_make_agent(agent_id, axes, display_name))

    seen_ids = set()
    unique_agents = []
    for agent in agents:
      if agent["agent_id"] not in seen_ids:
        seen_ids.add(agent["agent_id"])
        unique_agents.append(agent)
    assume(len(unique_agents) >= 3)
    agents = unique_agents

    source_agent_id = agents[0]["agent_id"]
    engine = CompatibilityEngine()

    result = await engine.recommend(source_agent_id, agents)

    for category, recs in result.items():
      for rec in recs:
        assert isinstance(rec, Recommendation), (
          f"Recommendation in '{category}' is not a Recommendation instance"
        )
        assert rec.agent_id != "", f"agent_id is empty in '{category}'"
        assert rec.display_name != "", f"display_name is empty in '{category}'"
        assert rec.score >= 0.0, f"score is negative in '{category}': {rec.score}"
        assert rec.explanation != "", f"explanation is empty in '{category}'"
