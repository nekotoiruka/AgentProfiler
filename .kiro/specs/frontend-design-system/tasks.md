# Implementation Plan: Frontend Design System

## Overview

Tailwind CSS v4 + shadcn-vue を導入し、Evolution ページを 3 タブ構成でフルリビルド。グローバルナビゲーションを Tailwind + shadcn-vue に統一し、既存ページ（SurveyView, ResultsDashboardView）には影響を与えない段階的移行を実施する。

## Tasks

- [ ] 1. Tailwind CSS v4 と shadcn-vue のセットアップ
  - [ ] 1.1 Tailwind CSS v4 をインストールし Vite に統合する
    - `@tailwindcss/vite` プラグインを devDependencies に追加
    - `vite.config.ts` に tailwindcss プラグインを追加
    - `src/assets/styles/globals.css` を作成し `@import "tailwindcss"` と `@theme` ブロックでカラーテーマ（ニュートラル + パープルアクセント #6d28d9）を定義
    - `src/main.ts` で globals.css をインポート
    - _Requirements: 1.1, 1.3, 1.4_

  - [ ] 1.2 shadcn-vue を初期化し必要なコンポーネントを追加する
    - shadcn-vue CLI でプロジェクトを初期化（`components.json` 生成）
    - Button, Card, Tabs, Input, Select, Avatar, Badge, ScrollArea, Sheet コンポーネントを追加
    - `src/components/ui/` 配下に各コンポーネントディレクトリが生成されることを確認
    - `tsconfig.json` のパスエイリアス設定を確認・調整
    - _Requirements: 1.2, 1.4_

- [ ] 2. グローバルナビゲーションの Tailwind + shadcn-vue 移行
  - [ ] 2.1 App.vue を Tailwind ユーティリティクラスで再スタイリングする
    - 既存の素の CSS スタイル（`<style>` ブロック）を削除
    - sticky ナビバーを実装（`sticky top-0 z-50`）
    - 左端に「Agent Profiler」ブランドロゴを配置
    - 診断・結果・Evolution の 3 ルートリンクを提供
    - アクティブリンクをパープルアクセント色（`text-primary bg-primary-muted`）で表示
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 2.2 グローバルナビゲーションのユニットテストを作成する
    - アクティブリンクの表示状態をテスト
    - 3 つのルートリンクが正しくレンダリングされることをテスト
    - _Requirements: 2.3, 2.4_

- [ ] 3. Checkpoint - ビルド確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Evolution ページのタブコンテナ実装
  - [ ] 4.1 EvolutionView.vue を shadcn-vue Tabs で再構築する
    - shadcn-vue Tabs / TabsList / TabsTrigger / TabsContent を使用
    - 3 タブ（エージェント / チャット / ディスカッション）を定義
    - デフォルトで「エージェント」タブをアクティブ表示
    - `activeTab` state と `selectedAgent` state を管理
    - プロファイル一覧の取得ロジックを含む
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 4.2 タブ切り替えのプロパティテストを作成する
    - **Property 2: Tab exclusivity**
    - **Validates: Requirements 3.2**

- [ ] 5. エージェント一覧タブの実装
  - [ ] 5.1 AgentsTab.vue コンポーネントを作成する
    - shadcn-vue Card でエージェントグリッド表示（1/2/3 列レスポンシブ）
    - 各カードに Avatar（頭文字）、表示名、プロファイル ID を含める
    - カードクリックで `select` イベントを emit
    - 新規エージェント作成フォーム（Select + Input + Button）を実装
    - プロファイル未登録時の誘導メッセージを表示
    - エージェント 0 件時の空状態 UI を表示
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 5.2 エージェントカード描画のプロパティテストを作成する
    - **Property 3: Agent card rendering fidelity**
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 5.3 エージェントカードクリックのプロパティテストを作成する
    - **Property 4: Agent card click navigates to chat**
    - **Validates: Requirements 4.3**

- [ ] 6. フルスクリーンチャットタブの実装
  - [ ] 6.1 ChatTab.vue コンポーネントを作成する
    - `h-[calc(100vh-220px)]` でフルスクリーン表示
    - shadcn-vue ScrollArea でメッセージ一覧をスクロール可能に
    - ChatThread コンポーネントを統合
    - エージェント未選択時のプレースホルダー表示
    - チャットヘッダーにエージェント情報と切り替えボタンを配置
    - _Requirements: 5.1, 5.2, 5.5_

  - [ ] 6.2 ChatInput.vue コンポーネントを Tailwind + shadcn-vue で再スタイリングする
    - 画面下部に固定配置
    - Input + 送信 Button の組み合わせ
    - `disabled` prop でストリーミング中の無効化に対応
    - _Requirements: 5.3, 5.4_

  - [ ]* 6.3 チャット入力無効化のプロパティテストを作成する
    - **Property 5: Chat input disabled during streaming or loading**
    - **Validates: Requirements 5.4**

- [ ] 7. Checkpoint - チャットタブ動作確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. エージェント切り替えドロワーの実装
  - [ ] 8.1 AgentDrawer.vue コンポーネントを作成する
    - shadcn-vue Sheet コンポーネントで左側スライドイン
    - エージェント一覧を Avatar + 表示名で表示
    - 選択中エージェントに Badge 表示
    - 選択時に `select` イベントを emit しドロワーを閉じる
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 8.2 ドロワーエージェント選択のプロパティテストを作成する
    - **Property 6: Drawer agent selection closes drawer and switches context**
    - **Validates: Requirements 6.4**

  - [ ]* 8.3 Badge ハイライトのプロパティテストを作成する
    - **Property 7: Badge highlights only the selected agent in drawer**
    - **Validates: Requirements 6.5**

- [ ] 9. ディスカッションタブの実装
  - [ ] 9.1 DiscussionTab.vue コンポーネントを作成する
    - 未開始時: DiscussionSetup（テーマ入力 + エージェント選択 + スタートボタン）を表示
    - ストリーミング中: DiscussionTheater でリアルタイム表示
    - 完了時: 「新しいディスカッションを開始」ボタンを有効化
    - エージェント 2 体未満時のメッセージ表示
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 9.2 DiscussionSetup.vue を Tailwind + shadcn-vue で再スタイリングする
    - テーマ入力フィールド（Input）
    - エージェント選択 UI（チェックボックス or マルチセレクト）
    - スタートボタン（Button）
    - _Requirements: 7.1_

  - [ ] 9.3 DiscussionTheater.vue と TurnBubble.vue を Tailwind で再スタイリングする
    - 各エージェント発言のリアルタイム表示
    - 進行状況インジケータの実装
    - _Requirements: 7.2, 7.3_

  - [ ]* 9.4 ディスカッションターン描画のプロパティテストを作成する
    - **Property 8: Discussion turns rendering completeness**
    - **Validates: Requirements 7.2, 7.3**

- [ ] 10. 既存ページとの共存確認
  - [ ] 10.1 Tailwind プレフライトが既存ページに影響しないことを確認する
    - SurveyView と ResultsDashboardView の内部スタイルに変更を加えていないことを確認
    - 既存のルーティング構成（/survey, /results, /evolution）が維持されていることを確認
    - 必要に応じて `@import "tailwindcss" layer(tailwind)` でレイヤー分離
    - _Requirements: 8.1, 8.2, 8.3_

- [ ] 11. 全体統合と最終確認
  - [ ] 11.1 全コンポーネントを EvolutionView に接続し統合テストを実施する
    - AgentsTab → ChatTab 遷移（エージェント選択）の動作確認
    - AgentDrawer からのエージェント切り替えの動作確認
    - DiscussionTab のセットアップ → 実行フローの動作確認
    - _Requirements: 3.2, 4.3, 6.4_

  - [ ]* 11.2 アクティブナビリンクのプロパティテストを作成する
    - **Property 1: Active nav link corresponds to current route**
    - **Validates: Requirements 2.4**

- [ ] 12. Final checkpoint - 全テスト通過確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- 既存の composables（useAgents, useChat, useDiscussion）はそのまま利用し、UI 層のみリビルドする
- shadcn-vue コンポーネントは CLI で自動生成されるため、手動コピーは不要

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "4.1"] },
    { "id": 3, "tasks": ["2.2", "4.2", "5.1"] },
    { "id": 4, "tasks": ["5.2", "5.3", "6.1", "9.1"] },
    { "id": 5, "tasks": ["6.2", "8.1", "9.2", "9.3"] },
    { "id": 6, "tasks": ["6.3", "8.2", "8.3", "9.4"] },
    { "id": 7, "tasks": ["10.1"] },
    { "id": 8, "tasks": ["11.1"] },
    { "id": 9, "tasks": ["11.2"] }
  ]
}
```
