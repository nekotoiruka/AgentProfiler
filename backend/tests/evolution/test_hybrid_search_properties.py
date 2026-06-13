"""HybridSearchEngine プロパティベーステスト

Feature: agent-evolution
Property 8: Hybrid merge correctness
Property 9: Hybrid weighting influence
Validates: Requirements 7.1, 7.2, 7.3, 7.4
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.evolution.hybrid_search import HybridResult, HybridSearchEngine, ResultSource
from app.evolution.lexical_retriever import LexicalRetriever
from app.evolution.semantic_retriever import SemanticResult, SemanticRetriever


# --- Hypothesis ストラテジー ---

# タグ名生成: アルファベット小文字 + 数字 (1〜15文字)
_tag_st = st.text(
  alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="_-"),
  min_size=1,
  max_size=15,
)

# タグリスト (重複なし、0〜10件)
_tag_list_st = st.lists(_tag_st, min_size=0, max_size=10, unique=True)

# ドメイン名 (semantic result 用)
_domain_st = st.text(
  alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="_-"),
  min_size=1,
  max_size=15,
)

# cosine similarity スコア (0.0〜1.0)
_score_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# weight パラメータ (0.0〜1.0)
_weight_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# SemanticResult 生成
_semantic_result_st = st.builds(
  SemanticResult,
  domain=_domain_st,
  text=st.text(min_size=1, max_size=30),
  score=_score_st,
)

# SemanticResult リスト (0〜8件、domain ユニーク)
_semantic_results_st = st.lists(
  _semantic_result_st,
  min_size=0,
  max_size=8,
).map(lambda rs: list({r.domain.lower(): r for r in rs}.values()))


# --- ヘルパー ---

def _make_engine(
  lexical_tags: list[str],
  semantic_results: list[SemanticResult],
  weight: float,
) -> HybridSearchEngine:
  """テスト用 HybridSearchEngine を構築する。

  LexicalRetriever は実インスタンス、SemanticRetriever はモック。
  """
  lexical = LexicalRetriever(lexical_tags)
  semantic = AsyncMock(spec=SemanticRetriever)
  semantic.search = AsyncMock(return_value=semantic_results)
  return HybridSearchEngine(
    lexical_retriever=lexical,
    semantic_retriever=semantic,
    weight=weight,
  )


# =============================================================================
# Property 8: Hybrid merge correctness
# Feature: agent-evolution
# =============================================================================


class TestHybridMergeCorrectness:
  """Property 8: All results from both retrievers appear in merged output
  (accounting for dedup rules).

  **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
  """

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(
    tags=_tag_list_st,
    semantic_results=_semantic_results_st,
    weight=_weight_st,
  )
  async def test_all_non_deduped_lexical_appear_in_output(
    self,
    tags: list[str],
    semantic_results: list[SemanticResult],
    weight: float,
  ) -> None:
    """重複排除対象外の lexical タグは全て結果に含まれる。

    dedup ルール: tag.lower() が semantic domain.lower() のいずれかと一致する場合除外。
    それ以外の lexical タグは全て LEXICAL ソースとして出力される。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    # lexical_tags をクエリとして全マッチさせるため、タグ自身をクエリに入れる
    query = " ".join(tags) if tags else "dummy"

    engine = _make_engine(tags, semantic_results, weight)
    results = await engine.search("prof_test", query)

    # dedup 対象の semantic domain キーセット (小文字)
    semantic_domains_lower = {r.domain.lower() for r in semantic_results}

    # 非 dedup lexical タグ
    expected_lexical = [t for t in tags if t.lower() not in semantic_domains_lower]

    # 結果の lexical コンテンツ
    actual_lexical = [r.content for r in results if r.source == ResultSource.LEXICAL]

    for tag in expected_lexical:
      assert tag in actual_lexical, (
        f"Non-deduped lexical tag '{tag}' missing from results. "
        f"Expected lexical: {expected_lexical}, Got: {actual_lexical}"
      )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(
    tags=_tag_list_st,
    semantic_results=_semantic_results_st,
    weight=_weight_st,
  )
  async def test_all_semantic_results_appear_in_output(
    self,
    tags: list[str],
    semantic_results: list[SemanticResult],
    weight: float,
  ) -> None:
    """全ての semantic 結果は常に出力に含まれる (semantic 側は dedup されない)。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    query = " ".join(tags) if tags else "dummy"
    engine = _make_engine(tags, semantic_results, weight)
    results = await engine.search("prof_test", query)

    actual_semantic_domains = [r.domain for r in results if r.source == ResultSource.SEMANTIC]

    for sr in semantic_results:
      assert sr.domain in actual_semantic_domains, (
        f"Semantic result domain '{sr.domain}' missing from output. "
        f"Expected: {[r.domain for r in semantic_results]}, Got: {actual_semantic_domains}"
      )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(
    tags=_tag_list_st,
    semantic_results=_semantic_results_st,
    weight=_weight_st,
  )
  async def test_deduped_lexical_excluded_from_output(
    self,
    tags: list[str],
    semantic_results: list[SemanticResult],
    weight: float,
  ) -> None:
    """semantic domain と一致する lexical タグは結果に含まれない (dedup)。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    query = " ".join(tags) if tags else "dummy"
    engine = _make_engine(tags, semantic_results, weight)
    results = await engine.search("prof_test", query)

    semantic_domains_lower = {r.domain.lower() for r in semantic_results}
    deduped_tags = [t for t in tags if t.lower() in semantic_domains_lower]

    actual_lexical = [r.content for r in results if r.source == ResultSource.LEXICAL]

    for tag in deduped_tags:
      assert tag not in actual_lexical, (
        f"Deduped tag '{tag}' should NOT appear in lexical results. "
        f"Got lexical: {actual_lexical}"
      )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(
    tags=_tag_list_st,
    semantic_results=_semantic_results_st,
    weight=_weight_st,
  )
  async def test_results_sorted_descending_by_score(
    self,
    tags: list[str],
    semantic_results: list[SemanticResult],
    weight: float,
  ) -> None:
    """統合結果はスコア降順でソートされている。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    query = " ".join(tags) if tags else "dummy"
    engine = _make_engine(tags, semantic_results, weight)
    results = await engine.search("prof_test", query)

    if len(results) > 1:
      for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score, (
          f"Results not sorted descending: "
          f"results[{i}].score={results[i].score} > results[{i+1}].score={results[i+1].score}"
        )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(weight=_weight_st)
  async def test_both_empty_returns_empty(self, weight: float) -> None:
    """両 retriever が空の場合、結果は空リスト (エラーなし)。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    engine = _make_engine([], [], weight)
    results = await engine.search("prof_test", "anything")
    assert results == []


# =============================================================================
# Property 9: Hybrid weighting influence
# Feature: agent-evolution
# =============================================================================


class TestHybridWeightingInfluence:
  """Property 9: When weight=0.0, only lexical results appear (unless empty);
  when weight=1.0, only semantic results appear (unless empty).
  Intermediate weights produce mixed results.

  **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
  """

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(tags=st.lists(_tag_st, min_size=1, max_size=8, unique=True))
  async def test_weight_zero_lexical_dominates(self, tags: list[str]) -> None:
    """weight=0.0 の場合、lexical スコアは 1.0 で semantic スコアは 0.0。

    lexical のみが実質的に影響を持つ（semantic は score=0 で最下位）。
    ただし semantic 結果は依然として出力に含まれる（score=0 で）。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    # semantic domain がタグと被らないようにする
    semantic_results = [
      SemanticResult(domain="unrelated_domain_xyz", text="some text", score=0.95),
    ]
    # semantic domain が tags のどれとも一致しないことを保証
    assume(all(t.lower() != "unrelated_domain_xyz" for t in tags))

    query = " ".join(tags)
    engine = _make_engine(tags, semantic_results, weight=0.0)
    results = await engine.search("prof_test", query)

    lexical_results = [r for r in results if r.source == ResultSource.LEXICAL]
    semantic_in_output = [r for r in results if r.source == ResultSource.SEMANTIC]

    # lexical スコアは (1-0)*1.0 = 1.0
    for r in lexical_results:
      assert r.score == pytest.approx(1.0), (
        f"weight=0.0: lexical score should be 1.0, got {r.score}"
      )

    # semantic スコアは 0*score = 0.0
    for r in semantic_in_output:
      assert r.score == pytest.approx(0.0), (
        f"weight=0.0: semantic score should be 0.0, got {r.score}"
      )

    # lexical が全て最上位に来る (score=1.0 > score=0.0)
    assert len(lexical_results) == len(tags)

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(
    semantic_results=st.lists(
      st.builds(
        SemanticResult,
        domain=st.text(
          alphabet=st.characters(whitelist_categories=("Ll",), whitelist_characters="_"),
          min_size=3,
          max_size=12,
        ),
        text=st.text(min_size=1, max_size=20),
        score=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
      ),
      min_size=1,
      max_size=5,
      unique_by=lambda r: r.domain.lower(),
    ),
  )
  async def test_weight_one_semantic_dominates(
    self, semantic_results: list[SemanticResult]
  ) -> None:
    """weight=1.0 の場合、semantic スコアが最大化され lexical スコアは 0.0。

    semantic のみが実質的に影響を持つ（lexical は score=0 で最下位）。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    # lexical タグは semantic domain と被らない
    tags = ["unique_tag_alpha", "unique_tag_beta"]
    assume(all(
      t.lower() != r.domain.lower()
      for t in tags for r in semantic_results
    ))

    query = " ".join(tags)
    engine = _make_engine(tags, semantic_results, weight=1.0)
    results = await engine.search("prof_test", query)

    lexical_in_output = [r for r in results if r.source == ResultSource.LEXICAL]
    semantic_in_output = [r for r in results if r.source == ResultSource.SEMANTIC]

    # lexical スコアは (1-1)*1.0 = 0.0
    for r in lexical_in_output:
      assert r.score == pytest.approx(0.0), (
        f"weight=1.0: lexical score should be 0.0, got {r.score}"
      )

    # semantic スコアは 1.0*cosine_similarity = cosine_similarity
    for r in semantic_in_output:
      # 対応する元の semantic result を見つけて検証
      original = next(sr for sr in semantic_results if sr.domain == r.domain)
      assert r.score == pytest.approx(original.score), (
        f"weight=1.0: semantic score should be {original.score}, got {r.score}"
      )

    # semantic が全て最上位に来る (score>0 > score=0)
    assert len(semantic_in_output) == len(semantic_results)

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(
    tags=st.lists(_tag_st, min_size=1, max_size=5, unique=True),
    weight=st.floats(
      min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False
    ),
  )
  async def test_intermediate_weight_produces_mixed_scores(
    self,
    tags: list[str],
    weight: float,
  ) -> None:
    """中間 weight (0<w<1) では lexical と semantic の両方が非ゼロスコアを持つ。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    semantic_results = [
      SemanticResult(domain="unique_sem_domain_abc", text="text", score=0.8),
    ]
    # タグが semantic domain と被らないことを保証
    assume(all(t.lower() != "unique_sem_domain_abc" for t in tags))

    query = " ".join(tags)
    engine = _make_engine(tags, semantic_results, weight=weight)
    results = await engine.search("prof_test", query)

    lexical_in_output = [r for r in results if r.source == ResultSource.LEXICAL]
    semantic_in_output = [r for r in results if r.source == ResultSource.SEMANTIC]

    # lexical スコア = (1 - weight) * 1.0 > 0
    for r in lexical_in_output:
      expected = (1 - weight) * 1.0
      assert r.score == pytest.approx(expected, abs=1e-6), (
        f"Lexical score should be {expected}, got {r.score}"
      )
      assert r.score > 0, f"Intermediate weight: lexical score should be > 0"

    # semantic スコア = weight * 0.8 > 0
    for r in semantic_in_output:
      expected = weight * 0.8
      assert r.score == pytest.approx(expected, abs=1e-6), (
        f"Semantic score should be {expected}, got {r.score}"
      )
      assert r.score > 0, f"Intermediate weight: semantic score should be > 0"

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(
    tags=_tag_list_st,
    weight=_weight_st,
  )
  async def test_lexical_score_formula(
    self,
    tags: list[str],
    weight: float,
  ) -> None:
    """lexical スコアは常に (1 - weight) * 1.0 で計算される。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    query = " ".join(tags) if tags else "dummy"
    engine = _make_engine(tags, [], weight)
    results = await engine.search("prof_test", query)

    expected_score = (1 - weight) * 1.0
    for r in results:
      assert r.source == ResultSource.LEXICAL
      assert r.score == pytest.approx(expected_score, abs=1e-6), (
        f"Lexical score should be (1-{weight})*1.0={expected_score}, got {r.score}"
      )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(
    semantic_results=st.lists(
      st.builds(
        SemanticResult,
        domain=st.text(
          alphabet=st.characters(whitelist_categories=("Ll",), whitelist_characters="_"),
          min_size=3,
          max_size=12,
        ),
        text=st.text(min_size=1, max_size=20),
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
      ),
      min_size=1,
      max_size=5,
      unique_by=lambda r: r.domain.lower(),
    ),
    weight=_weight_st,
  )
  async def test_semantic_score_formula(
    self,
    semantic_results: list[SemanticResult],
    weight: float,
  ) -> None:
    """semantic スコアは常に weight * cosine_similarity で計算される。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    engine = _make_engine([], semantic_results, weight)
    results = await engine.search("prof_test", "dummy")

    for r in results:
      assert r.source == ResultSource.SEMANTIC
      original = next(sr for sr in semantic_results if sr.domain == r.domain)
      expected_score = weight * original.score
      assert r.score == pytest.approx(expected_score, abs=1e-6), (
        f"Semantic score should be {weight}*{original.score}={expected_score}, got {r.score}"
      )
