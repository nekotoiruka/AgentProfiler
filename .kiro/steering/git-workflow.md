---
inclusion: auto
description: Git ブランチ戦略・コミットメッセージ規約・PR マージ前チェックのルール
---

# Git ワークフロー

## ブランチ戦略
- `main`: プロダクション相当。直接 push は避ける
- feature ブランチ: `feature/{短い説明}` で作成し、PR でマージ

## コミットメッセージ
- Conventional Commits 形式:
  - `feat:` 新機能
  - `fix:` バグ修正
  - `docs:` ドキュメント
  - `chore:` メンテナンス
  - `refactor:` リファクタリング
  - `test:` テスト追加/修正
- 日本語でも可（本文は自由）

## PR マージ前チェック
- CI (テスト) パス必須
- Security スキャン パス推奨
- コードレビュー推奨

## .gitignore 管理
- `.env` ファイル: 必ず除外
- `node_modules/`, `__pycache__/`, `.venv/`: 除外
- `*.db` (SQLiteファイル): 除外
- `.hypothesis/`: 除外
