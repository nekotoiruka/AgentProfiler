# Implementation Plan: Agent Profiler

## Overview

Agent Profilerの実装計画です。バックエンド（FastAPI + Python 3.12+）のコアロジックを先に構築し、フロントエンド（Vue 3 + TypeScript + Pinia）を接続、最後に統合テストで仕上げます。データファイル（YAML質問 + JSON Mapping Dictionary）とドキュメントを並行して整備します。

## Tasks

- [x] 1. プロジェクト構造とコアインターフェース定義
  - [x] 1.1 モノリポのディレクトリ構造とバックエンド初期セットアップ
    - `backend/` ディレクトリ作成、`pyproject.toml`（FastAPI, Pydantic v2, aiosqlite, PyYAML, Hypothesis, pytest依存）
    - `backend/app/main.py` にFastAPIアプリケーション骨格を作成
    - `backend/app/api/`, `backend/app/core/`, `backend/app/models/`, `backend/app/services/` ディレクトリ作成
    - `backend/data/` ディレクトリ作成
    - `backend/tests/unit/`, `backend/tests/property/`, `backend/tests/integration/` ディレクトリ作成
    - _Requirements: 11.11_

  - [x] 1.2 フロントエンド初期セットアップ
    - `frontend/` ディレクトリにVite + Vue 3 + TypeScript プロジェクトを作成
    - Pinia, vue-chartjs (Chart.js), vue-router を依存に追加
    - `frontend/src/components/`, `frontend/src/views/`, `frontend/src/composables/`, `frontend/src/stores/`, `frontend/src/types/` ディレクトリ構成
    - Vitest + Vue Test Utils をdevDependenciesに追加
    - _Requirements: 1.1_

  - [x] 1.3 Pydanticデータモデル定義
    - `backend/app/models/` に以下のモデルを定義:
      - `AxisScores` (4軸int), `NormalizedScores` (4軸float 0.00-1.00)
      - `Answer` (question_id, choice_id?, text?, submitted_at)
      - `Session` (session_id, status, answers, raw_scores, normalized_scores, profile_id, timestamps)
      - `Question`, `Choice`, `Category` (質問データ構造)
      - `MappingEntry`, `MappingDictionary` (マッピング辞書構造)
      - `ProfileOutput` (profile_id, base_os, lexical_tags, semantic_contexts, context_layers)
    - APIリクエスト/レスポンスのスキーマモデル
    - _Requirements: 3.2, 3.7, 5.1, 6.1, 6.2, 6.8, 9.1, 10.4, 11.11_

  - [x] 1.4 TypeScript型定義
    - `frontend/src/types/` に以下の型を定義:
      - `Question`, `Choice`, `Category` インターフェース
      - `Session`, `SessionStatus` インターフェース
      - `AnswerSubmission` (predefined choice / other text)
      - `ProfileOutput`, `BaseOS`, `NormalizedScores` インターフェース
      - API レスポンス型
    - _Requirements: 1.1, 6.1, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

- [x] 2. データファイルとマッピング辞書
  - [x] 2.1 マッピング辞書JSONファイル作成
    - `backend/data/mapping_dictionary.json` を作成
    - `metadata.theoretical_bounds` に各軸の理論的最小/最大値を定義
    - 質問ごと・選択肢ごとの4軸スコア（-10〜+10の整数）を定義
    - 各エントリが question_id, choice_id, 4軸スコアを全て含むことを保証
    - _Requirements: 4.1, 4.2, 4.5_

  - [x] 2.2 質問データYAMLファイル作成
    - `backend/data/questions.yaml` を作成
    - カテゴリ順序: Business OS → Communication → Lifestyle/Hobbies
    - 各カテゴリ最低3問、合計12〜30問
    - 各質問: id, text(≤200文字), category, 4選択肢(各id + label≤100文字), source_reference
    - 各質問が最低2軸を活性化するように設計
    - _Requirements: 9.1, 9.2, 9.3, 9.6, 9.8, 9.9_

  - [x] 2.3 心理測定ソースドキュメント作成
    - `docs/psychometric_sources.md` を作成
    - OEJTS: 4二分法構造、項目形式、スコアリング方法、CC BY-NC-SA 4.0ライセンス
    - IPIP-NEO-120: 5因子構造、30ファセット、120項目、パブリックドメイン
    - IPIP一般リポジトリ: 利用可能なスケール、パブリックドメイン、3,000+項目
    - 各ソースのFour_Axisへのマッピング（direct/inverse/partial/none）
    - 適応戦略（抽象特性→ビジネスシナリオ変換）
    - 各項目の分類（directly usable / require adaptation / design reference only）
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [x] 3. バックエンド コアロジック実装
  - [x] 3.1 Scoring Engine実装
    - `backend/app/core/scoring.py` に `ScoringEngine` クラスを実装
    - `apply_score()`: Mapping Dictionaryから4軸スコアを検索し累積加算
    - `apply_neutral()`: Other選択時は全軸0（スコア不変）を返す
    - マッピング不在時はエラーを返しスコアを変更しない
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.6_

  - [x] 3.2 Scoring Engine プロパティテスト
    - **Property 1: Score accumulation is commutative sum**
    - **Property 2: Neutral score invariant**
    - **Property 4: Missing mapping produces error without side effects**
    - **Validates: Requirements 3.1, 3.3, 3.4, 3.6, 4.7**

  - [x] 3.3 Normalizer実装
    - `backend/app/core/normalizer.py` に `Normalizer` クラスを実装
    - min-max正規化: `(raw - min) / (max - min)`
    - クランプ: 範囲外は0.0/1.0に制限
    - round-half-up 小数点2桁
    - min == max の場合は 0.5 を返しwarningログ出力
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 3.4 Normalizer プロパティテスト
    - **Property 5: Normalization bounds and formula**
    - **Validates: Requirements 5.1, 5.3, 5.4**

  - [x] 3.5 Profile Generator実装
    - `backend/app/core/profile_generator.py` に `ProfileGenerator` クラスを実装
    - `profile_id` 生成: `prof_` + 6桁ゼロパディング連番
    - `base_os.axes`: 4軸正規化スコア
    - `base_os.decision_style`: スコア>0.50→第1極、<0.50→第2極、==0.50→_balanced
    - `base_os.do_not_list`: スコア<0.30 or >0.70の軸から1〜4項目生成
    - `lexical_tags`: 回答から抽出、小文字、`[a-z0-9\-./]+`、5〜50件、重複なし
    - `semantic_contexts`: 固定ドメインキー、50〜500語の自然言語段落
    - `context_layers`: base_os→1, lexical_tags→2, semantic_contexts→3
    - lexical_tagsとsemantic_contextsのデータ分離保証
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 3.6 Profile Generator プロパティテスト
    - **Property 6: Profile output structural completeness**
    - **Property 7: Decision style derivation correctness**
    - **Property 8: Do-not-list generation from polarity**
    - **Property 9: Lexical tag format and uniqueness**
    - **Property 10: Semantic contexts structure**
    - **Property 11: Data separation between tags and contexts**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 13.1, 13.2, 13.3, 13.4**

- [x] 4. Checkpoint - バックエンドコアロジック検証
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. データロードとバリデーション
  - [x] 5.1 Mapping Dictionary ローダー実装
    - `backend/app/services/data_loader.py` に実装
    - 起動時にJSONファイルをロード
    - 各エントリのバリデーション: question_id, choice_id, 4軸スコア(-10〜+10)
    - 不正エントリはログ出力して除外、有効エントリのみ使用
    - ファイル不在/パース不能時は起動失敗
    - リクエスト毎にファイル変更を検知して再ロード（ホットリロード）
    - _Requirements: 4.1, 4.3, 4.4, 4.6_

  - [x] 5.2 Question Data ローダー実装
    - `backend/app/services/data_loader.py` に追加実装
    - YAMLファイルからカテゴリ順にロード
    - バリデーション: 必須フィールド、文字数制限、選択肢数(4)、重複ID、source_reference
    - Mapping Dictionaryとの整合性チェック（マッピング不在質問を除外）
    - 各質問が2軸以上を活性化することを検証
    - セッション開始時にファイル変更を反映
    - _Requirements: 9.1, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [x] 5.3 データバリデーション プロパティテスト
    - **Property 3: Mapping entry schema validation**
    - **Property 14: Question ordering invariant**
    - **Property 16: Question data validation**
    - **Validates: Requirements 3.2, 3.7, 4.2, 4.4, 9.5, 9.6, 9.7**

- [x] 6. セッション管理
  - [x] 6.1 Session Manager実装
    - `backend/app/services/session_manager.py` に `SessionManager` クラスを実装
    - SQLite (aiosqlite) によるセッション永続化
    - `create_session()`: UUID生成、ステータス"active"
    - `submit_answer()`: 回答保存（上書き対応）、タイムスタンプ記録
    - `get_session()`: セッション取得
    - `is_complete()`: 全質問回答済みチェック
    - `mark_complete()`: ステータスを"complete"に変更、以降回答拒否
    - 30日超非活動セッションを"expired"に遷移、回答拒否
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [x] 6.2 Session Manager プロパティテスト
    - **Property 12: Session answer persistence round-trip**
    - **Property 13: Session state machine transitions**
    - **Validates: Requirements 10.1, 10.3, 10.5, 10.6, 10.7**

  - [x] 6.3 Progress計算 プロパティテスト
    - **Property 15: Progress percentage calculation**
    - **Validates: Requirements 1.3, 1.4**

- [x] 7. REST APIエンドポイント
  - [x] 7.1 APIルートハンドラー実装
    - `backend/app/api/routes.py` に6エンドポイントを実装:
      - `POST /api/sessions` → 新規セッション作成
      - `POST /api/sessions/{id}/answers` → 回答送信（choice_id or text、500文字制限）
      - `GET /api/sessions/{id}/status` → ステータス取得（answered, total, category）
      - `GET /api/questions` → 質問一覧（カテゴリ別）
      - `POST /api/sessions/{id}/calculate` → スコア計算 + プロファイル生成
      - `GET /api/sessions/{id}/profile` → プロファイルJSON取得
    - エラーハンドリング: 404 (不明セッション/未生成プロファイル), 422 (バリデーション), 409 (未完了/変更不可)
    - 全レスポンス JSON format, Content-Type: application/json
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10, 11.11_

  - [x] 7.2 API統合テスト
    - 全6エンドポイントの正常系テスト
    - エラー系テスト: 不正セッションID(404), 不正リクエスト(422), 未完了計算(409), 未生成プロファイル(404)
    - 完全フロー: セッション作成→回答→計算→プロファイル取得
    - _Requirements: 11.7, 11.8, 11.9, 11.10_

- [x] 8. Checkpoint - バックエンド全体検証
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. フロントエンド コアコンポーネント実装
  - [x] 9.1 Pinia ストアとAPI通信層
    - `frontend/src/stores/session.ts`: セッションID管理、回答送信、ステータス取得
    - `frontend/src/stores/survey.ts`: 質問データ、進捗計算、現在の質問管理
    - `frontend/src/composables/useApi.ts`: Fetch wrapper、エラーハンドリング（リトライ、指数バックオフ）
    - _Requirements: 10.1, 10.2, 11.1, 11.2, 11.3_

  - [x] 9.2 QuestionCardコンポーネント
    - `frontend/src/components/QuestionCard.vue`
    - カードフリップアニメーション（300〜500ms）forward/backward対応
    - 4つの選択肢ボタン + "Other"オプション（排他的選択）
    - Other選択時: テキストエリア（slide-in 300ms、500文字制限、文字数カウント表示）
    - Other解除時: テキストエリア非表示＋内容クリア
    - Nextボタン: 未選択かつOtherテキスト空白時は disabled
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 9.3 ProgressBarコンポーネント
    - `frontend/src/components/ProgressBar.vue`
    - カテゴリ名表示
    - カテゴリ内進捗: (回答済み / カテゴリ内質問数) × 100（整数%）
    - 全体進捗: (全回答数 / 全質問数) × 100（整数%）
    - _Requirements: 1.3, 1.4_

  - [x] 9.4 SurveyViewページ
    - `frontend/src/views/SurveyView.vue`
    - セッション開始 → 質問ロード → 最初の質問表示
    - カテゴリ順に質問を順次表示（Business OS → Communication → Lifestyle/Hobbies）
    - 回答送信 → 次の質問へ遷移
    - 戻るナビゲーション（前の回答を保持、逆方向アニメーション）
    - 最後の質問回答後 → ResultsDashboardへ遷移
    - セッション復帰: 未回答の最初の質問から再開
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 1.7, 2.4, 2.5, 10.2_

  - [x] 9.5 フロントエンド コンポーネントテスト
    - QuestionCard: 選択肢選択、Other表示/非表示、文字数制限
    - ProgressBar: 進捗計算、表示
    - SurveyView: ナビゲーション、セッション復帰
    - Vitest + Vue Test Utils
    - _Requirements: 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.6_

- [x] 10. フロントエンド 結果ダッシュボード
  - [x] 10.1 ResultsDashboardView実装
    - `frontend/src/views/ResultsDashboardView.vue`
    - レーダーチャート: 4軸正規化スコア (0.0〜1.0) 軸ラベル付き (vue-chartjs)
    - JSON プレビュー: スクロール可能コードブロック＋シンタックスハイライト
    - コピーボタン: クリップボードにJSON全文コピー、成功時2秒確認表示、失敗時エラーメッセージ
    - decision_style ラベルを見出し表示
    - do_not_list を箇条書き表示
    - lexical_tags をチップリスト表示
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 10.2 ResultsDashboard テスト
    - レーダーチャート描画確認
    - クリップボードコピー成功/失敗
    - JSONプレビュー表示
    - Vitest + Vue Test Utils
    - _Requirements: 7.1, 7.3, 7.4_

- [x] 11. Checkpoint - フロントエンド検証
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. 統合とワイヤリング
  - [x] 12.1 フロントエンド↔バックエンド接続
    - Vite dev serverのAPIプロキシ設定 (`vite.config.ts`)
    - CORS設定 (`backend/app/main.py`)
    - API base URL環境変数化
    - エラーハンドリング: リトライ、セッション期限切れ処理、404リダイレクト
    - _Requirements: 11.1, 11.7, 11.8_

  - [x] 12.2 Vue Routerセットアップ
    - `/survey` → SurveyView
    - `/results` → ResultsDashboardView
    - セッション完了時の自動遷移
    - _Requirements: 1.7_

  - [x] 12.3 End-to-End統合テスト
    - セッション作成→全質問回答→計算→プロファイル表示の完全フロー
    - セッション復帰フロー
    - エラーハンドリングフロー
    - _Requirements: 1.7, 10.2, 10.3_

- [x] 13. Final checkpoint - 全テスト実行
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (16 properties defined in design)
- Backend (Python): pytest + Hypothesis for property-based tests
- Frontend (TypeScript): Vitest + Vue Test Utils for component tests
- Data files (YAML/JSON) are designed for hot-reload without restart

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "2.3"] },
    { "id": 2, "tasks": ["2.1", "2.2"] },
    { "id": 3, "tasks": ["3.1", "3.3", "5.1"] },
    { "id": 4, "tasks": ["3.2", "3.4", "5.2"] },
    { "id": 5, "tasks": ["3.5", "5.3"] },
    { "id": 6, "tasks": ["3.6", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3", "7.1"] },
    { "id": 8, "tasks": ["7.2"] },
    { "id": 9, "tasks": ["9.1"] },
    { "id": 10, "tasks": ["9.2", "9.3"] },
    { "id": 11, "tasks": ["9.4", "9.5"] },
    { "id": 12, "tasks": ["10.1"] },
    { "id": 13, "tasks": ["10.2", "12.1", "12.2"] },
    { "id": 14, "tasks": ["12.3"] }
  ]
}
```
