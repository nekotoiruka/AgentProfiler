"""Embedding API クライアント

OpenAI Embeddings API を非同期で呼び出し、テキストのベクトル表現を生成する。
既存の llm_client.py の OpenAI クライアント設定パターンを踏襲しつつ、
AsyncClient で embedding 生成に特化する。
"""

import logging

import numpy as np
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class EmbeddingClient:
  """OpenAI Embeddings API クライアント

  単一テキスト・バッチテキストの埋め込みベクトル生成を提供する。
  API 不通時は例外を握りつぶし、空の numpy 配列を返す。
  """

  def __init__(self, model: str = "text-embedding-ada-002", api_key: str = "") -> None:
    self._model = model
    self._client = AsyncOpenAI(api_key=api_key)
    logger.info("EmbeddingClient initialized: model=%s", self._model)

  async def embed(self, text: str) -> np.ndarray:
    """単一テキストの埋め込みベクトルを生成する

    Args:
      text: 埋め込み対象のテキスト

    Returns:
      shape (embedding_dim,) の numpy 配列。
      API 不通時は空配列 np.array([], dtype=np.float32) を返す。
    """
    try:
      response = await self._client.embeddings.create(
        model=self._model,
        input=text,
      )
      return np.array(response.data[0].embedding, dtype=np.float32)
    except Exception as e:
      logger.error("Embedding API call failed for single text: %s", e)
      return np.array([], dtype=np.float32)

  async def embed_batch(self, texts: list[str]) -> np.ndarray:
    """複数テキストの埋め込みベクトルをバッチ生成する

    Args:
      texts: 埋め込み対象のテキストリスト

    Returns:
      shape (len(texts), embedding_dim) の numpy 配列。
      API 不通時は np.empty((0, 0), dtype=np.float32) を返す。
    """
    try:
      response = await self._client.embeddings.create(
        model=self._model,
        input=texts,
      )
      return np.array(
        [d.embedding for d in response.data], dtype=np.float32
      )
    except Exception as e:
      logger.error("Embedding API call failed for batch (%d texts): %s", len(texts), e)
      return np.empty((0, 0), dtype=np.float32)
