# LLM API 調査ドキュメント

本ドキュメントは Agent Profiler の LLM 連携機能（Other自由記述のスコアリング、Semantic Contexts 生成）に使用する API の調査結果をまとめたものです。

---

## 1. API 選択肢の比較

| プロバイダー | API | エンドポイント | 認証方法 |
|-------------|-----|--------------|---------|
| OpenAI 直接 | Responses API | `https://api.openai.com/v1/responses` | API Key (`OPENAI_API_KEY`) |
| Azure OpenAI (Microsoft Foundry) | Responses API | `https://{resource}.openai.azure.com/openai/v1/responses` | API Key or Microsoft Entra ID |

**推奨: OpenAI 直接**（設定が簡単、Azure は組織の要件がある場合に選択）

---

## 2. Responses API 概要

2025年3月にリリースされた新しいAPI。Chat Completions API と Assistants API の機能を統合した後継。

### 基本的な呼び出し方

```python
from openai import OpenAI

client = OpenAI(api_key="sk-...")

response = client.responses.create(
    model="gpt-4.1-mini",
    input="テキスト入力"
)

print(response.output_text)
```

### 主要パラメータ

| パラメータ | 型 | 説明 |
|-----------|---|------|
| `model` | string | 使用するモデル名 |
| `input` | string or list | テキスト入力またはメッセージリスト |
| `instructions` | string | システム指示（オプション） |
| `tools` | list | 使用するツール定義（function calling等） |
| `text` | object | Structured Output 設定 |
| `stream` | bool | ストリーミング有効化 |
| `previous_response_id` | string | マルチターン時の前回レスポンスID |
| `store` | bool | レスポンスデータの保存（デフォルト: true） |
| `temperature` | float | 生成温度 (0-2) |

### Structured Output（JSON Schema 出力）

**Agent Profiler で最も重要な機能。** LLM の出力をスキーマに準拠した JSON に制約できます。

```python
response = client.responses.create(
    model="gpt-4.1-mini",
    input=[
        {"role": "user", "content": "この回答の4軸スコアを判定してください: ..."}
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": "axis_scores",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "extroverted_introverted": {"type": "integer", "minimum": -10, "maximum": 10},
                    "sensing_intuition": {"type": "integer", "minimum": -10, "maximum": 10},
                    "thinking_feeling": {"type": "integer", "minimum": -10, "maximum": 10},
                    "judging_perceiving": {"type": "integer", "minimum": -10, "maximum": 10},
                    "reasoning": {"type": "string"}
                },
                "required": ["extroverted_introverted", "sensing_intuition", "thinking_feeling", "judging_perceiving", "reasoning"],
                "additionalProperties": False
            }
        }
    }
)
```

これにより、LLM は必ず指定した JSON 構造で回答を返します。パースエラーが起きない保証があります。

---

## 3. 利用可能モデル一覧と推奨

### OpenAI 直接 API

| モデル名 | 入力コスト ($/1M tokens) | 出力コスト ($/1M tokens) | コンテキスト長 | 推奨用途 |
|---------|------------------------|------------------------|-------------|---------|
| `gpt-4.1-nano` | $0.10 | $0.40 | 1M | ⭐ **Agent Profiler 推奨** — 最安で十分な性能 |
| `gpt-4.1-mini` | $0.40 | $1.60 | 1M | コスト重視の代替 |
| `gpt-4.1` | $2.00 | $8.00 | 1M | 高精度が必要な場合 |
| `gpt-4o-mini` | $0.15 | $0.60 | 128K | レガシー（4.1-nano推奨） |
| `gpt-5-nano` | — | — | — | 最新だが高コスト |
| `o4-mini` | $1.10 | $4.40 | 200K | 推論モデル（不要） |

### Azure OpenAI

| モデル名 | 利用可能リージョン | 備考 |
|---------|----------------|------|
| `gpt-4.1` | eastus, westus, swedencentral 等 | Azure Foundry 経由 |
| `gpt-4.1-mini` | 同上 | |
| `gpt-4.1-nano` | 同上 | |
| `gpt-4o` | 広く利用可能 | レガシー |
| `gpt-5` 系 | 限定リージョン | 最新 |

### Agent Profiler での推奨

- **プライマリ: `gpt-4.1-nano`** — $0.10/1M入力。1回のOther回答スコアリングで約100トークン使用 = **1回あたり約$0.00001（0.001円）**
- **フォールバック: `gpt-4.1-mini`** — nano が利用不可の場合

---

## 4. Agent Profiler での具体的なユースケース

### 4.1 Other 自由記述の4軸スコアリング

**入力:** 質問テキスト + ユーザーの自由記述回答
**出力:** 4軸スコア（各 -10〜+10 の整数）

```python
SCORING_PROMPT = """
あなたは心理測定の専門家です。以下の質問に対するユーザーの自由記述回答を分析し、
4軸思考特性スコアを判定してください。

軸の定義:
- extroverted_introverted: 正=外向的（集団志向、対話重視）、負=内向的（個人志向、内省重視）
- sensing_intuition: 正=感覚的（具体、データ、実績重視）、負=直観的（抽象、パターン、可能性重視）
- thinking_feeling: 正=論理的（客観、効率、分析重視）、負=感情的（共感、調和、人間関係重視）
- judging_perceiving: 正=計画的（構造、スケジュール重視）、負=柔軟的（臨機応変、探索重視）

各スコアは -10 から +10 の整数で、回答内容から推定される傾向の強さを表します。
明確な傾向が見られない軸は 0 としてください。

質問: {question_text}
ユーザーの回答: {user_text}
"""
```

### 4.2 Semantic Contexts への自由記述反映（将来対応）

テンプレートベースの生成に加えて、自由記述テキストの要約をドメイン別に追記する。

---

## 5. Python SDK セットアップ

### インストール

```bash
pip install openai>=1.30.0
```

### 環境変数

```bash
# .env (gitignore 対象)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-nano

# Azure の場合
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_MODEL=gpt-4.1-nano
LLM_PROVIDER=azure  # "openai" or "azure"
```

### クライアント初期化パターン

```python
import os
from openai import OpenAI

def create_llm_client() -> OpenAI:
    provider = os.getenv("LLM_PROVIDER", "openai")
    
    if provider == "azure":
        return OpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            base_url=f"{os.getenv('AZURE_OPENAI_ENDPOINT')}/openai/v1/",
        )
    else:
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
        )
```

---

## 6. エラーハンドリング・制約事項

| 項目 | 内容 |
|------|------|
| レート制限 | Tier 1: 500 RPM, 30,000 TPM（nano） |
| リトライ戦略 | 429/500/503 → 指数バックオフ（最大3回） |
| タイムアウト | 30秒推奨 |
| フォールバック | LLM 呼び出し失敗時はニュートラルスコア [0,0,0,0] を返す |
| コスト見積もり | 1ユーザーあたり最大27問×Other全選択 = 約2,700トークン ≈ $0.0003 |

---

## 7. セキュリティ

- API キーは `.env` ファイルで管理し、`.gitignore` に含める
- `.env.example` にはプレースホルダーのみ記載
- バックエンド側でのみ API を呼び出す（フロントエンドには露出しない）
- ユーザーの自由記述テキストは LLM に送信されるため、プライバシーポリシーでの告知が必要

---

## 8. 実装計画

### Step 1: 基盤
- `backend/app/services/llm_client.py` — OpenAI/Azure 切り替え対応クライアント
- `backend/.env.example` — 環境変数テンプレート
- `backend/.env` — 実際のキー（gitignore済み）

### Step 2: スコアリング連携
- `ScoringEngine.apply_score_from_text()` — LLM を呼び出して自由記述から4軸スコアを推定
- Structured Output で JSON スキーマを強制
- フォールバック: 失敗時はニュートラル

### Step 3: APIルート修正
- Other回答送信時に LLM スコアリングを非同期実行
- レスポンスタイムへの影響を最小化（バックグラウンド処理 or 計算時に一括実行）

---

## 参考リンク

- [OpenAI Responses API ドキュメント](https://developers.openai.com/api/reference/cli/resources/responses)
- [Azure OpenAI Responses API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)
- [Structured Outputs ガイド](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [Python SDK (openai)](https://github.com/openai/openai-python)
