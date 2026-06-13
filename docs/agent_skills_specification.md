# Agent Skills 仕様リファレンス

本ドキュメントは、Agent Evolution のパッケージ生成機能（Requirement 14, 15）の実装時に参照するために、Agent Skills オープン標準の思想と仕様をまとめたものです。

## 概要

Agent Skills は、Anthropic が 2025年10月に公開したオープン標準で、AIエージェントに専門的な能力を与えるための軽量かつポータブルなパッケージ形式です。スキルは SKILL.md ファイルを含むフォルダとして構成され、メタデータ（YAML frontmatter）と指示（Markdown body）で構成されます。

**対応エージェント**: GitHub Copilot (VSCode / CLI / Cloud), Claude Code, OpenAI Codex, Cursor, Gemini CLI 等、複数のコーディングエージェントで横断的に動作します。

Sources: [agentskills.io](https://agentskills.io/), [VSCode Agent Skills documentation](https://code.visualstudio.com/docs/copilot/customization/agent-skills), [Microsoft Tech Community](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/giving-your-ai-agents-reliable-skills-with-the-agent-skills-sdk/4497074)

## 設計思想

### Progressive Disclosure（段階的開示）

エージェントは情報を3段階で読み込みます:

1. **Metadata** (~100 tokens): `name` と `description` のみ。全スキルについて起動時にロードされる
2. **Instructions** (< 5000 tokens推奨): SKILL.md の本文。スキルが活性化されたときにロード
3. **Resources** (必要時のみ): scripts/, references/, assets/ のファイル。参照されたときのみロード

この設計により、多数のスキルをインストールしてもコンテキストを圧迫しません。

### Agent Skills vs Custom Instructions

| 項目 | Agent Skills | Custom Instructions |
|------|-------------|-------------------|
| 目的 | 専門能力・ワークフローの定義 | コーディング規約・ガイドライン |
| 可搬性 | VSCode, CLI, Cloud Agent 横断 | VSCode / GitHub.com のみ |
| 内容 | 指示 + スクリプト + サンプル + リソース | 指示のみ |
| スコープ | タスク固有、オンデマンドロード | 常時適用（またはglob指定） |
| 標準 | オープン標準 (agentskills.io) | VSCode固有 |

## ディレクトリ構造

```
skill-name/
├── SKILL.md          # 必須: メタデータ + 指示
├── scripts/          # 任意: 実行可能コード
├── references/       # 任意: ドキュメント
├── assets/           # 任意: テンプレート、リソース
└── ...               # 追加ファイル
```

## SKILL.md フォーマット

### Frontmatter (YAML)

| フィールド | 必須 | 制約 |
|-----------|------|------|
| `name` | Yes | 最大64文字。小文字英数字 + ハイフンのみ。先頭・末尾ハイフン禁止。連続ハイフン禁止。親ディレクトリ名と一致必須 |
| `description` | Yes | 最大1024文字。スキルの機能と使用タイミングの両方を記述 |
| `license` | No | ライセンス名またはファイル参照 |
| `compatibility` | No | 最大500文字。環境要件 |
| `metadata` | No | 任意のキー/値マッピング |
| `allowed-tools` | No | スペース区切りの事前承認済みツール (experimental) |

### 完全な例

```markdown
---
name: code-review
description: Reviews code for quality, style, and correctness. Use when asked to review code changes or PRs.
license: MIT
metadata:
  author: my-org
  version: "1.0"
---

# Code Review Skill

## When to use
- User asks to review code or a PR
- Code quality assessment is needed

## Steps
1. Read the changed files
2. Check for style violations against the project's conventions
3. Identify logical errors or edge cases
4. Suggest improvements with rationale

## Examples
[See the reference guide](references/style-rules.md)
```

## スキルの配置場所

### プロジェクトスキル（リポジトリ内）
- `.github/skills/`
- `.claude/skills/`
- `.agents/skills/`

### パーソナルスキル（ユーザーレベル）
- `~/.copilot/skills/`
- `~/.claude/skills/`
- `~/.agents/skills/`

## Agent Profiler パッケージへの適用方針

### 我々の出力パッケージ構造

Agent Profiler のパッケージは Agent Skills 標準に「準拠しつつ拡張」する形式を取ります:

```
agent_pack_{agent_id}.zip
├── README.md                # セットアップガイド + 配置先案内
├── config.json              # 独自拡張: 4軸パラメータ等のメタデータ
├── system_prompt.md         # Base OS レイヤーのシステムプロンプト
├── skills/                  # Agent Skills 標準準拠
│   ├── reflection-wall/
│   │   └── SKILL.md        # 内省・壁打ちスキル
│   └── code-review-rules/
│       └── SKILL.md        # コードレビュースキル
└── tools/                   # 独自拡張: 静的コンテキスト
    └── project_context.json # 技術スタック情報
```

### 標準準拠ポイント

1. **skills/ 内は Agent Skills 標準に完全準拠**: 各スキルは `skill-name/SKILL.md` の構造
2. **name フィールド**: 小文字英数字 + ハイフン、64文字以内、ディレクトリ名と一致
3. **description フィールド**: 機能 + 使用タイミングの両方を記述
4. **Progressive Disclosure**: SKILL.md は500行以下に抑え、詳細はreferences/に分離

### 独自拡張ポイント

1. **config.json**: Agent Skills 標準にはないが、我々のシステム固有のメタデータ（4軸スコア、agent_id等）を格納
2. **system_prompt.md**: ルートに配置。エージェントランタイムが直接読み込むシステムプロンプト
3. **tools/**: Agent Skills の scripts/ と類似だが、実行コードではなく静的コンテキスト（技術スタック情報等）を格納
4. **README.md**: ユーザー向けセットアップガイド

### skills/ 内の SKILL.md 生成ルール

ProfileOutput の semantic_contexts から生成する各スキルは以下のルールに従います:

```yaml
# SKILL.md frontmatter 生成ルール
name: # semantic_contexts キーワードから導出。小文字英数字+ハイフン
description: # 「何ができるか」+「いつ使うか」を1024文字以内で生成
metadata:
  generated-by: agent-profiler
  profile-id: prof_XXXXXX
  version: "1.0"
```

本文（body）の生成ルール:
- semantic_contexts の該当ドメインテキストを指示として変換
- base_os.axes の関連軸を「このスキル発動時の判断基準」として記述
- do_not_list の関連項目をガードレールとして含める

### 配置ガイド（README.md に記載する内容）

```
## セットアップ

1. Zip を解凍
2. skills/ フォルダの中身を以下のいずれかにコピー:
   - .github/skills/ (GitHub Copilot)
   - .claude/skills/ (Claude Code)
   - .agents/skills/ (汎用)
3. system_prompt.md の内容をカスタムインストラクション(.github/copilot-instructions.md 等)に追記
4. tools/project_context.json をプロジェクトルートに配置（任意）
```

## バリデーション

生成したスキルは以下の基準で自動検証します:

- [ ] name: 1-64文字、`^[a-z0-9]([a-z0-9-]*[a-z0-9])?$` にマッチ
- [ ] name: ディレクトリ名と一致
- [ ] description: 1-1024文字、非空
- [ ] SKILL.md: YAML frontmatter + Markdown body の構造
- [ ] 本文: 500行以下（推奨）

## 参考リンク

- [Agent Skills 公式仕様](https://agentskills.io/specification)
- [VSCode Agent Skills ドキュメント](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
- [Microsoft Learn - Agent Skills](https://learn.microsoft.com/en-us/agent-framework/agents/skills)
- [GitHub awesome-copilot (コミュニティスキル集)](https://github.com/github/awesome-copilot)
- [Anthropic リファレンススキル](https://github.com/anthropics/skills)
- [Hugging Face - SKILL.md Format 解説](https://huggingface.co/learn/context-course/en/unit1/skill-format)
