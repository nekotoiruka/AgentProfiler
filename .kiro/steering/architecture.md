---
inclusion: auto
description: Backend (FastAPI) / Frontend (Vue 3) のアーキテクチャ・ディレクトリ構成ガイド
---

# アーキテクチャガイド

## プロジェクト構成

```
AgentProfiler/
├── backend/          # FastAPI + Python 3.12+
│   ├── app/
│   │   ├── api/      # ルートハンドラー + 依存性注入
│   │   ├── core/     # ビジネスロジック（スコアリング、正規化、プロファイル生成）
│   │   ├── models/   # Pydantic データモデル
│   │   ├── services/ # 外部連携（DB、LLM、データローダー）
│   │   └── main.py   # アプリケーションエントリーポイント
│   ├── data/         # 質問YAML + マッピングJSON
│   ├── tests/        # unit / property / integration
│   └── .env          # 環境変数（gitignore対象）
├── frontend/         # Vue 3 + TypeScript + Vite
│   ├── src/
│   │   ├── components/  # UIコンポーネント
│   │   ├── views/       # ページビュー
│   │   ├── stores/      # Pinia ストア
│   │   ├── composables/ # API通信等
│   │   └── types/       # TypeScript型定義
│   └── vite.config.ts
├── docs/             # 調査ドキュメント
└── .github/workflows/ # CI/CD + セキュリティスキャン
```

## データフロー

```
ユーザー回答 → API → ScoringEngine (4軸累積)
                        ↓
                  Normalizer (min-max正規化)
                        ↓
                  ProfileGenerator (JSON生成)
                        ↓
                  ProfileOutput (persona + tone + values + base_os + tags + contexts)
```

## 質問タイプ

| タイプ | 用途 | スコアリング |
|--------|------|------------|
| single_choice (マッピングあり) | 4軸思考特性 | Mapping Dictionary参照 |
| single_choice (マッピングなし) | ペルソナ/口調/価値観 | JSONフィールドに直接反映 |
| multi_select | 興味/スキル/好み | lexical_tags に直接反映 |

## LLM連携
- Other自由記述 → OpenAI Responses API (gpt-4.1-mini) で4軸スコア推定
- Structured Output (JSON Schema) で出力形式を保証
- フォールバック: API失敗時はニュートラル [0,0,0,0]

## 命名規則
- 質問ID: `{category_prefix}_{3桁番号}` (bos_001, com_001, per_001, ton_001, val_001, int_001)
- 選択肢ID: a, b, c, d (single_choice) / 英語snake_case (multi_select)
- 軸名: extroverted_introverted, sensing_intuition, thinking_feeling, judging_perceiving
- MBTI関連用語は使用禁止（E/I/S/N/T/F/J/Pの1文字コード含む）
