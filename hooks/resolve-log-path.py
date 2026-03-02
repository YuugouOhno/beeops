#!/usr/bin/env python3
"""Resolve the log directory path for the current project.

Priority: BO_LOG_DIR env var > git root detection > cwd fallback.
Default log location: <project>/.claude/beeops/logs/

Usage:
    python3 resolve-log-path.py          # Print LOG_BASE path
    python3 resolve-log-path.py --json   # JSON output: project, log_base, log_file
"""

import json
import re
import subprocess
import sys
from pathlib import Path


def resolve_project_name() -> str:
    """Resolve project name from GitHub remote > git root > cwd."""
    # GitHub remote: owner-repo
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        m = re.search(r'[:/]([^/]+/[^/]+?)(?:\.git)?$', remote)
        if m:
            return m.group(1).replace("/", "-")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Git repository root directory name
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip()).name
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback to current directory name
    return Path.cwd().name


def resolve_git_root() -> Path | None:
    """Resolve git repository root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def resolve_log_base() -> Path:
    """Resolve log base directory.

    Priority:
    1. BO_LOG_DIR environment variable (absolute path)
    2. <git-root>/.claude/beeops/logs/
    3. <cwd>/.claude/beeops/logs/
    """
    import os
    env_dir = os.environ.get("BO_LOG_DIR")
    if env_dir:
        return Path(env_dir)

    git_root = resolve_git_root()
    if git_root:
        return git_root / ".claude" / "beeops" / "logs"

    return Path.cwd() / ".claude" / "beeops" / "logs"


def main():
    log_base = resolve_log_base()

    if "--json" in sys.argv:
        print(json.dumps({
            "project": resolve_project_name(),
            "log_base": str(log_base),
            "log_file": str(log_base / "log.jsonl"),
        }))
    else:
        print(log_base)


if __name__ == "__main__":
    main()
