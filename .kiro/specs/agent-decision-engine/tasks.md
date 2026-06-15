# Implementation Plan: Agent Decision Engine

## Overview

Agent Decision Engine の実装を、コアインフラ → スコアリング → パイプライン → 統合 → フロントエンド → テストのフェーズで段階的に進めます。**全質問（既存53問 + 新規35問 = 88問）に統一3層パイプラインを適用**し、エージェントの行動規範を Rule Hierarchy として集約します。後方互換性は不要（再回答前提）です。

## Tasks

- [x] 1. コアインフラストラクチャ（モジュール・モデル・設定）
  - [x] 1.1 Decision Engine モジュール構造とモデル定義
    - `backend/app/decision_engine/__init__.py` を作成
    - `backend/app/decision_engine/config.py` に `DecisionEngineSettings` を実装（env_prefix="DECISION_"、feedback_threshold、weight_adjustment_step、confidence_mapping 等）
    - `backend/app/decision_engine/models.py` に全 Pydantic モデルを実装（FeedbackType, Permanence, NormalizationTagType, NormalizationTag, AnswerMetadata, ThreeLayerAnswerModel, FeedbackSubmission, FeedbackResponse, FeedbackListResponse, ModificationHistoryEntry, DecisionModelOutput, FailurePatternsOutput, ContextAdaptationOutput, ReasoningFlowOutput, RuleHierarchyOutput, AnswerMetadataSummary）
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.3, 16.1, 17.6_

  - [x] 1.2 ProfileOutput モデル拡張
    - `backend/app/models/profile.py` の `ProfileOutput` に新規フィールドを追加（decision_model, failure_patterns, context_adaptation, reasoning_flow, decision_rules, rule_hierarchy, modification_history, answer_metadata_summary）
    - decision_rules と rule_hierarchy は全質問から生成される必須フィールドとして定義
    - _Requirements: 6.1, 6.9, 12.1, 12.4_

  - [x] 1.3 質問データファイル拡張（questions.yaml）
    - decision_model カテゴリ（order: 7, dm_001〜dm_010, 4択 + Other）
    - tradeoff_scenarios カテゴリ（order: 8, ts_001〜ts_008, format: binary_choice, 2択）
    - failure_patterns カテゴリ（order: 9, fp_001〜fp_007, 4択 + Other）
    - context_adaptation カテゴリ（order: 10, ca_001〜ca_005, 4択 + Other）
    - reasoning_flow カテゴリ（order: 11, rf_001〜rf_005, ordering×2 + single_select×3）
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 5.2, 5.3, 5.4, 13.1, 13.2, 13.3, 13.4_

  - [x] 1.4 Mapping Dictionary 全面拡張（mapping_dictionary.json）
    - **既存エントリ全件に policy_text + normalized_tags を追記**（bos_001〜bos_009, com_001〜com_009, lif_001〜lif_009 の全選択肢）
    - decision_model: 各質問×各選択肢の priority_labels + weights + policy_text + normalized_tags
    - tradeoff_scenarios: 各質問×各選択肢の conflict_pair + tendency_score + policy_text + normalized_tags
    - failure_patterns: 各質問×各選択肢の subcategory + label + policy_text + normalized_tags
    - context_adaptation: 各質問×各選択肢の mode_name + mode_config + trigger + policy_text + normalized_tags
    - reasoning_flow: single_select 質問の verification_method / learning_style マッピング + policy_text
    - _Requirements: 1.3, 2.3, 3.3, 4.3, 5.7, 12.2, 13.5_

  - [x] 1.5 DI コンテナ（dependencies.py）
    - `backend/app/decision_engine/dependencies.py` に FastAPI Depends 用のファクトリ関数を実装
    - DecisionScorer, AnswerPipeline, RuleAggregator, FeedbackService, ModeDetector のインスタンス生成
    - _Requirements: 14.1_

- [~] 2. Checkpoint - コアインフラ検証
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Decision Scorer 実装
  - [~] 3.1 DecisionScorer クラス実装
    - `backend/app/decision_engine/scorer.py` に DecisionScorer を実装
    - `score_decision_model`: Mapping Dictionary 参照 → priority_label → weight_increment 返却
    - `score_tradeoff`: conflict_pair_name + tendency_score 返却
    - `score_failure_pattern`: subcategory + label_string 返却
    - `score_context_adaptation`: mode_name → {tone, detail, focus} 返却
    - `normalize_weights`: (value - min) / (max - min) 正規化、全値 [0.0, 1.0]、最大値 1.0 保証
    - `MappingNotFoundError` 例外クラス定義
    - _Requirements: 1.4, 1.5, 1.7, 2.4, 2.5, 3.4, 3.5, 4.4, 4.5, 5.7_

  - [~] 3.2 Property Test: Priority Weight 正規化（Property 1）
    - **Property 1: Priority Weight 正規化の不変条件**
    - Hypothesis で非空辞書に対し normalize_weights の出力が [0.0, 1.0] 範囲、最大値 1.0、小数点2桁を検証
    - **Validates: Requirements 1.7**

  - [~] 3.3 Property Test: Tradeoff Tendency スコア範囲（Property 2）
    - **Property 2: Tradeoff Tendency スコア範囲制約**
    - choice "a" → [0.0, 0.3], choice "b" → [0.7, 1.0] を全ペアで検証
    - **Validates: Requirements 2.4**

  - [~] 3.4 Property Test: 無効マッピングの一貫した拒否（Property 3）
    - **Property 3: 無効マッピングの一貫した拒否**
    - 存在しない question_id/choice_id の組み合わせで MappingNotFoundError を検証
    - **Validates: Requirements 1.5, 2.5, 3.5, 4.5, 5.7**

  - [~] 3.5 Property Test: Failure Pattern サブカテゴリ分類（Property 5）
    - **Property 5: Failure Pattern サブカテゴリ分類の妥当性**
    - 全 valid ペアで分類結果が4サブカテゴリのいずれかに属することを検証
    - **Validates: Requirements 3.4**

  - [~] 3.6 Property Test: Context Adaptation モード設定構造（Property 6）
    - **Property 6: Context Adaptation モード設定構造の妥当性**
    - tone ≤50文字, detail ∈ {"minimal","standard","comprehensive"}, focus ≤50文字 を検証
    - **Validates: Requirements 4.4**

  - [~] 3.7 Property Test: 確信度による重み乗算（Property 13）
    - **Property 13: 確信度による重み乗算の正確性**
    - base_weight (1〜10) × confidence (0.2〜1.0) = 実効重み増分を検証
    - **Validates: Requirements 17.4**

- [ ] 4. Answer Pipeline 実装
  - [~] 4.1 AnswerPipeline クラス実装
    - `backend/app/decision_engine/answer_pipeline.py` に AnswerPipeline を実装
    - `init_db`: answer_layers テーブル + インデックス作成
    - `process_predefined`: 定義済み選択肢 → 3層変換（LLM 不要）
    - `process_free_text`: 自由記述 → LLM 正規化 → 3層変換（失敗時 pending）
    - `re_normalize_pending`: pending エントリの再処理
    - `get_all_policies`: セッション全ポリシー取得
    - _Requirements: 16.1, 16.2, 16.3, 16.5, 17.6_

  - [~] 4.2 LLMNormalizer クラス実装
    - `backend/app/decision_engine/normalizer_llm.py` に LLMNormalizer を実装
    - `normalize`: 自由記述 → NormalizationResult (tags + policy_text)
    - `_build_prompt`: 正規化用プロンプト構築
    - `_parse_response`: LLM レスポンスパース
    - VALID_TAG_TYPES: value_tag, behavior_tag, prohibition_tag, condition_tag
    - リトライ（最大2回、exponential backoff）
    - _Requirements: 16.2_

  - [~] 4.3 Property Test: Ordering 回答の順序保存（Property 7）
    - **Property 7: Ordering 回答の順序保存**
    - 任意の step choice_id 順列が DB にそのまま保存されることを検証
    - **Validates: Requirements 5.6**

- [ ] 5. Rule Aggregator 実装
  - [~] 5.1 RuleAggregator クラス実装
    - `backend/app/decision_engine/rule_aggregator.py` に RuleAggregator を実装
    - `aggregate`: 全ポリシーを4層ヒエラルキー（core_invariants, context_rules, exceptions, preferences）に分類
    - `_classify_rule`: confidence / is_core_rule / normalization_tags による分類ロジック
    - MAX_CORE_INVARIANTS = 10 上限制御
    - _Requirements: 16.6, 17.5_

  - [~] 5.2 Property Test: Rule Hierarchy 分類の排他性と網羅性（Property 12）
    - **Property 12: Rule Hierarchy 分類の排他性と網羅性**
    - 各ルールが1層にのみ分類され、全ルールがいずれかの層に含まれることを検証
    - **Validates: Requirements 16.6**

  - [~] 5.3 Property Test: Core Invariant 候補の分類基準と上限（Property 14）
    - **Property 14: Core Invariant 候補の分類基準と上限**
    - confidence ≥ 0.8 AND permanence = "permanent" の条件、上限10件を検証
    - **Validates: Requirements 17.5**

- [ ] 6. Feedback Service 実装
  - [~] 6.1 FeedbackService クラス実装
    - `backend/app/decision_engine/feedback_service.py` に FeedbackService を実装
    - `init_db`: feedback_records テーブル + インデックス作成
    - `record_feedback`: フィードバック記録（reject 時 user_correction 必須バリデーション）
    - `check_and_adjust`: 10件以上 reject 蓄積時の重み調整（±0.1、0.0〜1.0 クランプ）
    - `get_modification_history`: 変更履歴取得
    - `_extract_dimension_keywords`: 修正テキストからキーワード抽出
    - `_adjust_weight`: 重み調整 + クランプ
    - _Requirements: 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

  - [~] 6.2 Property Test: フィードバック記録のラウンドトリップ（Property 8）
    - **Property 8: フィードバック記録のラウンドトリップ**
    - 送信した全フィールドが取得時に変更なく保持されることを検証
    - **Validates: Requirements 11.3**

  - [~] 6.3 Property Test: 重み調整のクランプ不変条件（Property 9）
    - **Property 9: 重み調整のクランプ不変条件**
    - w ∈ [0.0, 1.0], step = 0.1 で調整後の値が [0.0, 1.0] 範囲内を検証
    - **Validates: Requirements 11.5**

- [ ] 7. Mode Detector 実装
  - [~] 7.1 ModeDetector クラス実装
    - `backend/app/decision_engine/mode_detector.py` に ModeDetector を実装
    - `detect_mode`: メッセージ + 直近5ターンからモード判定
    - `get_mode_config`: mode_name → {tone, detail, focus}
    - `format_mode_prompt`: "## Current Mode: {mode_name}" 形式のプロンプト生成
    - `_check_urgency_triggers`: 緊急性トリガー検出
    - `_check_audience_triggers`: 聴衆依存トリガー検出
    - `_check_mental_state_triggers`: 認知状態トリガー検出
    - EMERGENCY_EXIT_THRESHOLD = 3（緊急モード解除条件）
    - _Requirements: 9.1, 9.2, 9.3_

  - [~] 7.2 Property Test: モード検出と switch_trigger の一致性（Property 15）
    - **Property 15: モード検出と switch_trigger の一致性**
    - switch_triggers 条件に合致するメッセージで対応モード名を返し、非合致で None を返すことを検証
    - **Validates: Requirements 9.1**

- [~] 8. Checkpoint - バックエンドコア検証
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. REST API エンドポイント実装
  - [~] 9.1 Decision Engine ルーター実装
    - `backend/app/decision_engine/routes.py` に FastAPI APIRouter を実装
    - POST /api/feedback: フィードバック記録（201 返却）
    - GET /api/feedback/{agent_id}: フィードバック一覧（limit/offset ページネーション）
    - GET /api/profiles/{profile_id}/modification-history: 変更履歴
    - GET /api/profiles/{profile_id}/decision-engine: decision engine データ取得
    - POST /api/sessions/{id}/re-normalize: pending 再処理
    - エラーハンドリング（404/422）
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

  - [~] 9.2 メインルーターへの統合
    - `backend/app/api/routes.py` に decision_router を include
    - _Requirements: 14.1_

  - [~] 9.3 API エンドポイントのユニットテスト
    - POST /api/feedback の正常系・異常系（422, 404）
    - GET /api/feedback/{agent_id} のページネーション
    - GET /api/profiles/{profile_id}/decision-engine の正常系・404
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

- [ ] 10. 既存モジュール統合
  - [~] 10.1 ProfileGenerator 拡張
    - `backend/app/core/profile_generator.py` に統一3層パイプライン集約 + decision engine セクション生成を追加
    - `_build_decision_rules`: AnswerPipeline から全質問（既存+新規88問）のポリシーを収集
    - `_build_rule_hierarchy`: RuleAggregator 経由で全ルールを4層集約（core_invariants > context_rules > exceptions > preferences）
    - `_build_decision_model`: priorities + priority_weights + escalation_rules + auto_approve_scope + tradeoff_tendencies
    - `_build_failure_patterns`: 4サブカテゴリ分類
    - `_build_context_adaptation`: modes + switch_triggers
    - `_build_reasoning_flow`: default_steps + verification_method + learning_style
    - `_build_answer_metadata_summary`: 統計サマリ
    - decision_rules と rule_hierarchy は全セッションで必ず生成（全質問にパイプライン適用）
    - 4軸スコア由来の base_os は従来通り並行生成（補助指標）
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 12.1, 12.4, 12.5, 12.7, 12.8, 16.4, 16.6, 17.5, 17.8_

  - [~] 10.2 Property Test: 部分完了時のセクション非生成（Property 4）
    - **Property 4: 部分完了時のセクション非生成**
    - 各カテゴリ未完了時に該当セクション出力が None であることを検証
    - **Validates: Requirements 1.8, 2.7, 3.7, 4.8, 5.10**

  - [~] 10.3 Property Test: 4軸スコアとパイプラインの並行動作（Property 10）
    - **Property 10: 4軸スコアとパイプラインの並行動作**
    - 全質問に3層パイプラインが適用されても、4軸スコア（base_os.axes, decision_style, do_not_list）の計算結果が従来ロジックと同一であることを検証
    - **Validates: Requirements 12.7**
    - **Validates: Requirements 12.3**

  - [~] 10.4 PromptEngine テンプレート拡張
    - `backend/app/evolution/prompt_engine.py` の Jinja2 テンプレートに Decision Framework / Known Weaknesses / Context Adaptation / Reasoning Process セクション追加
    - truncation 優先順位: reasoning_flow → context_adaptation → failure_patterns → decision_model
    - max_tokens (default 4000) 制限遵守
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [~] 10.5 Property Test: プロンプトトークン制限遵守（Property 11）
    - **Property 11: プロンプトトークン制限遵守**
    - 任意の decision engine セクション組み合わせで max_tokens を超過しないことを検証
    - **Validates: Requirements 7.6**

  - [~] 10.6 ChatService 拡張
    - `backend/app/evolution/chat.py` に ModeDetector を統合
    - `_detect_and_apply_mode`: モード検出 → システムプロンプト追記
    - `_index_failure_patterns`: failure_patterns を search_memory 用にインデックス
    - context_adaptation なしの場合スキップ（性能ペナルティなし）
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [~] 10.7 DiscussionEngine 拡張
    - `backend/app/evolution/discussion_engine.py` に decision model 注入
    - `_build_decision_prompt_section`: priorities + reasoning_flow をプロンプトに追加
    - `_build_conflict_directives`: tradeoff_tendencies 差 ≥ 0.4 で立場維持指示生成
    - トークン制限（4000）遵守、reasoning_flow から truncation
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [~] 10.8 Property Test: Discussion 対立指示の生成条件（Property 16）
    - **Property 16: Discussion 対立指示の生成条件**
    - tradeoff_tendencies 差の絶対値 ≥ 0.4 の場合に立場維持指示が含まれることを検証
    - **Validates: Requirements 10.3**

  - [~] 10.9 PackageGenerator 拡張
    - `backend/app/evolution/package_generator.py` に decision engine データのパッケージ生成を追加
    - system_prompt.md に "## Decision Framework" / "## Self-Awareness" 追加
    - skills/decision-rules/SKILL.md 生成
    - tools/reasoning_flow.json 生成
    - config.json に context_adaptation 追加
    - decision engine データなしの場合は追加ファイルを生成しない（後方互換性）
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [~] 11. Checkpoint - バックエンド統合検証
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. フロントエンド実装
  - [~] 12.1 TypeScript 型定義
    - `frontend/src/types/decision.ts` に全インターフェース定義（ThreeLayerAnswer, AnswerMetadata, FeedbackPayload, FeedbackRecord, ModificationHistoryEntry, OrderingChoice, DecisionEngineData）
    - _Requirements: 16.1, 11.3, 17.1_

  - [~] 12.2 BinaryChoice.vue コンポーネント
    - `frontend/src/components/decision/BinaryChoice.vue` を実装
    - トレードオフ質問用2択カード UI
    - 選択時ハイライト、排他的選択
    - _Requirements: 2.2_

  - [~] 12.3 OrderingDnD.vue コンポーネント
    - `frontend/src/components/decision/OrderingDnD.vue` を実装
    - Fisher-Yates シャッフルによる初期順序ランダム化
    - ドラッグ&ドロップ（ドロップシャドウ + 挿入ライン + 200ms アニメーション）
    - 768px 以下でナンバー入力フォールバック（重複バリデーション）
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 5.5_

  - [~] 12.4 MetadataPanel.vue コンポーネント
    - `frontend/src/components/decision/MetadataPanel.vue` を実装
    - 展開可能パネル（permanence トグル、confidence スライダー★1〜5、exception_note テキストエリア 200文字制限）
    - デフォルト値適用（未操作時: permanent, 0.6, null, false, 0.0）
    - _Requirements: 17.1, 17.2, 17.3_

  - [~] 12.5 FeedbackButtons.vue コンポーネント
    - `frontend/src/components/decision/FeedbackButtons.vue` を実装
    - 3ボタン: 👍「私らしい」/ ✏️「私ならこう言わない」/ ⏭️「スキップ」
    - reject 時テキストエリア展開（2000文字制限 + カウンター）
    - _Requirements: 11.1, 11.2_

  - [~] 12.6 Composable: useDecisionSurvey.ts
    - `frontend/src/components/decision/composables/useDecisionSurvey.ts` を実装
    - Decision Engine 質問の取得・回答送信・メタデータ管理
    - _Requirements: 1.2, 2.2, 3.2, 4.2, 5.5_

  - [~] 12.7 Composable: useFeedback.ts
    - `frontend/src/components/decision/composables/useFeedback.ts` を実装
    - フィードバック送信・一覧取得・変更履歴取得 API クライアント
    - _Requirements: 11.1, 11.2, 11.7_

  - [~] 12.8 フロントエンドユニットテスト
    - BinaryChoice.vue: 排他的選択・イベント発火テスト
    - OrderingDnD.vue: 順序変更・モバイルフォールバックテスト
    - MetadataPanel.vue: デフォルト値・展開/折り畳みテスト
    - FeedbackButtons.vue: ボタン表示・テキストエリア展開・文字数制限テスト
    - _Requirements: 2.2, 15.1, 17.1, 11.1_

- [~] 13. Checkpoint - フロントエンド検証
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. 最終統合とワイヤリング
  - [~] 14.1 Survey UI への Decision Engine カテゴリ統合
    - 既存 Survey フロー（order: 4〜6 の後）に decision engine カテゴリ（order: 7〜11）を追加
    - format に応じた UI コンポーネント切り替え（single_select / binary_choice / ordering）
    - MetadataPanel の各質問への統合
    - _Requirements: 12.5, 1.2, 2.2, 3.2, 4.2, 5.5, 17.1, 17.7_

  - [~] 14.2 全質問統一パイプライン E2E テスト
    - 全88問回答 → 3層変換 → Rule Hierarchy 集約 → ProfileOutput 生成の完全フロー
    - 既存カテゴリ（BOS/COM/LIF）の回答から policy_text が正しく生成されることを検証
    - Rule Hierarchy に既存カテゴリ由来のルールが含まれることを検証
    - PromptEngine が Rule Hierarchy を4軸base_osより優先してプロンプトに含めることを検証
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.7, 12.8_

- [~] 15. Final Checkpoint - 全テスト実行
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- タスクに `*` マークが付いたサブタスクは Optional（PBT / ユニットテスト）でありスキップ可能です
- 各タスクは参照する要件番号（Requirements）を明記し、トレーサビリティを確保しています
- Checkpoint タスクではコミットせず、テスト確認のみ行います
- Property-Based Tests は Hypothesis ライブラリ（プロジェクト既存）を使用します
- フロントエンドテストは Vitest + Vue Test Utils を使用します
- バックエンドテストは pytest を使用します

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3", "1.4"] },
    { "id": 1, "tasks": ["1.2", "1.5"] },
    { "id": 2, "tasks": ["3.1", "4.2"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "4.1"] },
    { "id": 4, "tasks": ["4.3", "5.1", "6.1", "7.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "6.2", "6.3", "7.2"] },
    { "id": 6, "tasks": ["9.1", "9.2"] },
    { "id": 7, "tasks": ["9.3", "10.1"] },
    { "id": 8, "tasks": ["10.2", "10.3", "10.4"] },
    { "id": 9, "tasks": ["10.5", "10.6", "10.7", "10.9"] },
    { "id": 10, "tasks": ["10.8", "12.1"] },
    { "id": 11, "tasks": ["12.2", "12.3", "12.4", "12.5"] },
    { "id": 12, "tasks": ["12.6", "12.7"] },
    { "id": 13, "tasks": ["12.8", "14.1"] },
    { "id": 14, "tasks": ["14.2"] }
  ]
}
```
