"""RoutingEngine プロパティベーステスト

Feature: agent-evolution
Property 13: Routing classification determinism
Validates: Requirements 9.1, 9.4
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.evolution.routing_engine import RoutingEngine, Complexity


# --- Hypothesis ストラテジー ---

# 発話テキスト: 空文字列〜100文字のランダムテキスト
_utterance_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
  min_size=0,
  max_size=100,
)

# matched_tags: None or 0〜5件のタグリスト
_tag_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=20,
)
_matched_tags_st = st.one_of(
  st.none(),
  st.lists(_tag_st, min_size=0, max_size=5),
)

# routing_hint: None, "light", "deep", または無効な文字列
_routing_hint_st = st.one_of(
  st.none(),
  st.just("light"),
  st.just("deep"),
  st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=1,
    max_size=10,
  ).filter(lambda s: s.lower() not in ("light", "deep")),
)

# token_threshold: 正の整数
_threshold_st = st.integers(min_value=1, max_value=200)


# =============================================================================
# Property 13: Routing classification determinism
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(
  utterance=_utterance_st,
  matched_tags=_matched_tags_st,
  routing_hint=_routing_hint_st,
  threshold=_threshold_st,
)
def test_classify_is_deterministic(
  utterance: str,
  matched_tags: list[str] | None,
  routing_hint: str | None,
  threshold: int,
) -> None:
  """同一入力に対して classify() は常に同じ Complexity 値を返す。

  **Validates: Requirements 9.1, 9.4**
  """
  engine = RoutingEngine(token_threshold=threshold)

  result1 = engine.classify(utterance, matched_tags, routing_hint)
  result2 = engine.classify(utterance, matched_tags, routing_hint)
  result3 = engine.classify(utterance, matched_tags, routing_hint)

  assert result1 == result2 == result3, (
    f"Non-deterministic classification: {result1}, {result2}, {result3} "
    f"for utterance={utterance!r}, tags={matched_tags}, hint={routing_hint}"
  )


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(
  utterance=_utterance_st,
  matched_tags=_matched_tags_st,
  routing_hint=st.sampled_from(["light", "LIGHT", "Light"]),
  threshold=_threshold_st,
)
def test_routing_hint_light_always_returns_light(
  utterance: str,
  matched_tags: list[str] | None,
  routing_hint: str,
  threshold: int,
) -> None:
  """routing_hint="light" (大文字小文字不問) は常に LIGHT を返す。

  routing_hint は最優先判定基準であるため、
  matched_tags やトークン数に関わらず LIGHT が確定する。

  **Validates: Requirements 9.1, 9.4**
  """
  engine = RoutingEngine(token_threshold=threshold)
  result = engine.classify(utterance, matched_tags, routing_hint)

  assert result == Complexity.LIGHT, (
    f"Expected LIGHT with hint={routing_hint!r}, got {result}. "
    f"utterance={utterance!r}, tags={matched_tags}"
  )


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(
  utterance=_utterance_st,
  matched_tags=_matched_tags_st,
  routing_hint=st.sampled_from(["deep", "DEEP", "Deep"]),
  threshold=_threshold_st,
)
def test_routing_hint_deep_always_returns_deep(
  utterance: str,
  matched_tags: list[str] | None,
  routing_hint: str,
  threshold: int,
) -> None:
  """routing_hint="deep" (大文字小文字不問) は常に DEEP を返す。

  routing_hint は最優先判定基準であるため、
  matched_tags やトークン数に関わらず DEEP が確定する。

  **Validates: Requirements 9.1, 9.4**
  """
  engine = RoutingEngine(token_threshold=threshold)
  result = engine.classify(utterance, matched_tags, routing_hint)

  assert result == Complexity.DEEP, (
    f"Expected DEEP with hint={routing_hint!r}, got {result}. "
    f"utterance={utterance!r}, tags={matched_tags}"
  )


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(
  utterance=_utterance_st,
  matched_tags=st.lists(_tag_st, min_size=1, max_size=5),
  threshold=_threshold_st,
)
def test_matched_tags_non_empty_returns_deep(
  utterance: str,
  matched_tags: list[str],
  threshold: int,
) -> None:
  """matched_tags が非空かつ routing_hint なしの場合、常に DEEP を返す。

  優先度 2: matched_tags 非空 → ドメイン固有語が含まれるため DEEP。

  **Validates: Requirements 9.1, 9.4**
  """
  engine = RoutingEngine(token_threshold=threshold)
  # routing_hint=None で matched_tags 非空
  result = engine.classify(utterance, matched_tags, routing_hint=None)

  assert result == Complexity.DEEP, (
    f"Expected DEEP with non-empty tags={matched_tags}, got {result}. "
    f"utterance={utterance!r}"
  )


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(
  utterance=_utterance_st,
  threshold=_threshold_st,
)
def test_token_threshold_boundary(
  utterance: str,
  threshold: int,
) -> None:
  """routing_hint なし・matched_tags なし/空の場合、
  トークン数 >= threshold → DEEP、それ以外 → LIGHT。

  優先度 3/4: トークン数による分類。

  **Validates: Requirements 9.1, 9.4**
  """
  engine = RoutingEngine(token_threshold=threshold)
  # routing_hint=None, matched_tags=None → トークン数のみで判定
  result = engine.classify(utterance, matched_tags=None, routing_hint=None)

  token_count = len(utterance.split())
  if token_count >= threshold:
    expected = Complexity.DEEP
  else:
    expected = Complexity.LIGHT

  assert result == expected, (
    f"token_count={token_count}, threshold={threshold}: "
    f"expected {expected}, got {result}. utterance={utterance!r}"
  )


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(
  utterance=_utterance_st,
  matched_tags=_matched_tags_st,
  routing_hint=_routing_hint_st,
  threshold=_threshold_st,
)
def test_consistency_across_instances(
  utterance: str,
  matched_tags: list[str] | None,
  routing_hint: str | None,
  threshold: int,
) -> None:
  """同一設定の2つの RoutingEngine インスタンスは同じ結果を返す。

  RoutingEngine は内部状態に依存しない純粋関数的な分類を行うため、
  設定が同一であればインスタンスが異なっても結果は一致する。

  **Validates: Requirements 9.1, 9.4**
  """
  engine_a = RoutingEngine(token_threshold=threshold)
  engine_b = RoutingEngine(token_threshold=threshold)

  result_a = engine_a.classify(utterance, matched_tags, routing_hint)
  result_b = engine_b.classify(utterance, matched_tags, routing_hint)

  assert result_a == result_b, (
    f"Different results from two instances: {result_a} vs {result_b}. "
    f"utterance={utterance!r}, tags={matched_tags}, hint={routing_hint}"
  )
