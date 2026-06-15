# Requirements Document

## Introduction

Agent Decision Engine は、既存の Agent Profiler / Agent Evolution システムに「意思決定エンジン」機能を追加する拡張モジュールである。フィードバックレポートから判明した不足観点（意思決定の重み付け・トレードオフ、コンテキスト適応、非合理的な人間らしさ、思考プロセス、フィードバックループ）を網羅的にカバーする。新規質問カテゴリ（35〜40問）を通じてユーザーの判断アルゴリズム・失敗パターン・場面適応・推論フローを抽出し、ProfileOutput JSON を拡張して decision_model / failure_patterns / context_adaptation / reasoning_flow セクションを追加する。拡張データは Agent Skills Package（Zip）と Chat / Discussion Engine（リアルタイム）の双方で活用される。さらに、エージェント回答に対するユーザーフィードバックループ（「私ならこう言わない」評価）により、プロファイルの継続的な微調整を実現する。

## Glossary

- **System**: Agent Decision Engine システム全体を指す
- **Decision_Engine**: 意思決定モデル・失敗パターン・コンテキスト適応・推論フローを統合管理するバックエンドモジュール
- **Survey_UI**: Vue.js で構築されたステップベース質問フロントエンド（既存拡張）
- **Profile_Generator**: ProfileOutput JSON を生成するコンポーネント（既存拡張）
- **Prompt_Engine**: ProfileOutput からシステムプロンプトを動的生成する Jinja2 テンプレートエンジン（既存拡張）
- **Package_Generator**: Agent Skills Package (Zip) を生成するコンポーネント（既存拡張）
- **Chat_Service**: 1対1チャット API + SSE ストリーミングサービス（既存拡張）
- **Discussion_Engine**: マルチエージェント・ターン制議論エンジン（既存拡張）
- **Feedback_Service**: ユーザーがエージェント回答を評価・修正し、プロファイル重みを更新するサービス（新規）
- **Decision_Model**: ユーザーの優先順位アルゴリズム・エスカレーションルール・自動承認スコープ・トレードオフ傾向を格納する構造体
- **Failure_Patterns**: 劣化トリガー・先延ばしパターン・過信条件・再発ミスを格納する構造体
- **Context_Adaptation**: 場面別モード（tone, detail, focus）とモード切替トリガーを格納する構造体
- **Reasoning_Flow**: デフォルト思考ステップ・検証方法・学習スタイルを格納する構造体
- **Feedback_Record**: エージェント回答に対するユーザー評価（賛同/修正）と修正内容を記録するデータ構造
- **Priority_Weight**: 意思決定における各優先項目の相対的重み（0.0〜1.0）
- **Tradeoff_Tendency**: 二律背反の判断における傾向スコア（0.0=前者寄り、1.0=後者寄り）
- **Adaptation_Mode**: コンテキストに応じたエージェントの振る舞いモード（executive_report, team_direction, emergency, deep_review 等）
- **Mapping_Dictionary**: 質問ID・選択肢ごとのスコアリングロジックを管理する独立ファイル（既存拡張）
- **Three_Layer_Answer**: 回答データの3層構造化形式（Raw: 元回答, Normalized: 正規化された要約値, Policy: エージェントが従うルール文）
- **Answer_Metadata**: 回答に付随するメタ情報（恒常性 permanence、確信度 confidence、例外条件 exceptions、上位ルール性 is_core_rule、迷い度 ambiguity）
- **Policy_Rule**: 回答から導出されたエージェント用一文ルール（when_条件: 行動指示 形式）
- **Normalization_Tag**: 自由記述テキストを分類する4種タグ（value_tag: 価値観, behavior_tag: 行動, prohibition_tag: 禁止, condition_tag: 条件）
- **Rule_Hierarchy**: プロファイル全体のルール優先順位体系（core_invariants > context_rules > exceptions > preferences）

## Requirements

### Requirement 1: Decision Model 質問カテゴリ（判断エンジン）

**User Story:** As a user, I want to answer scenario-based questions about my decision-making priorities, so that my AI agent can replicate my judgment algorithm.

#### Acceptance Criteria

1. THE System SHALL define a "decision_model" question Category containing exactly 10 questions in the questions.yaml file, each with a unique ID prefixed "dm_" (dm_001 through dm_010), category_id "decision_model", exactly 4 predefined choices (id: "a" through "d"), and a source_reference field
2. WHEN a decision_model question is presented, THE Survey_UI SHALL display a business scenario with exactly 4 predefined choices and one "Other" free-text option as a mutually exclusive single-selection group, where selecting any option deselects the previously selected option
3. THE System SHALL design each decision_model question as a prioritization scenario where each choice represents a distinct decision-making principle (root_cause_first, customer_first, speed_first, long_term_bias, consensus_driven, data_driven 等), with each choice mapped to one or more priority labels in the Mapping_Dictionary
4. WHEN a predefined choice is submitted for a decision_model question, THE Decision_Engine SHALL look up the Mapping_Dictionary entry for that question ID and choice ID combination and increment the corresponding Priority_Weight accumulators by the integer weight values (range: 1 to 10) defined in the entry
5. IF a submitted decision_model question ID and choice ID combination has no corresponding entry in the Mapping_Dictionary, THEN THE Decision_Engine SHALL reject the submission and return an error response indicating the missing mapping, consistent with existing Scoring_Engine validation behavior
6. WHEN a free-text "Other" answer is submitted for a decision_model question, THE Decision_Engine SHALL store the text content (maximum 500 characters, minimum 1 non-whitespace character) in a pending_other_answers array within the decision_model output without applying Priority_Weight scoring
7. WHEN all 10 decision_model questions are answered, THE Decision_Engine SHALL normalize accumulated Priority_Weight values to the range 0.0 to 1.0 using the formula: (accumulated_weight - min_possible) / (max_possible - min_possible), rounded to two decimal places, where 1.0 represents the strongest priority
8. IF fewer than 10 decision_model questions are answered in a session (partial completion), THEN THE Decision_Engine SHALL not produce a decision_model output and SHALL preserve the partial answers for later completion
9. THE System SHALL extract escalation_rules (conditions requiring human escalation) from at least 1 dedicated question and auto_approve_scope (conditions where autonomous action is permitted) from at least 1 dedicated question within the decision_model Category, where each extracted rule is stored as a string with a maximum length of 200 characters

### Requirement 2: Tradeoff Scenarios 質問カテゴリ（トレードオフ）

**User Story:** As a user, I want to answer forced-choice tradeoff questions, so that my AI agent understands my value conflict resolution tendencies.

#### Acceptance Criteria

1. THE System SHALL define a "tradeoff_scenarios" question Category containing exactly 8 questions in the questions.yaml file, each with a unique ID prefixed "ts_" (ts_001 through ts_008), category_id "tradeoff_scenarios", and exactly 2 choices (id: "a" and "b") representing opposing values
2. WHEN a tradeoff_scenarios question is presented, THE Survey_UI SHALL display a binary forced-choice pair (exactly 2 options representing opposing values) without an "Other" free-text option, requiring the user to select exactly one option before proceeding
3. THE System SHALL design each tradeoff_scenarios question to represent one of 8 predefined value conflict pairs: speed_vs_quality, innovation_vs_stability, individual_vs_team, short_term_vs_long_term, perfection_vs_progress, autonomy_vs_consensus, breadth_vs_depth, process_vs_outcome
4. WHEN a tradeoff choice is submitted, THE Decision_Engine SHALL look up the Mapping_Dictionary entry for that question ID and choice ID combination and record the selection as a Tradeoff_Tendency score, where choice "a" (first value) maps to a score in range 0.0 to 0.3 and choice "b" (second value) maps to a score in range 0.7 to 1.0, with the exact value defined in the Mapping_Dictionary
5. IF a submitted tradeoff_scenarios question ID and choice ID combination has no corresponding entry in the Mapping_Dictionary, THEN THE Decision_Engine SHALL reject the submission and return an error response indicating the missing mapping
6. WHEN all 8 tradeoff_scenarios questions are answered, THE Decision_Engine SHALL produce a tradeoff_tendencies dictionary mapping each of the 8 conflict pair names (as string keys) to its Tradeoff_Tendency score (float, 0.0 to 1.0, rounded to two decimal places)
7. IF fewer than 8 tradeoff_scenarios questions are answered in a session (partial completion), THEN THE Decision_Engine SHALL not produce a tradeoff_tendencies output and SHALL preserve the partial answers for later completion

### Requirement 3: Failure Patterns 質問カテゴリ（失敗パターン）

**User Story:** As a user, I want to describe my failure patterns and cognitive weaknesses, so that my AI agent can proactively warn me about recurring mistakes.

#### Acceptance Criteria

1. THE System SHALL define a "failure_patterns" question Category containing exactly 7 questions in the questions.yaml file, each with a unique ID prefixed "fp_" (fp_001 through fp_007), category_id "failure_patterns", exactly 4 predefined choices (id: "a" through "d"), and a source_reference field
2. WHEN a failure_patterns question is presented, THE Survey_UI SHALL display exactly 4 predefined choices and one "Other" free-text option as a mutually exclusive single-selection group, where selecting any option deselects the previously selected option
3. THE System SHALL design failure_patterns questions to cover all four failure subcategories: degradation_triggers (minimum 1 question), procrastination_patterns (minimum 1 question), overconfidence_conditions (minimum 1 question), and recurring_mistakes (minimum 1 question), with each question's target subcategory defined in the Mapping_Dictionary
4. WHEN a predefined choice is submitted for a failure_patterns question, THE Decision_Engine SHALL look up the Mapping_Dictionary entry for that question ID and choice ID combination and categorize the selection into its target failure subcategory (degradation_triggers, procrastination_patterns, overconfidence_conditions, or recurring_mistakes), storing the mapped label string (maximum 100 characters) in the corresponding subcategory array
5. IF a submitted failure_patterns question ID and choice ID combination has no corresponding entry in the Mapping_Dictionary, THEN THE Decision_Engine SHALL reject the submission and return an error response indicating the missing mapping
6. WHEN a free-text "Other" answer is submitted for a failure_patterns question, THE Decision_Engine SHALL store the text content (maximum 500 characters, minimum 1 non-whitespace character) as-is in the corresponding failure subcategory array determined by the question's target subcategory defined in the Mapping_Dictionary, without scoring transformation
7. IF fewer than 7 failure_patterns questions are answered in a session (partial completion), THEN THE Decision_Engine SHALL not produce a failure_patterns output and SHALL preserve the partial answers for later completion

### Requirement 4: Context Adaptation 質問カテゴリ（場面適応）

**User Story:** As a user, I want to describe how I adapt my behavior to different contexts, so that my AI agent can switch communication modes appropriately.

#### Acceptance Criteria

1. THE System SHALL define a "context_adaptation" question Category containing exactly 5 questions in the questions.yaml file, each with a unique ID prefixed "ca_" (ca_001 through ca_005), category_id "context_adaptation", exactly 4 predefined choices (id: "a" through "d"), and a source_reference field
2. WHEN a context_adaptation question is presented, THE Survey_UI SHALL display a situational scenario with exactly 4 predefined choices and one "Other" free-text option as a mutually exclusive single-selection group, where selecting any option deselects the previously selected option
3. THE System SHALL design context_adaptation questions to extract mode definitions for: audience-dependent behavior (minimum 1 question covering executive_report and team_direction modes), urgency-dependent behavior (minimum 1 question covering emergency and normal modes), and cognitive-state-dependent behavior (minimum 1 question covering deep_review and quick_response modes)
4. WHEN a predefined choice is submitted for a context_adaptation question, THE Decision_Engine SHALL look up the Mapping_Dictionary entry for that question ID and choice ID combination and derive the corresponding Adaptation_Mode configuration containing tone (string, maximum 50 characters), detail level (string, one of: "minimal", "standard", "comprehensive"), and focus (string, maximum 50 characters)
5. IF a submitted context_adaptation question ID and choice ID combination has no corresponding entry in the Mapping_Dictionary, THEN THE Decision_Engine SHALL reject the submission and return an error response indicating the missing mapping
6. WHEN a free-text "Other" answer is submitted for a context_adaptation question, THE Decision_Engine SHALL store the text content (maximum 500 characters, minimum 1 non-whitespace character) in a pending_other_answers array within the context_adaptation output without deriving mode configurations
7. WHEN all 5 context_adaptation questions are answered, THE Decision_Engine SHALL produce a modes dictionary mapping each Adaptation_Mode name (string key) to its configuration object (tone: string, detail: string, focus: string) and a switch_triggers dictionary mapping trigger categories ("audience", "urgency", "mental_state") to string arrays of conditions (each condition maximum 100 characters)
8. IF fewer than 5 context_adaptation questions are answered in a session (partial completion), THEN THE Decision_Engine SHALL not produce a context_adaptation output and SHALL preserve the partial answers for later completion

### Requirement 5: Reasoning Flow 質問カテゴリ（思考プロセス）

**User Story:** As a user, I want to describe my default thinking process, so that my AI agent can replicate my reasoning approach.

#### Acceptance Criteria

1. THE System SHALL define a "reasoning_flow" question Category containing exactly 5 questions in the questions.yaml file, each with a unique ID prefixed "rf_" (rf_001 through rf_005), category_id "reasoning_flow", and a source_reference field
2. THE System SHALL include at least 2 questions in the reasoning_flow Category that use an ordering format (field "format" set to "ordering") where the user arranges 4 to 6 predefined steps in their preferred execution order, with each step having a unique choice ID
3. THE System SHALL include at least 1 question in the reasoning_flow Category that uses a standard single-selection format (4 predefined choices with id "a" through "d" and one "Other" free-text option) for extracting verification_method
4. THE System SHALL include at least 1 question in the reasoning_flow Category that uses a standard single-selection format (4 predefined choices with id "a" through "d" and one "Other" free-text option) for extracting learning_style
5. WHEN an ordering-format question is presented, THE Survey_UI SHALL provide a drag-and-drop interface (or numbered input fields on mobile devices) for step reordering, displaying the choices in an initial randomized order to avoid position bias
6. WHEN a reasoning_flow ordering answer is submitted, THE Decision_Engine SHALL record the step sequence as an ordered array of choice IDs representing the user's ranked order, where index 0 is the highest-priority step
7. IF a submitted reasoning_flow question ID and choice ID combination (for single-selection questions) has no corresponding entry in the Mapping_Dictionary, THEN THE Decision_Engine SHALL reject the submission and return an error response indicating the missing mapping
8. WHEN a free-text "Other" answer is submitted for a reasoning_flow single-selection question, THE Decision_Engine SHALL store the text content (maximum 500 characters, minimum 1 non-whitespace character) as the value for the corresponding field (verification_method or learning_style) as-is without mapping transformation
9. WHEN all 5 reasoning_flow questions are answered, THE Decision_Engine SHALL produce a reasoning_flow object containing: default_steps (ordered string array with 4 to 6 elements derived from ordering questions), verification_method (string, maximum 100 characters), and learning_style (string, maximum 100 characters)
10. IF fewer than 5 reasoning_flow questions are answered in a session (partial completion), THEN THE Decision_Engine SHALL not produce a reasoning_flow output and SHALL preserve the partial answers for later completion

### Requirement 6: ProfileOutput JSON 拡張

**User Story:** As a downstream system, I want the ProfileOutput JSON extended with decision_model, failure_patterns, context_adaptation, and reasoning_flow sections, so that agent systems can access structured decision-making data.

#### Acceptance Criteria

1. WHEN all decision engine questions are answered, THE Profile_Generator SHALL produce a ProfileOutput JSON containing "decision_model", "failure_patterns", "context_adaptation", and "reasoning_flow" as additional top-level keys alongside existing keys (profile_id, persona, communication_tone, base_os, lexical_tags, semantic_contexts, context_layers)
2. THE Profile_Generator SHALL structure the "decision_model" object with the following keys: priorities (string array, 1 to 10 items, each string 1 to 100 characters), priority_weights (dictionary mapping priority name string to float rounded to 2 decimal places in range 0.0 to 1.0, where at least one entry must equal 1.0), escalation_rules (string array, 0 to 10 items, each string 1 to 200 characters), auto_approve_scope (string array, 0 to 10 items, each string 1 to 200 characters), tradeoff_tendencies (dictionary mapping exactly 8 conflict pair names to float rounded to 2 decimal places in range 0.0 to 1.0)
3. THE Profile_Generator SHALL structure the "failure_patterns" object with the following keys: degradation_triggers (string array, 0 to 10 items), procrastination_patterns (string array, 0 to 10 items), overconfidence_conditions (string array, 0 to 10 items), recurring_mistakes (string array, 0 to 10 items), where each string is 1 to 200 characters
4. THE Profile_Generator SHALL structure the "context_adaptation" object with the following keys: modes (dictionary mapping 1 to 6 mode name strings to objects each containing tone (string, 1 to 50 characters), detail (string, 1 to 50 characters), and focus (string, 1 to 50 characters)), switch_triggers (dictionary mapping trigger category strings to string arrays of 1 to 5 condition strings each 1 to 200 characters)
5. THE Profile_Generator SHALL structure the "reasoning_flow" object with the following keys: default_steps (ordered string array of 4 to 6 items, each string 1 to 100 characters), verification_method (string, 1 to 100 characters), learning_style (string, 1 to 100 characters)
6. THE Profile_Generator SHALL assign "decision_model" and "failure_patterns" to Layer 1 in the context_layers mapping, indicating data that is always loaded into the system prompt
7. THE Profile_Generator SHALL assign "context_adaptation" to Layer 2 in the context_layers mapping, indicating data loaded on demand based on conversation context
8. THE Profile_Generator SHALL assign "reasoning_flow" to Layer 2 in the context_layers mapping, indicating data loaded on demand during problem-solving interactions
9. IF decision engine questions have not been answered for a profile, THEN THE Profile_Generator SHALL omit the decision_model, failure_patterns, context_adaptation, and reasoning_flow keys from the output rather than generating placeholder values, and the context_layers mapping SHALL NOT include entries for these omitted keys
10. IF decision engine questions are only partially answered (some Categories complete, others not), THEN THE Profile_Generator SHALL include only the sections corresponding to fully completed Categories and omit sections for incomplete Categories

### Requirement 7: Prompt Engine テンプレート拡張

**User Story:** As a system component, I want the Prompt Engine to incorporate decision engine data into system prompts, so that AI agents exhibit the user's decision-making personality.

#### Acceptance Criteria

1. WHEN a ProfileOutput containing decision_model is provided, THE Prompt_Engine SHALL include a "## Decision Framework" section in the generated system prompt listing priorities in descending priority_weight order, formatted as "- {priority_name} (weight: {priority_weight})" for each entry
2. WHEN a ProfileOutput containing failure_patterns is provided, THE Prompt_Engine SHALL include a "## Known Weaknesses & Guardrails" section listing degradation_triggers as "⚠️ {trigger}" items and recurring_mistakes as "🔄 {mistake}" items, each on a separate line
3. WHEN a ProfileOutput containing context_adaptation is provided, THE Prompt_Engine SHALL include a "## Context Adaptation Rules" section defining each mode as "### {mode_name}" with tone, detail, focus values, followed by a "Switch Conditions:" subsection listing each trigger category and its conditions
4. WHEN a ProfileOutput containing reasoning_flow is provided, THE Prompt_Engine SHALL include a "## Default Reasoning Process" section presenting the default_steps as a numbered sequence ("1. {step}") the agent follows when approaching problems, followed by verification_method and learning_style as labeled items
5. IF a ProfileOutput does not contain decision_model, failure_patterns, context_adaptation, or reasoning_flow keys, THEN THE Prompt_Engine SHALL generate the system prompt without those sections, maintaining backward compatibility with existing profiles that lack these keys
6. WHEN all decision engine sections are included, THE Prompt_Engine SHALL ensure the total generated system prompt does not exceed the configured max_tokens limit (default 4000 tokens), truncating lower-priority sections (reasoning_flow first, then context_adaptation) if the limit would be exceeded

### Requirement 8: Package Generator 拡張

**User Story:** As a user downloading an Agent Skills Package, I want the package to include decision rules and reasoning flow definitions, so that I can use the agent in external tools with full decision-making personality.

#### Acceptance Criteria

1. WHEN a ProfileOutput containing decision_model is provided, THE Package_Generator SHALL include decision framework data in the system_prompt.md file under a "## Decision Framework" section listing priorities with weights and tradeoff_tendencies with their scores
2. WHEN a ProfileOutput containing decision_model is provided, THE Package_Generator SHALL generate a "skills/decision-rules/SKILL.md" file containing escalation_rules as a "## Escalation Rules" list, auto_approve_scope as a "## Auto-Approve Scope" list, and tradeoff_tendencies as a "## Tradeoff Tendencies" table, following the same YAML frontmatter format used by existing SKILL.md files
3. WHEN a ProfileOutput containing reasoning_flow is provided, THE Package_Generator SHALL generate a "tools/reasoning_flow.json" file containing a JSON object with keys: default_steps (ordered string array), verification_method (string), and learning_style (string), encoded as UTF-8 with 2-space indentation
4. WHEN a ProfileOutput containing failure_patterns is provided, THE Package_Generator SHALL include failure pattern awareness in the system_prompt.md under a "## Self-Awareness" section listing degradation_triggers, procrastination_patterns, overconfidence_conditions, and recurring_mistakes as categorized bullet lists
5. IF a ProfileOutput does not contain decision engine data (decision_model, failure_patterns, context_adaptation, and reasoning_flow keys are all absent), THEN THE Package_Generator SHALL generate the package without the "skills/decision-rules/SKILL.md" file and without "tools/reasoning_flow.json", and SHALL omit the "## Decision Framework" and "## Self-Awareness" sections from system_prompt.md, maintaining backward compatibility with existing profiles
6. WHEN a ProfileOutput containing context_adaptation is provided, THE Package_Generator SHALL include mode definitions in the config.json under a "context_adaptation" key containing the modes dictionary and switch_triggers dictionary

### Requirement 9: Chat Service コンテキスト適応

**User Story:** As a user chatting with my AI agent, I want the agent to dynamically switch communication modes based on conversation context, so that responses match the situation appropriately.

#### Acceptance Criteria

1. WHEN a user message is received and the agent's ProfileOutput contains context_adaptation data, THE Chat_Service SHALL evaluate the message content and the last 5 conversation turns against the switch_triggers conditions (audience, urgency, mental_state) to determine the applicable Adaptation_Mode
2. WHEN an Adaptation_Mode is determined, THE Chat_Service SHALL append the corresponding mode configuration (tone, detail, focus) as an additional system prompt section formatted as "## Current Mode: {mode_name}\n- Tone: {tone}\n- Detail: {detail}\n- Focus: {focus}" for that response generation
3. WHILE an emergency Adaptation_Mode is active (urgency trigger detected in switch_triggers), THE Chat_Service SHALL generate responses with the emergency mode configuration (tone: "direct", detail: "minimal", focus: "action") until 3 consecutive user messages contain no urgency trigger keywords
4. WHEN the Chat_Service detects a mode switch is needed mid-conversation, THE Chat_Service SHALL apply the new mode starting from the current response without retroactively modifying previous responses stored in the threads table
5. THE Chat_Service SHALL make failure_patterns data available via the search_memory tool by indexing degradation_triggers and recurring_mistakes as searchable semantic contexts when the profile is loaded, enabling the agent to reference them when contextually relevant
6. IF the agent's ProfileOutput does not contain context_adaptation data, THEN THE Chat_Service SHALL skip mode evaluation and generate responses using only the base system prompt, with no performance penalty from the mode evaluation logic

### Requirement 10: Discussion Engine 意思決定モデル反映

**User Story:** As a user observing multi-agent discussions, I want each agent to exhibit its unique decision-making personality during debates, so that discussions reflect authentic perspective diversity.

#### Acceptance Criteria

1. WHEN a discussion turn is generated, THE Discussion_Engine SHALL include the participating agent's decision_model priorities and priority_weights in the system prompt as a "## My Decision Priorities" section, formatted as a descending-weight ordered list
2. WHEN a discussion turn is generated, THE Discussion_Engine SHALL include the participating agent's reasoning_flow default_steps in the system prompt as a "## My Reasoning Approach" numbered list, guiding the agent's argumentation structure
3. WHEN agents with conflicting tradeoff_tendencies discuss a topic (defined as a difference of 0.4 or more on any shared tradeoff dimension), THE Discussion_Engine SHALL include a directive in each agent's system prompt stating "Maintain your position on {dimension}: your tendency is {score}" to preserve distinct perspectives without converging toward a middle ground
4. IF a participating agent's ProfileOutput does not contain decision engine data (decision_model, reasoning_flow keys absent), THEN THE Discussion_Engine SHALL generate that agent's turns using only existing profile data (base_os, persona, communication_tone) without injecting decision framework sections, maintaining backward compatibility
5. WHEN decision engine data is included in the system prompt for a discussion turn, THE Discussion_Engine SHALL ensure the combined system prompt (base profile + decision engine sections) does not exceed 4000 tokens, truncating reasoning_flow if necessary

### Requirement 11: フィードバックループ（評価・修正・学習）

**User Story:** As a user, I want to evaluate my AI agent's responses with "I wouldn't say it this way" or "This feels like me" feedback, so that the agent's personality gradually improves over time.

#### Acceptance Criteria

1. WHEN an agent response is displayed in the Chat UI, THE Survey_UI SHALL provide a feedback interface with three options: "私らしい" (approve), "私ならこう言わない" (reject with correction), and "スキップ" (no feedback), displayed as icon buttons below each agent response message
2. WHEN the user selects "私ならこう言わない", THE Survey_UI SHALL display a text input field (textarea) where the user can provide their preferred alternative response, with a maximum of 2000 characters enforced by client-side truncation and a visible character counter
3. WHEN feedback is submitted, THE Feedback_Service SHALL create a Feedback_Record containing: agent_id (UUID v4 string), thread_id (UUID v4 string), turn_id (UUID v4 string referencing the specific assistant turn in the threads table), feedback_type (enum: "approve" or "reject"), user_correction (string, null if feedback_type is "approve", 1 to 2000 characters if "reject"), original_response (string, the full agent response text), and timestamp (ISO 8601 UTC format)
4. THE Feedback_Service SHALL persist all Feedback_Records in a SQLite table named "feedback_records" with columns: id (INTEGER PRIMARY KEY AUTOINCREMENT), agent_id (TEXT NOT NULL), thread_id (TEXT NOT NULL), turn_id (TEXT NOT NULL), feedback_type (TEXT NOT NULL CHECK IN ('approve', 'reject')), user_correction (TEXT), original_response (TEXT NOT NULL), created_at (TEXT NOT NULL), and indexes on (agent_id, created_at) and (agent_id, feedback_type)
5. WHEN 10 or more Feedback_Records of type "reject" accumulate for a single priority or tradeoff_tendency dimension (identified by keyword matching between user_correction texts and priority/tradeoff names), THE Feedback_Service SHALL recalculate the corresponding Priority_Weight or Tradeoff_Tendency by adjusting the current value by up to ±0.1 per recalculation cycle, clamping the result to the range 0.0 to 1.0
6. WHEN a Priority_Weight or Tradeoff_Tendency is adjusted by the Feedback_Service, THE Feedback_Service SHALL append an entry to a modification_history array within the ProfileOutput JSON, containing: field_name (string), previous_value (float, 2 decimal places), new_value (float, 2 decimal places), adjustment_reason (string, 1 to 200 characters summarizing the correction pattern), feedback_count (integer, the number of reject records that triggered this adjustment), and timestamp (ISO 8601 UTC format)
7. THE Feedback_Service SHALL expose a GET endpoint to retrieve the modification_history for a given profile_id, returning all adjustments as a JSON array in chronological order (oldest first), with each entry containing field_name, previous_value, new_value, adjustment_reason, feedback_count, and timestamp
8. IF fewer than 10 Feedback_Records of type "reject" exist for a dimension, THEN THE Feedback_Service SHALL not perform automatic weight adjustment for that dimension, and the dimension's current value SHALL remain unchanged

### Requirement 12: 全質問統一3層パイプライン適用

**User Story:** As a system component, I want the Three_Layer_Answer pipeline applied to ALL questions (existing + new), so that every answer produces an executable policy rule and the agent's behavior is driven by a unified Rule Hierarchy rather than fragmented scoring mechanisms.

#### Acceptance Criteria

1. THE System SHALL apply the Three_Layer_Answer pipeline (Raw → Normalized → Policy) to ALL questions across ALL Categories (Business OS, Communication, Lifestyle/Hobbies, Persona, Communication Tone, Interests, Decision Model, Tradeoff Scenarios, Failure Patterns, Context Adaptation, Reasoning Flow), not only to decision engine Categories
2. THE System SHALL extend ALL existing Mapping_Dictionary entries (bos_*, com_*, lif_* prefixed) with policy_text (string, maximum 200 characters) and normalized_tags (array of {type, value} objects) fields, in addition to existing axes score fields
3. WHEN a predefined choice answer is submitted for ANY question (existing or new), THE AnswerPipeline SHALL produce a Three_Layer_Answer object with raw, normalized, and policy layers, persisting all three layers in the answer_layers table
4. THE Profile_Generator SHALL include ALL non-null policy_text values from answer_layers in the "decision_rules" array of the ProfileOutput, regardless of which Category the originating question belongs to
5. THE Rule_Hierarchy SHALL aggregate policy rules from ALL Categories into the four-tier structure (core_invariants, context_rules, exceptions, preferences), where existing Category rules (Business OS, Communication, Lifestyle) are eligible for core_invariant classification if their confidence >= 0.8 AND permanence = "permanent"
6. THE System SHALL present ALL Categories in the survey flow order: Persona (order: 1) → Communication Tone (order: 2) → Interests (order: 3) → Business OS (order: 4) → Communication (order: 5) → Lifestyle/Hobbies (order: 6) → Decision Model (order: 7) → Tradeoff Scenarios (order: 8) → Failure Patterns (order: 9) → Context Adaptation (order: 10) → Reasoning Flow (order: 11)
7. THE System SHALL retain the existing 4-axis scoring (extroverted_introverted, sensing_intuition, thinking_feeling, judging_perceiving) as a supplementary mechanism for base_os generation (decision_style, do_not_list), operating in parallel with the Three_Layer_Answer pipeline without conflict
8. WHEN the Prompt_Engine generates a system prompt, THE System SHALL prioritize Rule_Hierarchy (core_invariants first) as the primary behavioral specification, with base_os (4-axis derived personality description) serving as supplementary context

### Requirement 13: 質問データファイル拡張

**User Story:** As a system administrator, I want decision engine questions defined in the existing questions.yaml format, so that the scoring infrastructure remains unified.

#### Acceptance Criteria

1. THE System SHALL add decision engine question Categories to the existing questions.yaml file following the same YAML structure: category-level fields (id: string, name: string, order: integer, questions: array), question-level fields (id: unique string, text: string max 200 characters, category_id: string, choices: array, source_reference: string, format: string defaulting to "single_select")
2. THE System SHALL assign category order values for decision engine Categories that place them after existing Categories: decision_model (order: 7), tradeoff_scenarios (order: 8), failure_patterns (order: 9), context_adaptation (order: 10), reasoning_flow (order: 11)
3. THE System SHALL define each tradeoff_scenarios question with exactly 2 choices (binary forced-choice), where each choice has a unique choice_id and label (maximum 100 characters per label), and the format field set to "binary_choice"
4. THE System SHALL define each reasoning_flow ordering question with 4 to 6 choices representing steps to be ranked, with the format field set to "ordering" to distinguish from standard single-select questions, and each choice containing choice_id and label (maximum 100 characters per label)
5. THE System SHALL add corresponding entries in the Mapping_Dictionary for all decision engine questions, mapping each choice to its target output field: priority label and weight increment for decision_model, tradeoff pair name and tendency score for tradeoff_scenarios, failure subcategory for failure_patterns, mode configuration fields for context_adaptation, and step identifier for reasoning_flow
6. IF a decision engine question definition is missing required fields (id, text, category_id, choices with valid choice_id and label, source_reference) or has no corresponding Mapping_Dictionary entry, THEN THE System SHALL reject that question on load, log a validation error identifying the question_id and the specific missing field, and continue loading all other valid questions

### Requirement 14: REST API 拡張

**User Story:** As a frontend developer, I want well-defined API endpoints for decision engine features, so that I can integrate feedback and decision data into the UI.

#### Acceptance Criteria

1. THE System SHALL expose a POST endpoint at /api/feedback accepting a JSON body with required fields: agent_id (string, UUID v4 format), thread_id (string, UUID v4 format), turn_id (string, UUID v4 format), feedback_type (string, enum "approve" or "reject"), and optional field: user_correction (string, 1 to 2000 characters), returning HTTP 201 with a JSON body containing feedback_id and created_at on success
2. THE System SHALL expose a GET endpoint at /api/feedback/{agent_id} accepting query parameters limit (integer, 1 to 100, default 20) and offset (integer, minimum 0, default 0), returning a JSON body with items (array of Feedback_Records in reverse chronological order), total (integer total count), limit, and offset
3. THE System SHALL expose a GET endpoint at /api/profiles/{profile_id}/modification-history returning a JSON body with items (array of modification_history entries in chronological order) and total (integer count), where each entry contains field_name, previous_value, new_value, adjustment_reason, feedback_count, and timestamp
4. THE System SHALL expose a GET endpoint at /api/profiles/{profile_id}/decision-engine returning a JSON body containing the decision_model, failure_patterns, context_adaptation, and reasoning_flow objects for the specified profile_id
5. IF a feedback submission references an agent_id that does not exist in the agents table, or a thread_id that does not exist in the threads table, or a turn_id that does not exist in the threads table, THEN THE System SHALL return an HTTP 404 response with a JSON body containing error (string identifier) and message (string identifying the specific invalid reference)
6. IF a feedback submission contains feedback_type "reject" without user_correction text or with an empty string user_correction, THEN THE System SHALL return an HTTP 422 response with a JSON body containing error: "validation_error" and details array specifying that correction text is required for reject feedback
7. IF a profile_id has no decision engine data (no decision_model, failure_patterns, context_adaptation, or reasoning_flow keys exist), THEN THE GET /api/profiles/{profile_id}/decision-engine endpoint SHALL return an HTTP 404 response with a JSON body containing error: "decision_engine_not_available" and message indicating that decision engine profiling has not been completed for this profile

### Requirement 15: Ordering 形式 UI サポート

**User Story:** As a user, I want to rank reasoning steps in my preferred order using drag-and-drop, so that I can intuitively express my thinking process.

#### Acceptance Criteria

1. WHEN a question with format "ordering" is presented, THE Survey_UI SHALL display all choices as draggable card elements that can be reordered by drag-and-drop interaction, with each card showing the choice label text and a drag handle icon
2. WHEN a question with format "ordering" is presented, THE Survey_UI SHALL display an initial randomized order of the choices using a Fisher-Yates shuffle algorithm seeded per question presentation, ensuring the order differs from the data file sequence to avoid position bias
3. WHILE a user is reordering choices, THE Survey_UI SHALL provide visual feedback consisting of: a drop shadow (elevation change) on the dragged card, a highlighted insertion line (2px colored bar) at the current drop position, and a 200ms transition animation for displaced cards
4. WHEN the user confirms their ordering by clicking the "Next" button, THE Survey_UI SHALL submit the choice IDs as a JSON array in the user's specified sequence order (index 0 = highest priority, last index = lowest priority) to the backend answer submission endpoint
5. WHEN a viewport width of 768px or less is detected, THE Survey_UI SHALL provide numbered input fields (1 to N where N is the number of choices) adjacent to each choice card, allowing the user to type rank numbers as an alternative to drag-and-drop, with duplicate number validation displaying an inline error message
6. IF the user has not modified the initial randomized order, THEN THE Survey_UI SHALL still allow submission of the current order as a valid answer when the "Next" button is clicked, treating the displayed order as the user's intentional ranking

### Requirement 16: 回答3層構造化パイプライン（Raw → Normalized → Policy）

**User Story:** As a system component, I want each answer transformed into a three-layer structure (raw response, normalized value, and executable policy rule), so that the agent's behavior is driven by stable rules rather than raw sentiment.

#### Acceptance Criteria

1. WHEN a predefined choice answer is submitted for ANY question (existing or new Categories), THE Decision_Engine SHALL store the answer as a Three_Layer_Answer object containing: raw (object with question_id, choice_id, choice_label as original strings), normalized (object with one or more key-value pairs mapping a normalized tag name to a canonical value string, maximum 50 characters per value), and policy (string, a one-sentence agent-executable rule in the format "when_{condition}: {action}", maximum 200 characters)
2. WHEN a free-text "Other" answer is submitted for ANY question (existing or new Categories), THE Decision_Engine SHALL store the raw text in the raw layer, invoke LLM-based normalization to produce the normalized layer (extracting 1 to 4 Normalization_Tags classified as value_tag, behavior_tag, prohibition_tag, or condition_tag), and derive a policy rule from the normalized output; IF LLM normalization fails, THE Decision_Engine SHALL store the raw text with normalized set to null and policy set to null, marking the entry as "pending_normalization"
3. THE Decision_Engine SHALL persist all Three_Layer_Answer objects in a SQLite table named "answer_layers" with columns: id (INTEGER PRIMARY KEY AUTOINCREMENT), session_id (TEXT NOT NULL), question_id (TEXT NOT NULL), raw_json (TEXT NOT NULL, JSON string), normalized_json (TEXT, nullable JSON string), policy_text (TEXT, nullable), normalization_tags (TEXT, nullable JSON array of {type, value} objects), created_at (TEXT NOT NULL), updated_at (TEXT NOT NULL)
4. WHEN the Profile_Generator produces the final ProfileOutput, THE Profile_Generator SHALL include a "decision_rules" array in the output JSON containing all non-null policy_text values from Three_Layer_Answer objects for the session, ordered by question presentation sequence, where each entry is an object with keys: topic (string derived from question category_id), rule (string, the policy_text), confidence (float 0.0 to 1.0 from Answer_Metadata), and is_core (boolean from Answer_Metadata.is_core_rule)
5. THE Decision_Engine SHALL provide a batch re-normalization endpoint (POST /api/sessions/{id}/re-normalize) that re-processes all "pending_normalization" entries in the session using the LLM, updating the normalized and policy layers without modifying the raw layer
6. THE Profile_Generator SHALL aggregate all policy rules into the Rule_Hierarchy structure with four tiers: core_invariants (rules where is_core_rule = true AND confidence >= 0.8), context_rules (rules where confidence >= 0.5 AND is_core_rule = false), exceptions (rules tagged with condition_tag in normalization_tags), and preferences (all remaining rules), stored as a "rule_hierarchy" object in the ProfileOutput JSON

### Requirement 17: 回答メタデータと確信度付与

**User Story:** As a user, I want to indicate how confident I am in each answer and whether it applies universally or only in specific situations, so that the agent can distinguish between my core principles and situational preferences.

#### Acceptance Criteria

1. WHEN the user submits an answer for ANY question across ALL Categories, THE Survey_UI SHALL display an optional metadata panel (expandable, not blocking the flow) with the following fields: permanence (toggle: "常にそう" / "場合による", default "常にそう"), confidence (slider 1-5, default 3, displayed as ★), exception_note (optional free-text, maximum 200 characters, placeholder "例外がある場合を記述")
2. IF the user does not interact with the metadata panel before proceeding, THE System SHALL apply default values: permanence = "permanent", confidence = 0.6 (mapped from default 3 on 1-5 scale as: 1→0.2, 2→0.4, 3→0.6, 4→0.8, 5→1.0), exception_note = null, is_core_rule = false, ambiguity = 0.0
3. WHEN the user sets permanence to "場合による" and provides an exception_note, THE Decision_Engine SHALL store the Answer_Metadata with permanence = "contextual", the exception_note text as a condition_tag in the normalization process, and set the answer's policy_text to include the condition (format: "when_{condition}: {action}; EXCEPT when {exception_note}")
4. THE Decision_Engine SHALL use the confidence value from Answer_Metadata to weight the corresponding Priority_Weight or Tradeoff_Tendency calculation, multiplying the base weight from the Mapping_Dictionary by the confidence factor (0.2 to 1.0) before accumulation
5. WHEN the Profile_Generator aggregates answers into the Rule_Hierarchy, THE Profile_Generator SHALL classify any answer with confidence >= 0.8 AND permanence = "permanent" as a core_invariant candidate, subject to a maximum of 10 core_invariants per profile; IF more than 10 candidates exist, THE Profile_Generator SHALL select the 10 with the highest confidence values
6. THE Decision_Engine SHALL persist Answer_Metadata in the "answer_layers" table by extending the schema with additional columns: permanence (TEXT NOT NULL DEFAULT 'permanent'), confidence (REAL NOT NULL DEFAULT 0.6), exception_note (TEXT, nullable), is_core_rule (INTEGER NOT NULL DEFAULT 0), ambiguity (REAL NOT NULL DEFAULT 0.0)
7. WHEN the user revisits a previously answered question (back navigation), THE Survey_UI SHALL restore the previously set metadata values alongside the previously selected answer, allowing the user to modify both the answer and its metadata
8. THE Profile_Generator SHALL include a "answer_metadata_summary" object in the ProfileOutput containing: total_answers (integer), core_rule_count (integer, answers where is_core_rule = true), contextual_count (integer, answers where permanence = "contextual"), average_confidence (float, rounded to 2 decimal places), and high_ambiguity_count (integer, answers where ambiguity > 0.5)
