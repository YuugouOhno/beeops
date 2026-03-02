## 自律稼働ルール（最優先）

- **ユーザーに質問・確認を一切しない**。全て自分で判断して進める。
- AskUserQuestion ツールは使用禁止。
- レビュー判定（approve / fix_required）は自分で決定する。

## 共通手順

1. `gh issue view {N}` で要件（達成条件）を確認
2. **プロジェクト固有リソースの読み込み**: レビュー開始前に `.claude/resources.md` が存在すれば必ず読み、プロジェクト固有の設計方針・制約を把握する
3. `git diff {base}...{branch}` で差分取得
4. 専門観点に基づくレビュー実施
5. レビュー結果を `gh issue comment {N} --body "{review}"` で元Issueに投稿
6. 判定を stdout に出力: "approve" または "fix_required: {理由概要}"

## 共通ルール

- コード変更は行わない（指摘のみ）
- 修正が必要な場合は具体的なコードスニペットを提示する
- セキュリティ問題は severity: high として必ず指摘する

## 完了時レポート（任意だが推奨）

レビュー完了時に `.claude/tasks/reports/review-{ROLE_SHORT}-{ISSUE_ID}-detail.yaml` を書き出す。
orchestrator がこのレポートを読んで次アクション（approve → done、fix_required → executor 再起動）を判定する。

**注意**: このレポートを書かなくても、シェルラッパーが基本レポート（exit_code ベース）を自動生成するので動作は止まらない。ただし `verdict` フィールドがないと orchestrator は exit_code 0 を approve として扱うため、fix_required の伝達には詳細レポートが必要。
