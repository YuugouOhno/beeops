Queen セッション（beeops）をtmuxで起動し、自動表示します。
queue.yamlの生成・管理はtmux内のQueenがすべて担当します。

## 実行手順

### ステップ0：パッケージパスを解決

```bash
PKG_DIR=$(node -e "console.log(require.resolve('beeops/package.json').replace('/package.json',''))")
BO_SCRIPTS_DIR="$PKG_DIR/scripts"
BO_CONTEXTS_DIR="$PKG_DIR/contexts"
```

### ステップ1：既存セッションを確認

```bash
SESSION="bee-dev"

tmux has-session -t "$SESSION" 2>/dev/null && {
  echo "既存のboセッションが見つかりました。"
  echo "  tmux attach -t bee-dev   # 監視"
  echo "  tmux kill-session -t bee-dev  # 停止して再起動"
  # ここで停止。ユーザーに判断を委ねる。
}
```

既存セッションが見つかった場合は案内を表示して**停止**します。ユーザーが明示的にセッションを終了してから再実行する必要があります。

### ステップ2：tmuxセッションを起動

```bash
CWD=$(pwd)

tmux new-session -d -s "$SESSION" -n queen -c "$CWD" \
  "unset CLAUDECODE; BO_QUEEN=1 BO_SCRIPTS_DIR='$BO_SCRIPTS_DIR' BO_CONTEXTS_DIR='$BO_CONTEXTS_DIR' claude --dangerously-skip-permissions; echo '--- 完了（Enterで閉じる）---'; read"
```

### ステップ2.5：tmuxペイン表示を設定

```bash
# ペイン上部にロール名を表示
tmux set-option -t "$SESSION" pane-border-status top

# フォーマット: @agent_label を優先（Claude Codeから上書き不可）、フォールバックはpane_title
tmux set-option -t "$SESSION" pane-border-format \
  " #{?pane_active,#[bold],}#{?@agent_label,#{@agent_label},#{pane_title}}#[default] "

# Queenペイン: ゴールドボーダー + タイトル
tmux select-pane -t "$SESSION:queen.0" -T "👑 queen"
tmux set-option -p -t "$SESSION:queen.0" @agent_label "👑 queen" 2>/dev/null || true
tmux set-option -p -t "$SESSION:queen.0" allow-rename off 2>/dev/null || true
tmux set-option -p -t "$SESSION:queen.0" pane-border-style "fg=yellow" 2>/dev/null || true
```

### ステップ3：tmuxセッションに自動アタッチ

```bash
case "$(uname -s)" in
  Darwin)
    osascript -e '
    tell application "Terminal"
      activate
      do script "tmux attach -t bee-dev"
    end tell
    ' 2>/dev/null || echo "新しいターミナルを開いて実行: tmux attach -t bee-dev"
    ;;
  *)
    echo "Queenセッションを起動しました。接続: tmux attach -t bee-dev"
    ;;
esac
```

macOSではTerminal.appを自動で開き、tmuxセッションにアタッチします。
その他のプラットフォームではアタッチコマンドを表示します。

### ステップ4：起動を待機

```bash
for i in $(seq 1 60); do
  sleep 2
  if tmux capture-pane -t "$SESSION:queen" -p 2>/dev/null | grep -q 'Claude Code'; then
    break
  fi
done
```

最大120秒ポーリングします。`Claude Code` バナーが表示されたら起動完了です。

### ステップ5：実行モードを判定して初期プロンプトを送信

Queenに送る指示を決定します。優先順位:

1. **`$ARGUMENTS` が指定されている** → そのまま使用、設定ファイル/対話入力はスキップ
2. **設定ファイルが存在する** (`.beeops/settings.json`) → 設定から指示を生成
3. **引数も設定ファイルもない** → ユーザーに対話形式で確認

#### 5a. `$ARGUMENTS` が空でない場合

そのまま使用:

```bash
if [ -n "$ARGUMENTS" ]; then
  INSTRUCTION="$ARGUMENTS"
fi
```

#### 5b. 引数がない場合、設定ファイルを確認

```bash
SETTINGS_FILE=".beeops/settings.json"
if [ -z "$ARGUMENTS" ] && [ -f "$SETTINGS_FILE" ]; then
  echo "設定ファイルを検出: $SETTINGS_FILE"
  cat "$SETTINGS_FILE"
fi
```

設定ファイルが存在する場合、その内容に基づいて指示を生成します:

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `issues` | `number[]` | 処理する特定のIssue番号（例: `[42, 55]`） |
| `assignee` | `string` | `"me"` = 自分にアサインされたIssueのみ、`"all"` = 全オープンIssue |
| `skip_review` | `boolean` | trueの場合はレビューフェーズをスキップ（デフォルト: false） |
| `priority` | `string` | 指定した優先度以上のIssueのみ処理（`"high"`, `"medium"`, `"low"`） |
| `labels` | `string[]` | 指定したラベルを持つIssueのみ処理 |

`INSTRUCTION` 文字列の生成ルール:
- `issues` が設定されている場合: `"Sync GitHub Issues to queue.yaml and process only issues: #42, #55."`
- `assignee` が `"me"` の場合: `"Sync GitHub Issues to queue.yaml and process only issues assigned to me."`
- `assignee` が `"all"` または未設定の場合: `"Sync GitHub Issues to queue.yaml and complete all tasks."`
- オプションの付加: `skip_review` が true なら `" Skip the review phase."` を追加。`priority` が設定されていれば `" Only process issues with priority {priority} or higher."` を追加。`labels` が設定されていれば `" Only process issues with labels: {labels}."` を追加。

#### 5c. 引数も設定ファイルもない場合、対話形式で確認

以下の選択肢をユーザーに提示します（AskUserQuestion を使用するか、選択肢を表示して入力を待ちます）:

```
Queenにどの方法でIssueを処理させますか？

1. Issue番号を指定（例: 42, 55, 100）
2. 自分にアサインされたIssueのみ
3. すべてのオープンIssue

選択してください（1/2/3）:
```

ユーザーの回答に基づいて:
- **選択1**: Issue番号を確認し、`INSTRUCTION="Sync GitHub Issues to queue.yaml and process only issues: #42, #55."` を設定
- **選択2**: `INSTRUCTION="Sync GitHub Issues to queue.yaml and process only issues assigned to me."` を設定
- **選択3**: `INSTRUCTION="Sync GitHub Issues to queue.yaml and complete all tasks."` を設定

モード選択後、任意で以下を確認します:
```
デフォルト設定として保存しますか？（y/n）
```
yの場合、対応する `.beeops/settings.json` を書き込み、次回起動時に自動で使用されるようにします。

#### 5d. 指示をQueenに送信

```bash
tmux send-keys -t "$SESSION:queen" "$INSTRUCTION"
sleep 0.3
tmux send-keys -t "$SESSION:queen" Enter
```

### ステップ6：ユーザーにステータスを表示

起動後、以下を表示します:

```
Queenを起動しました（beeops）。tmuxセッションを表示中。
  queenウィンドウ: メインの制御ループ
  issue-{N}/review-{N}: Leader/Workerウィンドウは自動追加されます
  tmux kill-session -t bee-dev  # 停止するには
```

## 備考

- `$ARGUMENTS` にはスラッシュコマンドの引数が入ります
- このコマンドは**対象プロジェクトディレクトリ**で実行する必要があります
- queue.yamlの生成・更新はtmux内のQueenが管理します
