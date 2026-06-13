"""LexicalRetriever プロパティベーステスト

Feature: agent-evolution
Property 6: Lexical retrieval correctness
Validates: Requirements 5.2, 5.3, 5.6
"""

import re

from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.evolution.lexical_retriever import LexicalRetriever


# --- Hypothesis ストラテジー ---

# ASCII タグ (英数字 + 一般的な技術用語文字)
_ascii_tag_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
  min_size=1,
  max_size=30,
)

# 日本語タグ (ひらがな・カタカナ・漢字を含む)
_japanese_tag_st = st.text(
  alphabet=st.characters(
    whitelist_categories=("Lo", "L", "N"),
    whitelist_characters="-_",
  ),
  min_size=1,
  max_size=20,
)

# 混合タグリスト (5〜30件)
_tag_list_st = st.lists(
  st.one_of(_ascii_tag_st, _japanese_tag_st),
  min_size=5,
  max_size=30,
)

# デリミタ文字 (空白・カンマ・セミコロン・スラッシュ)
_delimiter_st = st.sampled_from([" ", ", ", "; ", "/", "  ", "\t"])


# =============================================================================
# Property 6: Lexical retrieval correctness
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(tags=_tag_list_st, data=st.data())
def test_matching_tags_are_returned(tags: list[str], data) -> None:
  """クエリトークンに一致するタグがすべて結果に含まれる (completeness)。

  ランダムにタグのサブセットを選択してクエリを構成し、
  それらのタグが結果に含まれることを検証する。

  **Validates: Requirements 5.2, 5.3**
  """
  retriever = LexicalRetriever(tags)

  # タグからサブセットを選択してクエリトークンとする
  subset_size = data.draw(st.integers(min_value=1, max_value=min(5, len(tags))))
  indices = data.draw(
    st.lists(
      st.integers(min_value=0, max_value=len(tags) - 1),
      min_size=subset_size,
      max_size=subset_size,
      unique=True,
    )
  )
  query_tokens = [tags[i] for i in indices]

  # デリミタで結合してクエリ文字列を構成
  delimiter = data.draw(_delimiter_st)
  query = delimiter.join(query_tokens)

  results = retriever.search(query)

  # 選択した各タグが結果に含まれる (case-insensitive match)
  for token in query_tokens:
    matching_tags = [t for t in tags if t.lower() == token.lower()]
    for tag in matching_tags:
      assert tag in results, (
        f"Expected tag '{tag}' (from query token '{token}') not found in results: {results}"
      )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(tags=_tag_list_st, data=st.data())
def test_no_false_positives(tags: list[str], data) -> None:
  """結果に含まれるタグは必ずクエリトークンとマッチしている (precision)。

  **Validates: Requirements 5.2**
  """
  retriever = LexicalRetriever(tags)

  # ランダムクエリ文字列を生成
  query_tokens = data.draw(
    st.lists(_ascii_tag_st, min_size=1, max_size=5)
  )
  delimiter = data.draw(_delimiter_st)
  query = delimiter.join(query_tokens)

  results = retriever.search(query)
  tokenized_query = retriever.tokenize(query)

  # 結果の全タグが、クエリトークンのいずれかと case-insensitive で一致
  for result_tag in results:
    assert result_tag.lower() in tokenized_query, (
      f"Result tag '{result_tag}' does not match any query token: {tokenized_query}"
    )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(tags=_tag_list_st, data=st.data())
def test_results_ordered_by_original_position(tags: list[str], data) -> None:
  """結果は元配列の出現順で返却される (ordering invariant)。

  結果のインデックスが単調増加であることを検証する。

  **Validates: Requirements 5.3**
  """
  retriever = LexicalRetriever(tags)

  # タグからサブセットを選択してクエリ構成
  subset_size = data.draw(st.integers(min_value=1, max_value=min(5, len(tags))))
  indices = data.draw(
    st.lists(
      st.integers(min_value=0, max_value=len(tags) - 1),
      min_size=subset_size,
      max_size=subset_size,
      unique=True,
    )
  )
  query_tokens = [tags[i] for i in indices]
  delimiter = data.draw(_delimiter_st)
  query = delimiter.join(query_tokens)

  results = retriever.search(query)

  # 結果のインデックスが単調増加
  result_indices = []
  for result_tag in results:
    # 元配列での位置を取得（最初に見つかった位置）
    for i, t in enumerate(tags):
      if t == result_tag and i not in result_indices:
        result_indices.append(i)
        break

  assert result_indices == sorted(result_indices), (
    f"Result indices {result_indices} are not monotonically increasing"
  )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(tags=_tag_list_st)
def test_empty_query_returns_empty(tags: list[str]) -> None:
  """空クエリは空リストを返す。

  **Validates: Requirements 5.2**
  """
  retriever = LexicalRetriever(tags)
  results = retriever.search("")
  assert results == [], f"Empty query should return [], got: {results}"


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(tags=_tag_list_st)
def test_whitespace_only_query_returns_empty(tags: list[str]) -> None:
  """空白のみのクエリは空リストを返す。

  **Validates: Requirements 5.2**
  """
  retriever = LexicalRetriever(tags)
  results = retriever.search("   \t  ")
  assert results == [], f"Whitespace-only query should return [], got: {results}"


# case-insensitive テスト用: ASCII 英数字のみのタグ
# (Unicode case-folding の例外 µ→Μ 等を回避)
_ascii_only_tag_st = st.text(
  alphabet=st.characters(
    whitelist_categories=("Lu", "Ll", "Nd"),
    whitelist_characters="-_",
    min_codepoint=32,
    max_codepoint=127,
  ),
  min_size=1,
  max_size=20,
)

_ascii_tag_list_st = st.lists(_ascii_only_tag_st, min_size=5, max_size=20)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(tags=_ascii_tag_list_st, data=st.data())
def test_case_insensitive_matching(tags: list[str], data) -> None:
  """検索は case-insensitive で行われる。

  タグの大文字・小文字を変換したクエリでも同じ結果が返る。
  ASCII 英数字タグで検証 (Python の str.lower()/upper() が
  安定的に可逆な範囲に限定)。

  **Validates: Requirements 5.2, 5.6**
  """
  assume(len(tags) > 0)
  retriever = LexicalRetriever(tags)

  # タグからランダムに1つ選択
  idx = data.draw(st.integers(min_value=0, max_value=len(tags) - 1))
  tag = tags[idx]

  # 大文字版と小文字版の両方でクエリ
  results_upper = retriever.search(tag.upper())
  results_lower = retriever.search(tag.lower())

  # 同じタグセットが返ることを検証 (順序は保持)
  assert results_upper == results_lower, (
    f"Case-insensitive mismatch: "
    f"upper='{tag.upper()}' → {results_upper}, "
    f"lower='{tag.lower()}' → {results_lower}"
  )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(tags=_tag_list_st, data=st.data())
def test_non_matching_query_returns_empty(tags: list[str], data) -> None:
  """どのタグとも一致しないクエリは空リストを返す。

  **Validates: Requirements 5.2**
  """
  retriever = LexicalRetriever(tags)

  # タグに含まれないことが保証されるランダム文字列を生成
  non_matching = data.draw(
    st.text(
      alphabet=st.characters(whitelist_categories=("L",), whitelist_characters="@#$%"),
      min_size=10,
      max_size=20,
    )
  )
  # 生成した文字列がどのタグとも一致しないことを前提条件にする
  assume(non_matching.lower() not in {t.lower() for t in tags})

  results = retriever.search(non_matching)
  assert results == [], (
    f"Non-matching query '{non_matching}' should return [], got: {results}"
  )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
def test_tokenization_splits_on_delimiters(data) -> None:
  """トークン化は空白・カンマ・セミコロン・スラッシュで分割する。

  **Validates: Requirements 5.6**
  """
  # 複数のトークンをデリミタで結合
  tokens = data.draw(
    st.lists(_ascii_tag_st, min_size=2, max_size=5)
  )
  delimiters = [" ", ",", ";", "/", ", ", "; ", " / "]
  delimiter = data.draw(st.sampled_from(delimiters))
  text = delimiter.join(tokens)

  retriever = LexicalRetriever([])
  result_tokens = retriever.tokenize(text)

  # 各元トークンが分割結果に含まれる
  for token in tokens:
    assert token.lower() in result_tokens, (
      f"Token '{token.lower()}' not found in tokenized result: {result_tokens}"
    )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
def test_japanese_text_tokenization(data) -> None:
  """日本語テキストはデリミタで分割され、個々の文字に分解されない。

  **Validates: Requirements 5.6**
  """
  # 日本語テキストをデリミタで結合
  japanese_words = data.draw(
    st.lists(
      st.sampled_from([
        "プログラミング", "テスト", "設計", "開発", "品質管理",
        "アジャイル", "スクラム", "リファクタリング", "デプロイ",
      ]),
      min_size=2,
      max_size=4,
      unique=True,
    )
  )
  delimiter = data.draw(st.sampled_from([",", ";", "/", " "]))
  text = delimiter.join(japanese_words)

  retriever = LexicalRetriever([])
  result_tokens = retriever.tokenize(text)

  # 各日本語単語が丸ごと1トークンとして含まれる
  for word in japanese_words:
    assert word.lower() in result_tokens, (
      f"Japanese word '{word}' not found as a whole token in: {result_tokens}"
    )

  # 個々の文字に分解されていないことを検証
  # (結果トークン数が元の単語数以下+デリミタ連続による空除去)
  assert len(result_tokens) <= len(japanese_words), (
    f"Tokenization produced more tokens ({len(result_tokens)}) than "
    f"input words ({len(japanese_words)}): {result_tokens}"
  )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(tags=_tag_list_st, data=st.data())
def test_duplicate_tags_all_returned(tags: list[str], data) -> None:
  """同一タグが複数存在する場合、全出現位置のタグが返される。

  **Validates: Requirements 5.3**
  """
  # タグリストに重複を追加
  assume(len(tags) > 0)
  idx = data.draw(st.integers(min_value=0, max_value=len(tags) - 1))
  dup_tag = tags[idx]
  # 重複タグをリストの末尾に追加
  extended_tags = tags + [dup_tag]

  retriever = LexicalRetriever(extended_tags)
  results = retriever.search(dup_tag)

  # 重複タグの全出現回数を数える
  expected_count = sum(1 for t in extended_tags if t.lower() == dup_tag.lower())
  actual_count = sum(1 for r in results if r.lower() == dup_tag.lower())

  assert actual_count == expected_count, (
    f"Tag '{dup_tag}' appears {expected_count} times in input but "
    f"{actual_count} times in results"
  )
