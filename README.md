# Agent Profiler

**仮想自分AIエージェントを生成するプロファイリングシステム**

質問に答えるだけで、あなたの思考特性・価値観・口調・興味関心を構造化データ（JSON）として出力し、AIエージェントの「ベースOS」として機能するプロファイルを生成します。生成されたプロファイルを使って「AI自分」を構築し、他のAIエージェントと対話させたり、代理で情報収集させたりすることを最終目標としています。

---

## コンセプト

```
あなた → 質問に回答 → プロファイルJSON生成 → AIエージェントにロード → 「AI自分」が活動
```

- **ステップベース質問UI**: 1問ずつカードフリップ形式で回答
- **4軸思考特性分析**: 独自の4軸モデルで思考傾向をスコアリング
- **LLM連携**: 自由記述回答をOpenAI APIで分析し、スコアリングに反映
- **3層コンテキストアーキテクチャ**: 常駐/オンデマンド/動的検索の階層でデータを管理

---

## 出力JSON構造

```json
{
  "profile_id": "prof_000001",
  "persona": {
    "nickname": "...",
    "age_range": "30代",
    "role": "テックリード",
    "industry": "IT/SaaS",
    "experience_years": "10年以上"
  },
  "communication_tone": {
    "pronoun": "私",
    "formality": "adaptive",
    "text_style": "concise_structured",
    "emotion_level": "neutral",
    "humor": "light_joke",
    "response_length": "medium"
  },
  "base_os": {
    "axes": { ... },
    "decision_style": "覇道の戦略家",
    "do_not_list": [...]
  },
  "lexical_tags": [...],
  "semantic_contexts": { ... },
  "context_layers": { ... }
}
```

---

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| フロントエンド | Vue 3 + TypeScript + Vite + Pinia |
| バックエンド | FastAPI + Python 3.12+ + Pydantic v2 |
| DB | SQLite (aiosqlite) |
| LLM連携 | OpenAI Responses API (gpt-4.1-mini) |
| テスト | pytest + Hypothesis (Backend) / Vitest (Frontend) |

---

## 起動方法

### バックエンド

```bash
cd backend
cp .env.example .env  # APIキーを設定
uv sync --all-extras
uv run uvicorn app.main:app --port 8001
```

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

アクセス: http://localhost:5173/

---

## 質問カテゴリ

| 順序 | カテゴリ | 質問タイプ | 問数 | 目的 |
|------|---------|-----------|------|------|
| 1 | Persona | 選択式 + Other | 5問 | 基本属性（年代、職種等） |
| 2 | Communication Tone | 選択式 | 5問 | 口調・表現スタイル |
| 3 | Interests & Preferences | チェックボックス（20択 + 自由入力4欄）×5問 | 5問 | 興味・スキル・好み |
| 4 | Business OS | 4択 + Other | 9問 | 思考特性スコアリング |
| 5 | Communication | 4択 + Other | 9問 | 思考特性スコアリング |
| 6 | Lifestyle/Hobbies | 4択 + Other | 9問 | 思考特性スコアリング |

---

## ビジョン

最終的に以下を実現する:

1. **AI自分の生成**: プロファイルJSONをLLMのシステムプロンプトにロードし、あなたの分身として振る舞うAIエージェントを構築
2. **AI同士の対話**: 異なるプロファイルを持つ「AI自分」同士を対話させ、議論やブレストを自動化
3. **代理行動**: AI自分が代理でミーティングに参加したり、情報収集したりする
4. **継続的学習**: 対話ログからプロファイルを自動更新し、より精度の高い分身へ進化

---

## ライセンス

**デュアルライセンス方式**

このプロジェクトは [GNU Affero General Public License v3.0 (AGPLv3)](./LICENSE) のもとで公開されています。

- **個人・非営利・オープンソース利用**: AGPLv3 のもと、無料で自由にご利用いただけます。ただし、本ソフトウェアを利用・改変してネットワーク経由でサービスを提供する場合、AGPLv3 の条項に基づきソースコードの公開義務が発生します。
- **商用利用**: ソースコード公開義務を免除する商用ライセンスを別途ご用意しています。クローズドソースでの組込み利用や SaaS 提供をご希望の場合はお問い合わせください。

```
Copyright (c) 2026 nekotoiruka

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.
```

商用ライセンスについてのお問い合わせ: [GitHub Issues](https://github.com/nekotoiruka/AgentProfiler/issues) または直接ご連絡ください。
