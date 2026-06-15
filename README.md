<div align="center">

# Agent Profiler

### 質問に答えるだけで、「判断まで再現できる」AI分身が生まれる。

[![CI](https://github.com/nekotoiruka/AgentProfiler/actions/workflows/ci.yml/badge.svg)](https://github.com/nekotoiruka/AgentProfiler/actions/workflows/ci.yml)
[![Security](https://github.com/nekotoiruka/AgentProfiler/actions/workflows/security.yml/badge.svg)](https://github.com/nekotoiruka/AgentProfiler/actions/workflows/security.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](./LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776ab.svg)](https://python.org)
[![Vue 3](https://img.shields.io/badge/Vue-3.5-42b883.svg)](https://vuejs.org)
[![Tests: 810+](https://img.shields.io/badge/Tests-810%2B%20passed-brightgreen.svg)](#)
[![PBT Properties: 52](https://img.shields.io/badge/PBT%20Properties-52-blueviolet.svg)](#)

</div>

---

## 生まれるエージェントは何ができるのか

88問の質問に回答すると、以下を**自律的に実行できる**AIエージェントが生成されます。

| できること | 具体例 |
|-----------|--------|
| **あなたと同じ優先順位で判断する** | 「品質 vs スピード」で迷ったとき、あなたと同じ側を選ぶ |
| **あなたの口調で話す** | 敬語レベル・文末表現・ユーモアの癖まで再現 |
| **状況に応じてモードを切り替える** | 経営報告は簡潔に、チーム指示は丁寧に、緊急時は端的に |
| **あなたの弱点を自覚している** | 「締切前に視野が狭くなる」「得意分野でレビューを怠る」を知っていて自制する |
| **判断に迷ったらエスカレーションする** | 「予算超過はあなたに確認する」「セキュリティ問題は即報告」のルールを持つ |
| **複数の分身で議論させる** | 異なる判断軸を持つ分身同士がテーマについて自律的に議論し、気づきを抽出 |
| **使うほど精度が上がる** | 「私ならこう言わない」フィードバックで自動的に重みが調整される |

口調だけ真似る「なんちゃってパーソナライズ」ではなく、**判断のアルゴリズムそのもの**を構造化して埋め込むから、本質的に「あなたの代わり」として機能します。

---

## なぜそれが可能なのか — 6層エージェントモデル

Agent Profiler は、人間の判断プロセスを**6つの層**に分解し、各層を独立に構造化してエージェントに埋め込みます。

```
┌─────────────────────────────────────────────────────────┐
│  Layer 6: 改善 (Improvement)                             │  ← 動的
│  失敗パターンの認識と自己学習                              │    エンジン
├─────────────────────────────────────────────────────────┤    (使うほど
│  Layer 5: 境界 (Boundary)                                │    成長する)
│  権限とエスカレーションの安全装置                          │
├─────────────────────────────────────────────────────────┤
│  Layer 4: 行動 (Action)                                  │
│  状況依存のモード切り替えと実行                            │
├─────────────────────────────────────────────────────────┤
│  Layer 3: 判断 (Decision) ← 最重要コア                   │
│  トレードオフ解消と優先順位付け                            │
├─────────────────────────────────────────────────────────┤
│  Layer 2: 知識 (Knowledge)                               │  ← 静的
│  専門知識、経験則、思考OS                                 │    データ
├─────────────────────────────────────────────────────────┤    (プロファイル
│  Layer 1: 人格 (Personality)                              │    生成時に確定)
│  価値観、口調、ベースとなる雰囲気                          │
└─────────────────────────────────────────────────────────┘
```

**従来の AI パーソナライズは L1（口調）+ L2（知識 = RAG で過去の発言や文書を参照する）で止まっていました。** 知識を持っていても「どう判断するか」は埋め込めないため、「事実は知ってるのに優先順位がおかしい」「口調は似てるけど意思決定が違う」という問題が残ります。Agent Profiler は **L3（判断アルゴリズム）を中心に L4〜L6 までを構造化する**ことで、この本質的なギャップを埋めます。

### 各層の技術的根拠

| Layer | 何を抽出するか | どう使うか | 質問設計の根拠 |
|-------|--------------|-----------|--------------|
| **L1: 人格** | 一人称・敬語レベル・文末表現・感情表現度 | システムプロンプトの口調ルールとして常時適用 | 社会言語学的な register 理論に基づく7問 |
| **L2: 知識** | 4軸思考特性（E/I, S/N, T/F, J/P）+ 興味領域 | Base OS スコアとして全推論の基盤に埋め込み | OEJTS / IPIP-NEO を業務シナリオにアダプト |
| **L3: 判断** | 優先順位重み・トレードオフ傾向（8対立軸） | 意思決定時の重み付きスコアリングとして適用 | Klein の NDM / Kahneman の System 1&2 理論 |
| **L4: 行動** | 状況別モード（tone, detail, focus）+ 切替条件 | メッセージ毎にモード検出→プロンプト動的切替 | Hersey-Blanchard 状況的リーダーシップ |
| **L5: 境界** | エスカレーション条件・自動承認スコープ | 「聞くべきか、やっていいか」の自律判断に使用 | Delegation Poker / Management 3.0 |
| **L6: 改善** | 失敗パターン・劣化トリガー・過信条件 | ガードレールとして自制ルールに変換 | Maslach バーンアウト / Dunning-Kruger |

---

## 技術設計: 3層パイプラインと Rule Hierarchy

回答データは以下の3段階で「実行可能なルール」に変換されます。

```
回答 (Raw)  →  正規化 (Normalized)  →  ポリシー (Policy)
─────────      ─────────────────      ──────────────────
元の選択肢     構造化タグに分類       "when_X: Y" 形式の
or 自由記述    (value / behavior /    1行ルールに変換
               prohibition /          
               condition)             
```

**全88問**にこのパイプラインを適用します。自由記述には LLM による正規化を挟みます。

生成された全ポリシーは **Rule Hierarchy** として4層に集約されます:

| 層 | 条件 | 役割 |
|----|------|------|
| **core_invariants** | confidence ≥ 0.8 + permanent + is_core | 絶対に破らないルール（上限10件） |
| **context_rules** | confidence ≥ 0.5 | 通常守るべきルール |
| **exceptions** | condition_tag を含む | 「〜の場合を除き」の例外 |
| **preferences** | 上記以外 | 余裕があれば従う好み |

この優先順位構造により、「ルールが多すぎて矛盾する」問題を解決しています。

---

## フィードバックループ

```
エージェントが回答
    ↓
ユーザーが評価: 👍 私らしい / ✏️ 私ならこう言わない / ⏭️ スキップ
    ↓
「私ならこう言わない」が特定次元に 10件蓄積
    ↓
該当する Priority Weight を ±0.1 自動調整（0.0〜1.0 にクランプ）
    ↓
次回以降の判断に反映
```

明示的な再設定なしに、使い続けるだけで精度が向上する設計です。

---

## 搭載機能一覧

| | 機能 | 詳細 |
|--|------|------|
| 🧠 | **6層プロファイリング** | 88問（4択 + トレードオフ2択 + 順序付け + LLM 自由記述分析）で6層全てを構造化 |
| 🎯 | **Decision Engine** | 判断層（L3）を中心に、モード切替（L4）・境界ルール（L5）・改善認識（L6）を統合管理 |
| 🔄 | **フィードバックループ** | 「私ならこう言わない」評価を蓄積し、10件以上で自動重み調整 |
| ⚡ | **分身エージェント生成** | 6層データを3層コンテキストアーキテクチャ（Base OS / Agent Skills / MCP）に変換して搭載 |
| 💬 | **1対1チャット** | Responses API + Function Calling で推論。`search_memory` ツールが L2 知識層を動的検索 |
| 🎭 | **マルチエージェント議論** | 2〜6体の分身がテーマについて自律議論。L3 のトレードオフ傾向差 ≥ 0.4 で対立を維持 |
| 💡 | **インサイト抽出** | 議論完了後、対立点・予想外の視点・actionable な提案を人間にフィードバック |
| 📦 | **Agent Pack Zip** | プロファイルから IDE 向け構成資産を自動生成（VSCode / Copilot / Claude Code 対応） |
| 🔍 | **ハイブリッド検索** | Lexical（O(1)）+ Semantic（cosine similarity）を統合。500タグ + 50コンテキストを 200ms 以内で検索 |
| 🔀 | **ハイブリッドルーティング** | 発話複雑度を 5ms 以内に分類 → ローカル SLM / Cloud LLM に自動振り分け |
| 🔗 | **MCP Server** | Model Context Protocol (stdio/SSE) で分身コンテキストを外部公開 |
| 🔐 | **6層セキュリティ** | Gitleaks + Bandit + Semgrep + Grype + pip-audit + npm audit |

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend                                                        │
│  Vue 3.5 + TypeScript + Tailwind CSS v4 + Pinia                 │
│  ├─ / ランディング                                               │
│  ├─ /survey 88問質問フロー（4択 / 2択 / 順序付け / 自由記述）      │
│  ├─ /results 6層プロファイル + Rule Hierarchy ビジュアライザ       │
│  └─ /evolution 分身管理 / チャット / ディスカッション              │
├─────────────────────────────────────────────────────────────────┤
│  Backend                                                         │
│  FastAPI + Python 3.12+ + Pydantic v2                           │
│  ├─ Profiling Engine (4軸スコアリング + LLM 分析)                 │
│  ├─ Decision Engine                                              │
│  │   ├─ AnswerPipeline (Raw → Normalized → Policy)              │
│  │   ├─ RuleAggregator (4層 Hierarchy 集約)                      │
│  │   ├─ ModeDetector (L4 コンテキスト適応)                        │
│  │   └─ FeedbackService (L6 自動重み調整)                         │
│  └─ Evolution Runtime (14 モジュール)                            │
│     Context Layer Manager │ Prompt Engine │ Hybrid Search        │
│     Semantic Cache │ Routing Engine │ Agent Manager              │
│     Chat Service │ Discussion Engine │ Compatibility Engine      │
│     Package Generator │ Export Service │ MCP Server              │
├─────────────────────────────────────────────────────────────────┤
│  Data Layer                                                      │
│  SQLite (sessions.db / evolution.db / decision_engine.db)        │
│  3層パイプライン永続化 + フィードバック蓄積 + 変更履歴            │
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
| LLM Integration | OpenAI Responses API (gpt-4.1-mini, Structured Output), ollama (local SLM) |
| Search | numpy cosine similarity, in-memory hash index |
| Protocol | MCP (Model Context Protocol) — stdio & SSE transport |
| Testing | pytest + Hypothesis (52 property-based tests), Vitest + Vue Test Utils |
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
| `OPENAI_API_KEY` | プロファイリング時の LLM 分析 + 自由記述正規化 |
| `EVOLUTION_CLOUD_LLM_API_KEY` | 分身チャット・議論の推論 |

---

## テスト

```bash
# Backend: 810+ テスト (52 PBT プロパティ含む)
cd backend && uv run pytest tests/ -q

# Frontend: 型チェック + ユニットテスト
cd frontend && npx vue-tsc --noEmit && npx vitest run
```

Property-Based Testing により、数万パターンの入力で以下の不変条件を検証しています:
- Priority Weight の正規化が常に [0.0, 1.0] 範囲かつ最大値 1.0
- Rule Hierarchy の分類が排他的かつ網羅的（全ルールがいずれか1層に属する）
- トレードオフスコアが範囲制約を満たす（choice "a" → [0.0, 0.3], "b" → [0.7, 1.0]）
- フィードバック重み調整が常にクランプ範囲内
- プロンプトトークン数が max_tokens を超過しない（段階的 truncation）
- 4軸スコアが Decision Engine 追加前後で同一（後方互換性）

---

## プロジェクト構成

```
AgentProfiler/
├── backend/
│   ├── app/
│   │   ├── api/              Profiling API (sessions, questions, calculate)
│   │   ├── core/             Scoring engine, normalizer, profile generator
│   │   ├── decision_engine/  3層パイプライン, Rule Hierarchy, Feedback, ModeDetector
│   │   ├── evolution/        14-module runtime (chat, discussion, prompt, search...)
│   │   ├── models/           Pydantic schemas (ProfileOutput, MappingEntry, etc.)
│   │   └── services/         Data loader, LLM client, session manager
│   ├── data/                 SQLite DBs + questions.yaml + mapping_dictionary.json
│   └── tests/                810+ tests (unit / pbt / evolution / integration)
├── frontend/
│   ├── src/
│   │   ├── views/            Landing, Survey, Results, Evolution
│   │   ├── components/       Question cards, Decision UI, Evolution UI
│   │   ├── composables/      useApi, useAgents, useChat, useDecisionSurvey, useFeedback
│   │   └── types/            TypeScript interfaces (profile, decision, api, session)
│   └── vite.config.ts        Tailwind v4 + Vite 6
├── .github/workflows/        CI + Security (6-layer pipeline)
└── .kiro/specs/              Full specifications (requirements → design → tasks)
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
