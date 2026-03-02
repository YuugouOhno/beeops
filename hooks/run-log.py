#!/usr/bin/env python3
"""Stop hook: Launch a background log-recording agent on session exit.

100% chance: run qb-log-writer (work log recording).
~10% chance: additionally run qb-self-improver (self-improvement analysis).

Reads hook input (transcript_path etc.) from stdin, extracts session context,
and embeds it into the prompt so the agent can record accurately without -c.
"""

import json
import os
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Turn:
    user_prompt: str
    file_changes: dict[str, list[str]] = field(default_factory=dict)
    bash_commands: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skills_used: list[str] = field(default_factory=list)
    assistant_texts: list[str] = field(default_factory=list)


# --- Read hook input from stdin ---
try:
    hook_input = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    hook_input = {}

transcript_path = hook_input.get("transcript_path", "")
stop_hook_active = hook_input.get("stop_hook_active", False)

# Loop prevention: skip if agent-modes.json marks this mode as skip_log
_skip_log = stop_hook_active

# Resolve agent-modes.json path via QB_CONTEXTS_DIR or package detection
_modes_file = None
_ctx_dir = os.environ.get("QB_CONTEXTS_DIR")
if _ctx_dir:
    _modes_file = Path(_ctx_dir) / "agent-modes.json"
else:
    # Try to resolve via require.resolve
    try:
        pkg_dir = subprocess.run(
            ["node", "-e", "console.log(require.resolve('queen-bee/package.json').replace('/package.json',''))"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        _modes_file = Path(pkg_dir) / "contexts" / "agent-modes.json"
    except Exception:
        pass

if not _skip_log and _modes_file and _modes_file.exists():
    try:
        _modes = json.loads(_modes_file.read_text()).get("modes", {})
        for _env_var, _conf in _modes.items():
            if os.environ.get(_env_var) == "1" and _conf.get("skip_log"):
                _skip_log = True
                break
    except Exception:
        pass
if _skip_log:
    sys.exit(0)


def _is_real_user_prompt(text: str) -> Optional[str]:
    """Extract meaningful instruction text from a user message. Returns None if not applicable."""
    text = text.strip()
    if len(text) <= 10:
        return None
    if (text.startswith("<") or text.startswith('{"session_id"')
            or text.startswith("<local-command")):
        return None
    cleaned = re.sub(r'<[^>]+>[^<]*</[^>]+>', '', text)
    cleaned = re.sub(
        r'\{"session_id":"[^"]*".*?"stop_hook_active":\s*(?:true|false)\}',
        '', cleaned,
    ).strip()
    if len(cleaned) > 10:
        return cleaned[:300]
    return None


def extract_session_turns(transcript_path: str) -> list[Turn]:
    """Segment transcript JSONL into user-instruction turns."""
    path = Path(transcript_path)
    if not path.exists():
        return []

    turns: list[Turn] = []
    current: Optional[Turn] = None
    tool_id_map: dict[str, str] = {}

    with open(path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type")
            if msg_type not in ("user", "assistant"):
                continue

            content = obj.get("message", {}).get("content", "")

            if msg_type == "user" and not obj.get("isMeta"):
                if isinstance(content, str):
                    prompt = _is_real_user_prompt(content)
                    if prompt is not None:
                        if current is not None:
                            turns.append(current)
                        current = Turn(user_prompt=prompt)
                        continue

                if isinstance(content, list) and current is not None:
                    for block in content:
                        if block.get("type") != "tool_result":
                            continue
                        tid = block.get("tool_use_id", "")
                        is_err = block.get("is_error", False)
                        result_text = block.get("content", "")
                        if isinstance(result_text, list):
                            result_text = " ".join(
                                b.get("text", "") for b in result_text if b.get("type") == "text"
                            )
                        if is_err and result_text:
                            et = result_text.strip()
                            if not any(skip in et.lower() for skip in [
                                "tool_use_error", "requested permissions",
                                "doesn't want to proceed", "requires approval",
                                "was rejected", "command substitution",
                                "command contains", "sensitive file",
                                "exceeds maximum allowed size",
                            ]):
                                current.errors.append(et[:200])
                        elif tool_id_map.get(tid) == "Bash" and result_text:
                            for err_line in result_text.split("\n"):
                                el = err_line.strip()
                                if el and any(kw in el.lower() for kw in
                                              ["error", "traceback", "exception",
                                               "failed", "errno", "not found"]):
                                    current.errors.append(el[:200])
                                    break

            elif msg_type == "assistant" and isinstance(content, list):
                if current is None:
                    current = Turn(user_prompt="(session start)")
                for block in content:
                    btype = block.get("type")
                    if btype == "text":
                        text = block.get("text", "").strip()
                        if len(text) > 30:
                            current.assistant_texts.append(text)
                    elif btype == "tool_use":
                        tool_name = block.get("name", "")
                        tool_id = block.get("id", "")
                        inp = block.get("input", {})
                        tool_id_map[tool_id] = tool_name
                        if tool_name == "Edit":
                            fp = inp.get("file_path", "?")
                            current.file_changes.setdefault(fp, []).append("Edit")
                        elif tool_name == "Write":
                            fp = inp.get("file_path", "?")
                            current.file_changes.setdefault(fp, []).append("Write")
                        elif tool_name == "Bash":
                            cmd = inp.get("command", "").strip()
                            if cmd and len(cmd) < 300:
                                current.bash_commands.append(cmd)
                        elif tool_name == "Skill":
                            skill = inp.get("skill", "")
                            if skill and skill not in current.skills_used:
                                current.skills_used.append(skill)

    if current is not None:
        turns.append(current)
    return turns


def merge_trivial_turns(turns: list[Turn]) -> list[Turn]:
    """Merge short turns with no file changes or errors into the previous turn."""
    if not turns:
        return turns

    merged: list[Turn] = [turns[0]]
    for turn in turns[1:]:
        is_trivial = (
            len(turn.user_prompt) <= 20
            and not turn.file_changes
            and not turn.errors
        )
        if is_trivial and merged:
            prev = merged[-1]
            prev.bash_commands.extend(turn.bash_commands)
            prev.skills_used.extend(
                s for s in turn.skills_used if s not in prev.skills_used
            )
            prev.assistant_texts.extend(turn.assistant_texts)
        else:
            merged.append(turn)
    return merged


def format_turns_summary(turns: list[Turn], max_chars: int = 12000) -> str:
    """Convert turn list to structured text with ### Turn N sections."""
    if not turns:
        return "(no extractable information)"

    budget_per_turn = max_chars // max(len(turns), 1)
    sections: list[str] = []

    for i, turn in enumerate(turns, 1):
        parts: list[str] = []
        parts.append(f"### Turn {i}: {turn.user_prompt}")

        if turn.file_changes:
            lines = []
            for fp, actions in turn.file_changes.items():
                counts: dict[str, int] = {}
                for a in actions:
                    counts[a] = counts.get(a, 0) + 1
                action_str = ", ".join(
                    f"{a} x{c}" if c > 1 else a for a, c in counts.items()
                )
                lines.append(f"- {fp} ({action_str})")
            parts.append("**File changes:**\n" + "\n".join(lines))

        if turn.bash_commands:
            seen: set[str] = set()
            deduped: list[str] = []
            for cmd in turn.bash_commands:
                key = cmd[:80]
                if key not in seen:
                    seen.add(key)
                    deduped.append(cmd[:150])
            cmd_lines = [f"- {c}" for c in deduped[:10]]
            parts.append("**Commands:**\n" + "\n".join(cmd_lines))

        if turn.errors:
            seen_e: set[str] = set()
            deduped_e: list[str] = []
            for e in turn.errors:
                key = e[:60]
                if key not in seen_e:
                    seen_e.add(key)
                    deduped_e.append(e)
            err_lines = [f"- {e}" for e in deduped_e[:5]]
            parts.append("**Errors:**\n" + "\n".join(err_lines))

        if turn.skills_used:
            parts.append("**Skills:** " + ", ".join(turn.skills_used))

        if turn.assistant_texts:
            filtered = [t for t in turn.assistant_texts if not t.startswith("<thinking>")]
            if filtered:
                tail = filtered[-2:]
                tail_lines = [t[:200] for t in tail]
                parts.append("**Response (tail):**\n" + "\n---\n".join(tail_lines))

        turn_text = "\n".join(parts)
        if len(turn_text) > budget_per_turn:
            turn_text = turn_text[:budget_per_turn] + "\n...(truncated)"
        sections.append(turn_text)

    result = "\n\n".join(sections)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n...(truncated)"
    return result


# --- Resolve log directory via resolve-log-path.py ---
cwd = Path.cwd()

# Find resolve-log-path.py: QB_CONTEXTS_DIR -> package detection -> fallback
_resolve_script = None
if _ctx_dir:
    _candidate = Path(_ctx_dir).parent / "hooks" / "resolve-log-path.py"
    if _candidate.exists():
        _resolve_script = _candidate
if not _resolve_script:
    try:
        pkg_dir = subprocess.run(
            ["node", "-e", "console.log(require.resolve('queen-bee/package.json').replace('/package.json',''))"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        _candidate = Path(pkg_dir) / "hooks" / "resolve-log-path.py"
        if _candidate.exists():
            _resolve_script = _candidate
    except Exception:
        pass

try:
    if _resolve_script:
        _log_info = json.loads(subprocess.run(
            ["python3", str(_resolve_script), "--json"],
            capture_output=True, text=True, check=True,
        ).stdout)
        LOG_DIR = Path(_log_info["log_base"])
        project_name = _log_info["project"]
    else:
        raise FileNotFoundError("resolve-log-path.py not found")
except Exception:
    project_name = cwd.name
    LOG_DIR = cwd / ".claude" / "queen-bee" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- log-pending.jsonl one-time cleanup ---
pending_file = LOG_DIR / "log-pending.jsonl"
log_file = LOG_DIR / "log.jsonl"
pending_merged = False
if pending_file.exists():
    try:
        pending_content = pending_file.read_text().strip()
        if pending_content:
            with open(log_file, "a") as f:
                f.write(pending_content + "\n")
            pending_merged = True
        pending_file.unlink()
    except Exception:
        pass

# --- Mode decision ---
include_fb = random.random() < 0.1

# --- Session context extraction ---
if transcript_path:
    turns = merge_trivial_turns(extract_session_turns(transcript_path))
    session_summary = format_turns_summary(turns)
    turn_count = len(turns)
else:
    session_summary = "(transcript_path not provided)"
    turn_count = 0

# --- Build prompt ---
log_file_path = LOG_DIR / "log.jsonl"

prompt = f"""\
Invoke qb-log-writer skill via Skill tool to record the previous session's work log.

## Log file path (fixed — do not change)

**{log_file_path}**

Do NOT run resolve-log-path.py. Append directly to the path above.
Do NOT create temporary files (.tmp-log-entries.jsonl etc.).

## Previous session structured summary (extracted by Python — {turn_count} turns)

The following data was auto-extracted and deduplicated from the transcript.
Use file changes and commands as-is; no need to re-verify with git diff.

{session_summary}

## Rules
- **Append one JSONL entry per Turn to {log_file_path}**
- Skip turns with no file changes and no skill usage
- Get timestamp via `date` command, increment by 1 second between turns
- changes: use the "File changes" data above as-is
- decisions: interpret the user instruction intent and record reasoning (main LLM task)
- errors: if "Errors" are listed, infer cause and resolution
- learnings: record reusable insights if any
- Only record logs — do NOT perform any other work (code changes, design, planning)
- **Append ONLY to {log_file_path}. Never create files with different names/paths**
"""

if include_fb:
    prompt += """
## Additional task: Self-improvement
After log recording is complete, invoke qb-self-improver skill via Skill tool.
"""

mode = "log + fb" if include_fb else "log"
if pending_merged:
    prompt += f"\n(Note: merged log-pending.jsonl contents into log.jsonl)\n"

# --- Generate bash script + run with osascript notification ---
escaped_prompt = prompt.replace("'", "'\\''")

allowed_tools = "Skill Read Write Edit 'Bash(git:*)' 'Bash(date:*)' 'Bash(python3:*)' Grep Glob"

# Dynamic max-turns based on turn count (base 6 + 2 per turn, max 25)
max_turns = min(6 + turn_count * 2, 25)

bash_script = f"""\
#!/bin/bash
osascript -e 'display notification "mode: {mode}" with title "QB Log Agent: started"' 2>/dev/null
claude --model sonnet --no-session-persistence --allowedTools {allowed_tools} --max-turns {max_turns} -p '{escaped_prompt}' > '{LOG_DIR}/temp.log' 2>&1
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    osascript -e 'display notification "mode: {mode}" with title "QB Log Agent: done"' 2>/dev/null
else
    osascript -e 'display notification "exit: '$EXIT_CODE'" with title "QB Log Agent: error"' 2>/dev/null
fi
exit $EXIT_CODE
"""

try:
    env = os.environ.copy()
    env["QB_FB_AGENT"] = "1"
    env["QB_LOG_DIR"] = str(LOG_DIR)
    if include_fb:
        env["QB_FB_INCLUDE_FB"] = "1"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as tmp:
        tmp.write(bash_script)
        tmp_path = tmp.name

    os.chmod(tmp_path, 0o755)

    subprocess.Popen(
        ["bash", tmp_path],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print(f"qb log agent started in background [{mode}]")
except Exception as e:
    print(f"qb log agent failed to start: {e}", file=sys.stderr)
    sys.exit(1)
