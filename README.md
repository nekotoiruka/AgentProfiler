# Agent Profiler

**あなたの中の「もうひとりの自分」に会いにいく。**

質問に答えるだけで、あなたの思考回路・価値観・意思決定パターンを持つ AI エージェント（分身）を生成。分身と対話し、分身同士を議論させ、自分を客観視する——そんな体験を提供するプロファイリング × AI エージェントプラットフォームです。

---

## できること

| 機能 | 概要 |
|------|------|
| 🧠 思考特性プロファイリング | 47問の質問（4択 + 自由記述）で4軸思考特性を数値化。LLM による自由記述スコアリング付き |
| ⚡ AI分身の生成 | プロファイルから複数の分身エージェントを生成。1つのプロファイルから何体でも作成可能 |
| 💬 1対1チャット | 分身との対話。SSE ストリーミングでリアルタイム応答 |
| 🎭 マルチエージェント議論 | 2〜6体の分身にテーマを投げると自律的にターン制議論を開始 |
| 📊 相性診断 & レコメンド | 4軸パラメータの Cosine Similarity / 相補性スコアで分身間の相性を可視化 |
| 📦 Agent Pack Zip | IDE（VSCode / GitHub Copilot / Claude Code）配置用の構成資産を自動生成 & ダウンロード |
| 🔍 ハイブリッド検索 | Lexical（キーワード完全一致）+ Semantic（ベクトル検索）の重み付き統合 |
| ⚙️ セマンティックキャッシュ | 類似発話を検知して LLM コストを自動削減 |
| 🔀 ハイブリッドルーティング | 軽量クエリ → ローカル SLM / 複雑クエリ → Cloud LLM に自動振り分け |
| 🌐 MCP Server | Model Context Protocol で分身のコンテキストを外部公開 |

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Tailwind CSS v4 + TypeScript)        │
│  ├─ / ランディング                                      │
│  ├─ /survey 質問フロー                                  │
│  ├─ /results 結果ダッシュボード                          │
│  └─ /evolution 分身管理・チャット・ディスカッション       │
├─────────────────────────────────────────────────────────┤
│  Backend (FastAPI + Python 3.12+)                       │
│  ├─ /api/sessions/* プロファイリング API                 │
│  └─ /api/v1/evolution/* Agent Evolution API             │
│     ├─ 3層コンテキスト管理 (Base OS / Skills / MCP)     │
│     ├─ ハイブリッド検索 + セマンティックキャッシュ        │
│     ├─ ルーティングエンジン (SLM / Cloud LLM)           │
│     ├─ Agent Manager (CRUD + DB 永続化)                 │
│     ├─ Chat Service (スレッド + SSE)                    │
│     ├─ Discussion Engine (ターン制議論)                  │
│     ├─ Compatibility Engine (相性診断)                   │
│     ├─ Package Generator (Zip 生成)                     │
│     └─ Export Service (JSON / Markdown)                  │
├─────────────────────────────────────────────────────────┤
│  Data                                                   │
│  ├─ SQLite (sessions.db / evolution.db / cache.db)      │
│  └─ MCP Server (stdio / SSE)                           │
└─────────────────────────────────────────────────────────┘
```

---

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| フロントエンド | Vue 3.5 + TypeScript + Vite 6 + Tailwind CSS v4 + Pinia |
| バックエンド | FastAPI + Python 3.12+ + Pydantic v2 |
| DB | SQLite (aiosqlite) — プロファイル / エージェント / チャット / キャッシュ |
| LLM | OpenAI API (gpt-4.1-mini) + ollama (SLM ルーティング) |
| 検索 | numpy cosine similarity + hash index |
| プロトコル | MCP (Model Context Protocol) stdio/SSE |
| テスト | pytest + Hypothesis (PBT: 36 プロパティ) / Vitest |

---

## クイックスタート

```bash
# バックエンド
cd backend
cp .env.example .env          # OPENAI_API_KEY + EVOLUTION_CLOUD_LLM_API_KEY を設定
uv sync --all-extras
uv run uvicorn app.main:app --port 8001

# フロントエンド
cd frontend
npm install
npm run dev
```

http://localhost:5173/ にアクセス。

### 環境変数

```bash
# 必須
OPENAI_API_KEY=sk-...                    # プロファイリング用 LLM
EVOLUTION_CLOUD_LLM_API_KEY=sk-...       # Evolution チャット用 LLM

# オプション（全てデフォルト値あり）
EVOLUTION_CLOUD_LLM_MODEL=gpt-4.1-mini
EVOLUTION_SLM_BASE_URL=http://localhost:11434
EVOLUTION_SLM_MODEL=llama3.2
EVOLUTION_SEMANTIC_CACHE_THRESHOLD=0.92
```

---

## 画面一覧

| パス | 画面 | 概要 |
|------|------|------|
| `/` | ランディング | プロダクト紹介 + CTA |
| `/survey` | 診断 | 47問の質問フロー |
| `/results` | 結果 | 4軸スライダー + JSON プレビュー |
| `/evolution` | 分身と遊ぶ | エージェント管理 / チャット / ディスカッション |

---

## テスト

```bash
# バックエンド（549テスト + 36 PBT プロパティ）
cd backend && uv run pytest tests/ -v

# フロントエンド
cd frontend && npm run test
```

---

## プロジェクト構成

```
├── backend/
│   ├── app/
│   │   ├── api/           # プロファイリング API
│   │   ├── core/          # スコアリング / 正規化 / プロファイル生成
│   │   ├── evolution/     # Agent Evolution サブモジュール (14ファイル)
│   │   ├── models/        # Pydantic モデル
│   │   └── services/      # データローダー / LLM / セッション管理
│   ├── data/              # SQLite DB + 質問 YAML + マッピング辞書
│   └── tests/             # pytest + Hypothesis
├── frontend/
│   ├── src/
│   │   ├── components/    # UI コンポーネント (質問カード + Evolution)
│   │   ├── composables/   # useApi, useTheme
│   │   ├── views/         # Landing / Survey / Results / Evolution
│   │   └── assets/styles/ # Tailwind globals.css (テーマ定義)
│   └── vite.config.ts
├── landing/               # 外部共有用プロモ HTML (単体)
└── .kiro/specs/           # 仕様書 (requirements / design / tasks)
```

---

## ライセンス

**デュアルライセンス方式**

- 個人・非営利・OSS: [AGPLv3](./LICENSE)
- 商用: 別途ライセンスあり（[お問い合わせ](https://github.com/nekotoiruka/AgentProfiler/issues)）

---

Built with obsession by [@nekotoiruka](https://github.com/nekotoiruka)
