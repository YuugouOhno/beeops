# queen-bee

[日本語版 README はこちら](README.ja.md)

3-layer multi-agent orchestration system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

**Queen → Leader → Worker** — automatically decomposes GitHub Issues into subtasks, implements them in parallel using git worktree isolation, runs code reviews, and checks CI — all orchestrated through tmux.

## How It Works

```
Queen (L1)                – Reads GitHub Issues, builds queue.yaml, dispatches Leaders
  ├─ Leader (L2)          – Decomposes issue into subtasks, dispatches Workers, creates PR
  │    ├─ Worker (coder)  – Implements a single subtask
  │    └─ Worker (tester) – Writes tests for a subtask
  └─ Review Leader (L2)   – Dispatches review Workers, aggregates findings
       ├─ Worker (code-reviewer)  – Code quality review
       ├─ Worker (security)       – Security vulnerability review
       └─ Worker (test-auditor)   – Test coverage audit
```

Each layer runs as a separate Claude Code instance in tmux. Communication flows through YAML reports and `tmux wait-for` signals. No external servers, databases, or APIs beyond GitHub.

Workers receive **multi-layer context injection** (base + specialization):

| Worker Role | Base Context | Specialization |
|-------------|-------------|----------------|
| `worker-coder` | `worker-base.md` | `coder.md` |
| `worker-tester` | `worker-base.md` | `tester.md` |
| `worker-code-reviewer` | `reviewer-base.md` | `code-reviewer.md` |
| `worker-security` | `reviewer-base.md` | `security-reviewer.md` |
| `worker-test-auditor` | `reviewer-base.md` | `test-auditor.md` |

## Prerequisites

- **Node.js** >= 18
- **git**
- **tmux**
- **python3**
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI (`claude`)
- [GitHub CLI](https://cli.github.com/) (`gh`) — for issue sync and PR operations

## Quick Start

```bash
# Install
npm install queen-bee

# Initialize in your project
cd your-project
npx queen-bee init

# Launch from Claude Code
# Type /qb in Claude Code
```

This installs:
- `/qb` slash command
- 4 skills (dispatch, leader-dispatch, task-decomposer, issue-sync)
- A UserPromptSubmit hook for context injection

## Init Options

```bash
npx queen-bee init                    # Hook in .claude/settings.local.json (default)
npx queen-bee init --shared           # Hook in .claude/settings.json (team-shared)
npx queen-bee init --global           # Hook in ~/.claude/settings.json (all projects)
npx queen-bee init --with-contexts    # Copy context files for customization
npx queen-bee init --locale ja        # Set locale to Japanese
```

## Multi-Language Support

queen-bee supports multiple locales for agent prompts. Currently available: **en** (English, default), **ja** (Japanese).

```bash
# Set during init
npx queen-bee init --locale ja

# Override at runtime
QB_LOCALE=ja /qb
```

Context files are resolved with a 4-step fallback:
1. Project local + locale (`<project>/.claude/queen-bee/contexts/<locale>/<file>`)
2. Project local root (`<project>/.claude/queen-bee/contexts/<file>`)
3. Package + locale (`<pkg>/contexts/<locale>/<file>`)
4. Package root (`<pkg>/contexts/<file>`)

## Customizing Agent Behavior

```bash
# Copy default contexts for editing
npx queen-bee init --with-contexts
```

This creates `.claude/queen-bee/contexts/` in your project. Edit any file to customize agent behavior. Delete a file to fall back to the package default.

Key files:
- `queen.md` — Queen orchestrator prompt
- `leader.md` — Implementation Leader prompt
- `review-leader.md` — Review Leader prompt
- `worker-base.md` — Worker base (autonomous rules, report format)
- `coder.md` — Coder specialization (coding standards, Fail Fast, prohibited patterns)
- `tester.md` — Tester specialization (test planning, boundary values, Given-When-Then)
- `reviewer-base.md` — Reviewer base (review procedure, verdict rules)
- `code-reviewer.md` — Code review specialization (design, quality, API, performance)
- `security-reviewer.md` — Security specialization (OWASP Top 10, injection, auth)
- `test-auditor.md` — Test audit specialization (coverage, edge cases, regression)
- `agent-modes.json` — Environment variable to context file mapping

## Architecture

### Workflow

1. **Issue Sync**: Queen fetches open GitHub Issues → builds `queue.yaml`
2. **Dispatch**: Queen launches a Leader in a new tmux window with git worktree
3. **Implementation**: Leader decomposes issue → launches Workers in tmux panes
4. **PR Creation**: Final Worker creates a pull request
5. **Review**: Queen dispatches a Review Leader → launches review Workers
6. **CI Check**: On approval, Queen monitors CI status
7. **Fix Loop**: On review/CI failure, Queen restarts Leader in fix mode (up to 3 times)

### tmux Layout

```
tmux session "qb"
├── [queen]     👑 Queen orchestrator (gold border)
├── [issue-42]  👑 Leader for issue #42 (blue border)
│   ├── pane 0: Leader
│   ├── pane 1: ⚡ Worker (coder, green border)
│   └── pane 2: 🧪 Worker (tester, cyan border)
└── [review-42] 🔮 Review Leader for issue #42 (magenta border)
    ├── pane 0: Review Leader
    ├── pane 1: 🔍 Worker (code-reviewer, blue border)
    ├── pane 2: 🛡 Worker (security, red border)
    └── pane 3: 🧪 Worker (test-auditor, yellow border)
```

Attach with `tmux attach -t qb` to watch all agents work in real-time.

## Verification

```bash
npx queen-bee check
```

Verifies that all components are correctly installed: command, skills, hook registration, and package resolution.

## License

MIT

## Author

[YuugouOhno](https://github.com/YuugouOhno)