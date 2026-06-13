"""SemanticRetriever ユニットテスト

EmbeddingClient をモックし、SemanticRetriever の振る舞いを検証する。
"""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from app.evolution.embedding_client import EmbeddingClient
from app.evolution.semantic_retriever import SemanticResult, SemanticRetriever


@pytest.fixture
def mock_embedding_client() -> EmbeddingClient:
  """モック済み EmbeddingClient"""
  client = EmbeddingClient(model="test-model", api_key="test-key")
  return client


@pytest.fixture
def retriever(mock_embedding_client: EmbeddingClient) -> SemanticRetriever:
  """テスト用 SemanticRetriever（top_k=3, threshold=0.7）"""
  return SemanticRetriever(
    embedding_client=mock_embedding_client,
    top_k=3,
    threshold=0.7,
  )


class TestCosineSimilarity:
  """cosine_similarity 静的メソッドのテスト"""

  def test_identical_vectors_return_1(self) -> None:
    """同一ベクトルの cosine similarity は 1.0"""
    a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert SemanticRetriever.cosine_similarity(a, a) == pytest.approx(1.0)

  def test_orthogonal_vectors_return_0(self) -> None:
    """直交ベクトルの cosine similarity は 0.0"""
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0], dtype=np.float32)
    assert SemanticRetriever.cosine_similarity(a, b) == pytest.approx(0.0)

  def test_zero_vector_a_returns_0(self) -> None:
    """ベクトル A がゼロの場合は 0.0"""
    a = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert SemanticRetriever.cosine_similarity(a, b) == 0.0

  def test_zero_vector_b_returns_0(self) -> None:
    """ベクトル B がゼロの場合は 0.0"""
    a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    b = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    assert SemanticRetriever.cosine_similarity(a, b) == 0.0

  def test_both_zero_vectors_return_0(self) -> None:
    """両方ゼロベクトルの場合は 0.0"""
    a = np.array([0.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 0.0], dtype=np.float32)
    assert SemanticRetriever.cosine_similarity(a, b) == 0.0

  def test_opposite_vectors_return_negative(self) -> None:
    """逆方向ベクトルの cosine similarity は -1.0"""
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([-1.0, 0.0], dtype=np.float32)
    assert SemanticRetriever.cosine_similarity(a, b) == pytest.approx(-1.0)


class TestIndexProfile:
  """index_profile() のテスト"""

  @pytest.mark.asyncio
  async def test_caches_embeddings_on_success(self, retriever: SemanticRetriever) -> None:
    """正常時: キャッシュにドメイン・テキスト・埋め込み行列が保存される"""
    contexts = {"domain1": "text one", "domain2": "text two"}
    mock_embeddings = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)

    with patch.object(
      retriever._embedding_client, "embed_batch", new_callable=AsyncMock, return_value=mock_embeddings
    ):
      await retriever.index_profile("prof_001", contexts)

    assert "prof_001" in retriever._cache
    domains, texts, matrix = retriever._cache["prof_001"]
    assert domains == ["domain1", "domain2"]
    assert texts == ["text one", "text two"]
    np.testing.assert_array_equal(matrix, mock_embeddings)

  @pytest.mark.asyncio
  async def test_does_not_cache_on_api_failure(self, retriever: SemanticRetriever) -> None:
    """API 不通時: キャッシュに何も保存しない"""
    contexts = {"domain1": "text one"}
    empty_result = np.empty((0, 0), dtype=np.float32)

    with patch.object(
      retriever._embedding_client, "embed_batch", new_callable=AsyncMock, return_value=empty_result
    ):
      await retriever.index_profile("prof_002", contexts)

    assert "prof_002" not in retriever._cache

  @pytest.mark.asyncio
  async def test_skips_empty_contexts(self, retriever: SemanticRetriever) -> None:
    """空の semantic_contexts: キャッシュに何も保存しない"""
    await retriever.index_profile("prof_003", {})
    assert "prof_003" not in retriever._cache


class TestSearch:
  """search() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_empty_for_unknown_profile(self, retriever: SemanticRetriever) -> None:
    """未キャッシュの profile_id に対しては空リスト"""
    result = await retriever.search("unknown_profile", "query")
    assert result == []

  @pytest.mark.asyncio
  async def test_returns_empty_on_query_embedding_failure(self, retriever: SemanticRetriever) -> None:
    """クエリ埋め込み生成失敗時: 空リスト"""
    # キャッシュにダミーデータを設定
    retriever._cache["prof_001"] = (
      ["domain1"],
      ["text one"],
      np.array([[1.0, 0.0]], dtype=np.float32),
    )

    with patch.object(
      retriever._embedding_client, "embed", new_callable=AsyncMock,
      return_value=np.array([], dtype=np.float32),
    ):
      result = await retriever.search("prof_001", "query")

    assert result == []

  @pytest.mark.asyncio
  async def test_returns_results_above_threshold(self, retriever: SemanticRetriever) -> None:
    """閾値以上のスコアを持つ結果のみ返す"""
    # 同一方向ベクトル (similarity=1.0) と直交ベクトル (similarity=0.0)
    retriever._cache["prof_001"] = (
      ["high_sim", "low_sim"],
      ["text high", "text low"],
      np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
    )

    # クエリベクトル: [1.0, 0.0] → high_sim=1.0, low_sim=0.0
    with patch.object(
      retriever._embedding_client, "embed", new_callable=AsyncMock,
      return_value=np.array([1.0, 0.0], dtype=np.float32),
    ):
      result = await retriever.search("prof_001", "query")

    assert len(result) == 1
    assert result[0].domain == "high_sim"
    assert result[0].score == pytest.approx(1.0)

  @pytest.mark.asyncio
  async def test_respects_top_k_limit(self) -> None:
    """top_k を超える結果は切り捨てる"""
    client = EmbeddingClient(model="test", api_key="key")
    retriever = SemanticRetriever(embedding_client=client, top_k=2, threshold=0.0)

    # 4つのベクトル全てがクエリと高い類似度を持つ
    retriever._cache["prof_001"] = (
      ["d1", "d2", "d3", "d4"],
      ["t1", "t2", "t3", "t4"],
      np.array([
        [1.0, 0.0],
        [0.9, 0.1],
        [0.8, 0.2],
        [0.7, 0.3],
      ], dtype=np.float32),
    )

    with patch.object(
      client, "embed", new_callable=AsyncMock,
      return_value=np.array([1.0, 0.0], dtype=np.float32),
    ):
      result = await retriever.search("prof_001", "query")

    assert len(result) == 2

  @pytest.mark.asyncio
  async def test_results_sorted_descending_by_score(self, retriever: SemanticRetriever) -> None:
    """結果はスコア降順でソートされる"""
    retriever._cache["prof_001"] = (
      ["d1", "d2", "d3"],
      ["t1", "t2", "t3"],
      np.array([
        [0.8, 0.2],
        [1.0, 0.0],
        [0.9, 0.1],
      ], dtype=np.float32),
    )

    with patch.object(
      retriever._embedding_client, "embed", new_callable=AsyncMock,
      return_value=np.array([1.0, 0.0], dtype=np.float32),
    ):
      result = await retriever.search("prof_001", "query")

    # threshold=0.7 なので全て通過する想定
    scores = [r.score for r in result]
    assert scores == sorted(scores, reverse=True)

  @pytest.mark.asyncio
  async def test_result_contains_correct_fields(self, retriever: SemanticRetriever) -> None:
    """SemanticResult に正しいフィールドが含まれる"""
    retriever._cache["prof_001"] = (
      ["coding"],
      ["I love Python programming"],
      np.array([[1.0, 0.0]], dtype=np.float32),
    )

    with patch.object(
      retriever._embedding_client, "embed", new_callable=AsyncMock,
      return_value=np.array([1.0, 0.0], dtype=np.float32),
    ):
      result = await retriever.search("prof_001", "Python")

    assert len(result) == 1
    assert isinstance(result[0], SemanticResult)
    assert result[0].domain == "coding"
    assert result[0].text == "I love Python programming"
    assert result[0].score == pytest.approx(1.0)


class TestProfileIsolation:
  """profile_id 間のキャッシュ隔離テスト"""

  @pytest.mark.asyncio
  async def test_different_profiles_are_isolated(self, retriever: SemanticRetriever) -> None:
    """異なる profile_id のキャッシュは独立している"""
    retriever._cache["prof_A"] = (
      ["domain_a"],
      ["text_a"],
      np.array([[1.0, 0.0]], dtype=np.float32),
    )
    retriever._cache["prof_B"] = (
      ["domain_b"],
      ["text_b"],
      np.array([[0.0, 1.0]], dtype=np.float32),
    )

    # prof_A で検索: [1.0, 0.0] と類似
    with patch.object(
      retriever._embedding_client, "embed", new_callable=AsyncMock,
      return_value=np.array([1.0, 0.0], dtype=np.float32),
    ):
      result_a = await retriever.search("prof_A", "query")
      result_b = await retriever.search("prof_B", "query")

    assert len(result_a) == 1
    assert result_a[0].domain == "domain_a"
    # prof_B のベクトル [0.0, 1.0] はクエリ [1.0, 0.0] と直交 → threshold 以下
    assert len(result_b) == 0
