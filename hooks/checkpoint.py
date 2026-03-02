#!/usr/bin/env python3
"""PostToolUse hook: Mid-session checkpoint logging trigger.

Fires on every PostToolUse matching Edit/Write/Bash/Skill.
Manages a counter in /tmp/qb-session-checkpoint.json and
outputs a log-recording instruction to stdout when thresholds are reached.

Thresholds:
- Edit/Write reaches 20 times (since last checkpoint)
- OR 15 minutes elapsed (since last checkpoint) with at least 1 Edit/Write
"""

import json
import os
import sys
import time

STATE_FILE = "/tmp/qb-session-checkpoint.json"

# Loop prevention: skip if running inside the feedback/log agent
if os.environ.get("QB_FB_AGENT"):
    sys.exit(0)

# Read hook input from stdin
try:
    hook_input = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    hook_input = {}

tool_name = hook_input.get("tool_name", "")
session_id = hook_input.get("session_id", "")

# Check if this is an Edit/Write call
is_edit_write = tool_name in ("Edit", "Write")

# Load state file
state = {
    "session_id": session_id,
    "edits_since_checkpoint": 0,
    "last_checkpoint_time": time.time(),
}

try:
    with open(STATE_FILE) as f:
        saved = json.load(f)
    # Session boundary: reset if session_id changed
    if saved.get("session_id") == session_id and session_id:
        state = saved
except (FileNotFoundError, json.JSONDecodeError, ValueError):
    pass

# Update counter
if is_edit_write:
    state["edits_since_checkpoint"] = state.get("edits_since_checkpoint", 0) + 1

# Update session ID
state["session_id"] = session_id

# Threshold check
edits = state.get("edits_since_checkpoint", 0)
elapsed = time.time() - state.get("last_checkpoint_time", time.time())
should_checkpoint = False

if edits >= 20:
    should_checkpoint = True
elif elapsed >= 900 and edits >= 1:  # 15 min = 900 sec
    should_checkpoint = True

# Save state
try:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
except OSError:
    pass

# On threshold: output instruction to stdout + reset state
if should_checkpoint:
    state["edits_since_checkpoint"] = 0
    state["last_checkpoint_time"] = time.time()
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except OSError:
        pass

    print("""Mid-session checkpoint: Record work so far to log.jsonl.
1. Invoke qb-log-writer skill via Skill tool
2. Record recent changes, decisions, and error resolutions in 1-2 entries
3. After recording, resume the original task""")
