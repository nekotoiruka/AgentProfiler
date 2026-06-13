# Requirements Document

## Introduction

Agent Evolution は、Agent Profiler が生成したプロファイル JSON を入力として受け取り、AIエージェントの動的パーソナライゼーションを実現するランタイムシステムである。3層コンテキスト・レイヤー（Base OS / Agent Skills / MCP）の実装、ハイブリッド記憶・検索（Lexical キーワード検索 + Semantic ベクトル検索）、マルチエージェント対話最適化（セマンティック・キャッシュ + ハイブリッド・ルーティング）、および動的プロンプト生成エンジンを提供する。PoC段階ではベクトル検索にインメモリ numpy/faiss を採用し、セマンティック・キャッシュには SQLite を使用する。

さらに本システムは以下の3フェーズで拡張機能を提供する。フェーズ1では ProfileOutput から VSCode Agent Skills 仕様準拠の構成資産（instruction.md / system_prompt.txt / カスタムツール）を自動ビルドし Zip ダウンロードを可能にする。フェーズ2では分身プロファイル管理（agent_id による複数分身の所有）、1対1チャット API、マルチエージェント・ターン制議論、4軸パラメータに基づく相性診断・レコメンドのバックエンド機能を実装する。フェーズ3では Vue.js フロントエンドとして分身セレクト・1対1チャット画面、マルチエージェント対話観覧シアター（トモコレ画面）、および会話ログの保存・エクスポート機能を構築する。

## Glossary

- **Evolution_System**: Agent Evolution システム全体を指す
- **Context_Layer_Manager**: 3層コンテキスト・レイヤーのロード・管理を担うコンポーネント
- **Prompt_Engine**: プロファイル JSON をパースし、動的にシステムプロンプトを組み立てるコンポーネント
- **Lexical_Retriever**: lexical_tags を用いた O(1) キーワード完全一致検索コンポーネント
- **Semantic_Retriever**: semantic_contexts をベクトル化し cosine similarity で類似行動特性を抽出するコンポーネント
- **Hybrid_Search_Engine**: Lexical_Retriever と Semantic_Retriever の結果を統合するコンポーネント
- **MCP_Server**: Model Context Protocol (stdio/SSE) に準拠した外部コンテキスト提供サーバー
- **Semantic_Cache**: SQLite ベースで類似発話の LLM 推論をバイパスするキャッシュ層
- **Routing_Engine**: 発話の複雑度に応じてローカル SLM とクラウド LLM を振り分けるルーティングコンポーネント
- **ProfileOutput**: Agent Profiler が生成するプロファイル JSON（profile_id, base_os, lexical_tags, semantic_contexts, context_layers を含む）
- **Base_OS**: Layer 1 常駐データ（axes, decision_style, do_not_list）
- **Layer_1**: Base OS レイヤー。システムプロンプトに常時ロードされる
- **Layer_2**: Agent Skills レイヤー。Function Calling 時に lexical_tags でスキルコンテキストを動的挿入する
- **Layer_3**: MCP レイヤー。MCP サーバー経由で semantic_contexts を動的フェッチする
- **Embedding_Model**: テキストをベクトル表現に変換するモデル（OpenAI text-embedding-ada-002 等）
- **SLM**: Small Language Model。ローカル実行の軽量推論モデル（ollama 等）
- **Cloud_LLM**: クラウド上のフルサイズ LLM（OpenAI GPT-4.1 等）
- **Agent_Package**: ProfileOutput から自動生成される VSCode 配置可能な構成ファイル一式の Zip アーカイブ
- **Agent_ID**: 分身プロファイルに払い出される一意の UUID v4 識別子
- **Thread**: 1対1チャットの会話スレッド。thread_id で識別される
- **Multi_Agent_Discussion**: 複数の分身がテーマに基づいてターン制で議論する対話セッション
- **Compatibility_Score**: 2つの分身間の4軸ベクトルに基づく類似度・相補性スコア
- **Discussion_Theater_UI**: マルチエージェント対話を視覚的に観覧するフロントエンド画面
- **Package_Generator**: ProfileOutput から Agent_Package を自動ビルドするコンポーネント
- **Agent_Manager**: 分身プロファイルの登録・管理を担う CRUD コンポーネント
- **Chat_API**: agent_id を指定した1対1テキスト対話を提供する API コンポーネント
- **Discussion_Engine**: 複数エージェント間のターン制自律議論を実行するコンポーネント
- **Compatibility_Engine**: 4軸パラメータに基づく相性診断・レコメンドを算出するコンポーネント
- **Instruction_MD**: Agent Skills 仕様で定義されるエージェント指示ファイル（instruction.md）
- **System_Prompt_TXT**: 生成済みシステムプロンプトを格納するテキストファイル（system_prompt.txt）
- **Custom_Tool**: ユーザーの技術スタック・こだわりから生成される Python スクリプトまたはスキーマ定義ファイル
- **VSCode_Agent_Directory**: VSCode がエージェントとして認識する配置先ディレクトリ（.vscode/agents/）
- **Conversation_Log**: チャットまたはマルチエージェント対話の全ターンを記録したデータ構造
- **Turn**: マルチエージェント議論における1エージェントの1発話単位
- **Cosine_Similarity**: 2つのベクトル間の角度に基づく類似度指標（0.0〜1.0）
- **Complementarity_Score**: 4軸パラメータの相補関係（対極同士の組み合わせ）から算出されるスコア
- **Recommendation_Engine**: 相性スコアに基づきマッチング候補を提示するコンポーネント

## Requirements

### Requirement 1: 動的プロンプト生成エンジン

**User Story:** As an agent system, I want the system prompt dynamically assembled from the profile JSON, so that the agent's personality and guardrails reflect the user's profiled characteristics.

#### Acceptance Criteria

1. WHEN a ProfileOutput is provided, THE Prompt_Engine SHALL parse the base_os section and generate a system prompt containing the axes values, decision_style label, and do_not_list items
2. THE Prompt_Engine SHALL include all do_not_list items as explicit behavioral guardrails in the generated system prompt, formatted as prohibited actions the agent must avoid
3. THE Prompt_Engine SHALL format axes values as descriptive personality trait sentences in the system prompt, mapping each normalized score (0.0–1.0) to a strength descriptor (0.0–0.29: strong second pole, 0.30–0.49: moderate second pole, 0.50: balanced, 0.51–0.70: moderate first pole, 0.71–1.0: strong first pole)
4. THE Prompt_Engine SHALL include the decision_style label as the agent's primary decision-making approach statement in the generated system prompt
5. IF the ProfileOutput is missing the base_os section or any required sub-field (axes, decision_style, do_not_list), THEN THE Prompt_Engine SHALL reject the input and return an error specifying which fields are missing
6. WHEN the Prompt_Engine generates a system prompt, THE Prompt_Engine SHALL produce the output as a single UTF-8 string not exceeding 4000 tokens in length
7. THE Prompt_Engine SHALL accept a Jinja2-compatible template parameter to customize the system prompt structure, falling back to a default template when no custom template is provided

### Requirement 2: Layer 1 — Base OS 常駐コンテキスト

**User Story:** As an agent runtime, I want the Base OS layer always loaded into the system prompt, so that the agent maintains consistent personality and guardrails across all interactions.

#### Acceptance Criteria

1. WHEN an agent session starts, THE Context_Layer_Manager SHALL load the Base_OS data (axes, decision_style, do_not_list) from the ProfileOutput and pass it to the Prompt_Engine for system prompt generation
2. WHILE an agent session is active, THE Context_Layer_Manager SHALL retain the Base_OS data in memory without re-fetching from the data source
3. THE Context_Layer_Manager SHALL validate that the ProfileOutput contains a context_layers mapping with base_os assigned to layer value 1 before loading
4. IF the ProfileOutput context_layers assigns base_os to a layer value other than 1, THEN THE Context_Layer_Manager SHALL reject the profile and return a configuration error
5. WHEN multiple agent sessions reference the same profile_id, THE Context_Layer_Manager SHALL share the cached Base_OS data across sessions to reduce memory allocation

### Requirement 3: Layer 2 — Agent Skills 動的挿入

**User Story:** As an agent runtime, I want skill-relevant context injected on demand during function calling, so that the agent receives task-specific context only when needed.

#### Acceptance Criteria

1. WHEN a Function Calling invocation occurs, THE Context_Layer_Manager SHALL query the Lexical_Retriever with the function name and parameters to find matching lexical_tags
2. WHEN the Lexical_Retriever returns matching tags, THE Context_Layer_Manager SHALL inject the corresponding skill context into the LLM conversation context as additional system-level content
3. THE Lexical_Retriever SHALL perform exact string matching against the lexical_tags array, returning all tags that match any token in the query input
4. THE Lexical_Retriever SHALL complete tag lookup within 10 milliseconds for a lexical_tags array of up to 500 entries
5. IF no lexical_tags match the Function Calling context, THEN THE Context_Layer_Manager SHALL proceed without injecting additional skill context
6. THE Context_Layer_Manager SHALL validate that the ProfileOutput contains a context_layers mapping with lexical_tags assigned to layer value 2 before performing Layer 2 operations

### Requirement 4: Layer 3 — MCP 外部動的フェッチ

**User Story:** As an agent runtime, I want semantic contexts fetched dynamically via MCP servers, so that the agent accesses rich behavioral context through standardized external protocols.

#### Acceptance Criteria

1. WHEN the Context_Layer_Manager requires semantic context for a query, THE MCP_Server SHALL accept requests via stdio or SSE transport protocol as specified in the server configuration
2. THE MCP_Server SHALL return semantic_contexts data matching the requested context domain (problem_solving, communication_style, analog_habits, vacation_planning, etc.) as UTF-8 text responses
3. THE Context_Layer_Manager SHALL connect to the MCP_Server using the transport protocol (stdio or SSE) specified in the runtime configuration
4. IF the MCP_Server connection fails or times out after 5 seconds, THEN THE Context_Layer_Manager SHALL fall back to local in-memory semantic_contexts data from the ProfileOutput
5. IF the MCP_Server returns an error response, THEN THE Context_Layer_Manager SHALL log the error and fall back to local in-memory semantic_contexts data
6. THE Context_Layer_Manager SHALL validate that the ProfileOutput contains a context_layers mapping with semantic_contexts assigned to layer value 3 before initiating MCP fetch operations
7. THE MCP_Server SHALL implement the Model Context Protocol specification for tool registration and context provision, exposing semantic_contexts as queryable resources

### Requirement 5: Lexical キーワード検索

**User Story:** As an agent runtime, I want O(1) exact-match keyword lookup against lexical tags, so that skill context is retrieved with minimal latency.

#### Acceptance Criteria

1. THE Lexical_Retriever SHALL build an in-memory hash index from the lexical_tags array at profile load time, enabling O(1) average-case lookup per tag
2. WHEN a query string is provided, THE Lexical_Retriever SHALL tokenize the query into individual terms and perform exact case-insensitive matching against the indexed tags
3. THE Lexical_Retriever SHALL return all matching tags as a list ordered by their original position in the lexical_tags array
4. WHEN a ProfileOutput is loaded, THE Lexical_Retriever SHALL complete index construction within 50 milliseconds for up to 500 tags
5. IF the query contains no tokens matching any indexed tag, THEN THE Lexical_Retriever SHALL return an empty list
6. THE Lexical_Retriever SHALL support queries containing Japanese text by tokenizing on whitespace and common delimiters (comma, semicolon, slash)

### Requirement 6: Semantic ベクトル検索

**User Story:** As an agent runtime, I want cosine-similarity vector search over semantic contexts, so that the agent retrieves behaviorally relevant context even when exact keywords do not match.

#### Acceptance Criteria

1. WHEN a ProfileOutput is loaded, THE Semantic_Retriever SHALL generate embedding vectors for each semantic_contexts entry using the configured Embedding_Model
2. THE Semantic_Retriever SHALL store embedding vectors in an in-memory index using numpy or faiss for PoC-stage cosine similarity search
3. WHEN a query is provided, THE Semantic_Retriever SHALL generate an embedding vector for the query and return the top-k (configurable, default k=3) most similar semantic_contexts entries ranked by cosine similarity score
4. THE Semantic_Retriever SHALL return results with cosine similarity scores, filtering out entries with a score below a configurable threshold (default 0.7)
5. THE Semantic_Retriever SHALL complete a single query against up to 50 semantic_contexts entries within 100 milliseconds excluding embedding generation time
6. IF the Embedding_Model API is unavailable, THEN THE Semantic_Retriever SHALL log the error and return an empty result set without raising an exception
7. THE Semantic_Retriever SHALL cache generated embeddings per profile_id to avoid redundant API calls when the same profile is queried multiple times

### Requirement 7: ハイブリッド検索統合

**User Story:** As an agent runtime, I want combined results from keyword and vector search, so that I get both precise tag matches and semantically relevant context in a single query.

#### Acceptance Criteria

1. WHEN a hybrid search query is issued, THE Hybrid_Search_Engine SHALL invoke both the Lexical_Retriever and Semantic_Retriever in parallel and merge their results
2. THE Hybrid_Search_Engine SHALL return a unified result set containing matched lexical_tags and ranked semantic_contexts entries, each annotated with source type ("lexical" or "semantic") and relevance score
3. THE Hybrid_Search_Engine SHALL deduplicate results where a lexical tag matches a key term in a semantic_contexts entry, preferring the semantic result with its full contextual description
4. THE Hybrid_Search_Engine SHALL accept a weighting parameter (default 0.5) that controls the relative ranking influence between lexical matches (score = 1.0 for exact match) and semantic similarity scores
5. IF both retrievers return empty results, THEN THE Hybrid_Search_Engine SHALL return an empty result set without error
6. THE Hybrid_Search_Engine SHALL complete the merged retrieval within 200 milliseconds excluding embedding generation time for profiles containing up to 500 lexical_tags and 50 semantic_contexts entries

### Requirement 8: セマンティック・キャッシュ

**User Story:** As a multi-agent system, I want similar utterances cached to bypass redundant LLM inference, so that repeated or near-duplicate queries are answered with reduced latency and cost.

#### Acceptance Criteria

1. WHEN a user utterance is received, THE Semantic_Cache SHALL generate an embedding vector for the utterance and search for cached entries with cosine similarity above a configurable threshold (default 0.92)
2. WHEN a cache hit occurs (similarity above threshold), THE Semantic_Cache SHALL return the cached LLM response without invoking the Cloud_LLM or SLM
3. WHEN a cache miss occurs, THE Semantic_Cache SHALL store the utterance embedding, the original utterance text, and the generated LLM response in the SQLite cache database after the LLM responds
4. THE Semantic_Cache SHALL store cache entries in a SQLite database with columns for entry_id, embedding_blob, utterance_text, response_text, profile_id, created_at, and hit_count
5. THE Semantic_Cache SHALL evict cache entries that have not been accessed (hit_count not incremented) for more than 7 days using a background cleanup process
6. THE Semantic_Cache SHALL scope cached entries by profile_id, ensuring responses generated for one profile are not returned for queries associated with a different profile
7. IF the SQLite database is unavailable or corrupted, THEN THE Semantic_Cache SHALL bypass caching and route all queries directly to the Routing_Engine without error

### Requirement 9: ハイブリッド・ルーティング

**User Story:** As a multi-agent system, I want lightweight queries routed to a local SLM and complex queries to the cloud LLM, so that system cost and latency are optimized per query complexity.

#### Acceptance Criteria

1. WHEN a user utterance is received and no cache hit occurs, THE Routing_Engine SHALL classify the utterance complexity as "light" or "deep" based on configurable classification criteria
2. WHEN the utterance is classified as "light", THE Routing_Engine SHALL route the request to the configured local SLM endpoint (ollama-compatible API)
3. WHEN the utterance is classified as "deep", THE Routing_Engine SHALL route the request to the configured Cloud_LLM endpoint (OpenAI / Azure OpenAI API)
4. THE Routing_Engine SHALL classify utterances using a scoring function that considers token count (threshold configurable, default 50 tokens), presence of domain-specific lexical_tags (detected by Lexical_Retriever), and explicit routing hints in the utterance metadata
5. THE Routing_Engine SHALL complete classification within 5 milliseconds per utterance
6. IF the local SLM endpoint is unavailable, THEN THE Routing_Engine SHALL fall back to the Cloud_LLM endpoint and log a warning indicating the fallback
7. IF the Cloud_LLM endpoint is unavailable, THEN THE Routing_Engine SHALL return an error response indicating that no LLM backend is available
8. THE Routing_Engine SHALL accept runtime configuration for both endpoints (base_url, model_name, api_key for Cloud_LLM; base_url, model_name for SLM) via environment variables or configuration file

### Requirement 10: プロファイル入力バリデーション

**User Story:** As an agent system, I want strict validation of incoming profile JSON, so that malformed or incomplete profiles are rejected before processing.

#### Acceptance Criteria

1. WHEN a ProfileOutput JSON is submitted to the Evolution_System, THE Evolution_System SHALL validate the JSON against the ProfileOutput Pydantic schema (profile_id format, base_os structure, lexical_tags constraints, semantic_contexts structure, context_layers mapping)
2. IF the profile_id does not match the pattern "prof_" followed by exactly 6 digits, THEN THE Evolution_System SHALL reject the input with a validation error specifying the invalid profile_id format
3. IF base_os.axes contains any value outside the 0.0 to 1.0 range, THEN THE Evolution_System SHALL reject the input with a validation error specifying which axis value is out of range
4. IF lexical_tags contains fewer than 5 entries or more than 500 entries, THEN THE Evolution_System SHALL reject the input with a validation error specifying the count violation
5. IF semantic_contexts contains any value shorter than 10 characters or longer than 2000 characters, THEN THE Evolution_System SHALL reject the input with a validation error specifying which context domain violates the length constraint
6. IF do_not_list contains fewer than 1 or more than 4 entries, THEN THE Evolution_System SHALL reject the input with a validation error specifying the count violation
7. WHEN validation passes, THE Evolution_System SHALL return a success acknowledgment containing the profile_id and a timestamp of acceptance

### Requirement 11: REST API エンドポイント

**User Story:** As a client application, I want well-defined REST API endpoints for the Evolution system, so that I can integrate profile loading, search, and inference functionalities.

#### Acceptance Criteria

1. THE Evolution_System SHALL expose a POST endpoint to load a ProfileOutput JSON and initialize all three context layers for a given profile_id
2. THE Evolution_System SHALL expose a POST endpoint to execute a hybrid search query, accepting a query string and returning combined lexical and semantic results with relevance scores
3. THE Evolution_System SHALL expose a POST endpoint to submit a user utterance for inference, which executes the full pipeline (cache check → routing → LLM inference → cache store → response)
4. THE Evolution_System SHALL expose a GET endpoint to retrieve the current system prompt generated for a given profile_id
5. THE Evolution_System SHALL expose a GET endpoint to retrieve cache statistics (total entries, hit rate, average similarity score) for a given profile_id
6. THE Evolution_System SHALL expose a DELETE endpoint to invalidate all cached entries for a given profile_id
7. IF an API request references a profile_id that has not been loaded, THEN THE Evolution_System SHALL return an HTTP 404 response with an error message indicating the profile is not loaded
8. IF an API request contains malformed JSON or missing required fields, THEN THE Evolution_System SHALL return an HTTP 422 response with field-level validation errors
9. THE Evolution_System SHALL return all API responses in JSON format with Content-Type application/json
10. THE Evolution_System SHALL prefix all endpoints with /api/v1/evolution/ as the base path

### Requirement 12: MCP サーバー実装

**User Story:** As an agent orchestration platform, I want a standards-compliant MCP server, so that external agents can access semantic contexts through the Model Context Protocol.

#### Acceptance Criteria

1. THE MCP_Server SHALL implement the Model Context Protocol specification supporting both stdio and SSE transport protocols
2. THE MCP_Server SHALL register semantic_contexts domains as queryable tools, exposing each context domain (problem_solving, communication_style, analog_habits, etc.) as an individual tool
3. WHEN a tool invocation request is received, THE MCP_Server SHALL return the corresponding semantic_contexts entry for the requested domain and profile_id
4. THE MCP_Server SHALL accept a profile_id parameter in tool invocation requests to scope context retrieval to the specified profile
5. IF a requested context domain does not exist for the given profile_id, THEN THE MCP_Server SHALL return an error response indicating the domain is not available
6. THE MCP_Server SHALL support concurrent connections from multiple client agents without data isolation violations between profile_ids
7. THE MCP_Server SHALL start and accept connections within 3 seconds of process initialization
8. THE MCP_Server SHALL log all tool invocations with timestamp, profile_id, requested domain, and response status for observability

### Requirement 13: 設定管理

**User Story:** As a system administrator, I want centralized configuration for all Evolution system components, so that I can tune parameters without code changes.

#### Acceptance Criteria

1. THE Evolution_System SHALL load configuration from environment variables with an optional .env file fallback, supporting all component-specific settings
2. THE Evolution_System SHALL support the following configuration parameters: EMBEDDING_MODEL (default "text-embedding-ada-002"), SEMANTIC_CACHE_THRESHOLD (default 0.92), SEMANTIC_SEARCH_TOP_K (default 3), SEMANTIC_SEARCH_THRESHOLD (default 0.7), ROUTING_TOKEN_THRESHOLD (default 50), HYBRID_SEARCH_WEIGHT (default 0.5), CACHE_EVICTION_DAYS (default 7)
3. THE Evolution_System SHALL support configuration for LLM endpoints: CLOUD_LLM_BASE_URL, CLOUD_LLM_MODEL, CLOUD_LLM_API_KEY, SLM_BASE_URL, SLM_MODEL
4. THE Evolution_System SHALL support MCP server configuration: MCP_TRANSPORT (default "stdio"), MCP_SSE_PORT (default 8081), MCP_SSE_HOST (default "localhost")
5. IF a required configuration parameter (CLOUD_LLM_API_KEY) is missing, THEN THE Evolution_System SHALL fail to start and log an error message specifying the missing parameter
6. WHEN a configuration parameter has an invalid value (non-numeric for numeric parameters, out-of-range for bounded parameters), THE Evolution_System SHALL fail to start and log a validation error specifying the parameter name and constraint

### Requirement 14: エージェント構成資産の自動ビルド

**User Story:** As a developer, I want the system to automatically generate Agent Skills-compliant configuration files from my profile, so that I can instantly deploy a personalized agent in my IDE or any agent runtime.

#### Acceptance Criteria

1. WHEN a valid ProfileOutput and agent_id are provided, THE Package_Generator SHALL produce the following directory structure: README.md, config.json, system_prompt.md, skills/ subdirectory, and tools/ subdirectory
2. THE Package_Generator SHALL generate a README.md file containing the agent's setup guide, startup instructions, and a summary of the agent's personality and skills
3. THE Package_Generator SHALL generate a config.json file containing agent metadata (agent_id, profile_id, display_name, version), base_os parameters (4-axis normalized scores), decision_style, do_not_list, and references to skills and tools files
4. THE Package_Generator SHALL generate a system_prompt.md file by invoking the Prompt_Engine with the ProfileOutput and formatting the output as a Markdown document with sections for personality traits, values, guardrails (do_not_list), and communication tone
5. WHEN the ProfileOutput semantic_contexts contain behavioral preferences (morning pages, reflection habits, etc.), THE Package_Generator SHALL generate skill files in the skills/ subdirectory as Python scripts (e.g., reflection_wall.py) implementing agent behaviors aligned with those preferences
6. WHEN the ProfileOutput semantic_contexts contain work methodology or aesthetic preferences, THE Package_Generator SHALL generate skill files (e.g., code_review_rules.py) encoding the user's standards as executable review rules
7. THE Package_Generator SHALL generate a tools/project_context.json file containing the user's technology stack identifiers extracted from lexical_tags (Vue, FastAPI, Python, TypeScript, Docker, etc.) as a static context file usable by the agent runtime
8. WHEN additional technology-specific tools are detectable from lexical_tags, THE Package_Generator SHALL generate corresponding tool files in the tools/ subdirectory with appropriate function signatures or schema definitions
9. IF the ProfileOutput lacks persona or communication_tone sections, THEN THE Package_Generator SHALL use default placeholder values and annotate the system_prompt.md with sections marked "[CUSTOMIZE]" for manual editing

### Requirement 15: Zip 圧縮ダウンロードエンドポイント

**User Story:** As a developer, I want to download the generated agent configuration as a Zip archive named with the agent_id, so that I can extract and deploy it to any agent runtime immediately.

#### Acceptance Criteria

1. THE Evolution_System SHALL expose a GET endpoint at /api/v1/evolution/agents/{agent_id}/package to generate and return a Zip archive containing the Agent_Package
2. WHEN the download endpoint is invoked, THE Evolution_System SHALL invoke the Package_Generator with the agent's associated ProfileOutput, compress all generated files into a single Zip archive, and return it with Content-Type application/zip
3. THE Evolution_System SHALL set the Content-Disposition header to attachment with filename format "agent_pack_{agent_id}.zip"
4. THE Evolution_System SHALL produce a Zip archive with the following top-level structure when extracted: README.md, config.json, system_prompt.md, skills/ (containing .py skill files), and tools/ (containing project_context.json and additional tool files)
5. IF the agent_id does not exist or is inactive, THEN THE Evolution_System SHALL return an HTTP 404 response with an error message indicating the agent is not found
6. THE Evolution_System SHALL complete Zip generation and begin streaming the response within 3 seconds for profiles containing up to 500 lexical_tags and 50 semantic_contexts entries
7. THE Evolution_System SHALL include the agent_id in the config.json within the Zip, enabling the receiving agent runtime to identify which persona the package belongs to

### Requirement 16: 分身プロファイル管理

**User Story:** As a user, I want to create and manage multiple agent personas (分身) from my profiles, so that I can have different specialized agents for different contexts.

#### Acceptance Criteria

1. WHEN a user requests creation of a new agent persona, THE Agent_Manager SHALL generate a unique Agent_ID (UUID v4) and associate it with the specified profile_id in the database
2. THE Agent_Manager SHALL store agent persona records in SQLite with columns: agent_id (UUID v4 primary key), profile_id (foreign key reference), display_name, created_at, and is_active flag
3. THE Agent_Manager SHALL allow a single profile_id to be associated with multiple Agent_IDs, enabling one user to own multiple distinct agent personas
4. THE Agent_Manager SHALL expose CRUD operations (create, read, update display_name, soft-delete via is_active flag) for agent persona records
5. WHEN an agent persona is created, THE Agent_Manager SHALL load the associated ProfileOutput and initialize the Base_OS and context layers for the new Agent_ID
6. IF the specified profile_id does not exist in the system, THEN THE Agent_Manager SHALL reject the creation request with a validation error indicating the profile is not found
7. THE Agent_Manager SHALL expose a GET endpoint to list all active agent personas for a given profile_id, returning agent_id, display_name, and created_at

### Requirement 17: 1対1チャット API

**User Story:** As a user, I want to have a text-based conversation with a specific agent persona, so that I can interact with my personalized AI assistant.

#### Acceptance Criteria

1. THE Chat_API SHALL expose a POST endpoint at /api/v1/evolution/agents/{agent_id}/chat accepting a text message and returning the agent response
2. WHEN a chat message is received, THE Chat_API SHALL load the Base_OS and Agent Skills context for the specified agent_id, construct the system prompt, and route the message through the inference pipeline (cache → routing → LLM)
3. THE Chat_API SHALL maintain conversation history per Thread, identified by a thread_id returned on the first message of a conversation
4. WHEN a thread_id is provided in the request, THE Chat_API SHALL include prior conversation turns (up to a configurable context window, default 20 turns) in the LLM request
5. IF the specified agent_id does not exist or is inactive, THEN THE Chat_API SHALL return an HTTP 404 response indicating the agent is not available
6. THE Chat_API SHALL store each conversation turn (user message and agent response) in the SQLite database with timestamp, agent_id, and thread_id
7. THE Chat_API SHALL support streaming responses via Server-Sent Events when the request includes an Accept header of text/event-stream

### Requirement 18: マルチエージェント・ターン制議論

**User Story:** As a user, I want multiple agent personas to autonomously discuss a topic in turns, so that I can observe diverse perspectives generated from different personality profiles.

#### Acceptance Criteria

1. THE Discussion_Engine SHALL expose a POST endpoint at /api/v1/evolution/discussions accepting a list of agent_ids (minimum 2, maximum 6), a discussion theme, and an optional max_turns parameter (integer, default 10, range 1–50)
2. WHEN a discussion is initiated, THE Discussion_Engine SHALL load the Base_OS and context layers for each specified agent_id and construct individual system prompts reflecting each agent's personality
3. THE Discussion_Engine SHALL execute the discussion in sequential turns, where each agent generates a response considering the theme and all prior turns in the conversation
4. THE Discussion_Engine SHALL terminate the discussion when the total turn count reaches max_turns × number of agents, or when the request-specified max_turns limit is reached, whichever comes first
5. WHEN an agent generates a turn, THE Discussion_Engine SHALL include the agent's display_name and agent_id in the turn metadata for attribution
6. THE Discussion_Engine SHALL store all discussion turns in the SQLite database with discussion_id, turn_number, agent_id, message content, and timestamp
7. IF any specified agent_id does not exist or is inactive, THEN THE Discussion_Engine SHALL return an HTTP 422 response listing the invalid agent_ids
8. THE Discussion_Engine SHALL support real-time turn delivery via Server-Sent Events, emitting each turn as it is generated

### Requirement 19: 相性診断アルゴリズム

**User Story:** As a user, I want to know the compatibility between two agent personas including partner recommendations, so that I can understand relationships and set up productive conversations.

#### Acceptance Criteria

1. WHEN two agent_ids are provided, THE Compatibility_Engine SHALL calculate a Compatibility_Score by computing Cosine_Similarity between the two agents' 4-axis parameter vectors (base_os.axes)
2. THE Compatibility_Engine SHALL calculate a Complementarity_Score by measuring the degree to which the two agents' axes values are inversely correlated (complementary strengths)
3. THE Compatibility_Engine SHALL produce a final compatibility percentage (0–100) by combining Cosine_Similarity weight (default 0.6) and Complementarity_Score weight (default 0.4)
4. THE Compatibility_Engine SHALL return a compatibility report containing: overall score, per-axis comparison, relationship_type (a human-readable label describing the dynamic, e.g., "最高のブレイン" or "建設的対立パートナー"), similarity classification (highly similar, moderately similar, complementary, contrasting), reason (1–2 sentence explanation of why the pairing works), and recommended interaction mode
5. IF either specified agent_id does not exist or is inactive, THEN THE Compatibility_Engine SHALL return an HTTP 404 response indicating the agent is not available
6. THE Compatibility_Engine SHALL expose a GET endpoint at /api/v1/evolution/agents/{agent_id}/compatibility that returns both the compatibility report for a specified target_agent_id (query parameter) AND the top recommendations from the Recommendation_Engine in a single response

### Requirement 20: レコメンドエンジン

**User Story:** As a user, I want recommendations for the best discussion partners among my agent personas, so that I can set up the most interesting or productive multi-agent conversations.

#### Acceptance Criteria

1. WHEN a source agent_id is provided, THE Recommendation_Engine SHALL compute compatibility scores against all other active agents owned by the same user and return ranked recommendations
2. THE Recommendation_Engine SHALL provide two recommendation categories: "most_heated_debate" (agents with highest Complementarity_Score, likely to disagree constructively) and "business_partner" (agents with highest Cosine_Similarity, sharing values and approach)
3. THE Recommendation_Engine SHALL return the top 3 recommendations per category, each containing the recommended agent_id, display_name, compatibility_score, relationship_type label, and reason explaining why the match is recommended
4. THE Recommendation_Engine SHALL be callable both standalone (GET /api/v1/evolution/agents/{agent_id}/recommendations) and as part of the compatibility endpoint response
5. IF fewer than 2 active agents exist for the user, THEN THE Recommendation_Engine SHALL return an empty recommendation set with a message indicating insufficient agents for matching

### Requirement 21: フロントエンド — 分身セレクト・1対1チャット画面

**User Story:** As a user, I want a visual interface to select an agent persona and chat with it in a threaded conversation, so that I can interact with my AI agents intuitively.

#### Acceptance Criteria

1. THE Discussion_Theater_UI SHALL display a list of all active agent personas with their display_name, showing selection state for the current chat target
2. WHEN a user selects an agent persona from the list, THE Discussion_Theater_UI SHALL open a chat thread view showing the conversation history for the selected agent
3. THE Discussion_Theater_UI SHALL render chat messages in a thread format with distinct visual styling for user messages (right-aligned) and agent responses (left-aligned with agent avatar)
4. WHEN the user submits a message, THE Discussion_Theater_UI SHALL send the message to the Chat_API and display the agent response in real-time using Server-Sent Events streaming
5. THE Discussion_Theater_UI SHALL support creating new conversation threads and switching between existing threads for the same agent
6. THE Discussion_Theater_UI SHALL be implemented as a Vue 3 component using TypeScript and Composition API, integrated into the existing frontend/ application structure

### Requirement 22: フロントエンド — マルチエージェント対話観覧シアター

**User Story:** As a user, I want to watch multiple agent personas discuss a topic in real-time with visual distinction between speakers, so that I can observe the emergent dynamics of different personalities interacting.

#### Acceptance Criteria

1. THE Discussion_Theater_UI SHALL provide an agent selection interface allowing the user to choose 2 to 6 agents for a multi-agent discussion
2. THE Discussion_Theater_UI SHALL provide a theme input field where the user enters the discussion topic before initiating the conversation
3. WHEN the discussion starts, THE Discussion_Theater_UI SHALL render each agent's turn as a speech bubble with the agent's avatar icon and display_name, visually distinguishing each participant by color
4. THE Discussion_Theater_UI SHALL support two playback modes: real-time (turns displayed as they are generated via SSE) and simulation speed (configurable delay between turns for review)
5. THE Discussion_Theater_UI SHALL display a turn counter and progress indicator showing the current turn number relative to the configured maximum
6. THE Discussion_Theater_UI SHALL be implemented as a Vue 3 component using TypeScript and Composition API, integrated into the existing frontend/ application structure

### Requirement 23: 会話ログの保存・エクスポート

**User Story:** As a user, I want to save and export conversation logs from both 1-on-1 chats and multi-agent discussions, so that I can review, share, or archive the interactions.

#### Acceptance Criteria

1. THE Evolution_System SHALL automatically persist all conversation turns (1-on-1 chat and multi-agent discussion) to the SQLite database with full metadata (timestamps, agent_ids, thread_id or discussion_id)
2. THE Evolution_System SHALL expose a GET endpoint at /api/v1/evolution/conversations/{thread_id}/export to download a 1-on-1 chat log as a structured JSON or Markdown file
3. THE Evolution_System SHALL expose a GET endpoint at /api/v1/evolution/discussions/{discussion_id}/export to download a multi-agent discussion log as a structured JSON or Markdown file
4. WHEN an export is requested, THE Evolution_System SHALL include metadata (participants, timestamps, theme if applicable) and all conversation turns ordered chronologically in the exported file
5. THE Evolution_System SHALL support export format selection via a query parameter (format=json or format=markdown), defaulting to JSON
6. IF the specified thread_id or discussion_id does not exist, THEN THE Evolution_System SHALL return an HTTP 404 response indicating the conversation is not found

### Requirement 24: プロファイル永続化と自動復元

**User Story:** As a system operator, I want profiles automatically restored on server restart, so that agents are immediately usable without manual re-loading.

#### Acceptance Criteria

1. WHEN a ProfileOutput is loaded via POST /profiles, THE Evolution_System SHALL persist the complete ProfileOutput JSON in the SQLite database (profiles table)
2. WHEN the Evolution_System starts up, THE Evolution_System SHALL restore all persisted profiles from the database and load them into ContextLayerManager automatically
3. IF a profile fails to restore on startup, THE Evolution_System SHALL log a warning and continue restoring other profiles
4. THE Evolution_System SHALL use UPSERT semantics when saving profiles (re-loading the same profile_id overwrites the previous version)

### Requirement 25: 質問フロー → Evolution 自動連携

**User Story:** As a user who completed the profiling questionnaire, I want my profile automatically available in the Evolution system, so that I can immediately create agents and start chatting without manual steps.

#### Acceptance Criteria

1. WHEN the profiling questionnaire is completed and a ProfileOutput is generated, THE system SHALL automatically load the profile into the Evolution_System
2. THE results dashboard (ResultsDashboardView) SHALL provide a "分身を作成" button that navigates to /evolution with the profile_id pre-filled
3. IF the Evolution_System is not initialized (API key missing), THE "分身を作成" button SHALL be hidden or disabled with an explanation

### Requirement 26: フロントエンドページ統合

**User Story:** As a user, I want a dedicated Evolution page accessible at /evolution, so that I can manage agents, chat, and watch discussions from the browser.

#### Acceptance Criteria

1. THE frontend SHALL provide an /evolution route accessible at http://localhost:5173/evolution
2. THE Evolution page SHALL contain three tabs: Setup (設定), Chat (チャット), Discussion (ディスカッション)
3. WHEN the page loads, THE Evolution page SHALL automatically list all active agents for the loaded profile without requiring manual profile load
