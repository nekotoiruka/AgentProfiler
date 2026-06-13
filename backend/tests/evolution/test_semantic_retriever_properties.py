"""SemanticRetriever プロパティベーステスト

Feature: agent-evolution
Property 7: Semantic retrieval correctness
Validates: Requirements 6.3, 6.4
"""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.evolution.embedding_client import EmbeddingClient
from app.evolution.semantic_retriever import SemanticResult, SemanticRetriever


# --- Hypothesis ストラテジー ---

# 非ゼロ浮動小数点ベクトル (次元数 2〜16)
_vector_dim_st = st.shared(st.integers(min_value=2, max_value=16), key="dim")

_nonzero_vector_st = st.lists(
  st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
  min_size=2,
  max_size=16,
).filter(lambda xs: any(x != 0.0 for x in xs))

# ゼロベクトル生成用
_zero_vector_st = st.integers(min_value=2, max_value=16).map(
  lambda dim: [0.0] * dim
)

# top_k パラメータ (1〜10)
_top_k_st = st.integers(min_value=1, max_value=10)

# threshold パラメータ (0.0〜1.0)
_threshold_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# profile_id 生成
_profile_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
  min_size=3,
  max_size=15,
).map(lambda s: f"prof_{s}")

# ドメイン名生成
_domain_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
  min_size=1,
  max_size=20,
)

# テキスト生成
_text_st = st.text(min_size=1, max_size=50)


# =============================================================================
# Property 7: Semantic retrieval correctness
# Feature: agent-evolution
# =============================================================================


class TestCosineSimilarityProperties:
  """cosine_similarity のプロパティテスト"""

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(vec_list=_nonzero_vector_st)
  def test_cosine_similarity_is_symmetric(self, vec_list: list[float]) -> None:
    """cosine_similarity(a, b) == cosine_similarity(b, a) が成り立つ。

    任意の非ゼロベクトル a, b に対して対称性が保証される。

    **Validates: Requirements 6.3, 6.4**
    """
    # 同次元の2ベクトルを生成するため、リストを半分に分割
    dim = len(vec_list)
    a = np.array(vec_list, dtype=np.float32)
    # ベクトルを反転させて b を作成 (異なるベクトルで対称性テスト)
    b = np.array(vec_list[::-1], dtype=np.float32)

    sim_ab = SemanticRetriever.cosine_similarity(a, b)
    sim_ba = SemanticRetriever.cosine_similarity(b, a)

    assert sim_ab == pytest.approx(sim_ba, abs=1e-6), (
      f"Symmetry violated: sim(a, b)={sim_ab}, sim(b, a)={sim_ba}"
    )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(a=_nonzero_vector_st, b=_nonzero_vector_st)
  def test_cosine_similarity_symmetric_independent_vectors(
    self, a: list[float], b: list[float]
  ) -> None:
    """独立に生成した2ベクトルに対しても対称性が成り立つ。

    **Validates: Requirements 6.3, 6.4**
    """
    # 同次元に揃える (短い方に合わせる)
    min_dim = min(len(a), len(b))
    vec_a = np.array(a[:min_dim], dtype=np.float32)
    vec_b = np.array(b[:min_dim], dtype=np.float32)

    # 両方非ゼロであることを保証
    assume(np.linalg.norm(vec_a) > 0)
    assume(np.linalg.norm(vec_b) > 0)

    sim_ab = SemanticRetriever.cosine_similarity(vec_a, vec_b)
    sim_ba = SemanticRetriever.cosine_similarity(vec_b, vec_a)

    assert sim_ab == pytest.approx(sim_ba, abs=1e-6), (
      f"Symmetry violated: sim(a, b)={sim_ab}, sim(b, a)={sim_ba}"
    )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(vec=_nonzero_vector_st)
  def test_cosine_similarity_bounds(self, vec: list[float]) -> None:
    """非ゼロベクトルの cosine similarity は [-1.0, 1.0] の範囲に収まる。

    **Validates: Requirements 6.3, 6.4**
    """
    a = np.array(vec, dtype=np.float32)
    # 任意のベクトルとの類似度を計算
    b = np.array(vec[::-1], dtype=np.float32)

    assume(np.linalg.norm(a) > 0)
    assume(np.linalg.norm(b) > 0)

    sim = SemanticRetriever.cosine_similarity(a, b)
    assert -1.0 - 1e-6 <= sim <= 1.0 + 1e-6, (
      f"Cosine similarity {sim} out of bounds [-1.0, 1.0]"
    )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(a=_nonzero_vector_st, b=_nonzero_vector_st)
  def test_cosine_similarity_bounds_independent(
    self, a: list[float], b: list[float]
  ) -> None:
    """独立な2ベクトルでも cosine similarity は [-1.0, 1.0] の範囲。

    **Validates: Requirements 6.3, 6.4**
    """
    min_dim = min(len(a), len(b))
    vec_a = np.array(a[:min_dim], dtype=np.float32)
    vec_b = np.array(b[:min_dim], dtype=np.float32)

    assume(np.linalg.norm(vec_a) > 0)
    assume(np.linalg.norm(vec_b) > 0)

    sim = SemanticRetriever.cosine_similarity(vec_a, vec_b)
    assert -1.0 - 1e-6 <= sim <= 1.0 + 1e-6, (
      f"Cosine similarity {sim} out of bounds [-1.0, 1.0]"
    )

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(dim=st.integers(min_value=2, max_value=16), b=_nonzero_vector_st)
  def test_zero_vector_returns_zero(self, dim: int, b: list[float]) -> None:
    """いずれかのベクトルがゼロの場合 0.0 を返す。

    **Validates: Requirements 6.3, 6.4**
    """
    zero = np.zeros(dim, dtype=np.float32)
    vec_b = np.array(b[:dim], dtype=np.float32)

    # ゼロベクトル a
    assert SemanticRetriever.cosine_similarity(zero, vec_b) == 0.0
    # ゼロベクトル b
    assert SemanticRetriever.cosine_similarity(vec_b, zero) == 0.0

  @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
  @given(vec=_nonzero_vector_st)
  def test_self_similarity_is_one(self, vec: list[float]) -> None:
    """同一ベクトル同士の cosine similarity は 1.0。

    **Validates: Requirements 6.3, 6.4**
    """
    a = np.array(vec, dtype=np.float32)
    assume(np.linalg.norm(a) > 0)

    sim = SemanticRetriever.cosine_similarity(a, a)
    assert sim == pytest.approx(1.0, abs=1e-6), (
      f"Self-similarity should be 1.0, got {sim}"
    )


class TestSearchProperties:
  """search() のプロパティテスト: ソート・閾値・top_k"""

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    top_k=_top_k_st,
    threshold=_threshold_st,
    num_entries=st.integers(min_value=2, max_value=10),
    dim=st.integers(min_value=2, max_value=8),
    data=st.data(),
  )
  def test_results_sorted_by_score_descending(
    self,
    top_k: int,
    threshold: float,
    num_entries: int,
    dim: int,
    data,
  ) -> None:
    """検索結果はスコア降順にソートされている。

    **Validates: Requirements 6.3, 6.4**
    """
    client = EmbeddingClient(model="test", api_key="key")
    retriever = SemanticRetriever(
      embedding_client=client, top_k=top_k, threshold=threshold
    )

    # ランダムなキャッシュデータを生成
    domains = [f"domain_{i}" for i in range(num_entries)]
    texts = [f"text_{i}" for i in range(num_entries)]
    embeddings = data.draw(
      st.lists(
        st.lists(
          st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
          min_size=dim,
          max_size=dim,
        ),
        min_size=num_entries,
        max_size=num_entries,
      )
    )
    embeddings_matrix = np.array(embeddings, dtype=np.float32)

    # クエリベクトルを生成
    query_vec = data.draw(
      st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=dim,
        max_size=dim,
      )
    )
    query_arr = np.array(query_vec, dtype=np.float32)
    assume(np.linalg.norm(query_arr) > 0)

    # キャッシュに直接設定
    retriever._cache["prof_test"] = (domains, texts, embeddings_matrix)

    # 同期的に search を実行 (embed をモック)
    import asyncio
    with patch.object(
      client, "embed", new_callable=AsyncMock, return_value=query_arr
    ):
      results = asyncio.run(retriever.search("prof_test", "query"))

    # スコアが降順であることを検証
    if len(results) > 1:
      for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score, (
          f"Results not sorted descending: "
          f"results[{i}].score={results[i].score} < results[{i+1}].score={results[i+1].score}"
        )

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    top_k=_top_k_st,
    threshold=_threshold_st,
    num_entries=st.integers(min_value=2, max_value=10),
    dim=st.integers(min_value=2, max_value=8),
    data=st.data(),
  )
  def test_results_respect_threshold(
    self,
    top_k: int,
    threshold: float,
    num_entries: int,
    dim: int,
    data,
  ) -> None:
    """すべての検索結果のスコアが threshold 以上である。

    **Validates: Requirements 6.3, 6.4**
    """
    client = EmbeddingClient(model="test", api_key="key")
    retriever = SemanticRetriever(
      embedding_client=client, top_k=top_k, threshold=threshold
    )

    # ランダムなキャッシュデータを生成
    domains = [f"domain_{i}" for i in range(num_entries)]
    texts = [f"text_{i}" for i in range(num_entries)]
    embeddings = data.draw(
      st.lists(
        st.lists(
          st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
          min_size=dim,
          max_size=dim,
        ),
        min_size=num_entries,
        max_size=num_entries,
      )
    )
    embeddings_matrix = np.array(embeddings, dtype=np.float32)

    # クエリベクトルを生成
    query_vec = data.draw(
      st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=dim,
        max_size=dim,
      )
    )
    query_arr = np.array(query_vec, dtype=np.float32)
    assume(np.linalg.norm(query_arr) > 0)

    retriever._cache["prof_test"] = (domains, texts, embeddings_matrix)

    import asyncio
    with patch.object(
      client, "embed", new_callable=AsyncMock, return_value=query_arr
    ):
      results = asyncio.run(retriever.search("prof_test", "query"))

    # 全結果のスコアが threshold 以上
    for result in results:
      assert result.score >= threshold - 1e-6, (
        f"Result score {result.score} is below threshold {threshold}"
      )

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    top_k=_top_k_st,
    threshold=_threshold_st,
    num_entries=st.integers(min_value=2, max_value=15),
    dim=st.integers(min_value=2, max_value=8),
    data=st.data(),
  )
  def test_results_respect_top_k_limit(
    self,
    top_k: int,
    threshold: float,
    num_entries: int,
    dim: int,
    data,
  ) -> None:
    """検索結果は top_k 件を超えない。

    **Validates: Requirements 6.3, 6.4**
    """
    client = EmbeddingClient(model="test", api_key="key")
    retriever = SemanticRetriever(
      embedding_client=client, top_k=top_k, threshold=threshold
    )

    # ランダムなキャッシュデータを生成
    domains = [f"domain_{i}" for i in range(num_entries)]
    texts = [f"text_{i}" for i in range(num_entries)]
    embeddings = data.draw(
      st.lists(
        st.lists(
          st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
          min_size=dim,
          max_size=dim,
        ),
        min_size=num_entries,
        max_size=num_entries,
      )
    )
    embeddings_matrix = np.array(embeddings, dtype=np.float32)

    # クエリベクトルを生成
    query_vec = data.draw(
      st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=dim,
        max_size=dim,
      )
    )
    query_arr = np.array(query_vec, dtype=np.float32)
    assume(np.linalg.norm(query_arr) > 0)

    retriever._cache["prof_test"] = (domains, texts, embeddings_matrix)

    import asyncio
    with patch.object(
      client, "embed", new_callable=AsyncMock, return_value=query_arr
    ):
      results = asyncio.run(retriever.search("prof_test", "query"))

    assert len(results) <= top_k, (
      f"Got {len(results)} results, exceeding top_k={top_k}"
    )


class TestProfileIsolationProperties:
  """profile_id 間の分離プロパティテスト"""

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(
    dim=st.integers(min_value=2, max_value=8),
    data=st.data(),
  )
  def test_profile_isolation(self, dim: int, data) -> None:
    """異なる profile_id のキャッシュは検索結果に混入しない。

    profile_A のみにキャッシュされたデータが、
    profile_B の検索結果に含まれないことを検証する。

    **Validates: Requirements 6.3, 6.4**
    """
    client = EmbeddingClient(model="test", api_key="key")
    retriever = SemanticRetriever(
      embedding_client=client, top_k=10, threshold=0.0
    )

    # 2つの profile_id を生成 (衝突回避)
    profile_a = "prof_alpha"
    profile_b = "prof_beta"

    # profile_a: ランダムベクトル (全同方向)
    num_a = data.draw(st.integers(min_value=1, max_value=5))
    domains_a = [f"a_domain_{i}" for i in range(num_a)]
    texts_a = [f"a_text_{i}" for i in range(num_a)]
    emb_a = np.ones((num_a, dim), dtype=np.float32)

    # profile_b: 直交方向ベクトル
    num_b = data.draw(st.integers(min_value=1, max_value=5))
    domains_b = [f"b_domain_{i}" for i in range(num_b)]
    texts_b = [f"b_text_{i}" for i in range(num_b)]
    emb_b = np.zeros((num_b, dim), dtype=np.float32)
    emb_b[:, 0] = -1.0  # 反対方向

    retriever._cache[profile_a] = (domains_a, texts_a, emb_a)
    retriever._cache[profile_b] = (domains_b, texts_b, emb_b)

    # クエリベクトル: 全成分 1.0 (profile_a と類似)
    query_vec = np.ones(dim, dtype=np.float32)

    import asyncio
    with patch.object(
      client, "embed", new_callable=AsyncMock, return_value=query_vec
    ):
      results_a = asyncio.run(retriever.search(profile_a, "query"))
      results_b = asyncio.run(retriever.search(profile_b, "query"))

    # profile_a の結果には profile_b のドメインが含まれない
    result_domains_a = {r.domain for r in results_a}
    result_domains_b = {r.domain for r in results_b}

    for domain in result_domains_a:
      assert domain.startswith("a_"), (
        f"Profile A results contain non-A domain: {domain}"
      )

    for domain in result_domains_b:
      assert domain.startswith("b_"), (
        f"Profile B results contain non-B domain: {domain}"
      )

  @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
  @given(data=st.data())
  def test_uncached_profile_returns_empty(self, data) -> None:
    """キャッシュに存在しない profile_id での検索は空リストを返す。

    **Validates: Requirements 6.3, 6.4**
    """
    client = EmbeddingClient(model="test", api_key="key")
    retriever = SemanticRetriever(
      embedding_client=client, top_k=5, threshold=0.0
    )

    # キャッシュに存在する profile
    retriever._cache["prof_exists"] = (
      ["d1"], ["t1"], np.array([[1.0, 0.0]], dtype=np.float32)
    )

    # 存在しない profile で検索
    random_suffix = data.draw(st.text(min_size=3, max_size=10, alphabet="abcdefgh"))
    non_existent = f"prof_{random_suffix}_missing"
    assume(non_existent not in retriever._cache)

    import asyncio
    results = asyncio.run(retriever.search(non_existent, "query"))
    assert results == [], (
      f"Non-existent profile '{non_existent}' should return empty, got: {results}"
    )
