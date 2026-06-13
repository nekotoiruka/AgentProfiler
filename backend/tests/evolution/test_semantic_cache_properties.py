"""SemanticCache プロパティベーステスト

Feature: agent-evolution
Property 10: Semantic cache round-trip
Property 11: Semantic cache profile isolation
Property 12: Semantic cache eviction
Validates: Requirements 8.3, 8.5, 8.6
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import aiosqlite
import numpy as np
import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.evolution.embedding_client import EmbeddingClient
from app.evolution.semantic_cache import SemanticCache


# --- Hypothesis ストラテジー ---

# profile_id: "prof_" + 6桁
_profile_id_st = st.from_regex(r"prof_[0-9]{6}", fullmatch=True)

# 発話テキスト (1〜50文字、空白含む英数字)
_utterance_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
  min_size=1,
  max_size=50,
).filter(lambda s: s.strip() != "")

# レスポンステキスト (1〜100文字)
_response_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
  min_size=1,
  max_size=100,
).filter(lambda s: s.strip() != "")

# 埋め込みベクトル次元
_EMBED_DIM = 8


# --- ヘルパー ---


def _make_unit_vector(seed: int) -> np.ndarray:
  """シードから決定論的な単位ベクトルを生成する。"""
  rng = np.random.default_rng(seed)
  vec = rng.standard_normal(_EMBED_DIM).astype(np.float32)
  norm = np.linalg.norm(vec)
  if norm == 0:
    vec[0] = 1.0
    return vec
  return vec / norm


async def _create_cache(tmp_path, embed_fn, **kwargs) -> SemanticCache:
  """テスト用 SemanticCache を構築する。

  各呼び出しで一意の DB ファイルを使用し、example 間の衝突を回避する。
  embed_fn: テキスト → np.ndarray のコールバック。
  """
  # 各 example で一意な DB ファイルを生成
  db_path = str(tmp_path / f"cache_{uuid.uuid4().hex}.db")
  embedding_client = AsyncMock(spec=EmbeddingClient)
  embedding_client.embed = AsyncMock(side_effect=embed_fn)

  cache = SemanticCache(
    db_path=db_path,
    embedding_client=embedding_client,
    threshold=kwargs.get("threshold", 0.92),
    eviction_days=kwargs.get("eviction_days", 7),
  )
  await cache.init_db()
  return cache


# =============================================================================
# Property 10: Semantic cache round-trip
# Feature: agent-evolution
# =============================================================================


class TestSemanticCacheRoundTrip:
  """Property 10: store then lookup returns the stored response.

  同一の埋め込みベクトルを返すテキストで store → lookup すると、
  保存したレスポンスが返される。

  **Validates: Requirements 8.3**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    utterance=_utterance_st,
    response=_response_st,
    seed=st.integers(min_value=0, max_value=10000),
  )
  async def test_store_then_lookup_returns_response(
    self,
    profile_id: str,
    utterance: str,
    response: str,
    seed: int,
    tmp_path,
  ) -> None:
    """store した後に同一発話で lookup すると保存レスポンスが返る。

    同一テキストに対して同じベクトルを返すモックにより、
    cosine similarity = 1.0 > threshold (0.92) でキャッシュヒットする。

    **Validates: Requirements 8.3**
    """
    vec = _make_unit_vector(seed)

    async def embed_fn(text: str) -> np.ndarray:
      return vec

    cache = await _create_cache(tmp_path, embed_fn)

    await cache.store(profile_id, utterance, response)
    result = await cache.lookup(profile_id, utterance)

    assert result == response, (
      f"Round-trip failed: stored response='{response}', got='{result}'"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    utterances=st.lists(_utterance_st, min_size=2, max_size=5, unique=True),
    responses=st.lists(_response_st, min_size=2, max_size=5),
  )
  async def test_multiple_stores_each_retrievable(
    self,
    profile_id: str,
    utterances: list[str],
    responses: list[str],
    tmp_path,
  ) -> None:
    """複数エントリを store した後、各々が正しく lookup できる。

    各テキストに固有のベクトルを割り当て、自己 similarity = 1.0 を保証。

    **Validates: Requirements 8.3**
    """
    pairs = list(zip(utterances[:len(responses)], responses[:len(utterances)]))
    assume(len(pairs) >= 2)

    # 各テキストに固有のベクトルを割り当てる
    text_to_vec: dict[str, np.ndarray] = {}
    for i, (utt, _) in enumerate(pairs):
      text_to_vec[utt] = _make_unit_vector(i * 1000)

    async def embed_fn(text: str) -> np.ndarray:
      if text in text_to_vec:
        return text_to_vec[text]
      # 未知テキストにはゼロに近い直交ベクトルを返す
      return _make_unit_vector(99999)

    cache = await _create_cache(tmp_path, embed_fn)

    for utt, resp in pairs:
      await cache.store(profile_id, utt, resp)

    for utt, resp in pairs:
      result = await cache.lookup(profile_id, utt)
      assert result == resp, (
        f"Multi-store round-trip failed for '{utt}': expected='{resp}', got='{result}'"
      )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    utterance=_utterance_st,
    seed=st.integers(min_value=0, max_value=10000),
  )
  async def test_lookup_miss_returns_none(
    self,
    profile_id: str,
    utterance: str,
    seed: int,
    tmp_path,
  ) -> None:
    """store していないプロファイルの lookup は None を返す。

    **Validates: Requirements 8.3**
    """
    vec = _make_unit_vector(seed)

    async def embed_fn(text: str) -> np.ndarray:
      return vec

    cache = await _create_cache(tmp_path, embed_fn)

    result = await cache.lookup(profile_id, utterance)
    assert result is None, (
      f"Empty cache should return None, got='{result}'"
    )


# =============================================================================
# Property 11: Semantic cache profile isolation
# Feature: agent-evolution
# =============================================================================


class TestSemanticCacheProfileIsolation:
  """Property 11: Cache entries for one profile_id are not returned for another.

  profile_A で store したエントリは、profile_B の lookup では返らない。

  **Validates: Requirements 8.5**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_a=_profile_id_st,
    profile_b=_profile_id_st,
    utterance=_utterance_st,
    response=_response_st,
    seed=st.integers(min_value=0, max_value=10000),
  )
  async def test_different_profile_no_hit(
    self,
    profile_a: str,
    profile_b: str,
    utterance: str,
    response: str,
    seed: int,
    tmp_path,
  ) -> None:
    """profile_A で store → profile_B で lookup → None。

    同一ベクトル (similarity = 1.0) であっても、profile_id が異なれば
    キャッシュヒットしない。

    **Validates: Requirements 8.5**
    """
    assume(profile_a != profile_b)

    vec = _make_unit_vector(seed)

    async def embed_fn(text: str) -> np.ndarray:
      return vec

    cache = await _create_cache(tmp_path, embed_fn)

    await cache.store(profile_a, utterance, response)

    result = await cache.lookup(profile_b, utterance)
    assert result is None, (
      f"Profile isolation violated: profile_a='{profile_a}' entry "
      f"returned for profile_b='{profile_b}'. Got='{result}'"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_a=_profile_id_st,
    profile_b=_profile_id_st,
    utterance=_utterance_st,
    response_a=_response_st,
    response_b=_response_st,
    seed=st.integers(min_value=0, max_value=10000),
  )
  async def test_same_utterance_different_profiles_independent(
    self,
    profile_a: str,
    profile_b: str,
    utterance: str,
    response_a: str,
    response_b: str,
    seed: int,
    tmp_path,
  ) -> None:
    """同一発話を異なるプロファイルで store → 各プロファイルの応答が独立。

    **Validates: Requirements 8.5**
    """
    assume(profile_a != profile_b)

    vec = _make_unit_vector(seed)

    async def embed_fn(text: str) -> np.ndarray:
      return vec

    cache = await _create_cache(tmp_path, embed_fn)

    await cache.store(profile_a, utterance, response_a)
    await cache.store(profile_b, utterance, response_b)

    result_a = await cache.lookup(profile_a, utterance)
    result_b = await cache.lookup(profile_b, utterance)

    assert result_a == response_a, (
      f"Profile A lookup failed: expected='{response_a}', got='{result_a}'"
    )
    assert result_b == response_b, (
      f"Profile B lookup failed: expected='{response_b}', got='{result_b}'"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_a=_profile_id_st,
    profile_b=_profile_id_st,
    utterance=_utterance_st,
    response=_response_st,
    seed=st.integers(min_value=0, max_value=10000),
  )
  async def test_invalidate_one_profile_preserves_other(
    self,
    profile_a: str,
    profile_b: str,
    utterance: str,
    response: str,
    seed: int,
    tmp_path,
  ) -> None:
    """profile_A を invalidate しても profile_B のエントリは残る。

    **Validates: Requirements 8.5**
    """
    assume(profile_a != profile_b)

    vec = _make_unit_vector(seed)

    async def embed_fn(text: str) -> np.ndarray:
      return vec

    cache = await _create_cache(tmp_path, embed_fn)

    await cache.store(profile_a, utterance, response)
    await cache.store(profile_b, utterance, response)

    await cache.invalidate(profile_a)

    result_a = await cache.lookup(profile_a, utterance)
    assert result_a is None, (
      f"Invalidated profile should return None, got='{result_a}'"
    )

    result_b = await cache.lookup(profile_b, utterance)
    assert result_b == response, (
      f"Non-invalidated profile should still return response, got='{result_b}'"
    )


# =============================================================================
# Property 12: Semantic cache eviction
# Feature: agent-evolution
# =============================================================================


class TestSemanticCacheEviction:
  """Property 12: Entries older than eviction_days are removed by evict_stale().

  last_accessed_at が eviction_days 超のエントリは evict_stale() で削除される。

  **Validates: Requirements 8.6**
  """

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    utterance=_utterance_st,
    response=_response_st,
    eviction_days=st.integers(min_value=1, max_value=30),
    stale_extra_days=st.integers(min_value=1, max_value=30),
    seed=st.integers(min_value=0, max_value=10000),
  )
  async def test_stale_entries_evicted(
    self,
    profile_id: str,
    utterance: str,
    response: str,
    eviction_days: int,
    stale_extra_days: int,
    seed: int,
    tmp_path,
  ) -> None:
    """last_accessed_at が eviction_days 超のエントリは evict_stale() で削除される。

    **Validates: Requirements 8.6**
    """
    vec = _make_unit_vector(seed)

    async def embed_fn(text: str) -> np.ndarray:
      return vec

    db_path = str(tmp_path / f"cache_{uuid.uuid4().hex}.db")
    embedding_client = AsyncMock(spec=EmbeddingClient)
    embedding_client.embed = AsyncMock(side_effect=embed_fn)

    cache = SemanticCache(
      db_path=db_path,
      embedding_client=embedding_client,
      threshold=0.92,
      eviction_days=eviction_days,
    )
    await cache.init_db()

    # store (正常にエントリを作成)
    await cache.store(profile_id, utterance, response)

    # last_accessed_at を古い日時に手動更新
    stale_time = datetime.now(timezone.utc) - timedelta(
      days=eviction_days + stale_extra_days
    )
    stale_time_str = stale_time.isoformat()

    async with aiosqlite.connect(db_path) as db:
      await db.execute(
        "UPDATE semantic_cache SET last_accessed_at = ? WHERE profile_id = ?",
        (stale_time_str, profile_id),
      )
      await db.commit()

    # evict_stale → 削除される
    evicted = await cache.evict_stale()
    assert evicted >= 1, f"Expected at least 1 eviction, got {evicted}"

    # lookup → None
    result = await cache.lookup(profile_id, utterance)
    assert result is None, (
      f"Stale entry should be evicted, but lookup returned='{result}'"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    utterance=_utterance_st,
    response=_response_st,
    eviction_days=st.integers(min_value=3, max_value=30),
    seed=st.integers(min_value=0, max_value=10000),
  )
  async def test_fresh_entries_not_evicted(
    self,
    profile_id: str,
    utterance: str,
    response: str,
    eviction_days: int,
    seed: int,
    tmp_path,
  ) -> None:
    """最近アクセスされたエントリは evict_stale() で削除されない。

    **Validates: Requirements 8.6**
    """
    vec = _make_unit_vector(seed)

    async def embed_fn(text: str) -> np.ndarray:
      return vec

    cache = await _create_cache(tmp_path, embed_fn, eviction_days=eviction_days)

    await cache.store(profile_id, utterance, response)

    # evict_stale → 削除されない (今保存したばかり)
    evicted = await cache.evict_stale()
    assert evicted == 0, (
      f"Fresh entry should not be evicted, but {evicted} entries were evicted"
    )

    # lookup → レスポンスが返る
    result = await cache.lookup(profile_id, utterance)
    assert result == response, (
      f"Fresh entry should still be accessible, got='{result}'"
    )

  @settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
  )
  @given(
    profile_id=_profile_id_st,
    eviction_days=st.integers(min_value=1, max_value=30),
    num_entries=st.integers(min_value=2, max_value=5),
    seed=st.integers(min_value=0, max_value=10000),
  )
  async def test_mixed_fresh_and_stale_only_stale_evicted(
    self,
    profile_id: str,
    eviction_days: int,
    num_entries: int,
    seed: int,
    tmp_path,
  ) -> None:
    """新しいエントリと古いエントリが混在する場合、古いもののみ削除される。

    **Validates: Requirements 8.6**
    """
    vectors: dict[str, np.ndarray] = {}
    for i in range(num_entries):
      vectors[f"utterance_{i}"] = _make_unit_vector(seed + i * 100)

    async def embed_fn(text: str) -> np.ndarray:
      if text in vectors:
        return vectors[text]
      return _make_unit_vector(seed + 99999)

    db_path = str(tmp_path / f"cache_{uuid.uuid4().hex}.db")
    embedding_client = AsyncMock(spec=EmbeddingClient)
    embedding_client.embed = AsyncMock(side_effect=embed_fn)

    cache = SemanticCache(
      db_path=db_path,
      embedding_client=embedding_client,
      threshold=0.92,
      eviction_days=eviction_days,
    )
    await cache.init_db()

    # 全エントリを store
    for i in range(num_entries):
      await cache.store(profile_id, f"utterance_{i}", f"response_{i}")

    # 先頭半分を stale に更新
    stale_count = num_entries // 2
    stale_time = datetime.now(timezone.utc) - timedelta(days=eviction_days + 1)
    stale_time_str = stale_time.isoformat()

    async with aiosqlite.connect(db_path) as db:
      for i in range(stale_count):
        await db.execute(
          "UPDATE semantic_cache SET last_accessed_at = ? WHERE utterance_text = ?",
          (stale_time_str, f"utterance_{i}"),
        )
      await db.commit()

    # evict
    evicted = await cache.evict_stale()
    assert evicted == stale_count, (
      f"Expected {stale_count} evictions, got {evicted}"
    )

    # stale エントリは lookup で None
    for i in range(stale_count):
      result = await cache.lookup(profile_id, f"utterance_{i}")
      assert result is None, (
        f"Stale entry 'utterance_{i}' should be evicted, got='{result}'"
      )

    # fresh エントリは lookup で正常
    for i in range(stale_count, num_entries):
      result = await cache.lookup(profile_id, f"utterance_{i}")
      assert result == f"response_{i}", (
        f"Fresh entry 'utterance_{i}' should remain, got='{result}'"
      )
