# Design Document: Agent Evolution

## Overview

Agent Evolution は、Agent Profiler が生成した `ProfileOutput` JSON を入力とし、AIエージェントの動的パーソナライゼーションを実現するランタイムシステムである。本設計は `backend/app/evolution/` サブモジュールとして既存 FastAPI アプリケーションを拡張し、3層コンテキスト管理・ハイブリッド検索・セマンティックキャッシュ・ルーティングの4つのコア機能を提供する。

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Application (backend/app/main.py)                      │
├─────────────────────────────────────────────────────────────────┤
│  /api/v1/evolution/*  ← evolution_router                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐   ┌───────────────────┐   ┌───────────────┐  │
│  │ Prompt Engine│   │ Context Layer Mgr │   │ Routing Engine│  │
│  └──────┬───────┘   └────────┬──────────┘   └───────┬───────┘  │
│         │                    │                       │          │
│         │            ┌───────┴────────┐              │          │
│         │            │                │              │          │
│  ┌──────▼───────┐  ┌▼────────┐ ┌─────▼──────┐ ┌────▼───────┐  │
│  │  Template    │  │ Lexical │ │ Semantic   │ │ Semantic   │  │
│  │  Renderer    │  │Retriever│ │ Retriever  │ │ Cache      │  │
│  └──────────────┘  └────┬────┘ └─────┬──────┘ └────┬───────┘  │
│                          │            │             │          │
│                    ┌─────▼────────────▼──┐    ┌─────▼───────┐  │
│                    │ Hybrid Search Engine │    │ SQLite DB   │  │
│                    └─────────────────────┘    └─────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  MCP Server (stdio / SSE)                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  External:  OpenAI Embeddings API  |  SLM (ollama)  |  Cloud   │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
backend/app/evolution/
├── __init__.py
├── config.py              # 設定管理 (Pydantic Settings)
├── models.py              # Evolution 固有のデータモデル
├── prompt_engine.py       # 動的プロンプト生成エンジン
├── context_layer_manager.py  # 3層コンテキスト管理
├── lexical_retriever.py   # キーワード完全一致検索
├── semantic_retriever.py  # ベクトル cosine similarity 検索
├── hybrid_search.py       # ハイブリッド検索統合
├── semantic_cache.py      # セマンティック・キャッシュ (SQLite)
├── routing_engine.py      # ハイブリッド・ルーティング
├── mcp_server.py          # MCP サーバー実装
├── embedding_client.py    # Embedding API クライアント
├── package_generator.py   # VSCode Agent Package 自動生成
├── agent_manager.py       # 分身プロファイル CRUD 管理
├── chat.py                # 1対1チャット API + SSE ストリーミング
├── discussion_engine.py   # マルチエージェント・ターン制議論
├── compatibility.py       # 相性診断・レコメンドエンジン
├── export.py              # 会話ログエクスポート
├── routes.py              # FastAPI ルーター (/api/v1/evolution/)
└── dependencies.py        # DI コンテナ

frontend/src/components/evolution/
├── AgentList.vue          # 分身セレクト一覧
├── ChatThread.vue         # 1対1チャットスレッド表示
├── ChatInput.vue          # メッセージ入力
├── DiscussionTheater.vue  # マルチエージェント対話観覧シアター
├── DiscussionSetup.vue    # 議論設定 (エージェント選択 + テーマ入力)
├── TurnBubble.vue         # 発話バブル
└── composables/
    ├── useChat.ts         # Chat API SSE クライアント
    ├── useDiscussion.ts   # Discussion SSE クライアント
    └── useAgents.ts       # Agent CRUD API クライアント
```

## Components and Interfaces

### 1. Configuration (config.py)

```python
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class EvolutionSettings(BaseSettings):
  """Evolution システム設定

  環境変数 or .env ファイルから読み込む。
  EVOLUTION_ プレフィクスで名前空間を分離。
  """

  # Embedding
  embedding_model: str = "text-embedding-ada-002"

  # Semantic Search
  semantic_search_top_k: int = Field(default=3, ge=1, le=50)
  semantic_search_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

  # Semantic Cache
  semantic_cache_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
  cache_eviction_days: int = Field(default=7, ge=1)

  # Routing
  routing_token_threshold: int = Field(default=50, ge=1)
  hybrid_search_weight: float = Field(default=0.5, ge=0.0, le=1.0)

  # Cloud LLM
  cloud_llm_base_url: str = "https://api.openai.com/v1"
  cloud_llm_model: str = "gpt-4.1-mini"
  cloud_llm_api_key: str  # required — 未設定時は起動失敗

  # SLM (ollama)
  slm_base_url: str = "http://localhost:11434"
  slm_model: str = "llama3.2"

  # MCP
  mcp_transport: str = Field(default="stdio", pattern=r"^(stdio|sse)$")
  mcp_sse_port: int = Field(default=8081, ge=1, le=65535)
  mcp_sse_host: str = "localhost"

  # Prompt
  max_prompt_tokens: int = Field(default=4000, ge=100)

  model_config = {"env_prefix": "EVOLUTION_", "env_file": ".env"}
```

### 2. Prompt Engine (prompt_engine.py)

```python
from dataclasses import dataclass
from jinja2 import Environment, BaseLoader, Template

from app.models.profile import ProfileOutput, BaseOS


# axes score → 強度記述子マッピング
SCORE_DESCRIPTORS = {
  (0.0, 0.29): "strong_second_pole",
  (0.30, 0.49): "moderate_second_pole",
  (0.50, 0.50): "balanced",
  (0.51, 0.70): "moderate_first_pole",
  (0.71, 1.0): "strong_first_pole",
}


@dataclass
class PromptResult:
  """プロンプト生成結果"""
  prompt: str
  token_count: int


class PromptEngine:
  """ProfileOutput → システムプロンプト変換エンジン

  Jinja2 テンプレートを用いてプロファイルデータから
  パーソナリティ特性・ガードレールを含むプロンプトを生成する。
  """

  def __init__(self, max_tokens: int = 4000, template_str: str | None = None):
    self._max_tokens = max_tokens
    self._env = Environment(loader=BaseLoader())
    self._template = self._env.from_string(
      template_str or DEFAULT_TEMPLATE
    )

  def generate(self, profile: ProfileOutput) -> PromptResult:
    """プロファイルからシステムプロンプトを生成する

    Raises:
      ValueError: base_os セクションまたは必須フィールドが欠落している場合
    """
    ...

  def _map_score_to_descriptor(self, score: float) -> str:
    """正規化スコア [0.0, 1.0] → 強度記述子文字列"""
    ...
```

### 3. Context Layer Manager (context_layer_manager.py)

```python
from app.models.profile import ProfileOutput


class ContextLayerManager:
  """3層コンテキストのライフサイクル管理

  Layer 1 (Base OS): セッション開始時にロード、常駐
  Layer 2 (Agent Skills): Function Calling 時に Lexical 検索で動的挿入
  Layer 3 (MCP): MCP サーバー経由で Semantic コンテキストを動的フェッチ
  """

  def __init__(
    self,
    lexical_retriever: "LexicalRetriever",
    semantic_retriever: "SemanticRetriever",
    mcp_client: "MCPClient | None" = None,
    mcp_timeout: float = 5.0,
  ):
    # profile_id → BaseOS のインメモリキャッシュ
    self._base_os_cache: dict[str, "BaseOS"] = {}
    ...

  async def load_profile(self, profile: ProfileOutput) -> None:
    """プロファイルをロードし、3層すべてを初期化する

    Raises:
      ValueError: context_layers の layer 割り当てが不正な場合
    """
    ...

  def get_base_os(self, profile_id: str) -> "BaseOS":
    """Layer 1: キャッシュ済み Base OS を返す"""
    ...

  async def get_skill_context(
    self, profile_id: str, function_name: str, params: dict
  ) -> list[str]:
    """Layer 2: Function Calling コンテキストに基づくスキル検索"""
    ...

  async def get_semantic_context(
    self, profile_id: str, query: str
  ) -> dict[str, str]:
    """Layer 3: MCP 経由 or ローカルフォールバックでセマンティックコンテキスト取得"""
    ...
```

### 4. Lexical Retriever (lexical_retriever.py)

```python
import re


class LexicalRetriever:
  """O(1) 完全一致キーワード検索

  lexical_tags 配列からハッシュインデックスを構築し、
  クエリトークンとの完全一致（case-insensitive）でタグを返す。
  """

  # トークン分割パターン: 空白・カンマ・セミコロン・スラッシュ
  _DELIMITERS = re.compile(r"[\s,;/]+")

  def __init__(self, tags: list[str]):
    # tag_lower → original index のマッピング
    self._index: dict[str, list[int]] = {}
    self._tags = tags
    self._build_index(tags)

  def _build_index(self, tags: list[str]) -> None:
    """ハッシュインデックスを構築する"""
    ...

  def search(self, query: str) -> list[str]:
    """クエリをトークン化し、完全一致するタグを元配列の順序で返す

    Args:
      query: 検索文字列（空白/カンマ/セミコロン/スラッシュで分割）

    Returns:
      マッチしたタグのリスト（元配列の出現順）
    """
    ...

  def tokenize(self, text: str) -> list[str]:
    """テキストをトークンに分割する（日本語対応）"""
    return [t for t in self._DELIMITERS.split(text.lower()) if t]
```

### 5. Semantic Retriever (semantic_retriever.py)

```python
import numpy as np
from dataclasses import dataclass


@dataclass
class SemanticResult:
  """セマンティック検索結果"""
  domain: str
  text: str
  score: float


class SemanticRetriever:
  """cosine similarity ベクトル検索

  numpy でインメモリベクトルインデックスを保持し、
  クエリ埋め込みとの cosine similarity で上位 k 件を返す。
  """

  def __init__(
    self,
    embedding_client: "EmbeddingClient",
    top_k: int = 3,
    threshold: float = 0.7,
  ):
    self._embedding_client = embedding_client
    self._top_k = top_k
    self._threshold = threshold
    # profile_id → (domains, embeddings_matrix)
    self._cache: dict[str, tuple[list[str], np.ndarray]] = {}

  async def index_profile(
    self, profile_id: str, semantic_contexts: dict[str, str]
  ) -> None:
    """プロファイルの semantic_contexts を埋め込み化してインデックスに追加する"""
    ...

  async def search(
    self, profile_id: str, query: str
  ) -> list[SemanticResult]:
    """クエリに最も類似する semantic_contexts を返す

    Returns:
      cosine similarity >= threshold の上位 k 件（降順ソート）
    """
    ...

  @staticmethod
  def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """2ベクトル間の cosine similarity を計算する"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
      return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
```

### 6. Hybrid Search Engine (hybrid_search.py)

```python
from dataclasses import dataclass
from enum import Enum


class ResultSource(str, Enum):
  LEXICAL = "lexical"
  SEMANTIC = "semantic"


@dataclass
class HybridResult:
  """ハイブリッド検索統合結果"""
  content: str
  source: ResultSource
  score: float
  domain: str | None = None  # semantic 結果のみ


class HybridSearchEngine:
  """Lexical + Semantic 検索の統合エンジン

  両 retriever を並列実行し、重み付けスコアで統合・重複排除する。
  """

  def __init__(
    self,
    lexical_retriever: "LexicalRetriever",
    semantic_retriever: "SemanticRetriever",
    weight: float = 0.5,
  ):
    self._lexical = lexical_retriever
    self._semantic = semantic_retriever
    self._weight = weight  # 0.0 = lexical only, 1.0 = semantic only

  async def search(
    self, profile_id: str, query: str
  ) -> list[HybridResult]:
    """ハイブリッド検索を実行し、統合結果を返す

    Lexical match のスコアは 1.0 固定。
    Semantic match のスコアは cosine similarity 値。
    最終スコア = (1 - weight) * lexical_score + weight * semantic_score

    重複: lexical tag が semantic domain のキーと一致する場合、
    semantic 側を優先（コンテキスト情報が豊富なため）。
    """
    ...
```

### 7. Semantic Cache (semantic_cache.py)

```python
import aiosqlite
from datetime import datetime, timezone


class SemanticCache:
  """SQLite ベースのセマンティック・キャッシュ

  発話の埋め込みベクトルを用いた類似度検索で、
  同一・類似の発話に対する LLM レスポンスを再利用する。
  """

  def __init__(
    self,
    db_path: str,
    embedding_client: "EmbeddingClient",
    threshold: float = 0.92,
    eviction_days: int = 7,
  ):
    self._db_path = db_path
    self._embedding_client = embedding_client
    self._threshold = threshold
    self._eviction_days = eviction_days

  async def init_db(self) -> None:
    """キャッシュテーブルを初期化する"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS semantic_cache (
          entry_id TEXT PRIMARY KEY,
          embedding_blob BLOB NOT NULL,
          utterance_text TEXT NOT NULL,
          response_text TEXT NOT NULL,
          profile_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          last_accessed_at TEXT NOT NULL,
          hit_count INTEGER NOT NULL DEFAULT 0
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_cache_profile
        ON semantic_cache(profile_id)
      """)
      await db.commit()

  async def lookup(
    self, profile_id: str, utterance: str
  ) -> str | None:
    """キャッシュヒット検索。閾値以上の類似エントリがあればレスポンスを返す"""
    ...

  async def store(
    self, profile_id: str, utterance: str, response: str
  ) -> None:
    """キャッシュミス後の保存"""
    ...

  async def evict_stale(self) -> int:
    """eviction_days 超未アクセスのエントリを削除し、削除数を返す"""
    ...

  async def invalidate(self, profile_id: str) -> int:
    """指定 profile_id のキャッシュを全削除し、削除数を返す"""
    ...

  async def get_stats(self, profile_id: str) -> dict:
    """キャッシュ統計を返す"""
    ...
```

### 8. Routing Engine (routing_engine.py)

```python
from enum import Enum


class Complexity(str, Enum):
  LIGHT = "light"
  DEEP = "deep"


class RoutingEngine:
  """発話複雑度に基づく LLM ルーティング

  分類基準:
  - トークン数が閾値未満 → light
  - lexical_tags にマッチするドメイン固有語が含まれる → deep
  - メタデータに routing_hint がある → hint に従う
  - 上記いずれにも該当しない場合 → token count で判定
  """

  def __init__(
    self,
    token_threshold: int = 50,
    lexical_retriever: "LexicalRetriever | None" = None,
    slm_base_url: str = "http://localhost:11434",
    slm_model: str = "llama3.2",
    cloud_base_url: str = "https://api.openai.com/v1",
    cloud_model: str = "gpt-4.1-mini",
    cloud_api_key: str = "",
  ):
    ...

  def classify(
    self,
    utterance: str,
    matched_tags: list[str] | None = None,
    routing_hint: str | None = None,
  ) -> Complexity:
    """発話の複雑度を分類する

    Returns:
      Complexity.LIGHT or Complexity.DEEP
    """
    ...

  async def route(
    self,
    utterance: str,
    system_prompt: str,
    matched_tags: list[str] | None = None,
    routing_hint: str | None = None,
  ) -> str:
    """分類結果に応じて適切な LLM にリクエストし、レスポンスを返す

    Raises:
      RuntimeError: Cloud LLM も SLM も利用不可の場合
    """
    ...
```

### 9. Embedding Client (embedding_client.py)

```python
import numpy as np
from openai import AsyncOpenAI


class EmbeddingClient:
  """OpenAI Embeddings API クライアント

  既存の llm_client.py の OpenAI クライアント設定パターンを踏襲しつつ、
  非同期 API で embedding 生成に特化する。
  """

  def __init__(self, model: str = "text-embedding-ada-002", api_key: str = ""):
    self._model = model
    self._client = AsyncOpenAI(api_key=api_key)

  async def embed(self, text: str) -> np.ndarray:
    """単一テキストの埋め込みベクトルを生成する"""
    response = await self._client.embeddings.create(
      model=self._model,
      input=text,
    )
    return np.array(response.data[0].embedding, dtype=np.float32)

  async def embed_batch(self, texts: list[str]) -> np.ndarray:
    """複数テキストの埋め込みベクトルをバッチ生成する

    Returns:
      shape (len(texts), embedding_dim) の numpy 配列
    """
    response = await self._client.embeddings.create(
      model=self._model,
      input=texts,
    )
    return np.array(
      [d.embedding for d in response.data], dtype=np.float32
    )
```

### 10. MCP Server (mcp_server.py)

```python
from mcp.server import Server
from mcp.types import Tool, TextContent


class EvolutionMCPServer:
  """Model Context Protocol サーバー

  semantic_contexts の各ドメインを MCP Tool として公開し、
  外部エージェントが標準プロトコルでコンテキストを取得可能にする。
  """

  def __init__(self, context_layer_manager: "ContextLayerManager"):
    self._server = Server("agent-evolution")
    self._clm = context_layer_manager
    self._register_tools()

  def _register_tools(self) -> None:
    """semantic_contexts ドメインを MCP Tool として登録する"""
    ...

  async def handle_tool_call(
    self, tool_name: str, arguments: dict
  ) -> TextContent:
    """Tool 呼び出しを処理し、対応する semantic_context を返す"""
    ...
```

### 11. REST API Routes (routes.py)

```python
from fastapi import APIRouter, Depends, HTTPException

evolution_router = APIRouter(prefix="/api/v1/evolution")


# POST /api/v1/evolution/profiles
#   → ProfileOutput ロード + 3層初期化

# POST /api/v1/evolution/search
#   → ハイブリッド検索実行

# POST /api/v1/evolution/infer
#   → 推論パイプライン (cache → routing → LLM → cache store)

# GET /api/v1/evolution/profiles/{profile_id}/prompt
#   → 生成済みシステムプロンプト取得

# GET /api/v1/evolution/profiles/{profile_id}/cache/stats
#   → キャッシュ統計

# DELETE /api/v1/evolution/profiles/{profile_id}/cache
#   → キャッシュ無効化
```

### 12. Package Generator (package_generator.py)

> 📖 実装時参照: [docs/agent_skills_specification.md](../../../docs/agent_skills_specification.md) — Agent Skills オープン標準の仕様・思想・バリデーションルールをまとめたリファレンスドキュメント

生成される Zip アーカイブの構造:

```
agent_pack_{agent_id}.zip
├── README.md               # エージェントの起動方法・セットアップガイド
├── config.json             # エージェントのメタデータと基本パラメータ（4軸スコア等）
├── system_prompt.md        # 人格・価値観・Do Notリストが定義されたシステムプロンプト
├── skills/                 # ユーザーの思考特性に特化したエージェントスキル定義
│   ├── reflection_wall.py  # モーニングページや内省をサポートする壁打ちスキル
│   └── code_review_rules.py# ユーザーの美学に準拠したコードレビュー用ルール
└── tools/                  # エージェントが外部環境とやり取りするためのカスタムツール群
    └── project_context.json# 技術スタック（Vue, FastAPI等）の静的コンテキストファイル
```

```python
import zipfile
import io
import json
from pathlib import Path

from app.models.profile import ProfileOutput
from app.evolution.prompt_engine import PromptEngine


# 既知テクノロジー識別子 → tools/ 内ファイルテンプレート
TECH_IDENTIFIERS: dict[str, str] = {
  "python": "python",
  "fastapi": "fastapi",
  "vue": "vue",
  "typescript": "typescript",
  "react": "react",
  "nodejs": "nodejs",
  "docker": "docker",
  "azure-openai": "azure-openai",
  "mcp": "mcp",
}

# semantic_contexts → skills/ 内スキル生成キーワード
SKILL_KEYWORDS: dict[str, str] = {
  "モーニングページ": "reflection_wall",
  "内省": "reflection_wall",
  "壁打ち": "reflection_wall",
  "bullet journal": "reflection_wall",
  "バレットジャーナル": "reflection_wall",
  "コードレビュー": "code_review_rules",
  "美学": "code_review_rules",
  "設計原則": "code_review_rules",
  "pomodoro": "focus_timer",
  "ポモドーロ": "focus_timer",
  "time blocking": "focus_timer",
}


class PackageGenerator:
  """ProfileOutput + agent_id → Agent Pack Zip 生成

  出力構造:
  - README.md: セットアップガイド
  - config.json: メタデータ + 4軸スコア + decision_style + do_not_list
  - system_prompt.md: PromptEngine 出力 (Markdown 形式)
  - skills/: 思考特性に特化したスキル定義 (Python)
  - tools/project_context.json: 技術スタックの静的コンテキスト
  """

  def __init__(self, prompt_engine: PromptEngine):
    self._prompt_engine = prompt_engine

  def generate(
    self, profile: ProfileOutput, agent_id: str, display_name: str
  ) -> dict[str, str]:
    """パッケージ全ファイルを生成し、パス → コンテンツの辞書で返す

    Returns:
      {"README.md": "...", "config.json": "...", "system_prompt.md": "...", ...}
    """
    files: dict[str, str] = {}
    files["README.md"] = self._generate_readme(profile, agent_id, display_name)
    files["config.json"] = self._generate_config_json(profile, agent_id, display_name)
    files["system_prompt.md"] = self._generate_system_prompt_md(profile)

    # skills/ 生成
    skills = self._generate_skills(profile)
    for filename, content in skills:
      files[f"skills/{filename}"] = content

    # tools/ 生成
    files["tools/project_context.json"] = self._generate_project_context(profile)
    tools = self._generate_additional_tools(profile)
    for filename, content in tools:
      files[f"tools/{filename}"] = content

    return files

  def _generate_readme(
    self, profile: ProfileOutput, agent_id: str, display_name: str
  ) -> str:
    """README.md: セットアップガイドとエージェント概要"""
    ...

  def _generate_config_json(
    self, profile: ProfileOutput, agent_id: str, display_name: str
  ) -> str:
    """config.json: メタデータ + base_os パラメータ

    構造:
    {
      "agent_id": "...",
      "profile_id": "prof_XXXXXX",
      "display_name": "...",
      "version": "1.0.0",
      "base_os": { axes, decision_style, do_not_list },
      "skills": ["skills/reflection_wall.py", ...],
      "tools": ["tools/project_context.json", ...]
    }
    """
    ...

  def _generate_system_prompt_md(self, profile: ProfileOutput) -> str:
    """system_prompt.md: PromptEngine 出力を Markdown 形式で保存

    セクション:
    - ## Personality Traits
    - ## Values & Decision Style
    - ## Guardrails (Do Not List)
    - ## Communication Tone

    persona/communication_tone 欠落時は [CUSTOMIZE] マーク付与
    """
    ...

  def _generate_skills(self, profile: ProfileOutput) -> list[tuple[str, str]]:
    """semantic_contexts からスキルキーワードを検出し、スキルファイルを生成

    Returns:
      [("reflection_wall.py", content), ("code_review_rules.py", content), ...]
    """
    ...

  def _generate_project_context(self, profile: ProfileOutput) -> str:
    """tools/project_context.json: lexical_tags から技術スタックを抽出

    出力例:
    {
      "tech_stack": ["vue", "fastapi", "python", "docker"],
      "methodologies": ["agile", "ci/cd"],
      "preferences": { ... }
    }
    """
    tech = [tag for tag in profile.lexical_tags if tag.lower() in TECH_IDENTIFIERS]
    ...

  def _generate_additional_tools(
    self, profile: ProfileOutput
  ) -> list[tuple[str, str]]:
    """lexical_tags から追加ツールファイルを生成

    Returns:
      [(filename, content), ...]
    """
    ...

  def build_zip(
    self, profile: ProfileOutput, agent_id: str, display_name: str
  ) -> bytes:
    """全ファイルを agent_pack_{agent_id}.zip として圧縮して返す"""
    files = self.generate(profile, agent_id, display_name)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
      for path, content in files.items():
        zf.writestr(path, content)
    return buffer.getvalue()
```

### 13. Agent Manager (agent_manager.py)

```python
import uuid
from datetime import datetime, timezone

import aiosqlite

from app.models.profile import ProfileOutput


class AgentRecord:
  """エージェントペルソナのデータレコード"""
  agent_id: str  # UUID v4
  profile_id: str
  display_name: str
  created_at: str  # ISO 8601
  is_active: bool


class AgentManager:
  """分身プロファイルの CRUD 管理

  SQLite agents テーブルを操作し、
  agent_id による複数分身の作成・管理を提供する。
  """

  def __init__(self, db_path: str):
    self._db_path = db_path

  async def init_db(self) -> None:
    """agents テーブルを初期化する"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS agents (
          agent_id TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          created_at TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agents_profile
        ON agents(profile_id)
      """)
      await db.commit()

  async def create(self, profile_id: str, display_name: str) -> AgentRecord:
    """新規エージェントペルソナを作成する

    Raises:
      ValueError: profile_id が存在しない場合
    """
    agent_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    ...

  async def get(self, agent_id: str) -> AgentRecord | None:
    """agent_id でレコードを取得する"""
    ...

  async def list_active(self, profile_id: str) -> list[AgentRecord]:
    """指定 profile_id の有効なエージェント一覧を返す"""
    ...

  async def update_display_name(self, agent_id: str, display_name: str) -> AgentRecord:
    """表示名を更新する"""
    ...

  async def soft_delete(self, agent_id: str) -> None:
    """is_active = False にソフトデリートする"""
    ...
```

### 14. Chat API (chat.py)

```python
import uuid
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.evolution.prompt_engine import PromptEngine
from app.evolution.routing_engine import RoutingEngine


chat_router = APIRouter(prefix="/api/v1/evolution/agents")


class ChatService:
  """1対1チャットサービス

  スレッド管理・会話履歴・推論パイプライン統合を担う。
  SSE ストリーミングレスポンスをサポート。

  推論パイプライン:
  1. AgentManager で agent_id → profile_id を解決
  2. ProfileOutput から persona/communication_tone/semantic_contexts を含む
     リッチなシステムプロンプトを生成
  3. OpenAI Responses API + Function Calling で推論実行
  4. search_memory ツールにより、ユーザーの実回答データ・lexical_tags・
     semantic_contexts を動的に検索し、LLM コンテキストに注入
  5. モデルは記憶データに基づいて人格として応答を生成
  """

  DEFAULT_CONTEXT_WINDOW: int = 20  # 直近20ターンをコンテキストに含む

  def __init__(
    self,
    db_path: str,
    prompt_engine: PromptEngine,
    routing_engine: RoutingEngine,
    context_window: int = 20,
  ):
    self._db_path = db_path
    self._prompt_engine = prompt_engine
    self._routing_engine = routing_engine
    self._context_window = context_window

  async def init_db(self) -> None:
    """threads テーブルを初期化する"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS threads (
          turn_id TEXT PRIMARY KEY,
          thread_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_threads_thread
        ON threads(thread_id, created_at)
      """)
      await db.commit()

  async def send_message(
    self,
    agent_id: str,
    message: str,
    thread_id: str | None = None,
  ) -> dict:
    """メッセージを送信し、レスポンスを返す

    thread_id が None の場合、新規スレッドを作成する。
    直近 context_window ターンを LLM コンテキストに含む。
    """
    thread_id = thread_id or str(uuid.uuid4())
    ...

  async def stream_response(
    self,
    agent_id: str,
    message: str,
    thread_id: str | None = None,
  ):
    """SSE ストリーミングレスポンスを生成する

    Yields:
      "data: {json_chunk}\\n\\n" 形式の SSE イベント
    """
    ...

  async def get_history(
    self, thread_id: str, limit: int | None = None
  ) -> list[dict]:
    """スレッドの会話履歴を取得する"""
    ...
```

### 15. Discussion Engine (discussion_engine.py)

```python
import uuid
from datetime import datetime, timezone

import aiosqlite
from fastapi.responses import StreamingResponse

from app.evolution.agent_manager import AgentManager
from app.evolution.prompt_engine import PromptEngine
from app.evolution.routing_engine import RoutingEngine


class DiscussionTurn:
  """議論の1ターン"""
  turn_number: int
  agent_id: str
  display_name: str
  content: str
  timestamp: str


class DiscussionEngine:
  """マルチエージェント・ターン制議論エンジン

  複数エージェントが順番にテーマについて発話し、
  全ターンを蓄積しながら議論を進行する。
  SSE によるリアルタイム配信をサポート。
  """

  DEFAULT_MAX_TURNS_PER_AGENT: int = 10
  MIN_AGENTS: int = 2
  MAX_AGENTS: int = 6

  def __init__(
    self,
    db_path: str,
    agent_manager: AgentManager,
    prompt_engine: PromptEngine,
    routing_engine: RoutingEngine,
    max_turns_per_agent: int = 10,
  ):
    self._db_path = db_path
    self._agent_manager = agent_manager
    self._prompt_engine = prompt_engine
    self._routing_engine = routing_engine
    self._max_turns_per_agent = max_turns_per_agent

  async def init_db(self) -> None:
    """discussions テーブルを初期化する"""
    async with aiosqlite.connect(self._db_path) as db:
      await db.execute("""
        CREATE TABLE IF NOT EXISTS discussions (
          turn_id TEXT PRIMARY KEY,
          discussion_id TEXT NOT NULL,
          turn_number INTEGER NOT NULL,
          agent_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
      """)
      await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_discussions_id
        ON discussions(discussion_id, turn_number)
      """)
      await db.commit()

  async def start_discussion(
    self,
    agent_ids: list[str],
    theme: str,
  ) -> str:
    """議論を開始し、discussion_id を返す

    Raises:
      ValueError: agent_ids が 2未満 or 6超、または無効な agent_id が含まれる場合
    """
    discussion_id = str(uuid.uuid4())
    ...

  async def run_turns(self, discussion_id: str):
    """全ターンを順次実行する

    各ターンでは前ターンまでの全履歴をコンテキストに含める。
    max_turns_per_agent × agent_count に達したら終了。

    Yields:
      DiscussionTurn
    """
    ...

  async def stream_discussion(
    self,
    agent_ids: list[str],
    theme: str,
  ):
    """SSE ストリーミングで議論を配信する

    Yields:
      "data: {json_turn}\\n\\n" 形式の SSE イベント
    """
    ...
```

### 16. Compatibility Engine (compatibility.py)

```python
import numpy as np
from dataclasses import dataclass
from enum import Enum


class SimilarityClassification(str, Enum):
  HIGHLY_SIMILAR = "highly_similar"
  MODERATELY_SIMILAR = "moderately_similar"
  COMPLEMENTARY = "complementary"
  CONTRASTING = "contrasting"


@dataclass
class CompatibilityReport:
  """相性診断レポート"""
  overall_score: float  # 0-100
  cosine_similarity: float  # 0.0-1.0
  complementarity_score: float  # 0.0-1.0
  per_axis_comparison: dict[str, dict]  # axis_name → {agent_1, agent_2, diff}
  classification: SimilarityClassification
  relationship_type: str  # 人間可読ラベル (e.g., "最高のブレイン", "建設的対立パートナー")
  reason: str  # 1-2文のマッチング理由
  recommended_interaction_mode: str


@dataclass
class Recommendation:
  """レコメンド結果1件"""
  agent_id: str
  display_name: str
  score: float
  explanation: str


class CompatibilityEngine:
  """4軸パラメータに基づく相性診断・レコメンドエンジン

  Cosine Similarity (類似度) と Complementarity (相補性) を
  重み付け合成して最終スコアを算出する。
  """

  def __init__(
    self,
    similarity_weight: float = 0.6,
    complementarity_weight: float = 0.4,
  ):
    self._sim_weight = similarity_weight
    self._comp_weight = complementarity_weight

  def compute_similarity(self, axes_a: list[float], axes_b: list[float]) -> float:
    """4軸ベクトル間の Cosine Similarity を計算する

    Returns:
      0.0〜1.0 のスコア
    """
    a = np.array(axes_a)
    b = np.array(axes_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
      return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

  def compute_complementarity(self, axes_a: list[float], axes_b: list[float]) -> float:
    """相補性スコアを計算する

    各軸の差の絶対値の平均を正規化して 0.0〜1.0 で返す。
    差が大きいほど相補性が高い。
    """
    diffs = [abs(a - b) for a, b in zip(axes_a, axes_b)]
    return sum(diffs) / len(diffs)  # max diff per axis = 1.0

  def compute_compatibility(
    self, axes_a: list[float], axes_b: list[float]
  ) -> CompatibilityReport:
    """総合相性レポートを生成する

    final_score = sim_weight * similarity + comp_weight * complementarity
    スケール: 0〜100
    """
    similarity = self.compute_similarity(axes_a, axes_b)
    complementarity = self.compute_complementarity(axes_a, axes_b)
    overall = (self._sim_weight * similarity + self._comp_weight * complementarity) * 100
    ...

  def classify(self, similarity: float, complementarity: float) -> SimilarityClassification:
    """類似度と相補性から分類を決定する"""
    ...

  async def recommend(
    self,
    source_agent_id: str,
    all_agents: list[dict],  # [{agent_id, axes, display_name}, ...]
  ) -> dict[str, list[Recommendation]]:
    """レコメンドを生成する

    Returns:
      {"most_heated_debate": [...], "business_partner": [...]}
      各カテゴリ最大3件
    """
    ...
```

### 17. Frontend Components (Vue 3)

```
frontend/src/components/evolution/
├── AgentList.vue          # 分身セレクト一覧
├── ChatThread.vue         # 1対1チャットスレッド表示
├── ChatInput.vue          # メッセージ入力コンポーネント
├── DiscussionTheater.vue  # マルチエージェント対話観覧シアター
├── DiscussionSetup.vue    # 議論設定 (エージェント選択 + テーマ入力)
├── TurnBubble.vue         # 発話バブル (アバター + 色分け)
└── composables/
    ├── useChat.ts         # Chat API SSE 接続
    ├── useDiscussion.ts   # Discussion SSE 接続
    └── useAgents.ts       # Agent CRUD API クライアント
```

**AgentList.vue**: アクティブなエージェント一覧を表示し、選択状態を管理する。`useAgents` composable 経由で `/api/v1/evolution/agents` を呼び出す。

**ChatThread.vue**: 選択されたエージェントとの1対1チャット画面。ユーザーメッセージ（右寄せ）とエージェント応答（左寄せ + アバター）を時系列で表示。`useChat` composable が SSE ストリームを購読し、リアルタイム描画する。

**DiscussionTheater.vue**: マルチエージェント議論の観覧画面。`DiscussionSetup` で2〜6エージェント選択 + テーマ入力後、`useDiscussion` composable が SSE でターンを受信し、`TurnBubble` を順次描画する。再生モード（リアルタイム / シミュレーション速度）切り替え、ターンカウンター、プログレスバーを表示。

### 18. Persona Registry (agent_manager.py 拡張)

```python
from enum import Enum


class AgentVisibility(str, Enum):
  PRIVATE = "private"
  PUBLISHED = "published"


class AgentManager:
  """拡張: 公開ペルソナレジストリ機能

  既存の CRUD に加え、visibility (private/published) の状態管理と
  公開ペルソナの全ユーザー横断一覧を提供する。
  ユーザーがプロファイリング完了後に「公開」を承認したエージェントのみが
  チャット・議論の相手として他者から選択可能になる。
  """

  async def publish(self, agent_id: str) -> "AgentRecord":
    """エージェントを公開状態に変更する（明示的 opt-in）

    Raises:
      ValueError: agent_id が存在しない / 非アクティブの場合
    """
    ...

  async def unpublish(self, agent_id: str) -> "AgentRecord":
    """エージェントを非公開に戻す"""
    ...

  async def list_published(self) -> list["AgentRecord"]:
    """公開済みの全エージェントを返す（全ユーザー横断）

    チャット・議論のパートナー選択用。
    """
    ...
```

**DB スキーマ変更:**
```sql
ALTER TABLE agents ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private';
CREATE INDEX idx_agents_visibility ON agents(visibility) WHERE is_active = 1;
```

**API エンドポイント:**
- `POST /api/v1/evolution/agents/{agent_id}/publish` — 公開承認
- `POST /api/v1/evolution/agents/{agent_id}/unpublish` — 非公開に戻す
- `GET /api/v1/evolution/agents/registry` — 公開済みペルソナ一覧

### 19. Discussion Insight Summary (discussion_engine.py 拡張)

```python
@dataclass
class InsightSummary:
  """議論完了後の発見サマリー"""
  discussion_id: str
  key_insights: list[str]  # 3-5 個の主要な気づき
  disagreements: list[str]  # 対立点
  unexpected_perspectives: list[str]  # 予想外の視点
  actionable_suggestions: list[str]  # 人間への actionable 提案
  generated_at: str  # ISO 8601


class DiscussionEngine:
  """拡張: 議論完了後のインサイト生成

  全ターンを LLM に投入し、人間にとって actionable な
  発見・気づき・対立点・提案をまとめる。
  """

  async def generate_summary(self, discussion_id: str) -> InsightSummary:
    """議論ログ全体を要約し、インサイトを抽出する。

    LLM に議論全文を投入し、以下を抽出:
    - key_insights: 主要な気づき (3-5個)
    - disagreements: エージェント間の対立点
    - unexpected_perspectives: 参加者の人格パラメータからは予想外だった視点
    - actionable_suggestions: ユーザーへの具体的提案

    Raises:
      ValueError: discussion_id が存在しない場合
      RuntimeError: LLM が利用不可の場合
    """
    ...
```

**API エンドポイント:**
- `POST /api/v1/evolution/discussions/{discussion_id}/summary` — インサイト生成
- `GET /api/v1/evolution/discussions/{discussion_id}/summary` — キャッシュ済みサマリー取得

**DB テーブル:**
```sql
CREATE TABLE IF NOT EXISTS discussion_summaries (
  discussion_id TEXT PRIMARY KEY,
  key_insights TEXT NOT NULL,       -- JSON array
  disagreements TEXT NOT NULL,       -- JSON array
  unexpected_perspectives TEXT NOT NULL, -- JSON array
  actionable_suggestions TEXT NOT NULL,  -- JSON array
  generated_at TEXT NOT NULL
);
```

## Data Models

```python
from pydantic import BaseModel, Field
from enum import Enum


class SearchResultSource(str, Enum):
  LEXICAL = "lexical"
  SEMANTIC = "semantic"


class SearchResultItem(BaseModel):
  """ハイブリッド検索結果の1件"""
  content: str
  source: SearchResultSource
  score: float = Field(ge=0.0, le=1.0)
  domain: str | None = None


class HybridSearchRequest(BaseModel):
  """ハイブリッド検索リクエスト"""
  profile_id: str = Field(pattern=r"^prof_\d{6}$")
  query: str = Field(min_length=1, max_length=1000)
  weight: float = Field(default=0.5, ge=0.0, le=1.0)
  top_k: int = Field(default=3, ge=1, le=50)


class HybridSearchResponse(BaseModel):
  """ハイブリッド検索レスポンス"""
  results: list[SearchResultItem]
  total: int


class InferRequest(BaseModel):
  """推論リクエスト"""
  profile_id: str = Field(pattern=r"^prof_\d{6}$")
  utterance: str = Field(min_length=1, max_length=5000)
  routing_hint: str | None = None


class InferResponse(BaseModel):
  """推論レスポンス"""
  response: str
  source: str  # "cache", "slm", "cloud_llm"
  profile_id: str


class CacheStats(BaseModel):
  """キャッシュ統計"""
  total_entries: int
  hit_rate: float
  avg_similarity: float


class ProfileLoadResponse(BaseModel):
  """プロファイルロード成功レスポンス"""
  profile_id: str
  accepted_at: str
  layers_initialized: list[int]


# --- Phase 2/3 追加モデル ---

class AgentCreateRequest(BaseModel):
  """エージェント作成リクエスト"""
  profile_id: str = Field(pattern=r"^prof_\d{6}$")
  display_name: str = Field(min_length=1, max_length=100)


class AgentResponse(BaseModel):
  """エージェントレスポンス"""
  agent_id: str
  profile_id: str
  display_name: str
  created_at: str
  is_active: bool


class ChatRequest(BaseModel):
  """チャットリクエスト"""
  message: str = Field(min_length=1, max_length=5000)
  thread_id: str | None = None


class ChatResponse(BaseModel):
  """チャットレスポンス"""
  thread_id: str
  agent_id: str
  response: str
  source: str  # "cache", "slm", "cloud_llm"


class DiscussionCreateRequest(BaseModel):
  """議論開始リクエスト"""
  agent_ids: list[str] = Field(min_length=2, max_length=6)
  theme: str = Field(min_length=1, max_length=1000)
  max_turns: int = Field(default=10, ge=1, le=50)


class DiscussionTurnResponse(BaseModel):
  """議論ターンレスポンス"""
  discussion_id: str
  turn_number: int
  agent_id: str
  display_name: str
  content: str
  timestamp: str


class CompatibilityReportResponse(BaseModel):
  """相性診断レスポンス"""
  overall_score: float = Field(ge=0.0, le=100.0)
  cosine_similarity: float = Field(ge=0.0, le=1.0)
  complementarity_score: float = Field(ge=0.0, le=1.0)
  per_axis_comparison: dict[str, dict]
  classification: str
  relationship_type: str  # 人間可読なラベル (e.g., "最高のブレイン", "建設的対立パートナー")
  reason: str  # 1-2文のマッチング理由
  recommended_interaction_mode: str
  recommendations: RecommendationResponse | None = None  # 統合レスポンス時に含む


class RecommendationItem(BaseModel):
  """レコメンド1件"""
  agent_id: str
  display_name: str
  score: float
  relationship_type: str  # 人間可読なラベル
  explanation: str


class RecommendationResponse(BaseModel):
  """レコメンドレスポンス"""
  most_heated_debate: list[RecommendationItem] = Field(max_length=3)
  business_partner: list[RecommendationItem] = Field(max_length=3)


class ExportRequest(BaseModel):
  """エクスポートクエリパラメータ"""
  format: str = Field(default="json", pattern=r"^(json|markdown)$")


class ConversationExport(BaseModel):
  """会話エクスポート"""
  metadata: dict  # participants, timestamps, theme
  turns: list[dict]  # chronologically ordered turns
```

## Error Handling

| Scenario | HTTP Status | Error Code | Recovery |
|----------|-------------|-----------|----------|
| ProfileOutput バリデーション失敗 | 422 | `validation_error` | フィールドレベルのエラー詳細を返却 |
| profile_id 未ロード | 404 | `profile_not_loaded` | プロファイルロード API を先に呼ぶ |
| context_layers 不正 | 422 | `invalid_layer_config` | 正しい layer 割り当てに修正 |
| Embedding API 不通 | 200 (degraded) | — | 空の semantic 結果を返却、ログ記録 |
| MCP 接続タイムアウト | 200 (degraded) | — | ローカルデータにフォールバック |
| SLM 不通 | 200 (fallback) | — | Cloud LLM にフォールバック |
| Cloud LLM 不通 | 503 | `llm_unavailable` | エラーレスポンスを返却 |
| SQLite 不通 | 200 (degraded) | — | キャッシュバイパス、直接推論 |
| 設定不備 (API key 未設定) | — | — | 起動失敗 + ログ出力 |
| agent_id 未登録 / 非アクティブ | 404 | `agent_not_found` | 有効な agent_id を指定 |
| agent_ids 数 < 2 or > 6 (議論) | 422 | `invalid_agent_count` | 2〜6 の agent_id を指定 |
| thread_id / discussion_id 不在 | 404 | `conversation_not_found` | 有効な ID を指定 |
| Package_Generator 生成失敗 | 500 | `package_generation_error` | プロファイルの整合性を確認 |
| エクスポート format 不正 | 422 | `invalid_format` | json or markdown を指定 |

## Integration with Existing Codebase

1. **main.py 拡張**: `evolution_router` を `app.include_router(evolution_router)` で追加登録。`chat_router`, `discussion_router`, `compatibility_router` も同様。
2. **llm_client.py 流用**: `EmbeddingClient` は既存の OpenAI クライアント初期化パターンを踏襲（環境変数によるプロバイダー切り替え）
3. **aiosqlite 共有**: 既存セッション DB と同じ `aiosqlite` パターンで `semantic_cache`, `agents`, `threads`, `discussions` テーブルを同一 DB ファイルに保持
4. **ProfileOutput モデル再利用**: `app.models.profile.ProfileOutput` をそのまま入力モデルとして使用
5. **DI パターン踏襲**: `evolution/dependencies.py` で `init_evolution_services()` を定義し、lifespan で呼び出す
6. **SSE ストリーミング**: `fastapi.responses.StreamingResponse` + `asyncio` ジェネレータでチャット・議論のリアルタイム配信を実現
7. **Zip 生成**: Python 標準ライブラリ `zipfile` を使用。外部依存追加なし
8. **Frontend**: Vue 3 + TypeScript + Vite。`frontend/` ディレクトリに Composition API コンポーネントとして追加

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Prompt faithfulness

*For any* valid `ProfileOutput`, the generated system prompt SHALL contain all `do_not_list` items, the `decision_style` label, and descriptive sentences for all four axes values from `base_os`.

**Validates: Requirements 1.1, 1.2, 1.4**

### Property 2: Axes score descriptor mapping

*For any* normalized score value in [0.0, 1.0], the `_map_score_to_descriptor` function SHALL return the correct strength descriptor according to the defined ranges (0.0–0.29: strong second pole, 0.30–0.49: moderate second pole, 0.50: balanced, 0.51–0.70: moderate first pole, 0.71–1.0: strong first pole).

**Validates: Requirements 1.3**

### Property 3: Prompt rejects invalid profile

*For any* `ProfileOutput` missing `base_os`, `axes`, `decision_style`, or `do_not_list`, the `PromptEngine.generate()` SHALL raise a `ValueError` specifying which fields are missing.

**Validates: Requirements 1.5**

### Property 4: Prompt token limit invariant

*For any* valid `ProfileOutput`, the generated system prompt SHALL not exceed `max_prompt_tokens` (default 4000) tokens in length.

**Validates: Requirements 1.6**

### Property 5: Context layer assignment validation

*For any* `ProfileOutput` where `context_layers.base_os != 1`, `context_layers.lexical_tags != 2`, or `context_layers.semantic_contexts != 3`, the `ContextLayerManager.load_profile()` SHALL reject the profile with a configuration error specifying the invalid assignment.

**Validates: Requirements 2.3, 2.4, 3.6, 4.6**

### Property 6: Lexical retrieval correctness

*For any* set of `lexical_tags` and any query string, the `LexicalRetriever.search()` SHALL return exactly those tags that match any query token (case-insensitive exact match), ordered by their original position in the `lexical_tags` array. Japanese text SHALL be tokenized on whitespace and delimiters (comma, semicolon, slash).

**Validates: Requirements 5.2, 5.3, 5.6**

### Property 7: Semantic retrieval correctness

*For any* set of embedding vectors and a query embedding, the `SemanticRetriever.search()` SHALL return at most `top_k` results, all with cosine similarity >= `threshold`, sorted in descending order of similarity score.

**Validates: Requirements 6.3, 6.4**

### Property 8: Hybrid merge correctness

*For any* combination of lexical results and semantic results, the `HybridSearchEngine.search()` SHALL produce a unified result set where: (a) each result is annotated with its source type ("lexical" or "semantic") and a relevance score, (b) duplicates where a lexical tag matches a semantic domain key are deduplicated in favor of the semantic result, and (c) results from both sources are included.

**Validates: Requirements 7.1, 7.2, 7.3**

### Property 9: Hybrid weighting influence

*For any* weight parameter `w` in [0.0, 1.0], the final score of lexical results SHALL be `(1 - w) * 1.0` and semantic results SHALL be `w * similarity_score`. Results SHALL be ordered by final score descending.

**Validates: Requirements 7.4**

### Property 10: Semantic cache round-trip

*For any* utterance and response pair stored in the `SemanticCache`, a subsequent lookup with the same utterance (similarity = 1.0, above threshold) for the same `profile_id` SHALL return the stored response.

**Validates: Requirements 8.3**

### Property 11: Semantic cache profile isolation

*For any* two distinct `profile_id` values, a cached response stored for one profile SHALL never be returned for a query associated with the other profile, regardless of utterance similarity.

**Validates: Requirements 8.6**

### Property 12: Semantic cache eviction

*For any* cache entry whose `last_accessed_at` exceeds `eviction_days` from the current time, the `evict_stale()` operation SHALL remove that entry from the database.

**Validates: Requirements 8.5**

### Property 13: Routing classification determinism

*For any* utterance, the `RoutingEngine.classify()` SHALL return exactly one of `Complexity.LIGHT` or `Complexity.DEEP`, determined by: (1) explicit `routing_hint` if present, (2) presence of domain-specific `lexical_tags` matches → DEEP, (3) token count >= threshold → DEEP, (4) otherwise → LIGHT.

**Validates: Requirements 9.1, 9.4**

### Property 14: Profile validation acceptance

*For any* JSON conforming to the `ProfileOutput` Pydantic schema (valid `profile_id` format, `base_os.axes` in [0.0, 1.0], `lexical_tags` count 5–500, `semantic_contexts` values 10–2000 chars, `do_not_list` count 1–4), the validation SHALL succeed and return the `profile_id` with an acceptance timestamp.

**Validates: Requirements 10.1, 10.7**

### Property 15: Profile validation rejection

*For any* JSON violating any `ProfileOutput` constraint (invalid `profile_id` pattern, out-of-range axes values, lexical_tags count violation, semantic_contexts length violation, do_not_list count violation), the validation SHALL reject the input with an error specifying the violated constraint.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**

### Property 16: Configuration defaults

*For any* configuration parameter not explicitly set via environment variable, the `EvolutionSettings` SHALL use the documented default value (e.g., `semantic_cache_threshold=0.92`, `semantic_search_top_k=3`, `routing_token_threshold=50`).

**Validates: Requirements 13.2**

### Property 17: Package structure completeness

*For any* valid `ProfileOutput`, the `PackageGenerator.generate()` SHALL produce a file set containing: (a) `agent.json` with `name` derived from `persona.nickname`, `version`, `description`, and `tools` declarations, (b) `instruction.md` containing persona description, communication tone, and values sections, (c) `system_prompt.txt`, and (d) a `tools/` subdirectory.

**Validates: Requirements 14.1, 14.5, 14.6**

### Property 18: System prompt file round-trip

*For any* valid `ProfileOutput`, the content of the generated `system_prompt.txt` file SHALL be identical to the output of `PromptEngine.generate(profile).prompt`.

**Validates: Requirements 14.2**

### Property 19: Technology tool generation

*For any* valid `ProfileOutput` whose `lexical_tags` contain one or more recognized technology identifiers (e.g., "python", "vue", "fastapi", "typescript"), the `PackageGenerator` SHALL generate a corresponding Python script file in the `tools/` subdirectory for each detected technology.

**Validates: Requirements 14.3**

### Property 20: Workflow tool schema generation

*For any* valid `ProfileOutput` whose `semantic_contexts` values contain recognized workflow preference keywords (e.g., "bullet journal", "pomodoro", "gtd"), the `PackageGenerator` SHALL generate a JSON Schema definition file in the `tools/` subdirectory for each detected workflow preference.

**Validates: Requirements 14.4**

### Property 21: Zip archive round-trip

*For any* valid `ProfileOutput`, the Zip archive produced by `PackageGenerator.build_zip()` SHALL, when extracted, contain exactly the same set of files (paths and contents) as returned by `PackageGenerator.generate()`.

**Validates: Requirements 15.2**

### Property 22: Agent ID uniqueness and multi-agent ownership

*For any* valid `profile_id` and any number N of agent creation requests, the `AgentManager` SHALL return N distinct UUID v4 `agent_id` values, all associated with the same `profile_id`.

**Validates: Requirements 16.1, 16.3**

### Property 23: Agent CRUD round-trip

*For any* agent created via `AgentManager.create()`, a subsequent `get()` SHALL return the same `agent_id`, `profile_id`, and `display_name`. After `update_display_name()`, the new name SHALL be reflected. After `soft_delete()`, `is_active` SHALL be `False`.

**Validates: Requirements 16.4**

### Property 24: Active agents filter

*For any* set of agents with mixed `is_active` states belonging to a `profile_id`, the `AgentManager.list_active()` SHALL return only those agents where `is_active` is `True`, each containing `agent_id`, `display_name`, and `created_at`.

**Validates: Requirements 16.7**

### Property 25: Conversation history accumulation

*For any* sequence of N messages sent to the same `thread_id`, the `ChatService` SHALL maintain a history of exactly N user-agent turn pairs, and each subsequent LLM request SHALL include all prior turns in the conversation context.

**Validates: Requirements 17.3**

### Property 26: Context window limit

*For any* thread with more than `context_window` (default 20) turns, the LLM request context SHALL include at most `context_window` most recent turns, discarding older turns.

**Validates: Requirements 17.4**

### Property 27: Chat turn persistence

*For any* chat interaction (user message + agent response), the `ChatService` SHALL store both turns in the SQLite `threads` table with correct `thread_id`, `agent_id`, `role`, `content`, and `created_at` timestamp.

**Validates: Requirements 17.6**

### Property 28: Discussion prompts reflect individual personalities

*For any* set of agents participating in a discussion, the `DiscussionEngine` SHALL construct a unique system prompt for each agent that reflects that agent's own `base_os` personality parameters, and no two agents with different profiles SHALL receive identical system prompts.

**Validates: Requirements 18.2**

### Property 29: Discussion turn accumulation

*For any* discussion turn N (N > 1), the LLM context for that turn SHALL include all prior turns 1 through N−1, ensuring each agent responds with awareness of the full conversation history.

**Validates: Requirements 18.3**

### Property 30: Discussion max turns invariant

*For any* discussion with K agents and `max_turns_per_agent` = M, the total number of turns generated SHALL NOT exceed K × M.

**Validates: Requirements 18.4**

### Property 31: Discussion turn attribution

*For any* turn in a discussion, the turn metadata SHALL include the generating agent's `agent_id` and `display_name`.

**Validates: Requirements 18.5**

### Property 32: Discussion turn persistence

*For any* completed discussion, ALL generated turns SHALL be stored in the SQLite `discussions` table with correct `discussion_id`, `turn_number`, `agent_id`, `display_name`, `content`, and `created_at`.

**Validates: Requirements 18.6**

### Property 33: Compatibility score computation

*For any* two agents with valid 4-axis parameter vectors, the `CompatibilityEngine` SHALL produce a report where: (a) `cosine_similarity` equals the mathematical cosine similarity of the two vectors, (b) `complementarity_score` equals the mean absolute difference of corresponding axes, (c) `overall_score` = (`similarity_weight` × `cosine_similarity` + `complementarity_weight` × `complementarity_score`) × 100, constrained to [0, 100], and (d) the report contains `per_axis_comparison`, `classification`, and `recommended_interaction_mode`.

**Validates: Requirements 19.1, 19.2, 19.3, 19.4**

### Property 34: Recommendation ranking

*For any* source agent with 2+ other active agents available, the `Recommendation_Engine` SHALL return at most 3 recommendations per category, where "most\_heated\_debate" is sorted by `complementarity_score` descending and "business\_partner" is sorted by `cosine_similarity` descending. Each recommendation SHALL contain `agent_id`, `display_name`, `score`, and `explanation`.

**Validates: Requirements 20.1, 20.2, 20.3**

### Property 35: Export completeness and ordering

*For any* conversation (thread or discussion) with N turns, the exported file SHALL contain exactly N turns ordered chronologically by timestamp, plus metadata including participant information and timestamps.

**Validates: Requirements 23.2, 23.3, 23.4**

### Property 36: Export format equivalence

*For any* conversation, exporting in JSON format and Markdown format SHALL produce logically equivalent data — the same number of turns with the same content and metadata, differing only in serialization format.

**Validates: Requirements 23.5**

## Testing Strategy

### Property-Based Testing (Hypothesis)

本プロジェクトでは `hypothesis` ライブラリを使用し、各 Correctness Property を最低100イテレーションで検証する。

**テスト構成:**
- ライブラリ: `hypothesis==6.119.3` (既存 dev dependency)
- 最小イテレーション: 100 回/プロパティ
- タグ形式: `# Feature: agent-evolution, Property {N}: {title}`

**テスト対象とアプローチ:**

| Property | テスト戦略 |
|----------|-----------|
| P1–P4 (Prompt) | ランダム ProfileOutput 生成 → プロンプト文字列検証 |
| P5 (Layer validation) | ランダム context_layers 値 → バリデーション挙動検証 |
| P6 (Lexical) | ランダム tags + query → 結果順序・完全一致検証 |
| P7 (Semantic) | ランダム embedding 行列 → top-k/threshold 検証 |
| P8–P9 (Hybrid) | Lexical + Semantic 結果マージ → 重複排除・重み付け検証 |
| P10–P12 (Cache) | ランダム utterance ペア → ラウンドトリップ・分離・eviction 検証 |
| P13 (Routing) | ランダム utterance → 分類決定論的検証 |
| P14–P16 (Validation/Config) | ランダム JSON → accept/reject 検証 |
| P17–P21 (Package) | ランダム ProfileOutput → ファイル構造・内容・Zip 検証 |
| P22–P24 (Agent CRUD) | ランダム profile_id/display_name → CRUD ラウンドトリップ |
| P25–P27 (Chat) | ランダムメッセージ列 → 履歴蓄積・ウィンドウ・永続化検証 |
| P28–P32 (Discussion) | ランダムエージェント集合 → プロンプト差異・ターン蓄積・上限・帰属・永続化 |
| P33 (Compatibility) | ランダム 4D ベクトルペア → 数学的正確性検証 |
| P34 (Recommendation) | ランダムエージェント集合 → ソート順・カテゴリ分類検証 |
| P35–P36 (Export) | ランダム会話データ → エクスポート完全性・フォーマット等価性 |

### Unit Tests (pytest)

- 各コンポーネントの具体的なシナリオ・エッジケース検証
- モック: LLM API / Embedding API / SQLite
- エッジケース: 空配列、最大長、不正フォーマット、非アクティブエージェント

### Integration Tests

- FastAPI TestClient を使用したエンドポイント結合テスト
- SSE ストリーミングの接続・切断テスト
- SQLite テーブル間の整合性テスト
