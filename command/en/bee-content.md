Launch a Content Queen in tmux for 3-layer content creation (bee-content: Content Queen → Content Leader → Workers).

## Execution steps

### Step 0: Interactive setup

Parse `$ARGUMENTS` first, then interactively ask for any missing values before launching tmux.

#### 0a. Parse $ARGUMENTS

- **instruction**: everything before the first `--` flag (or the entire string if no flags)
- **--criteria "..."**: quality criteria
- **--threshold N**: score threshold (integer)
- **--max-loops N**: maximum revision loops per piece (integer)
- **--count N**: number of pieces to generate (integer)
- **--name <name>**: session name for this task
- **--output <dir>**: output directory for approved pieces

#### 0b. Ask for missing values (always ask interactively — do NOT use defaults silently)

Use `AskUserQuestion` for each missing value in order:

**1. Instruction** (if not provided in $ARGUMENTS):
```
What content do you want to create?
```

**2. Criteria** (always ask, even if instruction was provided — unless explicitly given via --criteria):
```
What are the quality criteria for this content?
Examples: "Technically accurate, includes code examples, under 800 words"
         "Compelling headline, clear value prop, no jargon"
(Press Enter to use default: "High quality, accurate, engaging, and well-structured.")
```
If the user presses Enter or gives an empty response, use the default: `"High quality, accurate, engaging, and well-structured."`

**3. Threshold** (ask only if not provided via --threshold):
```
What score should the content reach to be accepted? (0-100, default: 80)
```
If empty, use `80`.

**4. Max loops** (ask only if not provided via --max-loops):
```
How many revision loops at most per piece? (default: 3)
```
If empty, use `3`.

**5. Count** (ask only if not provided via --count):
```
How many pieces of content do you want to generate? (default: 1)
```
If empty, use `1`.

**6. Name** (always ask — skip if --name was provided):
```
Give this session a name for later reference? (Enter to use timestamp)
```
If empty, leave blank (will use timestamp in Step 2).

After collecting all values, display a summary and confirm before proceeding:
```
Ready to start bee-content:
  instruction: {INSTRUCTION}
  criteria:    {CRITERIA}
  threshold:   {THRESHOLD}/100
  max_loops:   {MAX_LOOPS}
  count:       {COUNT}
  output:      {OUTPUT_DIR if set, else "(default: .beeops/tasks/content/{TASK_ID}/pieces/)"}

Start? (Y/n)
```
If the user says no or n, stop here.

### Step 1: Resolve package paths

```bash
PKG_DIR=$(node -e "console.log(require.resolve('beeops/package.json').replace('/package.json',''))")
BO_SCRIPTS_DIR="$PKG_DIR/scripts"
BO_CONTEXTS_DIR="$PKG_DIR/contexts"
```

### Step 2: Create task directory and files

```bash
TASK_ID="${NAME:-$(date +%Y%m%d-%H%M%S)}"
TASK_DIR=".beeops/tasks/content/$TASK_ID"
CWD=$(pwd)

mkdir -p "$TASK_DIR/pieces" "$TASK_DIR/reports" "$TASK_DIR/prompts"

echo "$INSTRUCTION" > "$TASK_DIR/instruction.txt"
echo "$CRITERIA"    > "$TASK_DIR/criteria.txt"
echo "$THRESHOLD"   > "$TASK_DIR/threshold.txt"
echo "$MAX_LOOPS"   > "$TASK_DIR/max_loops.txt"
echo "$OUTPUT_DIR" > "$TASK_DIR/output_dir.txt"
if [ -n "$OUTPUT_DIR" ]; then
  mkdir -p "$OUTPUT_DIR"
fi
# queue.yaml will be initialized by Content Queen
```

### Step 3: Create bee-content tmux session and launch Content Queen

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

### Step 4: Configure pane display

```bash
tmux select-pane -t "$SESSION:content-queen.0" -T "👑 content-queen"
tmux set-option -p -t "$SESSION:content-queen.0" @agent_label "👑 content-queen" 2>/dev/null || true
tmux set-option -p -t "$SESSION:content-queen.0" allow-rename off 2>/dev/null || true
tmux set-option -p -t "$SESSION:content-queen.0" pane-border-style "fg=yellow" 2>/dev/null || true
```

### Step 5: Send initial instruction to Content Queen

```bash
INSTRUCTION_MSG="Content task ready. TASK_DIR: $TASK_DIR COUNT: $COUNT BO_SCRIPTS_DIR: $BO_SCRIPTS_DIR OUTPUT_DIR: ${OUTPUT_DIR:-}. Read instruction.txt, initialize queue.yaml, and begin."
tmux send-keys -t "$SESSION:content-queen" "$INSTRUCTION_MSG" Enter
```

### Step 6: Auto-attach to tmux session

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

On macOS, auto-opens Terminal.app and attaches to the tmux session.
On other platforms, prints the attach command for the user.

### Step 7: Display status message

```
bee-content started.
  task_id:   {TASK_ID}
  count:     {COUNT}
  threshold: {THRESHOLD}/100
  max_loops: {MAX_LOOPS}
  output:    {OUTPUT_DIR if set, else .beeops/tasks/content/{TASK_ID}/pieces/}

  Monitor: tmux attach -t bee-content
  Stop:    tmux kill-session -t bee-content
```

## Notes

- `$ARGUMENTS` contains the slash command arguments
- This command must be run in the **target project directory**
- Content Queen manages queue.yaml and dispatches Content Leaders for each piece
- Approved pieces: `.beeops/tasks/content/{TASK_ID}/pieces/piece-{N}-approved.md` (also copied to `--output <dir>` if specified)
- Loop log: `.beeops/tasks/content/{TASK_ID}/loop.log`
- 3-layer flow: Content Queen → Content Leader → Workers (Creator, Reviewer, Researcher)
