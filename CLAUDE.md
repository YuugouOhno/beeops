# queen-bee

3-layer multi-agent orchestration system for Claude Code (Queen → Leader → Worker).

## Package Overview

Run `/qb` in Claude Code to launch a tmux-based multi-agent system.
Install with `npm install queen-bee` + `npx queen-bee init` in any project.

## Core Design: Environment Variable Chain

Eliminates hardcoded paths by dynamically resolving the package install location:

```
/qb execution → PKG_DIR resolved via require.resolve('queen-bee/package.json')
  → QB_SCRIPTS_DIR="$PKG_DIR/scripts"
  → QB_CONTEXTS_DIR="$PKG_DIR/contexts"
  → Injected as env vars when starting tmux session
  → Queen → launch-leader.sh (bakes QB_* into wrapper)
  → Leader → launch-worker.sh (bakes QB_* into wrapper)
  → Worker execution
```

## Context Resolution: 4-Step Locale Fallback

prompt-context.py resolves context files in the following order:

```
1. Project local (locale): <project>/.claude/queen-bee/contexts/<locale>/<file>
2. Project local (root):   <project>/.claude/queen-bee/contexts/<file>
3. Package (locale):        <pkg>/contexts/<locale>/<file>
4. Package (root):          <pkg>/contexts/<file>
```

- Local files take priority when present
- Falls back to package defaults for missing local files
- `agent-modes.json` follows the same fallback rules
- Locale determined by QB_LOCALE env var or `.claude/queen-bee/locale` file
- `npx queen-bee init --with-contexts` copies defaults locally for customization

## Directory Structure

```
queen-bee/
├── package.json                         # npm package definition
├── bin/queen-bee.js                     # CLI: init / update / check
├── scripts/
│   ├── launch-leader.sh                 # Launch Leader/Review Leader in tmux window
│   └── launch-worker.sh                 # Launch Worker in tmux pane
├── hooks/
│   └── prompt-context.py                # UserPromptSubmit hook (env var → context injection)
├── contexts/                            # Package default contexts
│   ├── en/                              # English locale
│   │   ├── queen.md
│   │   ├── leader.md
│   │   ├── review-leader.md
│   │   ├── executor.md
│   │   ├── reviewer-base.md
│   │   └── agent-modes.json
│   ├── ja/                              # Japanese locale
│   │   └── ...
│   ├── queen.md                         # Root fallback (English)
│   ├── leader.md
│   ├── review-leader.md
│   ├── agent-modes.json                 # Env var → context file mapping
│   ├── executor.md                      # Worker (coder/tester) context
│   ├── reviewer-base.md                 # Worker (reviewer) context
│   └── default.md                       # Default context (no mode active)
├── skills/
│   ├── qb-dispatch/SKILL.md             # Queen → Leader dispatch procedure
│   ├── qb-leader-dispatch/SKILL.md      # Leader → Worker dispatch procedure
│   ├── meta-task-decomposer/SKILL.md    # Task decomposition skill
│   └── orch-issue-sync/SKILL.md         # GitHub Issue → queue.yaml sync
└── command/
    └── qb.md                            # /qb slash command definition
```

### Files Generated in Target Project

```
<project>/
├── .claude/
│   ├── commands/qb.md                   # /qb command
│   ├── skills/
│   │   ├── qb-dispatch/SKILL.md         # Queen skill
│   │   ├── qb-leader-dispatch/SKILL.md  # Leader skill
│   │   ├── meta-task-decomposer/SKILL.md
│   │   └── orch-issue-sync/SKILL.md
│   ├── settings.local.json              # Hook registration (--local, default)
│   ├── settings.json                    # Hook registration (--shared)
│   └── queen-bee/
│       ├── locale                       # Locale preference file
│       └── contexts/                    # Custom contexts (--with-contexts only)
│           ├── en/
│           ├── ja/
│           └── ...
```

## `npx queen-bee init` Behavior

1. Prerequisites check (Node.js>=18, git, tmux, python3, claude, gh)
2. Detect project root via `git rev-parse --show-toplevel`
3. Copy `.claude/commands/qb.md`
4. Copy skills to `.claude/skills/`
5. Register hook (default: `.claude/settings.local.json`)
6. Save locale preference to `.claude/queen-bee/locale`
7. If `--with-contexts`: copy defaults to `.claude/queen-bee/contexts/`
8. Display completion message

### init Options

| Option | Hook target | Use case |
|--------|-------------|----------|
| `--local` (default) | `.claude/settings.local.json` | Personal use |
| `--shared` | `.claude/settings.json` | Team sharing (git committed) |
| `-g`, `--global` | `~/.claude/settings.json` | Global (all projects) |
| `--with-contexts` | — | Deploy contexts for customization |
| `--locale <lang>` | — | Set locale (default: en, available: en, ja) |

## Environment Variables

| Variable | Set by | Used by | Purpose |
|----------|--------|---------|---------|
| QB_QUEEN | command/qb.md | prompt-context.py | Identifies Queen agent |
| QB_LEADER | launch-leader.sh | prompt-context.py | Identifies Leader agent |
| QB_REVIEW_LEADER | launch-leader.sh | prompt-context.py | Identifies Review Leader |
| QB_WORKER_CODER | launch-worker.sh | prompt-context.py | Identifies coder Worker |
| QB_WORKER_REVIEWER | launch-worker.sh | prompt-context.py | Identifies reviewer Worker |
| QB_SCRIPTS_DIR | command/qb.md | launch-*.sh | Package scripts directory |
| QB_CONTEXTS_DIR | command/qb.md | prompt-context.py | Package contexts directory |
| QB_LOCALE | user | prompt-context.py | Override locale preference |

## Development

### Verification

```bash
cd /Users/yuugou/dev/oss/claude-ants
npm link
cd <test-project>
npm link queen-bee
npx queen-bee init
npx queen-bee init --shared
npx queen-bee init -g
npx queen-bee init --with-contexts --locale ja
npx queen-bee check
# In Claude Code: /qb → Queen launches
```

### Verification Points

1. `.claude/commands/qb.md` is generated
2. `.claude/skills/` contains all 4 skills
3. Hook is registered in the specified settings file
4. `/qb` launches Queen in tmux
5. Queen can execute `$QB_SCRIPTS_DIR/launch-leader.sh`
6. `QB_SCRIPTS_DIR`/`QB_CONTEXTS_DIR` propagate to Leader/Worker
7. `prompt-context.py` resolves contexts with locale fallback
8. Deleting a local file falls back to package default
