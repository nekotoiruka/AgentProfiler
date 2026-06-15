<div align="center">

# Agent Profiler

### あなたの中の「もうひとりの自分」に会いにいく。

**質問に答える → 思考を数値化 → AI分身が生まれる → 分身同士が議論する**

[![CI](https://github.com/nekotoiruka/AgentProfiler/actions/workflows/ci.yml/badge.svg)](https://github.com/nekotoiruka/AgentProfiler/actions/workflows/ci.yml)
[![Security](https://github.com/nekotoiruka/AgentProfiler/actions/workflows/security.yml/badge.svg)](https://github.com/nekotoiruka/AgentProfiler/actions/workflows/security.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](./LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776ab.svg)](https://python.org)
[![Vue 3](https://img.shields.io/badge/Vue-3.5-42b883.svg)](https://vuejs.org)
[![Tests: 810+](https://img.shields.io/badge/Tests-810%2B%20passed-brightgreen.svg)](#)
[![PBT Properties: 52](https://img.shields.io/badge/PBT%20Properties-52-blueviolet.svg)](#)

</div>

---

## 何が起きるか

```
あなた → 88問に回答 → 4軸思考特性 + Decision Engine プロファイル生成 → AI分身エージェント誕生
                                                        ↓
                            1対1チャット ← 分身と対話 → マルチエージェント議論
                                                        ↓
                                  公開レジストリ登録 → 他者の分身と議論
                                                        ↓
                            相性診断 / インサイト抽出 / Agent Pack Zip / 会話エクスポート
```

15分の質問に答えるだけで、**あなたの口調・判断軸・価値観・禁忌事項を内蔵したAIエージェント**が生まれます。そいつと話す。そいつ同士を戦わせる。自分の中の矛盾に気づく。

**新機能: Decision Engine** — 88問の質問に統一3層パイプライン（Raw → Normalized → Policy）を適用。エージェントの行動規範を **Rule Hierarchy**（core_invariants > context_rules > exceptions > preferences）として集約し、再現性を最大化します。フィードバックループで重みが自動調整され、使うほどあなたに近づく。

---

## 搭載機能

| | 機能 | 詳細 |
|--|------|------|
| 🧠 | **4軸プロファイリング** | 88問（4択 + トレードオフ2択 + 順序付け + LLM 自由記述分析）で思考特性を数値化。独自の正規化アルゴリズムで 0.0〜1.0 の精密スコアを算出 |
| 🎯 | **Decision Engine** | 意思決定モデル・失敗パターン・コンテキスト適応・推論フローを統合。全回答に3層パイプライン（Raw→Normalized→Policy）を適用し、Rule Hierarchy として4層集約 |
| 🔄 | **フィードバックループ** | エージェント回答に対する「私らしい / 私ならこう言わない」評価を蓄積し、10件以上で自動重み調整。使うほど精度が向上 |
| ⚡ | **分身エージェント生成** | プロファイルから AI 分身を生成。3層コンテキストアーキテクチャ（Base OS / Agent Skills / MCP）で人格を階層管理 |
| 🌐 | **ペルソナレジストリ** | 分身を「公開」すると共有プールに登録。他ユーザーの分身とチャット・議論が可能に。公開には明示的な承認が必要 |
| 💬 | **1対1チャット** | Responses API + Function Calling で推論。`search_memory` ツールがユーザーの実回答・タグ・行動傾向を動的検索し、人格に基づいた応答を生成 |
| 🎭 | **マルチエージェント議論** | 2〜6体の分身がテーマについてターン制で自律議論。異なる人格パラメータが対立と共鳴を生む |
| 💡 | **インサイト抽出** | 議論完了後、LLM が対話内容を分析。主要な気づき・対立点・予想外の視点・actionable な提案を人間にフィードバック |
| 📊 | **相性診断 & レコメンド** | 4軸ベクトルの Cosine Similarity + Complementarity スコアで相性を数値化。「最も議論が白熱する相手」を自動マッチング |
| 📦 | **Agent Pack Zip** | プロファイルから VSCode / GitHub Copilot / Claude Code 向けの構成資産を自動生成。解凍して配置するだけで分身が IDE 上で動く |
| 🔍 | **ハイブリッド検索** | Lexical（O(1) 完全一致）+ Semantic（cosine similarity ベクトル検索）を重み付き統合。500タグ + 50コンテキストを 200ms 以内で検索 |
| 🔀 | **ハイブリッドルーティング** | 発話の複雑度を 5ms 以内に分類し、軽量→ローカル SLM (ollama) / 複雑→Cloud LLM に自動振り分け |
| 🔗 | **MCP Server** | Model Context Protocol (stdio/SSE) で分身のコンテキストを外部公開。任意の MCP 対応クライアントから接続可能 |
| 🔐 | **セキュリティ** | Gitleaks + Bandit (SAST) + Semgrep + Grype (脆弱性スキャン) + pip-audit + npm audit の6層セキュリティパイプライン |

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend                                                        │
│  Vue 3.5 + TypeScript + Tailwind CSS v4 + Pinia                 │
│  ├─ / ランディング（マウス追従エフェクト + CTA）                  │
│  ├─ /survey 47問質問フロー（カードフリップ UI）                   │
│  ├─ /results 4軸スライダー + JSON プレビュー                     │
│  └─ /evolution 分身管理 / チャット / ディスカッション              │
├─────────────────────────────────────────────────────────────────┤
│  Backend                                                         │
│  FastAPI + Python 3.12+ + Pydantic v2                           │
│  ├─ Profiling Engine (スコアリング + LLM 分析 + プロファイル生成)  │
│  ├─ Decision Engine (3層パイプライン + Rule Hierarchy + Feedback) │
│  └─ Evolution Runtime (14 モジュール)                            │
│     Context Layer Manager │ Prompt Engine │ Hybrid Search        │
│     Semantic Cache │ Routing Engine │ Agent Manager              │
│     Chat Service │ Discussion Engine │ Compatibility Engine      │
│     Package Generator │ Export Service │ MCP Server              │
├─────────────────────────────────────────────────────────────────┤
│  Data Layer                                                      │
│  SQLite (sessions.db / evolution.db / evolution_cache.db)        │
│  DB 永続化 + サーバー再起動時自動復元                              │
├─────────────────────────────────────────────────────────────────┤
│  Security                                                        │
│  Gitleaks │ Bandit │ Semgrep │ Grype │ pip-audit │ npm audit    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 技術スタック

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3.5, TypeScript 5.7, Vite 6, Tailwind CSS v4, Pinia, Vue Router |
| Backend | FastAPI, Python 3.12+, Pydantic v2, aiosqlite, Jinja2, numpy |
| LLM Integration | OpenAI Responses API (gpt-4.1-mini, function calling), ollama (local SLM routing) |
| Search | numpy cosine similarity, in-memory hash index |
| Protocol | MCP (Model Context Protocol) — stdio & SSE transport |
| Testing | pytest + Hypothesis (36 property-based tests), Vitest |
| Security | Gitleaks, Bandit, Semgrep, Grype, pip-audit, npm audit |
| CI/CD | GitHub Actions (build + test + security scan) |

---

## クイックスタート

```bash
git clone https://github.com/nekotoiruka/AgentProfiler.git
cd AgentProfiler

# Backend
cd backend
cp .env.example .env   # ← API キーを設定
uv sync --all-extras
uv run uvicorn app.main:app --port 8001

# Frontend (別ターミナル)
cd frontend
npm install && npm run dev
```

→ **http://localhost:5173/** にアクセス

### 必須環境変数

| 変数 | 用途 |
|------|------|
| `OPENAI_API_KEY` | プロファイリング時の LLM 分析 |
| `EVOLUTION_CLOUD_LLM_API_KEY` | 分身チャット・議論の推論 |

---

## テスト

```bash
# Backend: 549 テスト (36 PBT プロパティ含む)
cd backend && uv run pytest tests/ -q

# Frontend: 型チェック + ユニットテスト
cd frontend && npx vue-tsc --noEmit && npm run test
```

全テストが 2 分以内に完了。プロパティベーステストにより、エッジケースを含む数千パターンの入力で正しさを保証。

---

## プロジェクト構成

```
AgentProfiler/
├── backend/
│   ├── app/
│   │   ├── api/           Profiling API (sessions, questions, calculate)
│   │   ├── core/          Scoring engine, normalizer, profile generator
│   │   ├── evolution/     14-module runtime (chat, discussion, search, cache, routing...)
│   │   ├── models/        Pydantic schemas (ProfileOutput, NormalizedScores, etc.)
│   │   └── services/      Data loader, LLM client, session manager
│   ├── data/              SQLite DBs + questions YAML + mapping dictionary
│   └── tests/             549 tests (pytest + Hypothesis PBT)
├── frontend/
│   ├── src/
│   │   ├── views/         Landing, Survey, Results, Evolution
│   │   ├── components/    Question cards, Evolution UI (chat, discussion, agents)
│   │   ├── composables/   useApi, useTheme, useAgents, useChat, useDiscussion
│   │   └── assets/        Tailwind theme (light/dark, auto OS detection)
│   └── vite.config.ts     Tailwind v4 + Vite 6
├── landing/               Standalone promo HTML (share anywhere)
├── .github/workflows/     CI + Security (6-layer pipeline)
└── .kiro/specs/           Full specifications (requirements → design → tasks)
```

---

## ライセンス

**デュアルライセンス**

| 用途 | ライセンス |
|------|-----------|
| 個人・OSS・非営利 | [AGPLv3](./LICENSE) — 無料 |
| 商用（SaaS / クローズドソース） | 別途商用ライセンス — [お問い合わせ](https://github.com/nekotoiruka/AgentProfiler/issues) |

---

<div align="center">

**Built with obsession.**

[@nekotoiruka](https://github.com/nekotoiruka)

</div>
