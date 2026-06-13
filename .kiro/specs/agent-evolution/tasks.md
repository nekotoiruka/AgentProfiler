# Implementation Plan: Agent Evolution

## Overview

Agent Profiler が生成した ProfileOutput JSON を入力とし、AIエージェントの動的パーソナライゼーションを実現するランタイムシステムを `backend/app/evolution/` サブモジュールとして実装する。3層コンテキスト管理・ハイブリッド検索・セマンティックキャッシュ・ルーティングの4つのコア機能を段階的に構築し、REST API として公開する。

## Tasks

- [x] 1. プロジェクト構造と設定管理
  - [x] 1.1 evolution サブモジュールの初期化と設定クラス作成
    - `backend/app/evolution/__init__.py` を作成
    - `backend/app/evolution/config.py` に `EvolutionSettings` (pydantic-settings) を実装
    - 環境変数プレフィクス `EVOLUTION_` で名前空間分離
    - 全パラメータにデフォルト値とバリデーションを設定
    - `CLOUD_LLM_API_KEY` 未設定時のスタートアップエラーを実装
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [x] 1.2 Evolution 固有データモデル定義
    - `backend/app/evolution/models.py` に API リクエスト/レスポンスモデルを定義
    - `HybridSearchRequest`, `HybridSearchResponse`, `InferRequest`, `InferResponse`, `CacheStats`, `ProfileLoadResponse`, `SearchResultItem` を実装
    - _Requirements: 10.1, 11.8, 11.9_

  - [x] 1.3 設定バリデーションのプロパティテスト
    - **Property 16: Configuration defaults**
    - **Validates: Requirements 13.2**

- [x] 2. Embedding クライアントとプロファイルバリデーション
  - [x] 2.1 Embedding Client 実装
    - `backend/app/evolution/embedding_client.py` に `EmbeddingClient` を実装
    - OpenAI AsyncClient を使用した `embed()` と `embed_batch()` メソッド
    - API 不通時のエラーハンドリング（例外を握りつぶし空結果を返す）
    - _Requirements: 6.1, 6.6_

  - [x] 2.2 プロファイル入力バリデーション実装
    - `backend/app/evolution/models.py` にバリデーションロジックを追加
    - profile_id パターン検証 (`prof_` + 6桁)
    - base_os.axes 値域チェック (0.0–1.0)
    - lexical_tags 件数チェック (5–500)
    - semantic_contexts 文字数チェック (10–2000文字)
    - do_not_list 件数チェック (1–4)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [x] 2.3 プロファイルバリデーションのプロパティテスト
    - **Property 14: Profile validation acceptance**
    - **Property 15: Profile validation rejection**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7**

- [x] 3. 動的プロンプト生成エンジン
  - [x] 3.1 PromptEngine 実装
    - `backend/app/evolution/prompt_engine.py` に `PromptEngine` クラスを実装
    - Jinja2 テンプレートによるシステムプロンプト組み立て
    - axes スコア → 強度記述子マッピング (`_map_score_to_descriptor`)
    - do_not_list をガードレールとしてフォーマット
    - decision_style を意思決定アプローチとして挿入
    - base_os 欠損時の ValueError 送出
    - トークン上限 (4000) チェック
    - カスタムテンプレートパラメータ対応
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x] 3.2 PromptEngine のプロパティテスト
    - **Property 1: Prompt faithfulness**
    - **Property 2: Axes score descriptor mapping**
    - **Property 3: Prompt rejects invalid profile**
    - **Property 4: Prompt token limit invariant**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

- [ ] 4. Checkpoint - 基盤コンポーネント確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Lexical Retriever
  - [x] 5.1 LexicalRetriever 実装
    - `backend/app/evolution/lexical_retriever.py` に `LexicalRetriever` クラスを実装
    - ハッシュインデックス構築 (tag_lower → original index)
    - トークン化: 空白・カンマ・セミコロン・スラッシュで分割（日本語対応）
    - case-insensitive 完全一致検索
    - 結果を元配列の出現順で返却
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 5.2 LexicalRetriever のプロパティテスト
    - **Property 6: Lexical retrieval correctness**
    - **Validates: Requirements 5.2, 5.3, 5.6**

- [x] 6. Semantic Retriever
  - [x] 6.1 SemanticRetriever 実装
    - `backend/app/evolution/semantic_retriever.py` に `SemanticRetriever` クラスを実装
    - numpy インメモリベクトルインデックス
    - cosine similarity 計算 (ゼロベクトル対応)
    - profile_id 別の埋め込みキャッシュ
    - top-k + threshold フィルタリング
    - Embedding API 不通時の空結果フォールバック
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 6.2 SemanticRetriever のプロパティテスト
    - **Property 7: Semantic retrieval correctness**
    - **Validates: Requirements 6.3, 6.4**

- [x] 7. Hybrid Search Engine
  - [x] 7.1 HybridSearchEngine 実装
    - `backend/app/evolution/hybrid_search.py` に `HybridSearchEngine` クラスを実装
    - Lexical + Semantic の並列実行 (asyncio.gather)
    - 重み付けスコア統合: `(1 - weight) * lexical_score + weight * semantic_score`
    - 重複排除: lexical tag が semantic domain キーと一致する場合 semantic 側を優先
    - 結果にソースタイプ ("lexical" / "semantic") とスコアを付与
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 7.2 HybridSearchEngine のプロパティテスト
    - **Property 8: Hybrid merge correctness**
    - **Property 9: Hybrid weighting influence**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

- [ ] 8. Checkpoint - 検索レイヤー確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Context Layer Manager
  - [x] 9.1 ContextLayerManager 実装
    - `backend/app/evolution/context_layer_manager.py` に `ContextLayerManager` クラスを実装
    - `load_profile()`: context_layers バリデーション + 3層初期化
    - `get_base_os()`: Layer 1 キャッシュ済みデータ返却
    - `get_skill_context()`: Layer 2 Lexical 検索による動的挿入
    - `get_semantic_context()`: Layer 3 MCP 経由 + ローカルフォールバック
    - profile_id 間の Base OS キャッシュ共有
    - MCP タイムアウト (5秒) 時のフォールバック
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.5, 3.6, 4.3, 4.4, 4.5, 4.6_

  - [x] 9.2 ContextLayerManager のプロパティテスト
    - **Property 5: Context layer assignment validation**
    - **Validates: Requirements 2.3, 2.4, 3.6, 4.6**

- [x] 10. Semantic Cache
  - [x] 10.1 SemanticCache 実装
    - `backend/app/evolution/semantic_cache.py` に `SemanticCache` クラスを実装
    - `init_db()`: SQLite テーブル + インデックス作成
    - `lookup()`: 埋め込み cosine similarity で閾値以上のエントリを検索、hit_count 更新
    - `store()`: キャッシュミス後のエントリ保存
    - `evict_stale()`: eviction_days 超のエントリ削除
    - `invalidate()`: profile_id 指定のキャッシュ全削除
    - `get_stats()`: 統計情報取得
    - SQLite 不通時のバイパス (例外を握りつぶし直接推論)
    - profile_id スコープによるキャッシュ隔離
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 10.2 SemanticCache のプロパティテスト
    - **Property 10: Semantic cache round-trip**
    - **Property 11: Semantic cache profile isolation**
    - **Property 12: Semantic cache eviction**
    - **Validates: Requirements 8.3, 8.5, 8.6**

- [x] 11. Routing Engine
  - [x] 11.1 RoutingEngine 実装
    - `backend/app/evolution/routing_engine.py` に `RoutingEngine` クラスを実装
    - `classify()`: トークン数 + lexical_tags マッチ + routing_hint による複雑度分類
    - `route()`: 分類結果に応じた SLM / Cloud LLM へのリクエスト
    - SLM 不通時の Cloud LLM フォールバック
    - Cloud LLM 不通時の RuntimeError 送出
    - ollama 互換 API (SLM) + OpenAI API (Cloud) 両対応
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x] 11.2 RoutingEngine のプロパティテスト
    - **Property 13: Routing classification determinism**
    - **Validates: Requirements 9.1, 9.4**

- [ ] 12. Checkpoint - コアエンジン確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. MCP Server
  - [x] 13.1 MCP Server 実装
    - `backend/app/evolution/mcp_server.py` に `EvolutionMCPServer` クラスを実装
    - mcp Python SDK を使用した Server インスタンス作成
    - semantic_contexts ドメインを MCP Tool として登録
    - stdio / SSE トランスポート対応
    - profile_id パラメータによるスコープ制御
    - 不存在ドメインのエラーレスポンス
    - 全 Tool 呼び出しのロギング（timestamp, profile_id, domain, status）
    - _Requirements: 4.1, 4.2, 4.7, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_

- [x] 14. REST API Routes と DI
  - [x] 14.1 DI コンテナと dependencies 実装
    - `backend/app/evolution/dependencies.py` に `init_evolution_services()` を実装
    - 全コンポーネントの初期化とライフサイクル管理
    - SemanticCache の DB 初期化
    - `backend/app/main.py` に `evolution_router` を登録
    - _Requirements: 11.10, 13.1_

  - [x] 14.2 REST API ルーター実装
    - `backend/app/evolution/routes.py` に `evolution_router` (prefix `/api/v1/evolution`) を実装
    - `POST /profiles`: ProfileOutput ロード + 3層初期化
    - `POST /search`: ハイブリッド検索実行
    - `POST /infer`: 推論パイプライン (cache → routing → LLM → cache store)
    - `GET /profiles/{profile_id}/prompt`: 生成済みシステムプロンプト取得
    - `GET /profiles/{profile_id}/cache/stats`: キャッシュ統計
    - `DELETE /profiles/{profile_id}/cache`: キャッシュ無効化
    - 404 (未ロード profile_id) / 422 (バリデーションエラー) のエラーハンドリング
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10_

  - [x] 14.3 REST API の統合テスト
    - httpx AsyncClient を用いた全エンドポイントのテスト
    - 正常系・異常系 (404, 422) のレスポンス検証
    - _Requirements: 11.7, 11.8_

- [ ] 15. pyproject.toml 依存関係追加
  - [x] 15.1 新規依存パッケージの追加
    - `pydantic-settings`, `jinja2`, `numpy`, `mcp`, `aiosqlite` (既存) を `pyproject.toml` に追加
    - dev dependencies に `hypothesis` (既存), `pytest` (既存) を確認
    - _Requirements: 13.1_

- [ ] 16. Final checkpoint - 全体統合確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Agent Manager + DB テーブル
  - [x] 17.1 AgentManager 実装
    - `backend/app/evolution/agent_manager.py` に `AgentManager` クラスを実装
    - `init_db()`: agents テーブル + profile インデックス作成
    - `create()`: UUID v4 生成、profile_id 存在チェック、レコード挿入
    - `get()`: agent_id によるレコード取得
    - `list_active()`: profile_id 指定の有効エージェント一覧
    - `update_display_name()`: 表示名更新
    - `soft_delete()`: is_active = False のソフトデリート
    - Agent 作成時に Base_OS + コンテキスト層の初期化を呼び出す
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_

  - [x] 17.2 Agent REST API エンドポイント実装
    - `backend/app/evolution/routes.py` にエージェント CRUD エンドポイントを追加
    - `POST /api/v1/evolution/agents`: 新規エージェント作成
    - `GET /api/v1/evolution/agents?profile_id={id}`: 有効エージェント一覧
    - `GET /api/v1/evolution/agents/{agent_id}`: 個別取得
    - `PATCH /api/v1/evolution/agents/{agent_id}`: display_name 更新
    - `DELETE /api/v1/evolution/agents/{agent_id}`: ソフトデリート
    - 404 (agent_id 未登録) / 422 (profile_id 不存在) エラーハンドリング
    - _Requirements: 16.4, 16.6, 16.7_

  - [x] 17.3 AgentManager のプロパティテスト
    - **Property 22: Agent ID uniqueness and multi-agent ownership**
    - **Property 23: Agent CRUD round-trip**
    - **Property 24: Active agents filter**
    - **Validates: Requirements 16.1, 16.3, 16.4, 16.7**

- [x] 18. Chat API + スレッド管理
  - [x] 18.1 ChatService 実装
    - `backend/app/evolution/chat.py` に `ChatService` クラスを実装
    - `init_db()`: threads テーブル + thread_id インデックス作成
    - `send_message()`: メッセージ送信 → 推論パイプライン → レスポンス返却
    - `stream_response()`: SSE ストリーミングレスポンス生成
    - `get_history()`: スレッド会話履歴取得
    - thread_id 自動生成（新規スレッド作成）
    - context_window (デフォルト20) 超過時の古いターン切り捨て
    - 各ターンの SQLite 永続化 (turn_id, thread_id, agent_id, role, content, created_at)
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

  - [x] 18.2 Chat REST API エンドポイント実装
    - `backend/app/evolution/routes.py` にチャットエンドポイントを追加
    - `POST /api/v1/evolution/agents/{agent_id}/chat`: メッセージ送信 + レスポンス
    - `GET /api/v1/evolution/agents/{agent_id}/chat/{thread_id}`: 会話履歴取得
    - Accept: text/event-stream ヘッダー時の SSE ストリーミング対応
    - agent_id 非アクティブ時の 404 レスポンス
    - _Requirements: 17.1, 17.5, 17.7_

  - [x] 18.3 ChatService のプロパティテスト
    - **Property 25: Conversation history accumulation**
    - **Property 26: Context window limit**
    - **Property 27: Chat turn persistence**
    - **Validates: Requirements 17.3, 17.4, 17.6**

- [ ] 19. Checkpoint - バックエンド基盤確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Package Generator + Zip ダウンロード
  - [x] 20.1 PackageGenerator 実装
    - 📖 参照: `docs/agent_skills_specification.md` (Agent Skills 標準仕様リファレンス)
    - `backend/app/evolution/package_generator.py` に `PackageGenerator` クラスを実装
    - `generate(profile, agent_id, display_name)`: ProfileOutput → ファイルパス/コンテンツ辞書を返却
    - `_generate_readme()`: セットアップガイド + エージェント概要
    - `_generate_config_json()`: メタデータ + base_os パラメータ (4軸スコア, decision_style, do_not_list)
    - `_generate_system_prompt_md()`: PromptEngine 出力を Markdown 形式で保存 (Personality/Values/Guardrails/Tone セクション)
    - `_generate_skills()`: semantic_contexts からスキルキーワード検出 → reflection_wall.py, code_review_rules.py 等生成
    - `_generate_project_context()`: lexical_tags から技術スタック抽出 → tools/project_context.json
    - `_generate_additional_tools()`: lexical_tags から追加ツールファイル生成
    - `build_zip(profile, agent_id, display_name)`: 全ファイルを agent_pack_{agent_id}.zip に圧縮
    - persona/communication_tone 欠落時の [CUSTOMIZE] マーク付きデフォルト対応
    - 出力構造: README.md, config.json, system_prompt.md, skills/, tools/project_context.json
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9_

  - [x] 20.2 Zip ダウンロードエンドポイント実装
    - `backend/app/evolution/routes.py` にパッケージダウンロードエンドポイントを追加
    - `GET /api/v1/evolution/agents/{agent_id}/package`: Zip 生成 + ストリーミング返却
    - Content-Type: application/zip
    - Content-Disposition: attachment; filename="agent_pack_{agent_id}.zip"
    - agent_id 未登録/非アクティブ時の 404 レスポンス
    - 3秒以内のレスポンス開始を目標とする
    - config.json に agent_id を含める
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [x] 20.3 PackageGenerator のプロパティテスト
    - **Property 17: Package structure completeness**
    - **Property 18: System prompt file round-trip**
    - **Property 19: Technology tool generation**
    - **Property 20: Workflow tool schema generation**
    - **Property 21: Zip archive round-trip**
    - **Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 15.2**

- [ ] 21. Discussion Engine + ターン制議論
  - [ ] 21.1 DiscussionEngine 実装
    - `backend/app/evolution/discussion_engine.py` に `DiscussionEngine` クラスを実装
    - `init_db()`: discussions テーブル + discussion_id インデックス作成
    - `start_discussion()`: agent_ids (2〜6) バリデーション + discussion_id 生成
    - `run_turns()`: 各エージェントのプロンプト構築 → 順次推論 → ターン蓄積
    - `stream_discussion()`: SSE ストリーミングでターンを逐次配信
    - エージェントごとに固有のシステムプロンプトを構築 (base_os 反映)
    - 前ターンまでの全履歴をコンテキストに含める
    - max_turns_per_agent × agent_count の上限チェック
    - 各ターンに display_name, agent_id のメタデータ付与
    - 全ターンの SQLite 永続化
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8_

  - [ ] 21.2 Discussion REST API エンドポイント実装
    - `backend/app/evolution/routes.py` に議論エンドポイントを追加
    - `POST /api/v1/evolution/discussions`: 議論開始 (agent_ids + theme)
    - `GET /api/v1/evolution/discussions/{discussion_id}`: 議論履歴取得
    - SSE ストリーミング対応 (Accept: text/event-stream)
    - 無効 agent_id 時の 422 レスポンス
    - _Requirements: 18.1, 18.7, 18.8_

  - [ ] 21.3 DiscussionEngine のプロパティテスト
    - **Property 28: Discussion prompts reflect individual personalities**
    - **Property 29: Discussion turn accumulation**
    - **Property 30: Discussion max turns invariant**
    - **Property 31: Discussion turn attribution**
    - **Property 32: Discussion turn persistence**
    - **Validates: Requirements 18.2, 18.3, 18.4, 18.5, 18.6**

- [ ] 22. Compatibility Engine + レコメンド
  - [ ] 22.1 CompatibilityEngine 実装
    - `backend/app/evolution/compatibility.py` に `CompatibilityEngine` クラスを実装
    - `compute_similarity()`: 4軸ベクトルの Cosine Similarity 計算
    - `compute_complementarity()`: 各軸の差の絶対値の平均 (0.0〜1.0)
    - `compute_compatibility()`: 重み付け合成 (sim_weight=0.6, comp_weight=0.4) → 0〜100 スコア
    - `classify()`: similarity/complementarity から分類決定
    - `recommend()`: 全アクティブエージェントとの比較 → 2カテゴリ × 最大3件
    - per_axis_comparison, classification, recommended_interaction_mode を含むレポート生成
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 20.1, 20.2, 20.3, 20.4, 20.5_

  - [ ] 22.2 Compatibility + Recommendation REST API エンドポイント実装
    - `backend/app/evolution/routes.py` に相性・レコメンドエンドポイントを追加
    - `GET /api/v1/evolution/compatibility/{agent_id_1}/{agent_id_2}`: 相性レポート
    - `GET /api/v1/evolution/agents/{agent_id}/recommendations`: カテゴリ別レコメンド
    - agent_id 非アクティブ/不存在時の 404 レスポンス
    - アクティブエージェント 2未満時の空レコメンド + メッセージ
    - _Requirements: 19.5, 19.6, 20.4, 20.5_

  - [ ] 22.3 CompatibilityEngine のプロパティテスト
    - **Property 33: Compatibility score computation**
    - **Property 34: Recommendation ranking**
    - **Validates: Requirements 19.1, 19.2, 19.3, 19.4, 20.1, 20.2, 20.3**

- [ ] 23. 会話ログ永続化 + エクスポート
  - [ ] 23.1 Export サービス実装
    - `backend/app/evolution/export.py` に `ExportService` クラスを実装
    - `export_thread()`: thread_id 指定の1対1チャットログ取得 → JSON/Markdown 変換
    - `export_discussion()`: discussion_id 指定の議論ログ取得 → JSON/Markdown 変換
    - メタデータ (participants, timestamps, theme) 付与
    - 全ターンを時系列順に整序
    - format パラメータ (json / markdown) によるフォーマット切り替え
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5, 23.6_

  - [ ] 23.2 Export REST API エンドポイント実装
    - `backend/app/evolution/routes.py` にエクスポートエンドポイントを追加
    - `GET /api/v1/evolution/conversations/{thread_id}/export?format=json|markdown`
    - `GET /api/v1/evolution/discussions/{discussion_id}/export?format=json|markdown`
    - thread_id / discussion_id 不在時の 404 レスポンス
    - デフォルト format=json
    - _Requirements: 23.2, 23.3, 23.5, 23.6_

  - [ ] 23.3 Export のプロパティテスト
    - **Property 35: Export completeness and ordering**
    - **Property 36: Export format equivalence**
    - **Validates: Requirements 23.2, 23.3, 23.4, 23.5**

- [ ] 24. Checkpoint - バックエンド Phase 2/3 確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 25. Frontend: AgentList + ChatThread
  - [ ] 25.1 useAgents composable 実装
    - `frontend/src/components/evolution/composables/useAgents.ts` を作成
    - Agent CRUD API クライアント (fetch / axios)
    - リアクティブなエージェント一覧状態管理
    - `createAgent()`, `listAgents()`, `deleteAgent()` メソッド
    - _Requirements: 21.1_

  - [ ] 25.2 useChat composable 実装
    - `frontend/src/components/evolution/composables/useChat.ts` を作成
    - Chat API SSE クライアント (EventSource)
    - メッセージ送信、ストリーミング受信、スレッド切り替え
    - リアクティブな会話履歴・ロード状態管理
    - _Requirements: 21.4_

  - [ ] 25.3 AgentList.vue 実装
    - `frontend/src/components/evolution/AgentList.vue` を作成
    - アクティブエージェント一覧表示 (display_name, 選択状態)
    - エージェント選択イベント emit
    - _Requirements: 21.1, 21.2_

  - [ ] 25.4 ChatThread.vue + ChatInput.vue 実装
    - `frontend/src/components/evolution/ChatThread.vue` を作成
    - `frontend/src/components/evolution/ChatInput.vue` を作成
    - ユーザーメッセージ (右寄せ) / エージェント応答 (左寄せ + アバター) の描画
    - SSE ストリーミングによるリアルタイム描画
    - スレッド作成・切り替え機能
    - Vue 3 Composition API + TypeScript
    - _Requirements: 21.2, 21.3, 21.4, 21.5, 21.6_

- [ ] 26. Frontend: DiscussionTheater
  - [ ] 26.1 useDiscussion composable 実装
    - `frontend/src/components/evolution/composables/useDiscussion.ts` を作成
    - Discussion SSE クライアント (EventSource)
    - ターン受信、議論状態管理、プログレス計算
    - _Requirements: 22.3, 22.4_

  - [ ] 26.2 DiscussionSetup.vue 実装
    - `frontend/src/components/evolution/DiscussionSetup.vue` を作成
    - エージェント選択 UI (2〜6 人のバリデーション)
    - テーマ入力フィールド
    - 議論開始ボタン
    - _Requirements: 22.1, 22.2_

  - [ ] 26.3 DiscussionTheater.vue + TurnBubble.vue 実装
    - `frontend/src/components/evolution/DiscussionTheater.vue` を作成
    - `frontend/src/components/evolution/TurnBubble.vue` を作成
    - 各エージェントの発話バブル（アバター + 色分け + display_name）
    - 再生モード切り替え（リアルタイム / シミュレーション速度）
    - ターンカウンター + プログレスバー
    - Vue 3 Composition API + TypeScript
    - _Requirements: 22.3, 22.4, 22.5, 22.6_

- [ ] 27. Final checkpoint - Phase 2/3 全体統合確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- 既存の `app.models.profile.ProfileOutput` をそのまま入力モデルとして再利用する
- `EmbeddingClient` は既存 `llm_client.py` の OpenAI クライアント初期化パターンを踏襲する
- SQLite キャッシュ DB は既存 `sessions.db` とは別ファイル (`evolution_cache.db`) に保持する
- Agent Manager, Chat, Discussion, Compatibility のテーブルは同一 DB ファイル (`evolution.db`) に集約する
- Frontend コンポーネントは Vue 3 + TypeScript + Composition API で統一する
- SSE ストリーミングは `fastapi.responses.StreamingResponse` + `EventSource` (フロント) で実現する

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "2.2", "15.1"] },
    { "id": 2, "tasks": ["2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "5.1"] },
    { "id": 4, "tasks": ["5.2", "6.1"] },
    { "id": 5, "tasks": ["6.2", "7.1"] },
    { "id": 6, "tasks": ["7.2", "9.1"] },
    { "id": 7, "tasks": ["9.2", "10.1"] },
    { "id": 8, "tasks": ["10.2", "11.1"] },
    { "id": 9, "tasks": ["11.2", "13.1"] },
    { "id": 10, "tasks": ["14.1"] },
    { "id": 11, "tasks": ["14.2"] },
    { "id": 12, "tasks": ["14.3"] },
    { "id": 13, "tasks": ["17.1", "20.1"] },
    { "id": 14, "tasks": ["17.2", "17.3", "20.2"] },
    { "id": 15, "tasks": ["18.1", "20.3"] },
    { "id": 16, "tasks": ["18.2", "18.3"] },
    { "id": 17, "tasks": ["21.1", "22.1"] },
    { "id": 18, "tasks": ["21.2", "21.3", "22.2"] },
    { "id": 19, "tasks": ["22.3", "23.1"] },
    { "id": 20, "tasks": ["23.2", "23.3"] },
    { "id": 21, "tasks": ["25.1", "25.2", "26.1"] },
    { "id": 22, "tasks": ["25.3", "26.2"] },
    { "id": 23, "tasks": ["25.4", "26.3"] }
  ]
}
```
