"""FastAPIアプリケーションのエントリーポイント

起動時にサービス初期化、ルーター登録を行う。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import init_services
from app.api.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
  """アプリケーションのライフサイクル管理

  起動時: サービス初期化（DB、データローダー、エンジン等）
  終了時: クリーンアップ（現時点では不要）
  """
  logger.info("Initializing services...")
  await init_services()
  logger.info("Services initialized successfully")
  yield
  # 終了時のクリーンアップ（将来の拡張用）
  logger.info("Shutting down...")


app = FastAPI(
  title="Agent Profiler",
  version="0.1.0",
  description="ユーザーの価値観・意思決定基準・嗜好を構造化データとして抽出するAPI",
  lifespan=lifespan,
)

# CORS設定: フロントエンド開発サーバーからのクロスオリジンリクエストを許可
app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173", "http://localhost:3000"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# ルーター登録
app.include_router(router)


@app.get("/health")
async def health_check() -> dict[str, str]:
  return {"status": "ok"}
