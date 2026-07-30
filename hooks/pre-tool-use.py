#!/usr/bin/env python3
"""Claude Code PreToolUse hook — intercepts destructive bash commands before execution.

Reads tool-call JSON from stdin, inspects the command field against a curated list
of dangerous patterns, and either denies the call with a clear reason or allows it.

Blocked attempts are logged to ~/.claude/hooks/blocked.log with timestamp,
command, working directory, and the matched pattern.

Exit codes:
  0 — allow (safe command or non-bash tool)
  2 — deny  (blocked pattern matched)
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Blocked patterns — (regex, human-readable reason)
# Each regex is matched case-insensitively against the full command string.
# ---------------------------------------------------------------------------
BLOCKED_PATTERNS: List[Tuple[str, str]] = [
    # ── Recursive force delete ──────────────────────────────────────────
    (
        r"\brm\s+(?:-[a-zA-Z]*[rR][a-zA-Z]*[fF]|-[a-zA-Z]*[fF][a-zA-Z]*[rR])",
        "rm -rf / recursive force delete blocked",
    ),
    (
        r"\brm\s+--recursive\s+--force\b",
        "rm --recursive --force blocked",
    ),
    (
        r"\brm\s+--force\s+--recursive\b",
        "rm --force --recursive blocked",
    ),
    (
        r"\brm\s+-rf?\b",
        "rm -rf blocked",
    ),
    # ── Filesystem destruction ──────────────────────────────────────────
    (
        r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+/(?:\s|$)",
        "rm -r / (root deletion) blocked",
    ),
    (
        r"\b(?:mkfs\.|mke2fs|mkdosfs|mkntfs)\b",
        "Filesystem format command blocked",
    ),
    (
        r"\bdd\s+if=.*\s+of=/dev/",
        "dd write to block device blocked",
    ),
    # ── SQL destruction ─────────────────────────────────────────────────
    (
        r"\bDROP\s+TABLE\b",
        "SQL DROP TABLE blocked",
    ),
    (
        r"\bDROP\s+DATABASE\b",
        "SQL DROP DATABASE blocked",
    ),
    (
        r"\bTRUNCATE\s+(?:TABLE\s+)?",
        "SQL TRUNCATE blocked",
    ),
    (
        r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)",
        "DELETE FROM without WHERE clause blocked",
    ),
    # ── Git force push ──────────────────────────────────────────────────
    (
        r"\bgit\s+push\s+.*(--force|--force-with-lease)\b",
        "git push --force blocked",
    ),
    (
        r"\bgit\s+push\s+.*-[fF]\b",
        "git push -f blocked",
    ),
    # ── Fork bomb ───────────────────────────────────────────────────────
    (
        r":\(\)\s*\{?\s*:\s*\|?\s*:?\s*&\s*\}?\s*;?\s*:",
        "Fork bomb blocked",
    ),
    # ── Permission escalation on sensitive paths ────────────────────────
    (
        r"\bchmod\s+(-R\s+)?[0]*777\s+/",
        "chmod 777 on root path blocked",
    ),
    (
        r"\bchown\s+-R\s+\S+\s+/\s",
        "chown -R on root path blocked",
    ),
]

# Compiled regex cache
_COMPILED: List[Tuple[re.Pattern, str]] = [
    (re.compile(p, re.IGNORECASE), reason) for p, reason in BLOCKED_PATTERNS
]

LOG_DIR = Path.home() / ".claude" / "hooks"
LOG_FILE = LOG_DIR / "blocked.log"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def parse_input() -> Dict:
    """Read and parse the JSON tool-call from stdin.

    Claude Code sends something like:
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}
    """
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def extract_command(data: Dict) -> str:
    """Extract the shell command from the tool-call payload."""
    tool_input = data.get("tool_input", {})
    if isinstance(tool_input, dict):
        return tool_input.get("command", "")
    return ""


def extract_cwd(data: Dict) -> str:
    """Extract the working directory / project path from the payload."""
    tool_input = data.get("tool_input", {})
    if isinstance(tool_input, dict):
        return tool_input.get("cwd", "") or os.getcwd()
    return os.getcwd()


def check_command(command: str) -> Tuple[bool, str]:
    """Test *command* against every blocked pattern.

    Returns (is_blocked, reason).
    """
    if not command:
        return False, ""

    for regex, reason in _COMPILED:
        if regex.search(command):
            return True, reason

    return False, ""


def log_block(command: str, reason: str, cwd: str) -> None:
    """Append a blocked-attempt entry to the log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = {
        "timestamp": timestamp,
        "reason": reason,
        "command": command,
        "cwd": cwd,
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # Non-fatal: don't let log failures block the hook
        pass


def deny(reason: str, command: str) -> None:
    """Emit the Claude Code deny decision and exit."""
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"🛡️ BLOCKED: {reason}\n\n"
                f"   Command: {command}\n\n"
                "   This command matches a destructive pattern and was blocked\n"
                "   by the pre-tool-use safety hook. If you are certain this is\n"
                "   safe, temporarily disable the hook or modify the patterns.\n\n"
                f"   Attempt logged to: {LOG_FILE}"
            ),
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    data = parse_input()

    # Non-Bash tools or empty input → allow
    tool_name = data.get("tool_name", "")
    if tool_name and tool_name != "Bash":
        sys.exit(0)

    command = extract_command(data)
    if not command:
        sys.exit(0)

    cwd = extract_cwd(data)
    is_blocked, reason = check_command(command)

    if is_blocked:
        log_block(command, reason, cwd)
        deny(reason, command)

    # Safe command — allow
    sys.exit(0)


if __name__ == "__main__":
    main()
