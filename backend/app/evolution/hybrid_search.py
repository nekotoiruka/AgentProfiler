"""Hybrid Search Engine: Lexical + Semantic 検索の統合エンジン

両 retriever を並列実行し、重み付けスコアで統合・重複排除する。
weight パラメータで Lexical / Semantic の比重を制御し、
結果にソースタイプとスコアを付与して降順ソートで返却する。
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

from app.evolution.lexical_retriever import LexicalRetriever
from app.evolution.semantic_retriever import SemanticResult, SemanticRetriever

logger = logging.getLogger(__name__)


class ResultSource(str, Enum):
  """検索結果のソースタイプ"""

  LEXICAL = "lexical"
  SEMANTIC = "semantic"


@dataclass
class HybridResult:
  """ハイブリッド検索統合結果"""

  content: str
  source: ResultSource
  score: float
  domain: str | None = None  # semantic 結果のみ


class HybridSearchEngine:
  """Lexical + Semantic 検索の統合エンジン

  両 retriever を並列実行し、重み付けスコアで統合・重複排除する。
  weight=0.0 で lexical only、weight=1.0 で semantic only となる。
  """

  def __init__(
    self,
    lexical_retriever: LexicalRetriever,
    semantic_retriever: SemanticRetriever,
    weight: float = 0.5,
  ):
    """HybridSearchEngine を初期化する。

    Args:
      lexical_retriever: キーワード完全一致検索エンジン
      semantic_retriever: ベクトル cosine similarity 検索エンジン
      weight: semantic 側の重み (0.0〜1.0)。
              0.0 = lexical only, 1.0 = semantic only
    """
    self._lexical = lexical_retriever
    self._semantic = semantic_retriever
    self._weight = weight
    logger.debug("HybridSearchEngine initialized: weight=%.2f", self._weight)

  async def search(
    self, profile_id: str, query: str
  ) -> list[HybridResult]:
    """ハイブリッド検索を実行し、統合結果を返す。

    Lexical match のスコアは 1.0 固定（完全一致）。
    Semantic match のスコアは cosine similarity 値。
    最終スコア = (1 - weight) * lexical_score + weight * semantic_score

    重複排除: lexical tag が semantic domain のキーと一致する場合（case-insensitive）、
    semantic 側を優先（コンテキスト情報が豊富なため）。

    結果は最終スコア降順でソートされる。

    Args:
      profile_id: 検索対象のプロファイル識別子
      query: 検索クエリテキスト

    Returns:
      HybridResult のリスト（スコア降順）
    """
    # Lexical (sync) と Semantic (async) を並列実行
    lexical_tags, semantic_results = await asyncio.gather(
      asyncio.to_thread(self._lexical.search, query),
      self._semantic.search(profile_id, query),
    )

    logger.debug(
      "search: lexical=%d results, semantic=%d results",
      len(lexical_tags),
      len(semantic_results),
    )

    # semantic domain キーを小文字で集める（重複排除用）
    semantic_domains_lower: set[str] = {
      r.domain.lower() for r in semantic_results
    }

    results: list[HybridResult] = []

    # Lexical 結果を追加（重複排除: semantic domain と一致するタグは除外）
    for tag in lexical_tags:
      if tag.lower() in semantic_domains_lower:
        # semantic 側に同じドメインがある → lexical 側を除外し semantic を優先
        logger.debug("dedup: lexical tag '%s' matches semantic domain, skipping", tag)
        continue
      # Lexical スコア: 完全一致 = 1.0、weight 調整後 = (1 - weight) * 1.0
      adjusted_score = (1 - self._weight) * 1.0
      results.append(HybridResult(
        content=tag,
        source=ResultSource.LEXICAL,
        score=adjusted_score,
      ))

    # Semantic 結果を追加
    for sr in semantic_results:
      # Semantic スコア: cosine similarity、weight 調整後 = weight * score
      adjusted_score = self._weight * sr.score
      results.append(HybridResult(
        content=sr.text,
        source=ResultSource.SEMANTIC,
        score=adjusted_score,
        domain=sr.domain,
      ))

    # 最終スコア降順でソート
    results.sort(key=lambda r: r.score, reverse=True)

    logger.info(
      "search: returning %d hybrid results for profile_id=%s",
      len(results),
      profile_id,
    )
    return results
