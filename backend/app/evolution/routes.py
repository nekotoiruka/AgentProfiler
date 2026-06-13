"""Evolution REST API ルーター

/api/v1/evolution/ プレフィクスで Evolution 機能のエンドポイントを提供する。

エンドポイント:
- POST /profiles — ProfileOutput ロード + 3層初期化
- POST /search — ハイブリッド検索実行
- POST /infer — 推論パイプライン (cache → routing → LLM → cache store)
- GET /profiles/{profile_id}/prompt — 生成済みシステムプロンプト取得
- GET /profiles/{profile_id}/cache/stats — キャッシュ統計情報
- DELETE /profiles/{profile_id}/cache — キャッシュ無効化
- GET /agents/{agent_id}/package — Agent Pack Zip ダウンロード
- POST /agents/{agent_id}/chat — チャットメッセージ送信 + レスポンス (SSE 対応)
- GET /agents/{agent_id}/chat/{thread_id} — 会話履歴取得
- POST /discussions — マルチエージェント議論セッション開始 (SSE 対応)
- GET /discussions/{discussion_id} — 議論ターン履歴取得
- GET /compatibility/{agent_id_1}/{agent_id_2} — 2エージェント間の相性診断
- GET /agents/{agent_id}/recommendations — カテゴリ別レコメンド
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from app.evolution.agent_manager import AgentManager
from app.evolution.chat import ChatService
from app.evolution.compatibility import CompatibilityEngine
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.dependencies import get_service
from app.evolution.discussion_engine import DiscussionEngine
from app.evolution.hybrid_search import HybridSearchEngine
from app.evolution.models import (
  AgentResponse,
  CacheStats,
  ChatMessageRequest,
  CreateAgentRequest,
  HybridSearchRequest,
  HybridSearchResponse,
  InferRequest,
  InferResponse,
  ProfileLoadResponse,
  ProfileValidationError,
  SearchResultItem,
  StartDiscussionRequest,
  UpdateAgentRequest,
  validate_profile_for_evolution,
)
from app.evolution.package_generator import PackageGenerator
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


# --- Agent CRUD エンドポイント ---


@evolution_router.post("/agents", response_model=AgentResponse, status_code=201)
async def create_agent(request: CreateAgentRequest) -> AgentResponse:
  """新規エージェントペルソナを作成する。

  profile_id が ContextLayerManager にロード済みであることを検証し、
  AgentManager を介してレコードを作成する。

  Validates: Requirements 16.4, 16.6
  """
  _require_services()

  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore

  try:
    record = await agent_manager.create(
      profile_id=request.profile_id,
      display_name=request.display_name,
    )
  except ValueError as e:
    # profile_id が未ロードの場合
    raise HTTPException(status_code=422, detail=str(e))

  return AgentResponse(
    agent_id=record.agent_id,
    profile_id=record.profile_id,
    display_name=record.display_name,
    created_at=record.created_at,
    is_active=record.is_active,
  )


@evolution_router.get("/agents", response_model=list[AgentResponse])
async def list_agents(profile_id: str) -> list[AgentResponse]:
  """指定プロファイルの有効エージェント一覧を取得する。

  Validates: Requirements 16.7
  """
  _require_services()

  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore
  records = await agent_manager.list_active(profile_id)

  return [
    AgentResponse(
      agent_id=r.agent_id,
      profile_id=r.profile_id,
      display_name=r.display_name,
      created_at=r.created_at,
      is_active=r.is_active,
    )
    for r in records
  ]


@evolution_router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str) -> AgentResponse:
  """エージェントペルソナを個別取得する。

  Validates: Requirements 16.4
  """
  _require_services()

  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore
  record = await agent_manager.get(agent_id)

  if record is None or not record.is_active:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id}' not found or not active",
    )

  return AgentResponse(
    agent_id=record.agent_id,
    profile_id=record.profile_id,
    display_name=record.display_name,
    created_at=record.created_at,
    is_active=record.is_active,
  )


@evolution_router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
  agent_id: str, request: UpdateAgentRequest
) -> AgentResponse:
  """エージェントの display_name を更新する。

  Validates: Requirements 16.4
  """
  _require_services()

  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore

  # 存在確認 + アクティブチェック
  existing = await agent_manager.get(agent_id)
  if existing is None or not existing.is_active:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id}' not found or not active",
    )

  try:
    record = await agent_manager.update_display_name(
      agent_id=agent_id,
      display_name=request.display_name,
    )
  except ValueError:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id}' not found",
    )

  return AgentResponse(
    agent_id=record.agent_id,
    profile_id=record.profile_id,
    display_name=record.display_name,
    created_at=record.created_at,
    is_active=record.is_active,
  )


@evolution_router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str) -> dict:
  """エージェントをソフトデリートする。

  Validates: Requirements 16.4
  """
  _require_services()

  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore

  # 存在確認 + アクティブチェック
  existing = await agent_manager.get(agent_id)
  if existing is None or not existing.is_active:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id}' not found or not active",
    )

  try:
    await agent_manager.soft_delete(agent_id)
  except ValueError:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id}' not found",
    )

  return {"agent_id": agent_id, "status": "deleted"}


@evolution_router.get("/agents/{agent_id}/package")
async def download_agent_package(agent_id: str) -> Response:
  """Agent Pack Zip をダウンロードする。

  agent_id に紐づくプロファイルから PackageGenerator で構成資産を生成し、
  Zip アーカイブとして返却する。

  Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7
  """
  _require_services()

  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore
  clm: ContextLayerManager = get_service("context_layer_manager")  # type: ignore
  package_generator: PackageGenerator = get_service("package_generator")  # type: ignore

  # エージェント存在確認 + アクティブチェック
  record = await agent_manager.get(agent_id)
  if record is None or not record.is_active:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id}' not found or not active",
    )

  # プロファイル取得（CLM にキャッシュ済みの完全な ProfileOutput）
  try:
    profile = clm.get_profile(record.profile_id)
  except KeyError:
    raise HTTPException(
      status_code=404,
      detail=f"Profile '{record.profile_id}' is not loaded",
    )

  # Zip 生成
  zip_bytes = package_generator.build_zip(
    profile=profile,
    agent_id=agent_id,
    display_name=record.display_name,
  )

  filename = f"agent_pack_{agent_id}.zip"
  return Response(
    content=zip_bytes,
    media_type="application/zip",
    headers={
      "Content-Disposition": f'attachment; filename="{filename}"',
    },
  )


# --- Chat エンドポイント ---


async def _require_active_agent(agent_id: str) -> None:
  """エージェントが存在しアクティブであることを確認する。

  非アクティブまたは未登録の場合は 404 Not Found を送出する。
  """
  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore
  record = await agent_manager.get(agent_id)
  if record is None or not record.is_active:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id}' not found or not active",
    )


@evolution_router.post("/agents/{agent_id}/chat", response_model=None)
async def send_chat_message(
  agent_id: str, request: ChatMessageRequest, raw_request: Request
) -> dict | StreamingResponse:
  """チャットメッセージを送信し、エージェントのレスポンスを返す。

  Accept: text/event-stream ヘッダー指定時は SSE ストリーミングで返却する。
  通常リクエスト時は JSON レスポンスを返却する。

  Validates: Requirements 17.1, 17.5, 17.7
  """
  _require_services()
  await _require_active_agent(agent_id)

  chat_service: ChatService = get_service("chat_service")  # type: ignore

  # Accept ヘッダーで SSE ストリーミング判定
  accept = raw_request.headers.get("accept", "")
  if "text/event-stream" in accept:
    return StreamingResponse(
      chat_service.stream_response(agent_id, request.message, request.thread_id),
      media_type="text/event-stream",
    )

  # 通常 JSON レスポンス
  result = await chat_service.send_message(
    agent_id=agent_id,
    message=request.message,
    thread_id=request.thread_id,
  )
  return result


@evolution_router.get("/agents/{agent_id}/chat/{thread_id}")
async def get_chat_history(agent_id: str, thread_id: str) -> list[dict]:
  """指定スレッドの会話履歴を取得する。

  時系列昇順で全ターンを返却する。

  Validates: Requirements 17.1, 17.5
  """
  _require_services()
  await _require_active_agent(agent_id)

  chat_service: ChatService = get_service("chat_service")  # type: ignore
  history = await chat_service.get_history(thread_id)
  return history


# --- Discussion エンドポイント ---


@evolution_router.post("/discussions", response_model=None)
async def start_discussion(
  request: StartDiscussionRequest, raw_request: Request
) -> dict | StreamingResponse:
  """マルチエージェント議論セッションを開始する。

  Accept: text/event-stream ヘッダー指定時は SSE ストリーミングで
  各ターンを逐次配信する。通常リクエスト時は全ターン完了後に
  JSON レスポンスを返却する。

  Validates: Requirements 18.1, 18.7, 18.8
  """
  _require_services()

  discussion_engine: DiscussionEngine = get_service("discussion_engine")  # type: ignore
  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore

  # エージェントの存在・アクティブ状態を検証
  invalid_ids: list[str] = []
  for agent_id in request.agent_ids:
    record = await agent_manager.get(agent_id)
    if record is None or not record.is_active:
      invalid_ids.append(agent_id)

  if invalid_ids:
    raise HTTPException(
      status_code=422,
      detail=f"Invalid or inactive agent_ids: {invalid_ids}",
    )

  # Accept ヘッダーで SSE ストリーミング判定
  accept = raw_request.headers.get("accept", "")
  if "text/event-stream" in accept:
    return StreamingResponse(
      discussion_engine.stream_discussion(
        agent_ids=request.agent_ids,
        theme=request.theme,
        max_turns_per_agent=request.max_turns_per_agent,
      ),
      media_type="text/event-stream",
    )

  # 通常 JSON レスポンス: 全ターンを実行して結果を返す
  discussion_id = await discussion_engine.start_discussion(
    agent_ids=request.agent_ids,
    theme=request.theme,
  )

  turns: list[dict] = []
  async for turn in discussion_engine.run_turns(
    discussion_id=discussion_id,
    agent_ids=request.agent_ids,
    theme=request.theme,
    max_turns_per_agent=request.max_turns_per_agent,
  ):
    turns.append({
      "turn_number": turn.turn_number,
      "agent_id": turn.agent_id,
      "display_name": turn.display_name,
      "content": turn.content,
      "timestamp": turn.timestamp,
    })

  return {
    "discussion_id": discussion_id,
    "theme": request.theme,
    "agent_ids": request.agent_ids,
    "turns": turns,
  }


@evolution_router.get("/discussions/{discussion_id}")
async def get_discussion_history(discussion_id: str) -> list[dict]:
  """議論の全ターン履歴を取得する。

  turn_number 昇順で全発話を返却する。

  Validates: Requirements 18.1, 18.7
  """
  _require_services()

  discussion_engine: DiscussionEngine = get_service("discussion_engine")  # type: ignore
  history = await discussion_engine.get_history(discussion_id)
  return history


# --- Compatibility & Recommendation エンドポイント ---


def _get_axes_from_agent_profile(profile_id: str) -> list[float]:
  """エージェントの profile_id から4軸スコアをリストとして取得する。

  ContextLayerManager から BaseOS を取得し、
  NormalizedScores を [E/I, S/N, T/F, J/P] のリストに変換する。

  Args:
    profile_id: プロファイル識別子

  Returns:
    4軸スコアのリスト [0.0-1.0] × 4

  Raises:
    KeyError: profile_id が未ロードの場合
  """
  clm: ContextLayerManager = get_service("context_layer_manager")  # type: ignore
  base_os = clm.get_base_os(profile_id)
  axes = base_os.axes
  return [
    axes.extroverted_introverted,
    axes.sensing_intuition,
    axes.thinking_feeling,
    axes.judging_perceiving,
  ]


@evolution_router.get("/compatibility/{agent_id_1}/{agent_id_2}")
async def get_compatibility(agent_id_1: str, agent_id_2: str) -> dict:
  """2エージェント間の相性診断レポートを返す。

  両エージェントの4軸パラメータから Cosine Similarity と
  Complementarity を算出し、分類・推奨モードを含むレポートを返却する。

  Validates: Requirements 19.5, 19.6
  """
  _require_services()

  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore
  compatibility_engine: CompatibilityEngine = get_service("compatibility_engine")  # type: ignore

  # 両エージェントの存在・アクティブ状態を検証
  record_1 = await agent_manager.get(agent_id_1)
  if record_1 is None or not record_1.is_active:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id_1}' not found or not active",
    )

  record_2 = await agent_manager.get(agent_id_2)
  if record_2 is None or not record_2.is_active:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id_2}' not found or not active",
    )

  # 各エージェントの4軸スコアを取得
  try:
    axes_1 = _get_axes_from_agent_profile(record_1.profile_id)
  except KeyError:
    raise HTTPException(
      status_code=404,
      detail=f"Profile '{record_1.profile_id}' for agent '{agent_id_1}' is not loaded",
    )

  try:
    axes_2 = _get_axes_from_agent_profile(record_2.profile_id)
  except KeyError:
    raise HTTPException(
      status_code=404,
      detail=f"Profile '{record_2.profile_id}' for agent '{agent_id_2}' is not loaded",
    )

  # 相性レポート生成
  report = compatibility_engine.compute_compatibility(axes_1, axes_2)

  return {
    "agent_id_1": agent_id_1,
    "agent_id_2": agent_id_2,
    "overall_score": report.overall_score,
    "cosine_similarity": report.cosine_similarity,
    "complementarity_score": report.complementarity_score,
    "per_axis_comparison": report.per_axis_comparison,
    "classification": report.classification.value,
    "relationship_type": report.relationship_type,
    "reason": report.reason,
    "recommended_interaction_mode": report.recommended_interaction_mode,
  }


@evolution_router.get("/agents/{agent_id}/recommendations")
async def get_recommendations(agent_id: str) -> dict:
  """カテゴリ別レコメンドを返す。

  指定エージェントと全アクティブエージェントの相性を比較し、
  most_heated_debate (相補性上位) と business_partner (類似度上位) の
  2カテゴリ × 最大3件のレコメンドを返却する。

  Validates: Requirements 20.4, 20.5
  """
  _require_services()

  agent_manager: AgentManager = get_service("agent_manager")  # type: ignore
  compatibility_engine: CompatibilityEngine = get_service("compatibility_engine")  # type: ignore

  # ソースエージェントの存在・アクティブ状態を検証
  record = await agent_manager.get(agent_id)
  if record is None or not record.is_active:
    raise HTTPException(
      status_code=404,
      detail=f"Agent '{agent_id}' not found or not active",
    )

  # 全アクティブエージェントを取得
  all_records = await agent_manager.list_all_active()

  # アクティブエージェントが2未満の場合は空レコメンド + メッセージ
  if len(all_records) < 2:
    return {
      "agent_id": agent_id,
      "most_heated_debate": [],
      "business_partner": [],
      "message": "レコメンドには2体以上のアクティブエージェントが必要です",
    }

  # 各エージェントの axes を収集（プロファイル未ロード分はスキップ）
  all_agents: list[dict] = []
  for r in all_records:
    try:
      axes = _get_axes_from_agent_profile(r.profile_id)
      all_agents.append({
        "agent_id": r.agent_id,
        "axes": axes,
        "display_name": r.display_name,
      })
    except KeyError:
      # プロファイル未ロードのエージェントはスキップ
      logger.debug(
        "Skipping agent '%s': profile '%s' not loaded",
        r.agent_id,
        r.profile_id,
      )
      continue

  # axes 収集後に2体未満の場合
  if len(all_agents) < 2:
    return {
      "agent_id": agent_id,
      "most_heated_debate": [],
      "business_partner": [],
      "message": "レコメンドには2体以上のアクティブエージェントが必要です",
    }

  # レコメンド生成
  recommendations = await compatibility_engine.recommend(
    source_agent_id=agent_id,
    all_agents=all_agents,
  )

  # dataclass → dict 変換
  result: dict = {
    "agent_id": agent_id,
    "most_heated_debate": [
      {
        "agent_id": rec.agent_id,
        "display_name": rec.display_name,
        "score": rec.score,
        "explanation": rec.explanation,
      }
      for rec in recommendations["most_heated_debate"]
    ],
    "business_partner": [
      {
        "agent_id": rec.agent_id,
        "display_name": rec.display_name,
        "score": rec.score,
        "explanation": rec.explanation,
      }
      for rec in recommendations["business_partner"]
    ],
  }

  return result
