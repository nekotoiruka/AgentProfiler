"""Context Layer Manager: 3層コンテキストのライフサイクル管理

Layer 1 (Base OS): セッション開始時にロード、常駐
Layer 2 (Agent Skills): Function Calling 時に Lexical 検索で動的挿入
Layer 3 (MCP): MCP サーバー経由で Semantic コンテキストを動的フェッチ
"""

import asyncio
import logging

from app.evolution.lexical_retriever import LexicalRetriever
from app.evolution.semantic_retriever import SemanticRetriever
from app.models.profile import BaseOS, ProfileOutput

logger = logging.getLogger(__name__)


class ContextLayerManager:
  """3層コンテキストのライフサイクル管理

  Layer 1 (Base OS): セッション開始時にロード、常駐
  Layer 2 (Agent Skills): Function Calling 時に Lexical 検索で動的挿入
  Layer 3 (MCP): MCP サーバー経由で Semantic コンテキストを動的フェッチ

  profile_id 間で Base OS キャッシュを共有し、メモリ割当を最小化する。
  """

  def __init__(
    self,
    lexical_retriever: LexicalRetriever | None = None,
    semantic_retriever: SemanticRetriever | None = None,
    mcp_timeout: float = 5.0,
  ):
    """ContextLayerManager を初期化する。

    Args:
      lexical_retriever: Layer 2 用の Lexical 検索コンポーネント（未使用、互換性のため保持）
      semantic_retriever: Layer 3 用の Semantic 検索コンポーネント
      mcp_timeout: MCP サーバーへの接続タイムアウト秒数（デフォルト5秒）
    """
    # profile_id → BaseOS のインメモリキャッシュ（セッション間で共有）
    self._base_os_cache: dict[str, BaseOS] = {}
    # profile_id → LexicalRetriever（プロファイルごとに個別インスタンス）
    self._lexical_retrievers: dict[str, LexicalRetriever] = {}
    # profile_id → semantic_contexts（MCP フォールバック用ローカルデータ）
    self._semantic_contexts_local: dict[str, dict[str, str]] = {}
    self._semantic_retriever = semantic_retriever
    self._mcp_timeout = mcp_timeout
    logger.debug(
      "ContextLayerManager initialized: mcp_timeout=%.1fs",
      self._mcp_timeout,
    )

  async def load_profile(self, profile: ProfileOutput) -> None:
    """プロファイルをロードし、3層すべてを初期化する。

    context_layers の layer 割り当てをバリデーションし、
    各レイヤーのデータを初期化・キャッシュする。

    Validates:
    - context_layers.base_os == 1
    - context_layers.lexical_tags == 2
    - context_layers.semantic_contexts == 3

    Args:
      profile: ロード対象の ProfileOutput

    Raises:
      ValueError: context_layers の layer 割り当てが不正な場合
    """
    # context_layers バリデーション
    if profile.context_layers.base_os != 1:
      raise ValueError(
        f"context_layers.base_os must be 1, got {profile.context_layers.base_os}"
      )
    if profile.context_layers.lexical_tags != 2:
      raise ValueError(
        f"context_layers.lexical_tags must be 2, got {profile.context_layers.lexical_tags}"
      )
    if profile.context_layers.semantic_contexts != 3:
      raise ValueError(
        f"context_layers.semantic_contexts must be 3, got {profile.context_layers.semantic_contexts}"
      )

    # Layer 1: Base OS をキャッシュ（profile_id 間で共有）
    self._base_os_cache[profile.profile_id] = profile.base_os
    logger.info("Layer 1 (Base OS) cached for profile_id=%s", profile.profile_id)

    # Layer 2: LexicalRetriever を構築
    self._lexical_retrievers[profile.profile_id] = LexicalRetriever(profile.lexical_tags)
    logger.info(
      "Layer 2 (Lexical) indexed %d tags for profile_id=%s",
      len(profile.lexical_tags),
      profile.profile_id,
    )

    # Layer 3: ローカル semantic_contexts を保存 + SemanticRetriever にインデックス
    self._semantic_contexts_local[profile.profile_id] = profile.semantic_contexts
    if self._semantic_retriever:
      await self._semantic_retriever.index_profile(
        profile.profile_id, profile.semantic_contexts
      )
    logger.info(
      "Layer 3 (Semantic) stored %d contexts for profile_id=%s",
      len(profile.semantic_contexts),
      profile.profile_id,
    )

  def get_base_os(self, profile_id: str) -> BaseOS:
    """Layer 1: キャッシュ済み Base OS を返す。

    セッション間で共有されるインメモリキャッシュから Base OS データを返却する。
    プロファイルが未ロードの場合は KeyError を送出する。

    Args:
      profile_id: 対象のプロファイル識別子

    Returns:
      キャッシュ済みの BaseOS データ

    Raises:
      KeyError: profile_id が未ロードの場合
    """
    if profile_id not in self._base_os_cache:
      raise KeyError(f"Profile '{profile_id}' is not loaded")
    return self._base_os_cache[profile_id]

  async def get_skill_context(
    self, profile_id: str, function_name: str, params: dict
  ) -> list[str]:
    """Layer 2: Function Calling コンテキストに基づくスキル検索。

    function_name とパラメータ値を結合してクエリを構築し、
    LexicalRetriever で完全一致検索を実行する。
    マッチしたタグをスキルコンテキストとして返却する。

    Args:
      profile_id: 対象のプロファイル識別子
      function_name: 呼び出し対象の関数名
      params: 関数のパラメータ辞書

    Returns:
      マッチしたタグのリスト（元配列の出現順）。
      profile_id が未ロードの場合は空リスト。
    """
    if profile_id not in self._lexical_retrievers:
      return []
    retriever = self._lexical_retrievers[profile_id]
    # function_name + パラメータ値をクエリトークンとして結合
    query_parts = [function_name] + [str(v) for v in params.values() if v]
    query = " ".join(query_parts)
    return retriever.search(query)

  async def get_semantic_context(
    self, profile_id: str, query: str
  ) -> dict[str, str]:
    """Layer 3: MCP 経由 or ローカルフォールバックでセマンティックコンテキスト取得。

    SemanticRetriever が利用可能な場合はベクトル検索を実行する。
    タイムアウト（mcp_timeout 秒）またはエラー発生時は
    ローカルの semantic_contexts にフォールバックする。

    PoC段階: MCP 統合は Task 13.1 で追加予定。
    現在は SemanticRetriever → ローカルデータのフォールバックチェーン。

    Args:
      profile_id: 対象のプロファイル識別子
      query: 検索クエリテキスト

    Returns:
      domain → テキストの辞書。
      profile_id が未ロードの場合は空辞書。
    """
    if profile_id not in self._semantic_contexts_local:
      return {}

    # SemanticRetriever でのベクトル検索を試行（タイムアウト付き）
    if self._semantic_retriever:
      try:
        results = await asyncio.wait_for(
          self._semantic_retriever.search(profile_id, query),
          timeout=self._mcp_timeout,
        )
        if results:
          return {r.domain: r.text for r in results}
      except asyncio.TimeoutError:
        logger.warning(
          "Semantic retriever timed out (%.1fs) for profile_id=%s, "
          "falling back to local data",
          self._mcp_timeout,
          profile_id,
        )
      except Exception as e:
        logger.warning(
          "Semantic retriever error for profile_id=%s: %s, "
          "falling back to local data",
          profile_id,
          e,
        )

    # フォールバック: ローカルの semantic_contexts を全件返却
    return self._semantic_contexts_local[profile_id]
