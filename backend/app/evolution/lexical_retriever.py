"""Lexical Retriever: O(1) 完全一致キーワード検索

lexical_tags 配列からハッシュインデックスを構築し、
クエリトークンとの完全一致（case-insensitive）でタグを返す。
"""

import logging
import re

logger = logging.getLogger(__name__)


class LexicalRetriever:
  """O(1) 完全一致キーワード検索

  lexical_tags 配列からハッシュインデックスを構築し、
  クエリトークンとの完全一致（case-insensitive）でタグを返す。
  結果は元配列の出現順で返却される。
  """

  # トークン分割パターン: 空白・カンマ・セミコロン・スラッシュ
  # 日本語テキストもサポート（全角スペースも空白として扱われる）
  _DELIMITERS = re.compile(r"[\s,;/]+")

  def __init__(self, tags: list[str]):
    """ハッシュインデックスを構築する。

    Args:
      tags: lexical_tags 配列（プロファイルから取得）
    """
    self._tags = tags
    self._index: dict[str, list[int]] = {}
    self._build_index(tags)
    logger.debug("LexicalRetriever initialized with %d tags", len(tags))

  def _build_index(self, tags: list[str]) -> None:
    """ハッシュインデックスを構築する。

    tag_lower → original index のマッピングを作成。
    同一の小文字キーが複数存在する場合、全インデックスを保持する。
    """
    for i, tag in enumerate(tags):
      key = tag.lower()
      if key not in self._index:
        self._index[key] = []
      self._index[key].append(i)

  def search(self, query: str) -> list[str]:
    """クエリをトークン化し、完全一致するタグを元配列の順序で返す。

    Args:
      query: 検索文字列（空白/カンマ/セミコロン/スラッシュで分割）

    Returns:
      マッチしたタグのリスト（元配列の出現順）
    """
    tokens = self.tokenize(query)
    if not tokens:
      return []

    # マッチしたインデックスを収集
    matched_indices: set[int] = set()
    for token in tokens:
      if token in self._index:
        matched_indices.update(self._index[token])

    # 元配列の出現順でソート
    sorted_indices = sorted(matched_indices)
    return [self._tags[i] for i in sorted_indices]

  def tokenize(self, text: str) -> list[str]:
    """テキストをトークンに分割する（日本語対応）。

    空白・カンマ・セミコロン・スラッシュで分割し、
    小文字に正規化して空文字列を除外する。

    Args:
      text: 分割対象のテキスト

    Returns:
      小文字正規化済みトークンのリスト
    """
    return [t for t in self._DELIMITERS.split(text.lower()) if t]
