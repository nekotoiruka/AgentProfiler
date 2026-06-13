# Requirements Document

## Introduction

AgentProfiler フロントエンドのデザインシステム刷新。素の CSS を Tailwind CSS v4 + shadcn-vue に置き換え、Evolution ページを 3 タブ構成（agents / chat / discussion）でフルリビルドする。グローバルナビゲーション（App.vue）も Tailwind + shadcn-vue に統一する。Light テーマのみ、ニュートラル基調 + パープルアクセント (#6d28d9)。

## Glossary

- **Design_System**: Tailwind CSS v4 と shadcn-vue を基盤とするフロントエンド UI コンポーネント群およびスタイル設計の総称
- **Global_Nav**: App.vue に実装されるアプリケーション全体のナビゲーションバー
- **Evolution_Page**: `/evolution` ルートに対応するエージェント操作ページ（3 タブ構成）
- **Agents_Tab**: Evolution_Page 内でエージェント一覧表示と新規作成を行うタブ
- **Chat_Tab**: Evolution_Page 内でエージェントとの 1 対 1 チャットを行うタブ
- **Discussion_Tab**: Evolution_Page 内で複数エージェントによるディスカッションを閲覧するタブ
- **Agent_Drawer**: Chat_Tab においてエージェント切り替えに使用する shadcn-vue Sheet コンポーネントベースのサイドドロワー
- **shadcn_vue**: Vue 3 向けの UI コンポーネントライブラリ（コピー&ペースト方式でプロジェクトに組み込む）
- **Tailwind_CSS**: ユーティリティファーストの CSS フレームワーク（v4 を使用）

## Requirements

### Requirement 1: Tailwind CSS v4 と shadcn-vue の導入

**User Story:** As a 開発者, I want プロジェクトに Tailwind CSS v4 と shadcn-vue が正しく設定されている, so that 全コンポーネントで統一されたユーティリティクラスと UI パーツを利用できる

#### Acceptance Criteria

1. THE Design_System SHALL Tailwind CSS v4 を devDependencies としてインストールし Vite と統合する
2. THE Design_System SHALL shadcn-vue を初期化し、必要なコンポーネント（Button, Card, Tabs, Input, Select, Avatar, Badge, ScrollArea, Sheet）をプロジェクトに追加する
3. THE Design_System SHALL カラーテーマとして Light テーマのみを定義し、ニュートラルカラーとパープルアクセント (#6d28d9) を CSS 変数で設定する
4. THE Design_System SHALL 既存の Vue 3.5 + Vite 6 + TypeScript + Pinia + Vue Router 構成を変更せず共存する

### Requirement 2: グローバルナビゲーションの Tailwind + shadcn-vue 移行

**User Story:** As a ユーザー, I want アプリケーション全体のナビゲーションが統一されたデザインで表示される, so that どのページでも一貫した操作体験を得られる

#### Acceptance Criteria

1. THE Global_Nav SHALL 既存の素の CSS スタイルを削除し、Tailwind CSS ユーティリティクラスで再スタイリングする
2. THE Global_Nav SHALL アプリケーション名「Agent Profiler」をブランドロゴとして左端に表示する
3. THE Global_Nav SHALL 診断・結果・Evolution の 3 つのルートリンクを提供する
4. WHEN ユーザーが現在のルートに対応するリンクを閲覧する場合, THE Global_Nav SHALL アクティブ状態をパープルアクセント色で視覚的に示す
5. THE Global_Nav SHALL ビューポート上部に sticky 配置する

### Requirement 3: Evolution ページのタブナビゲーション

**User Story:** As a ユーザー, I want Evolution ページで agents / chat / discussion をタブで切り替えたい, so that 目的の機能に素早くアクセスできる

#### Acceptance Criteria

1. THE Evolution_Page SHALL shadcn-vue Tabs コンポーネントを使用して 3 タブ（エージェント / チャット / ディスカッション）を表示する
2. WHEN ユーザーがタブを切り替えた場合, THE Evolution_Page SHALL 選択されたタブのコンテンツのみを表示し、他タブのコンテンツを非表示にする
3. THE Evolution_Page SHALL デフォルトで「エージェント」タブをアクティブ状態で表示する

### Requirement 4: エージェント一覧タブ

**User Story:** As a ユーザー, I want 登録済みエージェントを一覧で確認し新規作成したい, so that エージェントの管理を効率的に行える

#### Acceptance Criteria

1. THE Agents_Tab SHALL 登録済みエージェントを shadcn-vue Card コンポーネントを用いたグリッドレイアウトで表示する
2. THE Agents_Tab SHALL 各エージェントカードに Avatar（表示名の頭文字）、表示名、プロファイル ID を含める
3. WHEN ユーザーがエージェントカードをクリックした場合, THE Agents_Tab SHALL Chat_Tab に遷移し当該エージェントを選択状態にする
4. THE Agents_Tab SHALL 新規エージェント作成フォーム（プロファイル選択 Select、名前入力 Input、作成 Button）を表示する
5. IF プロファイルが未登録の場合, THEN THE Agents_Tab SHALL 質問フローへの誘導メッセージを表示する
6. IF エージェントが 0 件の場合, THEN THE Agents_Tab SHALL 空状態の案内メッセージと質問フロー開始ボタンを表示する

### Requirement 5: フルスクリーンチャットタブ

**User Story:** As a ユーザー, I want エージェントとのチャットを画面全体で行いたい, so that 会話に集中でき情報を見やすくなる

#### Acceptance Criteria

1. THE Chat_Tab SHALL チャットエリアを画面の利用可能な高さ全体に拡張して表示する
2. THE Chat_Tab SHALL メッセージ一覧を shadcn-vue ScrollArea コンポーネントでスクロール可能に表示する
3. THE Chat_Tab SHALL 画面下部にメッセージ入力エリア（Input + 送信 Button）を固定配置する
4. WHEN メッセージの送信中またはストリーミング中の場合, THE Chat_Tab SHALL 入力フォームを無効状態にする
5. WHEN エージェントが未選択の場合, THE Chat_Tab SHALL エージェント選択を促すプレースホルダーメッセージを表示する

### Requirement 6: エージェント切り替えドロワー

**User Story:** As a ユーザー, I want チャット中に別のエージェントに素早く切り替えたい, so that 複数エージェントとの会話を効率的に行える

#### Acceptance Criteria

1. THE Agent_Drawer SHALL shadcn-vue Sheet コンポーネントを使用し、画面の左側からスライドインする
2. WHEN ユーザーがチャットヘッダーのエージェント切り替えボタンを押下した場合, THE Agent_Drawer SHALL 開いてエージェント一覧を表示する
3. THE Agent_Drawer SHALL 各エージェントを Avatar と表示名で一覧表示する
4. WHEN ユーザーがドロワー内のエージェントを選択した場合, THE Agent_Drawer SHALL 閉じて選択されたエージェントとのチャットスレッドに切り替える
5. THE Agent_Drawer SHALL 現在選択中のエージェントを Badge でハイライト表示する

### Requirement 7: ディスカッションタブ

**User Story:** As a ユーザー, I want 複数エージェント間のディスカッションを設定・観察したい, so that 多角的な議論の結果を確認できる

#### Acceptance Criteria

1. WHEN ディスカッションが未開始の場合, THE Discussion_Tab SHALL テーマ入力フィールドとエージェント選択 UI およびスタートボタンを表示する
2. WHILE ディスカッションがストリーミング中の場合, THE Discussion_Tab SHALL 各エージェントの発言をリアルタイムに表示し、進行状況インジケータを表示する
3. WHEN ディスカッションが完了した場合, THE Discussion_Tab SHALL 全ターンの会話履歴を表示し「新しいディスカッションを開始」ボタンを有効にする
4. IF エージェントが 2 体未満の場合, THEN THE Discussion_Tab SHALL ディスカッション開始に 2 体以上必要である旨のメッセージを表示する

### Requirement 8: 既存ページとの共存

**User Story:** As a 開発者, I want 既存ページ（SurveyView, ResultsDashboardView）が影響を受けない, so that 段階的にデザインシステムを適用できる

#### Acceptance Criteria

1. THE Design_System SHALL 既存の SurveyView および ResultsDashboardView の内部スタイルに変更を加えない
2. THE Design_System SHALL Tailwind CSS のプレフライト（リセット CSS）が既存ページのレイアウトを破壊しないよう設定する
3. THE Design_System SHALL 既存のルーティング構成（/survey, /results, /evolution）を維持する
