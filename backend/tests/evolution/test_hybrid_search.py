"""HybridSearchEngine ユニットテスト

LexicalRetriever と SemanticRetriever をモックし、
HybridSearchEngine の統合・重複排除・スコアリングの振る舞いを検証する。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.evolution.hybrid_search import HybridResult, HybridSearchEngine, ResultSource
from app.evolution.lexical_retriever import LexicalRetriever
from app.evolution.semantic_retriever import SemanticResult, SemanticRetriever


@pytest.fixture
def mock_lexical() -> MagicMock:
  """モック LexicalRetriever"""
  retriever = MagicMock(spec=LexicalRetriever)
  retriever.search.return_value = []
  return retriever


@pytest.fixture
def mock_semantic() -> AsyncMock:
  """モック SemanticRetriever"""
  retriever = AsyncMock(spec=SemanticRetriever)
  retriever.search.return_value = []
  return retriever


@pytest.fixture
def engine(mock_lexical: MagicMock, mock_semantic: AsyncMock) -> HybridSearchEngine:
  """デフォルト weight=0.5 の HybridSearchEngine"""
  return HybridSearchEngine(
    lexical_retriever=mock_lexical,
    semantic_retriever=mock_semantic,
    weight=0.5,
  )


class TestBasicSearch:
  """基本的な検索動作のテスト"""

  @pytest.mark.asyncio
  async def test_empty_results_from_both(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """両方空の場合は空リストを返す"""
    mock_lexical.search.return_value = []
    mock_semantic.search.return_value = []

    results = await engine.search("prof_001", "query")
    assert results == []

  @pytest.mark.asyncio
  async def test_lexical_only_results(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """Lexical のみ結果がある場合"""
    mock_lexical.search.return_value = ["python", "fastapi"]
    mock_semantic.search.return_value = []

    results = await engine.search("prof_001", "python fastapi")

    assert len(results) == 2
    assert all(r.source == ResultSource.LEXICAL for r in results)
    # weight=0.5 なので adjusted = (1-0.5)*1.0 = 0.5
    assert all(r.score == pytest.approx(0.5) for r in results)
    assert results[0].domain is None

  @pytest.mark.asyncio
  async def test_semantic_only_results(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """Semantic のみ結果がある場合"""
    mock_lexical.search.return_value = []
    mock_semantic.search.return_value = [
      SemanticResult(domain="coding", text="Python is great", score=0.9),
      SemanticResult(domain="design", text="Clean architecture", score=0.8),
    ]

    results = await engine.search("prof_001", "programming")

    assert len(results) == 2
    assert all(r.source == ResultSource.SEMANTIC for r in results)
    # weight=0.5: 0.5*0.9=0.45, 0.5*0.8=0.40
    assert results[0].score == pytest.approx(0.45)
    assert results[1].score == pytest.approx(0.40)
    assert results[0].domain == "coding"
    assert results[1].domain == "design"

  @pytest.mark.asyncio
  async def test_mixed_results_sorted_by_score(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """Lexical + Semantic の混合結果はスコア降順でソートされる"""
    mock_lexical.search.return_value = ["typescript"]
    mock_semantic.search.return_value = [
      SemanticResult(domain="coding", text="TS patterns", score=0.95),
    ]

    results = await engine.search("prof_001", "typescript")

    assert len(results) == 2
    # Lexical: (1-0.5)*1.0 = 0.5
    # Semantic: 0.5*0.95 = 0.475
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0].source == ResultSource.LEXICAL
    assert results[1].source == ResultSource.SEMANTIC


class TestDeduplication:
  """重複排除のテスト"""

  @pytest.mark.asyncio
  async def test_lexical_tag_matching_semantic_domain_is_excluded(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """lexical tag が semantic domain と一致する場合、lexical 側を除外"""
    mock_lexical.search.return_value = ["coding", "python"]
    mock_semantic.search.return_value = [
      SemanticResult(domain="coding", text="I love coding", score=0.9),
    ]

    results = await engine.search("prof_001", "coding python")

    # "coding" は semantic domain と一致 → lexical 除外
    # "python" は semantic にない → lexical 保持
    # semantic "coding" は残る
    assert len(results) == 2
    lexical_results = [r for r in results if r.source == ResultSource.LEXICAL]
    semantic_results = [r for r in results if r.source == ResultSource.SEMANTIC]
    assert len(lexical_results) == 1
    assert lexical_results[0].content == "python"
    assert len(semantic_results) == 1
    assert semantic_results[0].domain == "coding"

  @pytest.mark.asyncio
  async def test_deduplication_is_case_insensitive(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """重複排除は case-insensitive で行われる"""
    mock_lexical.search.return_value = ["Python", "CODING"]
    mock_semantic.search.return_value = [
      SemanticResult(domain="python", text="Python text", score=0.85),
      SemanticResult(domain="Coding", text="Coding text", score=0.80),
    ]

    results = await engine.search("prof_001", "python coding")

    # "Python".lower() == "python" (semantic domain) → 除外
    # "CODING".lower() == "coding" == "Coding".lower() → 除外
    lexical_results = [r for r in results if r.source == ResultSource.LEXICAL]
    assert len(lexical_results) == 0

    semantic_results = [r for r in results if r.source == ResultSource.SEMANTIC]
    assert len(semantic_results) == 2


class TestWeighting:
  """重み付けスコアのテスト"""

  @pytest.mark.asyncio
  async def test_weight_zero_lexical_only(
    self, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """weight=0.0: lexical スコアが最大、semantic スコアが 0"""
    engine = HybridSearchEngine(mock_lexical, mock_semantic, weight=0.0)
    mock_lexical.search.return_value = ["tag1"]
    mock_semantic.search.return_value = [
      SemanticResult(domain="d1", text="text", score=0.9),
    ]

    results = await engine.search("prof_001", "query")

    lexical_r = [r for r in results if r.source == ResultSource.LEXICAL]
    semantic_r = [r for r in results if r.source == ResultSource.SEMANTIC]
    # (1-0)*1.0 = 1.0
    assert lexical_r[0].score == pytest.approx(1.0)
    # 0*0.9 = 0.0
    assert semantic_r[0].score == pytest.approx(0.0)

  @pytest.mark.asyncio
  async def test_weight_one_semantic_only(
    self, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """weight=1.0: lexical スコアが 0、semantic スコアが最大"""
    engine = HybridSearchEngine(mock_lexical, mock_semantic, weight=1.0)
    mock_lexical.search.return_value = ["tag1"]
    mock_semantic.search.return_value = [
      SemanticResult(domain="d1", text="text", score=0.9),
    ]

    results = await engine.search("prof_001", "query")

    lexical_r = [r for r in results if r.source == ResultSource.LEXICAL]
    semantic_r = [r for r in results if r.source == ResultSource.SEMANTIC]
    # (1-1)*1.0 = 0.0
    assert lexical_r[0].score == pytest.approx(0.0)
    # 1*0.9 = 0.9
    assert semantic_r[0].score == pytest.approx(0.9)

  @pytest.mark.asyncio
  async def test_custom_weight(
    self, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """weight=0.7: lexical=0.3, semantic=0.7*score"""
    engine = HybridSearchEngine(mock_lexical, mock_semantic, weight=0.7)
    mock_lexical.search.return_value = ["tag1"]
    mock_semantic.search.return_value = [
      SemanticResult(domain="d1", text="text", score=0.8),
    ]

    results = await engine.search("prof_001", "query")

    lexical_r = [r for r in results if r.source == ResultSource.LEXICAL]
    semantic_r = [r for r in results if r.source == ResultSource.SEMANTIC]
    # (1-0.7)*1.0 = 0.3
    assert lexical_r[0].score == pytest.approx(0.3)
    # 0.7*0.8 = 0.56
    assert semantic_r[0].score == pytest.approx(0.56)


class TestResultStructure:
  """結果データ構造のテスト"""

  @pytest.mark.asyncio
  async def test_lexical_result_fields(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """Lexical 結果のフィールドが正しい"""
    mock_lexical.search.return_value = ["vue"]
    mock_semantic.search.return_value = []

    results = await engine.search("prof_001", "vue")

    assert len(results) == 1
    r = results[0]
    assert r.content == "vue"
    assert r.source == ResultSource.LEXICAL
    assert r.score == pytest.approx(0.5)
    assert r.domain is None

  @pytest.mark.asyncio
  async def test_semantic_result_fields(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """Semantic 結果のフィールドが正しい"""
    mock_lexical.search.return_value = []
    mock_semantic.search.return_value = [
      SemanticResult(domain="testing", text="TDD approach", score=0.88),
    ]

    results = await engine.search("prof_001", "testing")

    assert len(results) == 1
    r = results[0]
    assert r.content == "TDD approach"
    assert r.source == ResultSource.SEMANTIC
    assert r.score == pytest.approx(0.44)
    assert r.domain == "testing"


class TestParallelExecution:
  """並列実行の検証"""

  @pytest.mark.asyncio
  async def test_both_retrievers_are_called(
    self, engine: HybridSearchEngine, mock_lexical: MagicMock, mock_semantic: AsyncMock
  ) -> None:
    """両 retriever が呼び出される"""
    mock_lexical.search.return_value = []
    mock_semantic.search.return_value = []

    await engine.search("prof_001", "query")

    mock_lexical.search.assert_called_once_with("query")
    mock_semantic.search.assert_called_once_with("prof_001", "query")
