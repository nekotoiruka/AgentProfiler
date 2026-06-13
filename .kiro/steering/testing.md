---
inclusion: fileMatch
fileMatchPattern: "**/*test*,**/tests/**"
description: pytest・Hypothesis・Vitest のテスト実行ルールとプロパティベーステスト方針
---

# テスト規約

## Backend (Python)

### テスト構成
- `tests/unit/` — 純粋関数のユニットテスト
- `tests/property/` — Hypothesis プロパティベーステスト
- `tests/integration/` — API エンドポイント統合テスト

### 実行方法
```bash
cd backend
uv run pytest              # 全テスト
uv run pytest tests/unit/  # ユニットテストのみ
uv run pytest -k "test_scoring"  # 名前フィルタ
```

### プロパティテスト規約
- `@settings(max_examples=200)` を設定
- タグコメント: `# Feature: agent-profiler, Property N: {description}`
- Hypothesis ストラテジーはテストファイル先頭にまとめて定義

### 統合テスト規約
- `httpx.AsyncClient` + `ASGITransport` パターンを使用
- テスト用DBは `tmp_path` で一時ファイルを使用
- `ALL_QUESTION_IDS` リストを更新した場合、テストも更新すること

## Frontend (TypeScript)

### テスト構成
- `src/__tests__/` — コンポーネントテスト

### 実行方法
```bash
cd frontend
npm run test       # 全テスト（vitest run）
npm run test:watch # ウォッチモード
```

### コンポーネントテスト規約
- `@vue/test-utils` の `mount()` を使用
- モック: `vi.mock()` で外部依存をモック
- Props テスト: ヘルパー関数 `createWrapper()` パターン
- イベントテスト: `wrapper.emitted()` で検証
