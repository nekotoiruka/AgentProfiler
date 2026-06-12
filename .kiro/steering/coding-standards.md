---
inclusion: auto
---

# コーディング規約

## 全般
- インデントはスペース2つ
- 複雑なロジックには Why を説明するコメントを付与
- DRY原則に従い、再利用性を高める
- セキュリティとパフォーマンスを常に意識

## Python (Backend)
- Python 3.12+ の機能を積極活用（type union `X | Y`、match文等）
- Pydantic v2 のモデルを使用（`BaseModel`）
- 非同期処理は `async/await` を使用
- ロギングは `logging.getLogger(__name__)` パターン
- 環境変数は `python-dotenv` + `.env` で管理（`.env` は gitignore 対象）
- APIキーなどの秘密情報は絶対にハードコードしない

## TypeScript (Frontend)
- strict mode 必須
- Composition API + `<script setup lang="ts">` スタイル
- 型定義は `frontend/src/types/` に集約
- Pinia ストアは setup store パターン（Composition API スタイル）

## テスト
- Backend: pytest + Hypothesis（プロパティベーステスト）
- Frontend: Vitest + Vue Test Utils
- テストファイルは対応するソースと同じ構造で配置

## セキュリティ
- ユーザー入力は必ずバリデーション（Pydantic モデルで自動検証）
- SQLインジェクション防止: パラメータバインディング必須
- APIキーは `.env` ファイルで管理、`.gitignore` に含める
- CORSは明示的に許可するオリジンのみ設定
- 依存パッケージはバージョンをピン留め
