"""EmbeddingClient ユニットテスト

OpenAI API のモック利用でクライアントの振る舞いを検証する。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.evolution.embedding_client import EmbeddingClient


@pytest.fixture
def client() -> EmbeddingClient:
  """テスト用 EmbeddingClient（API キーはダミー）"""
  return EmbeddingClient(model="text-embedding-ada-002", api_key="test-key")


class TestEmbed:
  """単一テキスト embed() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_numpy_array_on_success(self, client: EmbeddingClient) -> None:
    """正常時: shape (embedding_dim,) の float32 配列を返す"""
    mock_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=mock_embedding)]

    with patch.object(
      client._client.embeddings, "create", new_callable=AsyncMock, return_value=mock_response
    ):
      result = await client.embed("hello world")

    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert result.shape == (5,)
    np.testing.assert_allclose(result, mock_embedding, rtol=1e-5)

  @pytest.mark.asyncio
  async def test_returns_empty_array_on_api_error(self, client: EmbeddingClient) -> None:
    """API エラー時: 空の float32 配列を返し、例外は送出しない"""
    with patch.object(
      client._client.embeddings, "create", new_callable=AsyncMock, side_effect=Exception("API down")
    ):
      result = await client.embed("hello world")

    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert result.shape == (0,)

  @pytest.mark.asyncio
  async def test_passes_correct_model_and_input(self, client: EmbeddingClient) -> None:
    """API 呼び出し時のパラメータが正しい"""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.0])]

    with patch.object(
      client._client.embeddings, "create", new_callable=AsyncMock, return_value=mock_response
    ) as mock_create:
      await client.embed("test input")

    mock_create.assert_called_once_with(
      model="text-embedding-ada-002",
      input="test input",
    )


class TestEmbedBatch:
  """バッチ embed_batch() のテスト"""

  @pytest.mark.asyncio
  async def test_returns_2d_numpy_array_on_success(self, client: EmbeddingClient) -> None:
    """正常時: shape (n, embedding_dim) の float32 配列を返す"""
    mock_embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=e) for e in mock_embeddings]

    with patch.object(
      client._client.embeddings, "create", new_callable=AsyncMock, return_value=mock_response
    ):
      result = await client.embed_batch(["hello", "world"])

    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert result.shape == (2, 3)
    np.testing.assert_allclose(result, mock_embeddings, rtol=1e-5)

  @pytest.mark.asyncio
  async def test_returns_empty_2d_array_on_api_error(self, client: EmbeddingClient) -> None:
    """API エラー時: shape (0, 0) の float32 配列を返し、例外は送出しない"""
    with patch.object(
      client._client.embeddings, "create", new_callable=AsyncMock, side_effect=Exception("timeout")
    ):
      result = await client.embed_batch(["hello", "world"])

    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert result.shape == (0, 0)

  @pytest.mark.asyncio
  async def test_passes_texts_as_input_list(self, client: EmbeddingClient) -> None:
    """API 呼び出し時に texts リストがそのまま渡される"""
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.0]), MagicMock(embedding=[0.0])]

    with patch.object(
      client._client.embeddings, "create", new_callable=AsyncMock, return_value=mock_response
    ) as mock_create:
      await client.embed_batch(["text1", "text2"])

    mock_create.assert_called_once_with(
      model="text-embedding-ada-002",
      input=["text1", "text2"],
    )


class TestErrorHandling:
  """エラーハンドリング: 例外が呼び出し元に伝播しないことの確認"""

  @pytest.mark.asyncio
  async def test_embed_catches_any_exception(self, client: EmbeddingClient) -> None:
    """embed() は任意の例外を握りつぶす"""
    with patch.object(
      client._client.embeddings, "create", new_callable=AsyncMock, side_effect=RuntimeError("unexpected")
    ):
      result = await client.embed("test")

    assert result.shape == (0,)

  @pytest.mark.asyncio
  async def test_embed_batch_catches_any_exception(self, client: EmbeddingClient) -> None:
    """embed_batch() は任意の例外を握りつぶす"""
    with patch.object(
      client._client.embeddings, "create", new_callable=AsyncMock, side_effect=ValueError("bad input")
    ):
      result = await client.embed_batch(["a", "b"])

    assert result.shape == (0, 0)
