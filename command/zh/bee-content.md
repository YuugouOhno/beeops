在 tmux 中启动 Content Queen，进行三层内容创作（bee-content：Content Queen → Content Leader → Workers）。

## 执行步骤

### 步骤 0：交互式设置

首先解析 `$ARGUMENTS`，然后在启动 tmux 之前交互式询问缺失的值。

#### 0a. 解析 $ARGUMENTS

- **instruction**：第一个 `--` 标志之前的所有内容（若无标志则为整个字符串）
- **--criteria "..."**：质量标准
- **--threshold N**：评分阈值（整数）
- **--max-loops N**：每篇内容的最大修订循环次数（整数）
- **--count N**：要生成的内容篇数（整数）
- **--name <name>**：本次任务的会话名称

#### 0b. 询问缺失的值（务必交互式询问——不得静默使用默认值）

对每个缺失的值按顺序使用 `AskUserQuestion`：

**1. 指令**（若 $ARGUMENTS 中未提供）：
```
您想创作什么内容？
```

**2. 质量标准**（始终询问，即使已提供指令——除非通过 --criteria 明确给出）：
```
此内容的质量标准是什么？
示例："技术准确，包含代码示例，800字以内"
     "标题吸引人，价值主张清晰，无行话"
（直接按 Enter 使用默认值："High quality, accurate, engaging, and well-structured."）
```
若用户按 Enter 或给出空响应，使用默认值：`"High quality, accurate, engaging, and well-structured."`

**3. 评分阈值**（仅在未通过 --threshold 提供时询问）：
```
内容需要达到多少分才算合格？（0-100，默认：80）
```
若为空，使用 `80`。

**4. 最大循环次数**（仅在未通过 --max-loops 提供时询问）：
```
每篇内容最多修订几轮？（默认：3）
```
若为空，使用 `3`。

**5. 内容篇数**（仅在未通过 --count 提供时询问）：
```
您想生成几篇内容？（默认：1）
```
若为空，使用 `1`。

**6. 会话名称**（始终询问——若已提供 --name 则跳过）：
```
为本次会话指定一个名称以便后续参考？（直接按 Enter 使用时间戳）
```
若为空，留空（将在步骤 2 中使用时间戳）。

收集所有值后，显示摘要并在继续前确认：
```
准备启动 bee-content：
  instruction: {INSTRUCTION}
  criteria:    {CRITERIA}
  threshold:   {THRESHOLD}/100
  max_loops:   {MAX_LOOPS}
  count:       {COUNT}

是否开始？（Y/n）
```
若用户回答 no 或 n，停止此处。

### 步骤 1：解析包路径

```bash
PKG_DIR=$(node -e "console.log(require.resolve('beeops/package.json').replace('/package.json',''))")
BO_SCRIPTS_DIR="$PKG_DIR/scripts"
BO_CONTEXTS_DIR="$PKG_DIR/contexts"
```

### 步骤 2：创建任务目录和文件

```bash
TASK_ID="${NAME:-$(date +%Y%m%d-%H%M%S)}"
TASK_DIR=".beeops/tasks/content/$TASK_ID"
CWD=$(pwd)

mkdir -p "$TASK_DIR/pieces" "$TASK_DIR/reports" "$TASK_DIR/prompts"

echo "$INSTRUCTION" > "$TASK_DIR/instruction.txt"
echo "$CRITERIA"    > "$TASK_DIR/criteria.txt"
echo "$THRESHOLD"   > "$TASK_DIR/threshold.txt"
echo "$MAX_LOOPS"   > "$TASK_DIR/max_loops.txt"
# queue.yaml will be initialized by Content Queen
```

### 步骤 3：创建 bee-content tmux 会话并启动 Content Queen

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

### 步骤 4：配置面板显示

```bash
tmux select-pane -t "$SESSION:content-queen.0" -T "👑 content-queen"
tmux set-option -p -t "$SESSION:content-queen.0" @agent_label "👑 content-queen" 2>/dev/null || true
tmux set-option -p -t "$SESSION:content-queen.0" allow-rename off 2>/dev/null || true
tmux set-option -p -t "$SESSION:content-queen.0" pane-border-style "fg=yellow" 2>/dev/null || true
```

### 步骤 5：向 Content Queen 发送初始指令

```bash
INSTRUCTION_MSG="Content task ready. TASK_DIR: $TASK_DIR COUNT: $COUNT BO_SCRIPTS_DIR: $BO_SCRIPTS_DIR. Read instruction.txt, initialize queue.yaml, and begin."
tmux send-keys -t "$SESSION:content-queen" "$INSTRUCTION_MSG" Enter
```

### 步骤 6：自动连接到 tmux 会话

```bash
case "$(uname -s)" in
  Darwin)
    osascript -e '
    tell application "Terminal"
      activate
      do script "tmux attach -t bee-content"
    end tell
    ' 2>/dev/null || echo "Open a new terminal and run: tmux attach -t bee-content"
    ;;
  *)
    echo "bee-content started. Attach with: tmux attach -t bee-content"
    ;;
esac
```

在 macOS 上，自动打开 Terminal.app 并连接到 tmux 会话。
在其他平台上，打印连接命令供用户使用。

### 步骤 7：显示状态消息

```
bee-content started.
  task_id:   {TASK_ID}
  count:     {COUNT}
  threshold: {THRESHOLD}/100
  max_loops: {MAX_LOOPS}
  output:    .beeops/tasks/content/{TASK_ID}/pieces/

  Monitor: tmux attach -t bee-content
  Stop:    tmux kill-session -t bee-content
```

## 注意事项

- `$ARGUMENTS` 包含斜杠命令的参数
- 此命令必须在**目标项目目录**中运行
- Content Queen 负责管理 queue.yaml，并为每篇内容调度 Content Leader
- 已审批的内容：`.beeops/tasks/content/{TASK_ID}/pieces/piece-{N}-approved.md`
- 循环日志：`.beeops/tasks/content/{TASK_ID}/loop.log`
- 三层流程：Content Queen → Content Leader → Workers（Creator、Reviewer、Researcher）
