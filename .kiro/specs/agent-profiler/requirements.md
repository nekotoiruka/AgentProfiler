# Requirements Document

## Introduction

Agent Profiler は、ユーザー固有の価値観・意思決定基準・趣味・嗜好を「仕事のコンテキスト」に特化した質問を通じて抽出し、AIエージェントの「ベースOS（コンテキスト）」として機能する構造化データ（JSON）を生成するシステムである。内部パラメータ処理は4軸思考特性（外向/内向、感覚/直観、論理/感情、計画/柔軟）を採用し、1問多軸ブレンド型スコアリングにより少ない質問数で精度の高いプロファイルを構築する。生成されたプロファイルは3層コンテキストレイヤー（Base OS / Agent Skills / MCP）に分離され、ハイブリッド検索（キーワード完全一致 + ベクトル意味検索）を通じてエージェントにプログレッシブにロードされる。

## Glossary

- **System**: Agent Profilerシステム全体を指す
- **Survey_UI**: Vue.jsで構築されたステップベースの質問フロントエンド
- **Scoring_Engine**: FastAPIで構築された1問多軸ブレンドスコアリングバックエンド
- **Profile_Generator**: 正規化されたスコアから最終的なプロファイルJSON出力を生成するコンポーネント
- **Mapping_Dictionary**: 質問ID・選択肢ごとの多軸スコアリングロジックを管理する独立したJSON/YAMLファイル
- **Four_Axis**: 内部パラメータの4軸思考特性（extroverted_introverted, sensing_intuition, thinking_feeling, judging_perceiving）
- **Base_OS**: エージェントの基本トーン＆マナーとガードレールを担保する常駐レイヤー（axes, decision_style, do_not_list）
- **Lexical_Tags**: キーワード完全一致検索用のタグ配列（技術スタック、趣味、ツール名等の固有名詞）
- **Semantic_Contexts**: ベクトル検索用の自然言語記述（行動特性、価値観、意思決定スタイル）
- **Evaluation_Axis**: Four_Axisの各軸（E/I, S/N, T/F, J/P に相当する独自パラメータ）
- **Normalization**: 全質問回答後に各軸スコアを0.0〜1.0の範囲に正規化する処理
- **Category**: 質問のグループ分け（Business OS, Communication, Lifestyle/Hobbies等）
- **Context_Layer**: プロファイルデータのロード階層（Layer 1: Base OS, Layer 2: Agent Skills, Layer 3: MCP）
- **Hybrid_Search**: Lexical_Tags による完全一致検索と Semantic_Contexts によるベクトル検索を組み合わせた検索方式

## Requirements

### Requirement 1: ステップベース質問UI

**User Story:** As a user, I want to answer one question per screen in a card flip format, so that I can focus on each question without cognitive overload.

#### Acceptance Criteria

1. WHEN a survey session starts, THE Survey_UI SHALL display the first question of the first Category as a single card occupying the main content area, with only one question visible at a time
2. WHEN the user answers a question, THE Survey_UI SHALL transition to the next question with a card flip animation completing within 300 to 500 milliseconds
3. WHILE a survey session is active, THE Survey_UI SHALL display a progress indicator showing the current Category name and the completion percentage (0% to 100%, integer) calculated as (answered questions in current Category / total questions in current Category × 100)
4. WHILE a survey session is active, THE Survey_UI SHALL show the overall completion percentage calculated as (total answered questions / total questions across all Categories × 100) as an integer from 0% to 100%
5. WHEN a survey session loads questions, THE Survey_UI SHALL group and present questions in fixed Category order (Business OS → Communication → Lifestyle/Hobbies), completing all questions in one Category before advancing to the next
6. WHEN the user is on any question other than the first question, THE Survey_UI SHALL provide a back navigation control that returns to the previous question with a reverse card flip animation, preserving the previously selected answer
7. WHEN the user answers the last question across all Categories, THE Survey_UI SHALL navigate to the results dashboard without displaying further question cards

### Requirement 2: 選択肢入力フォーマット（4選択肢 + Other）

**User Story:** As a user, I want to select from 4 predefined choices or provide a custom answer, so that I can express my preferences accurately.

#### Acceptance Criteria

1. THE Survey_UI SHALL present exactly 4 predefined choices and one "Other" option for each question as a mutually exclusive single-selection group, where selecting any option deselects the previously selected option
2. WHEN the user selects "Other", THE Survey_UI SHALL display a free-text textarea with a slide-in animation completing within 300ms
3. WHEN the user selects a predefined choice after previously selecting "Other", THE Survey_UI SHALL hide the free-text textarea and clear its content
4. WHEN the user selects a predefined choice, THE Survey_UI SHALL send only the question ID and choice ID to the Scoring_Engine
5. WHEN the user submits a free-text answer via "Other", THE Survey_UI SHALL send the question ID and text content (maximum 500 characters) to the Scoring_Engine
6. IF the user has not selected a predefined choice and has not entered at least 1 non-whitespace character in the "Other" textarea, THEN THE Survey_UI SHALL keep the "Next" action disabled
7. IF the user enters text exceeding 500 characters in the "Other" textarea, THEN THE Survey_UI SHALL truncate input at the 500-character limit and display a character count indicator

### Requirement 3: 1問多軸ブレンドスコアリング

**User Story:** As a system administrator, I want each answer to receive weighted scoring across multiple Four_Axis values simultaneously, so that a single question captures multidimensional user traits with fewer total questions.

#### Acceptance Criteria

1. WHEN a predefined choice answer is submitted, THE Scoring_Engine SHALL apply integer score values simultaneously across all four Evaluation_Axis values (extroverted_introverted, sensing_intuition, thinking_feeling, judging_perceiving) by looking up the Mapping_Dictionary entry for that question ID and choice ID combination
2. THE Scoring_Engine SHALL support integer score values in the range of -10 to +10 per Evaluation_Axis per choice, rejecting any Mapping_Dictionary entry that contains values outside this range
3. WHEN a free-text "Other" answer is submitted, THE Scoring_Engine SHALL apply a neutral score vector (0 for all four axes) for that question, receiving the question ID and text content from the frontend
4. THE Scoring_Engine SHALL accumulate scores for each Evaluation_Axis by arithmetic sum across all answered questions within a session
5. WHEN a predefined choice answer is submitted, THE Scoring_Engine SHALL receive only the question ID and choice ID from the frontend, with no score values transmitted from the client
6. IF a submitted question ID and choice ID combination has no corresponding entry in the Mapping_Dictionary, THEN THE Scoring_Engine SHALL reject the submission and return an error response indicating the missing mapping
7. THE Scoring_Engine SHALL require each Mapping_Dictionary entry to define a score value for all four Evaluation_Axis values, treating any entry with missing axis scores as invalid

### Requirement 4: マッピング辞書管理

**User Story:** As a system administrator, I want scoring logic managed in independent JSON/YAML files, so that I can tune scoring without code changes.

#### Acceptance Criteria

1. WHEN the Scoring_Engine starts, THE Scoring_Engine SHALL load scoring logic from an independent JSON or YAML Mapping_Dictionary file before accepting any scoring requests
2. THE Mapping_Dictionary SHALL define score values per question ID, choice ID, and all Four_Axis values (extroverted_introverted, sensing_intuition, thinking_feeling, judging_perceiving) as a single entry, where each axis score is an integer in the range -10 to +10
3. WHEN the Mapping_Dictionary file is updated, THE Scoring_Engine SHALL reflect the changes on the next scoring request without requiring a restart
4. IF the Mapping_Dictionary contains entries with missing required fields (question ID, choice ID, or any Four_Axis score value) or score values outside the -10 to +10 range, THEN THE Scoring_Engine SHALL log a validation error identifying the invalid entry and reject that entry while continuing to use all valid entries
5. THE Mapping_Dictionary SHALL include theoretical minimum and maximum scores per Evaluation_Axis for Normalization reference
6. IF the Mapping_Dictionary file is missing or entirely unparseable at startup, THEN THE Scoring_Engine SHALL fail to start and log an error message indicating the file path and parse failure reason
7. IF a scoring request references a question ID and choice ID combination not present in the Mapping_Dictionary, THEN THE Scoring_Engine SHALL return an error response indicating the missing mapping entry and SHALL NOT update the session scores

### Requirement 5: スコア正規化

**User Story:** As a system component, I want raw axis scores normalized to 0.0–1.0 range, so that scores are comparable and usable as agent parameters.

#### Acceptance Criteria

1. WHEN all questions in a session are answered, THE Scoring_Engine SHALL normalize each of the four Evaluation_Axis scores to the range 0.0 to 1.0 using the formula: (raw_score - theoretical_min) / (theoretical_max - theoretical_min)
2. THE Scoring_Engine SHALL use the theoretical minimum and maximum scores per Evaluation_Axis as defined in the Mapping_Dictionary for the normalization calculation
3. IF an Evaluation_Axis raw score is less than the theoretical minimum or greater than the theoretical maximum, THEN THE Scoring_Engine SHALL clamp the normalized value to 0.0 or 1.0 respectively
4. THE Scoring_Engine SHALL output normalized scores rounded to two decimal places using round-half-up rounding
5. IF the theoretical minimum equals the theoretical maximum for an Evaluation_Axis, THEN THE Scoring_Engine SHALL output a normalized score of 0.5 for that axis and log a configuration warning

### Requirement 6: プロファイルJSON生成（3層対応構造）

**User Story:** As a downstream AI agent system, I want the profile output structured as base_os, lexical_tags, and semantic_contexts, so that I can load data progressively across the 3-layer context architecture.

#### Acceptance Criteria

1. WHEN normalization is complete, THE Profile_Generator SHALL produce a JSON output containing "profile_id", "base_os", "lexical_tags", and "semantic_contexts" as top-level keys, where "base_os" contains "axes", "decision_style", and "do_not_list" sub-keys
2. THE Profile_Generator SHALL populate "base_os.axes" with the four normalized Evaluation_Axis scores (extroverted_introverted, sensing_intuition, thinking_feeling, judging_perceiving) as numeric values with two decimal places in the range 0.00 to 1.00
3. THE Profile_Generator SHALL derive "base_os.decision_style" by selecting the higher-scoring pole on each Evaluation_Axis (score > 0.50 = first pole, score < 0.50 = second pole) and combining the four dominant poles into a single label string
4. IF two or more Evaluation_Axis scores are exactly 0.50, THEN THE Profile_Generator SHALL treat the axis as neutral and exclude it from the decision_style label derivation, appending "_balanced" for each neutral axis
5. THE Profile_Generator SHALL generate "base_os.do_not_list" containing 1 to 4 natural language descriptions of behaviors the agent should avoid, derived from Evaluation_Axis traits where the normalized score is below 0.30 or above 0.70 (representing strong polarity)
6. THE Profile_Generator SHALL populate "lexical_tags" as a flat array of 5 to 30 unique keyword strings, each between 1 and 50 characters, extracted from the user's predefined choice selections and the Category tags associated with answered questions
7. THE Profile_Generator SHALL populate "semantic_contexts" as key-value pairs where keys are drawn from a fixed set of context domains defined in the question Category structure (problem_solving, communication_style, work_rhythm, analog_habits, lifestyle_preferences) and values are natural language descriptions of 1 to 3 sentences describing user behavior patterns
8. THE Profile_Generator SHALL assign a unique "profile_id" with the format "prof_" followed by a 6-digit zero-padded sequential number (e.g., "prof_000001")
9. IF normalization output is missing one or more Evaluation_Axis scores, THEN THE Profile_Generator SHALL reject the input and return an error indication specifying which axes are missing

### Requirement 7: 結果ダッシュボード

**User Story:** As a user, I want to visualize my extracted profile parameters and access the generated JSON, so that I can understand and use my agent profile.

#### Acceptance Criteria

1. WHEN a survey session is complete, THE Survey_UI SHALL display a results dashboard with a radar chart visualizing the four normalized Evaluation_Axis scores (extroverted_introverted, sensing_intuition, thinking_feeling, judging_perceiving) on a 0.0 to 1.0 scale with axis labels
2. WHEN the results dashboard is displayed, THE Survey_UI SHALL show a JSON preview of the complete generated profile output in a scrollable code block with syntax highlighting
3. WHEN the user clicks the copy-to-clipboard button, THE Survey_UI SHALL copy the complete generated JSON output to the system clipboard and display a confirmation indicator for 2 seconds
4. IF the clipboard copy operation fails, THEN THE Survey_UI SHALL display an error message indicating the copy failed
5. WHEN the results dashboard is displayed, THE Survey_UI SHALL display the derived decision_style label as a heading and do_not_list items as a bulleted list
6. WHEN the results dashboard is displayed, THE Survey_UI SHALL display Lexical_Tags as a chip list on the results dashboard

### Requirement 8: 元データソース調査・ドキュメント化

**User Story:** As a system designer, I want psychometric source data researched, documented, and internalized, so that question and scoring design is grounded in validated methodologies and later selection is informed.

#### Acceptance Criteria

1. THE System SHALL maintain a research documentation file that catalogs all investigated psychometric data sources with source name, URL, license type, item count, axis/factor structure, and applicability assessment (rated as "High / Medium / Low" with a one-sentence rationale stating coverage of Four_Axis dimensions and license compatibility)
2. THE System SHALL document the OEJTS (Open Extended Jungian Type Scales) source including its 4-dichotomy structure (E/I, S/N, T/F, J/P), item format (bipolar 5-point scale pairs), scoring methodology (mean level differences), and Creative Commons BY-NC-SA 4.0 license constraints
3. THE System SHALL document the IPIP-NEO-120 source including its 5-factor structure (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism), 30 facets, 120 public-domain items, and Likert-scale scoring method
4. THE System SHALL document the IPIP (International Personality Item Pool) general repository including available scale constructs, public-domain status, and item pool size (3,000+ items)
5. THE System SHALL document how each source's factors map to the internal Four_Axis model by specifying, for each source factor, the target Evaluation_Axis (extroverted_introverted, sensing_intuition, thinking_feeling, or judging_perceiving), the mapping type (direct, inverse, partial, or none), and a rationale sentence explaining the relationship
6. THE System SHALL document the adaptation strategy for transforming generic personality items into business-context and lifestyle trade-off scenarios, including at minimum: the transformation principle (abstract trait → concrete scenario), an example before/after pair per source, and the criteria for preserving construct validity during adaptation
7. THE System SHALL record for each source whether items are classified as "directly usable" (items can be used as-is with no wording changes and license permits inclusion), "require adaptation" (items need rewording into business/lifestyle scenarios but the underlying construct is applicable), or "design reference only" (factor structure or scoring methodology informs design but items themselves are not transferable), enabling informed selection at implementation time

### Requirement 9: 質問データ管理（ビジネスコンテキスト特化）

**User Story:** As a system administrator, I want questions designed around work and lifestyle trade-off scenarios grounded in validated psychometric principles, so that the profile captures actionable agent context with scientific backing.

#### Acceptance Criteria

1. THE System SHALL load question definitions from a JSON or YAML structured data file containing question ID (unique string), text (maximum 200 characters), Category, exactly 4 predefined choices each with a unique choice ID and label (maximum 100 characters per label), and source_reference indicating which psychometric source inspired the question
2. THE System SHALL define questions as work-context or lifestyle trade-off scenarios (project crisis response, reporting preferences, planning styles, collaboration patterns, etc.) where each question's source_reference traces to a documented source in the research documentation file defined in Requirement 8
3. THE System SHALL group and order questions by Category during survey presentation in the order defined by the data file
4. WHEN a question data file is updated, THE System SHALL reflect changes on the next session start without requiring a redeployment
5. THE System SHALL validate question data files on load and reject entries missing required fields (ID, text, Category, exactly 4 choices each with choice ID and label, source_reference) or containing duplicate question IDs, while continuing to load all valid entries
6. THE System SHALL design each question to activate at least 2 of the 4 Four_Axis values simultaneously, with each activated axis having a non-zero score defined in the Mapping_Dictionary for at least one choice
7. IF a question definition exists in the question data file without a corresponding entry in the Mapping_Dictionary, THEN THE System SHALL reject that question on load and log a validation error indicating the missing mapping
8. THE System SHALL avoid using the term "MBTI" in any user-facing content, code, or documentation, using "4軸思考特性診断" or "エージェント基本OS特性" as the public-facing name
9. THE System SHALL contain a minimum of 3 questions per Category, with a total question count between 12 and 30 questions across all categories

### Requirement 10: セッション管理

**User Story:** As a user, I want my survey progress preserved, so that I can resume an incomplete session later.

#### Acceptance Criteria

1. WHILE a survey session is active, THE System SHALL persist the user's answers after each question submission, recording the question ID, selected choice ID or free-text content, and a submission timestamp
2. WHEN a user returns to an incomplete session, THE System SHALL restore all previously submitted answers and resume from the first unanswered question in Category order
3. WHEN all questions are answered, THE System SHALL mark the session as complete, prevent further answer submissions to that session, and trigger score calculation and profile generation
4. THE System SHALL associate each session with a unique session identifier generated at session creation time
5. IF a user submits an answer to a question that has already been answered in the same session, THEN THE System SHALL overwrite the previous answer with the new submission and update the submission timestamp
6. IF a session has been inactive for more than 30 days, THEN THE System SHALL mark the session as expired and reject resume attempts with an error indicating session expiration
7. IF a user attempts to submit an answer to a session marked as complete or expired, THEN THE System SHALL reject the submission with an error indicating the session is no longer modifiable

### Requirement 11: REST API設計

**User Story:** As a frontend developer, I want well-defined REST API endpoints, so that I can integrate the Survey_UI with the Scoring_Engine seamlessly.

#### Acceptance Criteria

1. THE Scoring_Engine SHALL expose a POST endpoint to start a new survey session and return a session ID in JSON format
2. THE Scoring_Engine SHALL expose a POST endpoint to submit an individual question answer with session ID, question ID, and choice ID or free-text content (maximum 500 characters)
3. THE Scoring_Engine SHALL expose a GET endpoint to retrieve session status including answered question count, total question count, and current Category
4. THE Scoring_Engine SHALL expose a GET endpoint to retrieve the list of questions grouped by Category
5. THE Scoring_Engine SHALL expose a POST endpoint to trigger final score calculation and profile generation for a completed session
6. THE Scoring_Engine SHALL expose a GET endpoint to retrieve the generated profile JSON for a completed session
7. IF an API request contains an invalid session ID, THEN THE Scoring_Engine SHALL return an HTTP 404 response with an error message indicating the session was not found
8. IF an API request contains malformed data, THEN THE Scoring_Engine SHALL return an HTTP 422 response with field-level validation errors indicating which fields failed and why
9. IF a score calculation request is made for a session that has unanswered questions, THEN THE Scoring_Engine SHALL return an HTTP 409 response with an error message indicating the session is incomplete
10. IF a profile retrieval request is made for a session whose profile has not yet been generated, THEN THE Scoring_Engine SHALL return an HTTP 404 response with an error message indicating the profile is not available
11. THE Scoring_Engine SHALL return all API responses in JSON format with Content-Type application/json

### Requirement 12: ハイブリッド検索対応データ分離

**User Story:** As an agent runtime system, I want the profile data separated into exact-match searchable tags and vector-searchable semantic descriptions, so that I can perform O(1) keyword lookup and cosine-similarity semantic retrieval independently.

#### Acceptance Criteria

1. THE Profile_Generator SHALL produce Lexical_Tags as a flat array of lowercase, whitespace-trimmed string values containing only alphanumeric characters, hyphens, dots, and slashes (e.g., "python", "vue.js", "ci/cd"), with each tag no longer than 64 characters
2. THE Profile_Generator SHALL produce Semantic_Contexts as natural language paragraphs of 50 to 500 words each, written in complete sentences suitable for text embedding models
3. THE Profile_Generator SHALL ensure Lexical_Tags include technology stack names, tool names, hobby keywords, and methodology names extracted from user answers, producing a minimum of 5 and a maximum of 50 unique tags per profile
4. THE Profile_Generator SHALL ensure Semantic_Contexts describe behavioral patterns, decision-making approaches, and preference rationales, producing one paragraph per context domain (e.g., problem_solving, communication_style, analog_habits)
5. THE Profile_Generator SHALL not duplicate information between Lexical_Tags and Semantic_Contexts such that proper nouns and keywords appear only in Lexical_Tags while behavioral descriptions and rationales appear only in Semantic_Contexts
6. THE Profile_Generator SHALL ensure Lexical_Tags contain no duplicate values within a single profile
7. IF no extractable keywords exist for a given Category in the user's answers, THEN THE Profile_Generator SHALL omit tags for that Category rather than generating placeholder values

### Requirement 13: 3層コンテキストレイヤー対応メタデータ

**User Story:** As an agent orchestration system, I want the profile JSON to include layer assignment metadata, so that each data element can be routed to the correct context layer (Base OS / Agent Skills / MCP).

#### Acceptance Criteria

1. THE Profile_Generator SHALL include a "context_layers" object in the output JSON that maps each top-level profile section name ("base_os", "lexical_tags", "semantic_contexts") to an integer layer value (1, 2, or 3)
2. THE Profile_Generator SHALL assign "base_os" (including "do_not_list") to Layer 1 in the "context_layers" mapping, indicating data that is always loaded into the system prompt
3. THE Profile_Generator SHALL assign "lexical_tags" to Layer 2 in the "context_layers" mapping, indicating task-specific data loaded on demand
4. THE Profile_Generator SHALL assign "semantic_contexts" to Layer 3 in the "context_layers" mapping, indicating data fetched dynamically via hybrid search
5. IF the "context_layers" mapping references a section name that does not exist in the profile output, THEN THE Profile_Generator SHALL omit that entry from the "context_layers" object
