"""Evolution REST API ルーター

/api/v1/evolution/ プレフィクスで Evolution 機能のエンドポイントを提供する。

エンドポイント:
- POST /profiles — ProfileOutput ロード + 3層初期化
- POST /search — ハイブリッド検索実行
- POST /infer — 推論パイプライン (cache → routing → LLM → cache store)
- GET /profiles/{profile_id}/prompt — 生成済みシステムプロンプト取得
- GET /profiles/{profile_id}/cache/stats — キャッシュ統計情報
- DELETE /profiles/{profile_id}/cache — キャッシュ無効化
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.dependencies import get_service
from app.evolution.hybrid_search import HybridSearchEngine
from app.evolution.models import (
  CacheStats,
  HybridSearchRequest,
  HybridSearchResponse,
  InferRequest,
  InferResponse,
  ProfileLoadResponse,
  ProfileValidationError,
  SearchResultItem,
  validate_profile_for_evolution,
)
from app.evolution.prompt_engine import PromptEngine
from app.evolution.routing_engine import RoutingEngine
from app.evolution.semantic_cache import SemanticCache
from app.evolution.semantic_retriever import SemanticRetriever
from app.models.profile import ProfileOutput

logger = logging.getLogger(__name__)

evolution_router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])


def _require_services() -> None:
  """Evolution サービスが初期化済みであることを確認する。

  未初期化の場合は 503 Service Unavailable を送出する。
  """
  if get_service("context_layer_manager") is None:
    raise HTTPException(
      status_code=503,
      detail="Evolution services not initialized. Set EVOLUTION_CLOUD_LLM_API_KEY to enable.",
    )


def _require_profile_loaded(profile_id: str) -> None:
  """プロファイルがロード済みであることを確認する。

  未ロードの場合は 404 Not Found を送出する。
  """
  clm: ContextLayerManager = get_service("context_layer_manager")  # type: ignore
  try:
    clm.get_base_os(profile_id)
  except KeyError:
    raise HTTPException(
      status_code=404,
      detail=f"Profile '{profile_id}' is not loaded",
    )


@evolution_router.post("/profiles", response_model=ProfileLoadResponse)
async def load_profile(profile: ProfileOutput) -> ProfileLoadResponse:
  """ProfileOutput をロードし、3層コンテキストを初期化する。

  Validates: Requirements 11.1, 11.2
  """
  _require_services()

  # Evolution 固有バリデーション
  try:
    validate_profile_for_evolution(profile)
  except ProfileValidationError as e:
    raise HTTPException(status_code=422, detail=e.errors)

  clm: ContextLayerManager = get_service("context_layer_manager")  # type: ignore
  await clm.load_profile(profile)

  return ProfileLoadResponse(
    profile_id=profile.profile_id,
    timestamp=datetime.now(timezone.utc).isoformat(),
    status="loaded",
  )


@evolution_router.post("/search", response_model=HybridSearchResponse)
async def hybrid_search(request: HybridSearchRequest) -> HybridSearchResponse:
  """ハイブリッド検索を実行する。

  プロファイルの LexicalRetriever と SemanticRetriever を組み合わせ、
  重み付きスコアで統合した検索結果を返す。

  Validates: Requirements 11.3, 11.4
  """
  _require_services()
  _require_profile_loaded(request.profile_id)

  clm: ContextLayerManager = get_service("context_layer_manager")  # type: ignore
  semantic_retriever: SemanticRetriever = get_service("semantic_retriever")  # type: ignore

  # プロファイルの LexicalRetriever を取得
  lexical_retriever = clm._lexical_retrievers.get(request.profile_id)
  if lexical_retriever is None:
    raise HTTPException(
      status_code=404,
      detail=f"Lexical index not found for profile '{request.profile_id}'",
    )

  # HybridSearchEngine を構築して検索実行
  engine = HybridSearchEngine(
    lexical_retriever=lexical_retriever,
    semantic_retriever=semantic_retriever,
    weight=request.weight,
  )
  results = await engine.search(request.profile_id, request.query)

  # HybridResult → SearchResultItem に変換
  items = [
    SearchResultItem(
      content=r.content,
      source=r.source.value,
      score=round(r.score, 4),
      domain=r.domain,
    )
    for r in results
  ]

  return HybridSearchResponse(results=items)


@evolution_router.post("/infer", response_model=InferResponse)
async def infer(request: InferRequest) -> InferResponse:
  """推論パイプラインを実行する。

  1. セマンティックキャッシュで lookup
  2. キャッシュミス時: システムプロンプト生成 → ルーティング → LLM 呼び出し
  3. レスポンスをキャッシュに格納

  Validates: Requirements 11.5, 11.6, 11.7
  """
  _require_services()
  _require_profile_loaded(request.profile_id)

  cache: SemanticCache = get_service("semantic_cache")  # type: ignore
  routing: RoutingEngine = get_service("routing_engine")  # type: ignore
  prompt_engine: PromptEngine = get_service("prompt_engine")  # type: ignore
  clm: ContextLayerManager = get_service("context_layer_manager")  # type: ignore

  # 1. セマンティックキャッシュ lookup
  cached_response = await cache.lookup(request.profile_id, request.utterance)
  if cached_response is not None:
    # キャッシュヒット: ルーティング分類のみ実行して complexity を返す
    complexity = routing.classify(
      request.utterance, routing_hint=request.routing_hint
    )
    return InferResponse(
      response=cached_response,
      complexity=complexity.value,
      cache_hit=True,
    )

  # 2. キャッシュミス: プロンプト生成
  # Base OS からプロファイル情報を取得してプロンプト生成
  # PromptEngine.generate には ProfileOutput が必要なため、
  # CLM から base_os を取得し最低限の ProfileOutput を再構成する
  # → 簡略化: CLM にプロファイル全体を保持させず、prompt_engine 用に
  #   base_os + lexical_tags から matched_tags を取得
  base_os = clm.get_base_os(request.profile_id)

  # Layer 2: 発話に基づくスキルコンテキスト取得
  matched_tags = await clm.get_skill_context(
    request.profile_id, "infer", {"utterance": request.utterance}
  )

  # 複雑度分類
  complexity = routing.classify(
    request.utterance,
    matched_tags=matched_tags,
    routing_hint=request.routing_hint,
  )

  # GET /profiles/{id}/prompt と同じロジックでシステムプロンプト生成
  # PromptEngine は ProfileOutput を要求するが、ここでは部分情報のみ利用可能
  # → プロンプトエンドポイントで完全な ProfileOutput を保持する設計に変更が必要
  # → 現状: CLM 内部にプロンプト文字列をキャッシュする方式を採用
  # → 暫定対応: base_os から直接プロンプトテキストを組み立てる
  system_prompt = _build_system_prompt_from_base_os(base_os)

  # 3. ルーティング → LLM 呼び出し
  try:
    response_text = await routing.route(
      utterance=request.utterance,
      system_prompt=system_prompt,
      matched_tags=matched_tags,
      routing_hint=request.routing_hint,
    )
  except RuntimeError as e:
    raise HTTPException(status_code=503, detail=str(e))

  # 4. キャッシュに格納
  await cache.store(request.profile_id, request.utterance, response_text)

  return InferResponse(
    response=response_text,
    complexity=complexity.value,
    cache_hit=False,
  )


@evolution_router.get("/profiles/{profile_id}/prompt")
async def get_prompt(profile_id: str) -> dict:
  """生成済みシステムプロンプトを取得する。

  ProfileOutput の base_os セクションからプロンプトを動的生成する。

  Validates: Requirements 11.8
  """
  _require_services()
  _require_profile_loaded(profile_id)

  clm: ContextLayerManager = get_service("context_layer_manager")  # type: ignore
  base_os = clm.get_base_os(profile_id)
  system_prompt = _build_system_prompt_from_base_os(base_os)

  return {"profile_id": profile_id, "prompt": system_prompt}


@evolution_router.get("/profiles/{profile_id}/cache/stats", response_model=CacheStats)
async def get_cache_stats(profile_id: str) -> CacheStats:
  """キャッシュ統計情報を取得する。

  Validates: Requirements 11.9
  """
  _require_services()
  _require_profile_loaded(profile_id)

  cache: SemanticCache = get_service("semantic_cache")  # type: ignore
  stats = await cache.get_stats(profile_id)

  return CacheStats(
    total_entries=stats["total_entries"],
    hit_rate=min(stats["hit_rate"], 1.0),
    avg_similarity=stats["avg_similarity"],
  )


@evolution_router.delete("/profiles/{profile_id}/cache")
async def invalidate_cache(profile_id: str) -> dict:
  """指定プロファイルのキャッシュを全削除する。

  Validates: Requirements 11.10
  """
  _require_services()
  _require_profile_loaded(profile_id)

  cache: SemanticCache = get_service("semantic_cache")  # type: ignore
  deleted_count = await cache.invalidate(profile_id)

  return {
    "profile_id": profile_id,
    "deleted_entries": deleted_count,
    "status": "invalidated",
  }


def _build_system_prompt_from_base_os(base_os) -> str:
  """BaseOS データからシステムプロンプトを簡易生成する。

  PromptEngine.generate() は ProfileOutput 全体を必要とするが、
  ルート側では base_os のみ利用可能なケースがあるため、
  直接テンプレート展開する補助関数を提供する。

  将来的には CLM にプロンプトキャッシュを追加し、
  load_profile 時に生成・保持する設計に移行予定。
  """
  from app.evolution.prompt_engine import (
    AXIS_POLES,
    DESCRIPTOR_TEMPLATES,
    SCORE_DESCRIPTORS,
  )

  # axes → トレイト記述
  traits: list[str] = []
  axes = base_os.axes
  for axis_name, (first_pole, second_pole) in AXIS_POLES.items():
    score = getattr(axes, axis_name)
    rounded = round(score, 2)
    descriptor = "balanced"
    for low, high, desc in SCORE_DESCRIPTORS:
      if low <= rounded <= high:
        descriptor = desc
        break
    template = DESCRIPTOR_TEMPLATES[descriptor]
    traits.append(template.format(first_pole=first_pole, second_pole=second_pole))

  # プロンプト組み立て
  lines = ["You are an AI agent with the following personality profile.", ""]
  lines.append("## Personality Traits")
  for trait in traits:
    lines.append(f"- {trait}")
  lines.append("")
  lines.append("## Values & Decision Style")
  lines.append("")
  lines.append(f"Your primary decision-making approach is: {base_os.decision_style}")
  lines.append("")
  lines.append("## Guardrails")
  lines.append("")
  lines.append("You MUST NOT perform the following actions under any circumstances:")
  for item in base_os.do_not_list:
    lines.append(f"- {item}")

  return "\n".join(lines)
