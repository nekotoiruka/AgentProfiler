"""DI コンテナ: Evolution サービスの初期化とライフサイクル管理

アプリケーション起動時に init_evolution_services() を呼び出し、
全コンポーネントをモジュールレベル辞書に格納する。
各ルートハンドラは get_service() で必要なサービスを取得する。
"""

import json
import logging
from pathlib import Path

from app.evolution.agent_manager import AgentManager
from app.evolution.chat import ChatService
from app.evolution.compatibility import CompatibilityEngine
from app.evolution.config import EvolutionSettings
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.discussion_engine import DiscussionEngine
from app.evolution.embedding_client import EmbeddingClient
from app.evolution.export import ExportService
from app.evolution.package_generator import PackageGenerator
from app.evolution.prompt_engine import PromptEngine
from app.evolution.routing_engine import RoutingEngine
from app.evolution.semantic_cache import SemanticCache
from app.evolution.semantic_retriever import SemanticRetriever
from app.models.profile import ProfileOutput

logger = logging.getLogger(__name__)

# モジュールレベルのサービスコンテナ
_services: dict[str, object] = {}


async def init_evolution_services() -> None:
  """全 Evolution サービスを初期化する。

  アプリケーション起動時 (lifespan) で呼び出される。
  EVOLUTION_CLOUD_LLM_API_KEY が未設定の場合はスキップし、
  警告ログのみ出力して正常終了する。
  """
  try:
    settings = EvolutionSettings()
  except Exception:
    # API キー未設定など設定不備時は Evolution 機能を無効化
    logger.warning(
      "Evolution services not initialized (config missing). "
      "Set EVOLUTION_CLOUD_LLM_API_KEY to enable."
    )
    return

  # Embedding クライアント
  embedding_client = EmbeddingClient(
    model=settings.embedding_model,
    api_key=settings.cloud_llm_api_key,
  )

  # Semantic Retriever (Layer 3 ベクトル検索)
  semantic_retriever = SemanticRetriever(
    embedding_client=embedding_client,
    top_k=settings.semantic_search_top_k,
    threshold=settings.semantic_search_threshold,
  )

  # Context Layer Manager (3層コンテキスト管理)
  context_layer_manager = ContextLayerManager(
    semantic_retriever=semantic_retriever,
  )

  # Prompt Engine (動的プロンプト生成)
  prompt_engine = PromptEngine(max_tokens=settings.max_prompt_tokens)

  # Routing Engine (SLM / Cloud LLM 振り分け)
  routing_engine = RoutingEngine(
    token_threshold=settings.routing_token_threshold,
    slm_base_url=settings.slm_base_url,
    slm_model=settings.slm_model,
    cloud_base_url=settings.cloud_llm_base_url,
    cloud_model=settings.cloud_llm_model,
    cloud_api_key=settings.cloud_llm_api_key,
  )

  # Semantic Cache (SQLite ベースの推論キャッシュ)
  cache_db_path = str(
    Path(__file__).resolve().parent.parent.parent / "data" / "evolution_cache.db"
  )
  semantic_cache = SemanticCache(
    db_path=cache_db_path,
    embedding_client=embedding_client,
    threshold=settings.semantic_cache_threshold,
    eviction_days=settings.cache_eviction_days,
  )
  await semantic_cache.init_db()

  # Agent Manager (分身プロファイル CRUD 管理)
  evolution_db_path = str(
    Path(__file__).resolve().parent.parent.parent / "data" / "evolution.db"
  )
  agent_manager = AgentManager(
    db_path=evolution_db_path,
    context_layer_manager=context_layer_manager,
  )
  await agent_manager.init_db()

  # Package Generator (Agent Pack Zip 生成)
  package_generator = PackageGenerator(prompt_engine=prompt_engine)

  # Chat Service (1対1チャット: スレッド管理・会話履歴・SSE)
  chat_service = ChatService(
    db_path=evolution_db_path,
    routing_engine=routing_engine,
    context_layer_manager=context_layer_manager,
    agent_manager=agent_manager,
  )
  await chat_service.init_db()

  # Discussion Engine (マルチエージェント・ターン制議論)
  discussion_engine = DiscussionEngine(
    db_path=evolution_db_path,
    routing_engine=routing_engine,
    context_layer_manager=context_layer_manager,
    agent_manager=agent_manager,
  )
  await discussion_engine.init_db()

  # Compatibility Engine (4軸パラメータ相性診断・レコメンド)
  compatibility_engine = CompatibilityEngine()

  # Export Service (会話ログエクスポート: JSON / Markdown)
  export_service = ExportService(
    chat_service=chat_service,
    discussion_engine=discussion_engine,
  )

  # サービスコンテナに登録
  _services["settings"] = settings
  _services["embedding_client"] = embedding_client
  _services["semantic_retriever"] = semantic_retriever
  _services["context_layer_manager"] = context_layer_manager
  _services["prompt_engine"] = prompt_engine
  _services["routing_engine"] = routing_engine
  _services["semantic_cache"] = semantic_cache
  _services["agent_manager"] = agent_manager
  _services["package_generator"] = package_generator
  _services["chat_service"] = chat_service
  _services["discussion_engine"] = discussion_engine
  _services["compatibility_engine"] = compatibility_engine
  _services["export_service"] = export_service

  logger.info("Evolution services initialized successfully")

  # --- プロファイル自動復元 ---
  # DB に保存されている全プロファイルを ContextLayerManager にロードする。
  # これによりサーバー再起動後もエージェントが即座に利用可能になる。
  profile_ids = await agent_manager.list_profile_ids()
  restored_count = 0
  for pid in profile_ids:
    try:
      profile_json = await agent_manager.get_profile_json(pid)
      if profile_json:
        profile = ProfileOutput.model_validate_json(profile_json)
        await context_layer_manager.load_profile(profile)
        restored_count += 1
    except Exception as e:
      logger.warning("Failed to restore profile %s: %s", pid, e)

  if restored_count > 0:
    logger.info("Restored %d profiles from DB", restored_count)


def get_service(name: str) -> object | None:
  """名前でサービスを取得する。

  Args:
    name: サービス名 (settings, embedding_client, semantic_retriever,
          context_layer_manager, prompt_engine, routing_engine,
          semantic_cache, agent_manager, package_generator,
          chat_service, discussion_engine, compatibility_engine,
          export_service)

  Returns:
    登録済みサービスインスタンス。未初期化の場合は None。
  """
  return _services.get(name)
