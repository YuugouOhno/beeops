在 tmux 中启动 Queen 会话（beeops）并自动显示。
queue.yaml 的生成与管理完全由 tmux 内的 Queen 负责。

## 执行步骤

### 步骤 0：解析包路径

```bash
PKG_DIR=$(node -e "console.log(require.resolve('beeops/package.json').replace('/package.json',''))")
BO_SCRIPTS_DIR="$PKG_DIR/scripts"
BO_CONTEXTS_DIR="$PKG_DIR/contexts"
```

### 步骤 1：检查是否存在已有会话

```bash
SESSION="bee-dev"

tmux has-session -t "$SESSION" 2>/dev/null && {
  echo "An existing bo session was found."
  echo "  tmux attach -t bee-dev   # monitor"
  echo "  tmux kill-session -t bee-dev  # stop and restart"
  # Stop here. Let the user decide.
}
```

若发现已有会话，显示操作提示后**停止**。用户必须主动终止该会话后才能重新启动。

### 步骤 2：启动 tmux 会话

```bash
CWD=$(pwd)

tmux new-session -d -s "$SESSION" -n queen -c "$CWD" \
  "unset CLAUDECODE; BO_QUEEN=1 BO_SCRIPTS_DIR='$BO_SCRIPTS_DIR' BO_CONTEXTS_DIR='$BO_CONTEXTS_DIR' claude --dangerously-skip-permissions; echo '--- Done (press Enter to close) ---'; read"
```

### 步骤 2.5：配置 tmux 面板显示

```bash
# Show role name at top of each pane
tmux set-option -t "$SESSION" pane-border-status top

# Format: prefer @agent_label (not overridable by Claude Code), fallback to pane_title
tmux set-option -t "$SESSION" pane-border-format \
  " #{?pane_active,#[bold],}#{?@agent_label,#{@agent_label},#{pane_title}}#[default] "

# Queen pane: gold border + title
tmux select-pane -t "$SESSION:queen.0" -T "👑 queen"
tmux set-option -p -t "$SESSION:queen.0" @agent_label "👑 queen" 2>/dev/null || true
tmux set-option -p -t "$SESSION:queen.0" allow-rename off 2>/dev/null || true
tmux set-option -p -t "$SESSION:queen.0" pane-border-style "fg=yellow" 2>/dev/null || true
```

### 步骤 3：自动连接到 tmux 会话

```bash
case "$(uname -s)" in
  Darwin)
    osascript -e '
    tell application "Terminal"
      activate
      do script "tmux attach -t bee-dev"
    end tell
    ' 2>/dev/null || echo "Open a new terminal and run: tmux attach -t bee-dev"
    ;;
  *)
    echo "Queen session started. Attach with: tmux attach -t bee-dev"
    ;;
esac
```

在 macOS 上，自动打开 Terminal.app 并连接到 tmux 会话。
在其他平台上，打印连接命令供用户使用。

### 步骤 4：等待启动完成

```bash
for i in $(seq 1 60); do
  sleep 2
  if tmux capture-pane -t "$SESSION:queen" -p 2>/dev/null | grep -q 'Claude Code'; then
    break
  fi
done
```

最多轮询 120 秒，当 `Claude Code` 横幅出现时即视为启动完成。

### 步骤 5：确定执行模式并发送初始提示

确定向 Queen 发送的指令。优先级顺序如下：

1. **提供了 `$ARGUMENTS`** → 直接使用，跳过设置文件和交互式询问
2. **存在设置文件**（`.beeops/settings.json`）→ 根据设置构建指令
3. **既无参数也无设置文件** → 向用户交互式询问

#### 5a. 若 `$ARGUMENTS` 非空

直接使用：

```bash
if [ -n "$ARGUMENTS" ]; then
  INSTRUCTION="$ARGUMENTS"
fi
```

#### 5b. 若无参数，检查设置文件

```bash
SETTINGS_FILE=".beeops/settings.json"
if [ -z "$ARGUMENTS" ] && [ -f "$SETTINGS_FILE" ]; then
  echo "Found settings: $SETTINGS_FILE"
  cat "$SETTINGS_FILE"
fi
```

若设置文件存在，根据其内容构建指令：

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `issues` | `number[]` | 要处理的指定 Issue 编号（例：`[42, 55]`） |
| `assignee` | `string` | `"me"` = 仅处理分配给当前 GitHub 用户的 Issue，`"all"` = 所有未关闭的 Issue |
| `skip_review` | `boolean` | 若为 true 则跳过评审阶段（默认：false） |
| `priority` | `string` | 仅处理该优先级及以上的 Issue（`"high"`、`"medium"`、`"low"`） |
| `labels` | `string[]` | 仅处理带有这些标签的 Issue |

按如下方式构建 `INSTRUCTION` 字符串：
- 若设置了 `issues`：`"Sync GitHub Issues to queue.yaml and process only issues: #42, #55."`
- 若 `assignee` 为 `"me"`：`"Sync GitHub Issues to queue.yaml and process only issues assigned to me."`
- 若 `assignee` 为 `"all"` 或未设置：`"Sync GitHub Issues to queue.yaml and complete all tasks."`
- 追加选项：若 `skip_review` 为 true，追加 `" Skip the review phase."`；若设置了 `priority`，追加 `" Only process issues with priority {priority} or higher."`；若设置了 `labels`，追加 `" Only process issues with labels: {labels}."`

#### 5c. 若既无参数也无设置文件，向用户交互式询问

向用户展示以下选项（使用 AskUserQuestion 或显示选项后等待输入）：

```
Queen 应如何处理 Issue？

1. 指定 Issue 编号（例：42, 55, 100）
2. 仅处理分配给我的 Issue
3. 所有未关闭的 Issue

请输入选择（1/2/3）：
```

根据用户的回答：
- **选择 1**：询问 Issue 编号，然后设置 `INSTRUCTION="Sync GitHub Issues to queue.yaml and process only issues: #42, #55."`
- **选择 2**：设置 `INSTRUCTION="Sync GitHub Issues to queue.yaml and process only issues assigned to me."`
- **选择 3**：设置 `INSTRUCTION="Sync GitHub Issues to queue.yaml and complete all tasks."`

确定模式后，可选择性地询问：
```
是否将此设置保存为默认值？（y/n）
```
若回答 yes，将对应的 `.beeops/settings.json` 文件写入磁盘，以便下次运行时自动使用。

#### 5d. 向 Queen 发送指令

```bash
tmux send-keys -t "$SESSION:queen" "$INSTRUCTION"
sleep 0.3
tmux send-keys -t "$SESSION:queen" Enter
```

### 步骤 6：向用户显示状态

启动完成后，显示：

```
Queen started (beeops). tmux session displayed.
  queen window: main control loop
  issue-{N}/review-{N}: Leader/Worker windows are added automatically
  tmux kill-session -t bee-dev  # to stop
```

## 注意事项

- `$ARGUMENTS` 包含斜杠命令的参数
- 此命令必须在**目标项目目录**中运行
- queue.yaml 的生成与更新由 tmux 内的 Queen 管理
