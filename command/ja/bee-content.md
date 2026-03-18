3層構造のコンテンツ制作（bee-content: Content Queen → Content Leader → Worker）をtmuxで起動します。

## 実行手順

### ステップ0：対話形式でセットアップ

まず `$ARGUMENTS` を解析し、不足している値をtmux起動前に対話形式で確認します。

#### 0a. $ARGUMENTSの解析

- **instruction**: 最初の `--` フラグより前のすべて（フラグがない場合は文字列全体）
- **--criteria "..."**: 品質基準
- **--threshold N**: 採用スコアの閾値（整数）
- **--max-loops N**: 1件あたりの最大改訂ループ数（整数）
- **--count N**: 生成するコンテンツ件数（整数）
- **--name <name>**: このタスクのセッション名

#### 0b. 不足している値を対話形式で確認（デフォルトを黙って使わず、必ず聞く）

不足している値を順番に `AskUserQuestion` で確認します：

**1. 指示内容**（$ARGUMENTSに含まれていない場合）:
```
どんなコンテンツを作成しますか？
```

**2. 評価基準**（--criteriaで明示されていない場合は常に確認）:
```
このコンテンツの品質基準を教えてください。
例: "技術的に正確、コード例を含む、800字以内"
   "魅力的な見出し、明確な価値提案、専門用語なし"
（Enterを押すとデフォルト: "高品質で正確、読みやすく構造化されたコンテンツ"を使用）
```
空回答またはEnterの場合はデフォルト `"高品質で正確、読みやすく構造化されたコンテンツ"` を使用。

**3. 採用スコアの閾値**（--thresholdで指定されていない場合）:
```
何点以上で採用しますか？（0-100、デフォルト: 80）
```
空回答の場合は `80` を使用。

**4. 最大ループ回数**（--max-loopsで指定されていない場合）:
```
1件あたりの改訂ループは最大何回ですか？（デフォルト: 3）
```
空回答の場合は `3` を使用。

**5. 生成件数**（--countで指定されていない場合）:
```
コンテンツを何件生成しますか？（デフォルト: 1）
```
空回答の場合は `1` を使用。

**6. セッション名**（--nameが指定されていない場合は常に確認）:
```
後で参照するためにセッション名を付けますか？（Enterでスキップ、タイムスタンプを使用）
```
空回答の場合はタイムスタンプを使用（ステップ2で自動設定）。

全ての値が揃ったら内容を表示して確認を取ります：
```
bee-content を開始します：
  指示内容:   {INSTRUCTION}
  評価基準:   {CRITERIA}
  採用閾値:   {THRESHOLD}/100
  最大ループ: {MAX_LOOPS}回
  生成件数:   {COUNT}件

開始しますか？ (Y/n)
```
n または no の場合はここで終了します。

### ステップ1：パッケージパスの解決

```bash
PKG_DIR=$(node -e "console.log(require.resolve('beeops/package.json').replace('/package.json',''))")
BO_SCRIPTS_DIR="$PKG_DIR/scripts"
BO_CONTEXTS_DIR="$PKG_DIR/contexts"
```

### ステップ2：タスクディレクトリとファイルの作成

```bash
TASK_ID="${NAME:-$(date +%Y%m%d-%H%M%S)}"
TASK_DIR=".beeops/tasks/content/$TASK_ID"
CWD=$(pwd)

mkdir -p "$TASK_DIR/pieces" "$TASK_DIR/reports" "$TASK_DIR/prompts"

echo "$INSTRUCTION" > "$TASK_DIR/instruction.txt"
echo "$CRITERIA"    > "$TASK_DIR/criteria.txt"
echo "$THRESHOLD"   > "$TASK_DIR/threshold.txt"
echo "$MAX_LOOPS"   > "$TASK_DIR/max_loops.txt"
# queue.yamlはContent Queenが初期化する
```

### ステップ3：bee-content tmuxセッションの作成とContent Queen起動

```bash
SESSION="bee-content"

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" -n "content-queen" -c "$CWD" \
    "unset CLAUDECODE; BO_CONTENT_QUEEN=1 \
     BO_SCRIPTS_DIR='$BO_SCRIPTS_DIR' \
     BO_CONTEXTS_DIR='$BO_CONTEXTS_DIR' \
     TASK_DIR='$TASK_DIR' \
     COUNT='$COUNT' \
     claude --dangerously-skip-permissions \
     --permission-mode bypassPermissions \
     --allowedTools 'Read,Write,Edit,Bash,Glob,Grep,Skill' \
     --max-turns 80; read"
  tmux set-option -t "$SESSION" pane-border-status top
  tmux set-option -t "$SESSION" pane-border-format \
    " #{?pane_active,#[bold],}#{?@agent_label,#{@agent_label},#{pane_title}}#[default] "
else
  tmux new-window -t "$SESSION" -n "content-queen" -c "$CWD" \
    "unset CLAUDECODE; BO_CONTENT_QUEEN=1 \
     BO_SCRIPTS_DIR='$BO_SCRIPTS_DIR' \
     BO_CONTEXTS_DIR='$BO_CONTEXTS_DIR' \
     TASK_DIR='$TASK_DIR' \
     COUNT='$COUNT' \
     claude --dangerously-skip-permissions \
     --permission-mode bypassPermissions \
     --allowedTools 'Read,Write,Edit,Bash,Glob,Grep,Skill' \
     --max-turns 80; read"
fi
```

### ステップ4：ペイン表示設定

```bash
tmux select-pane -t "$SESSION:content-queen.0" -T "👑 content-queen"
tmux set-option -p -t "$SESSION:content-queen.0" @agent_label "👑 content-queen" 2>/dev/null || true
tmux set-option -p -t "$SESSION:content-queen.0" allow-rename off 2>/dev/null || true
tmux set-option -p -t "$SESSION:content-queen.0" pane-border-style "fg=yellow" 2>/dev/null || true
```

### ステップ5：Content Queenに初期指示を送信

```bash
INSTRUCTION_MSG="Content task ready. TASK_DIR: $TASK_DIR COUNT: $COUNT BO_SCRIPTS_DIR: $BO_SCRIPTS_DIR. Read instruction.txt, initialize queue.yaml, and begin."
tmux send-keys -t "$SESSION:content-queen" "$INSTRUCTION_MSG" Enter
```

### ステップ6：tmuxセッションへの自動接続

```bash
case "$(uname -s)" in
  Darwin)
    osascript -e '
    tell application "Terminal"
      activate
      do script "tmux attach -t bee-content"
    end tell
    ' 2>/dev/null || echo "新しいターミナルを開いて実行してください: tmux attach -t bee-content"
    ;;
  *)
    echo "bee-contentを開始しました。接続: tmux attach -t bee-content"
    ;;
esac
```

macOSでは、Terminal.appを自動的に開いてtmuxセッションに接続します。
その他のプラットフォームでは、接続コマンドを表示します。

### ステップ7：ステータスメッセージの表示

```
bee-content を開始しました。
  task_id:   {TASK_ID}
  count:     {COUNT}件
  threshold: {THRESHOLD}/100
  max_loops: {MAX_LOOPS}回
  output:    .beeops/tasks/content/{TASK_ID}/pieces/

  モニター: tmux attach -t bee-content
  停止:     tmux kill-session -t bee-content
```

## 注意事項

- `$ARGUMENTS` はスラッシュコマンドの引数を含みます
- このコマンドは**対象プロジェクトディレクトリ**で実行する必要があります
- Content Queenがqueue.yamlを管理し、各コンテンツ件のContent Leaderを起動します
- 承認済みコンテンツ: `.beeops/tasks/content/{TASK_ID}/pieces/piece-{N}-approved.md`
- ループログ: `.beeops/tasks/content/{TASK_ID}/loop.log`
- 3層構造: Content Queen → Content Leader → Worker（Creator・Reviewer・Researcher）
