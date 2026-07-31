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
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── shlex-aware parsing constants ──────────────────────────────────────
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
SQL_CLIENTS = {"psql", "mysql", "mariadb", "sqlite3", "sqlcmd", "duckdb"}
WRAPPERS = {"command", "builtin", "nohup", "env", "sudo", "su"}

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
        r"\brm\s+-r[fv]?\s+/(?:\s|$)",
        "rm -r / (root deletion) blocked",
    ),
    (
        r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+/(?:\s|$)",
        "rm -r / (root deletion) blocked",
    ),
    # ── Filesystem destruction ──────────────────────────────────────────
    (
        r"\b(?:mkfs\.|mke2fs|mkdosfs|mkntfs|newfs)\b",
        "Filesystem format command blocked",
    ),
    (
        r"\bdd\s+.*of=/dev/[a-z]",
        "dd write to block device blocked",
    ),
    (
        r">\s*/dev/[a-z]",
        "Redirect to block device blocked",
    ),
    # ── SQL table/database destruction ──────────────────────────────────
    (
        r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b",
        "DROP TABLE/DATABASE/SCHEMA blocked",
    ),
    (
        r"\bTRUNCATE\s+(TABLE\s+)?\w+",
        "TRUNCATE blocked",
    ),
    (
        r"\bDELETE\s+FROM\s+\w+(?:\s*;\s*$|\s*$)",
        "Unconditional DELETE FROM blocked (missing WHERE)",
    ),
    # ── Git destructive operations ──────────────────────────────────────
    (
        r"\bgit\s+push\s+(?:--force|-[fF])\b",
        "git push --force blocked",
    ),
    (
        r"\bgit\s+push\s+--force-with-lease\b",
        "git push --force-with-lease blocked",
    ),
    (
        r"\bgit\s+push\s+.*--delete\b",
        "git push --delete blocked",
    ),
    (
        r"\bgit\s+reset\s+--hard\b",
        "git reset --hard blocked",
    ),
    (
        r"\bgit\s+clean\s+-[a-zA-Z]*[fF]",
        "git clean -f blocked",
    ),
    # ── Fork bomb ───────────────────────────────────────────────────────
    (
        r":\(\)\s*\{\s*:\|:?\s*&\s*\};?\s*:",
        "Fork bomb blocked",
    ),
    (
        r"\bperl\s+-e\s+.*fork",
        "Perl fork bomb blocked",
    ),
    # ── Permission escalation on system dirs ────────────────────────────
    (
        r"\bchmod\s+(?:-R\s+)?777\s+/(?:etc|usr|bin|sbin|lib|boot|var|sys|home|root|opt)",
        "chmod 777 on system directory blocked",
    ),
    (
        r"\bchmod\s+(?:-R\s+)?[0-7]*7[0-7]*\s+/(?:etc|usr|bin|sbin|lib|boot)",
        "chmod with write-all on system directory blocked",
    ),
    (
        r"\bchown\s+-R\s+\w+:\w+\s+/(?:etc|usr|bin|sbin|lib|boot|var|sys)",
        "chown -R on system directory blocked",
    ),
    # ── System takeover ─────────────────────────────────────────────────
    (
        r"\b(?:shutdown|reboot|halt|poweroff|init\s+[06])\b",
        "System shutdown/reboot command blocked",
    ),
    (
        r"\biptables\s+-F\b",
        "iptables flush blocked",
    ),
    (
        r"\b(?:systemctl|service)\s+(?:stop|disable)\s+(?:ssh|sshd|firewalld|ufw)",
        "Disabling critical service blocked",
    ),
    # ── Dangerous network operations ────────────────────────────────────
    (
        r"\bcurl\s+.*\|\s*(?:ba)?sh\b",
        "curl pipe to shell blocked",
    ),
    (
        r"\bwget\s+.*\|\s*(?:ba)?sh\b",
        "wget pipe to shell blocked",
    ),
    (
        r"\bnc\s+-[lL]\s+-[pP]\s+\d+\s+-[eE]\s+/",
        "netcat reverse shell blocked",
    ),
    # ── Docker destructive ──────────────────────────────────────────────
    (
        r"\bdocker\s+(?:rm|rmi|system\s+prune)\s+-[a-zA-Z]*[fF]",
        "docker force remove/prune blocked",
    ),
    (
        r"\bdocker\s+container\s+prune\s+-[fF]",
        "docker container prune -f blocked",
    ),
    # ── Sudo/su abuse ───────────────────────────────────────────────────
    (
        r"\bsudo\s+rm\s+-rf\b",
        "sudo rm -rf blocked",
    ),
    (
        r"\bsudo\s+su\b",
        "sudo su blocked",
    ),
    # ── Environment destruction ─────────────────────────────────────────
    (
        r"\bexport\s+PATH=/dev/null",
        "PATH destruction blocked",
    ),
    (
        r"\bunset\s+(?:PATH|HOME|USER|SHELL)\b",
        "Critical env var unset blocked",
    ),
]


def _get_log_dir() -> Path:
    """Return the hooks log directory, creating it if needed."""
    log_dir = Path.home() / ".claude" / "hooks"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _get_project_dir() -> str:
    """Best-effort guess at the project root from CWD or environment."""
    cwd = os.getenv("CLAUDE_PROJECT_DIR", "")
    if not cwd:
        cwd = os.getcwd()
    return cwd


def _log_blocked(command: str, reason: str) -> None:
    """Append a blocked-attempt entry to the log file."""
    log_path = _get_log_dir() / "blocked.log"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    project = _get_project_dir()
    entry = (
        f"[{timestamp}] BLOCKED\n"
        f"  Reason:   {reason}\n"
        f"  Command:  {command}\n"
        f"  Project:  {project}\n"
        f"  User:     {os.getenv('USER', os.getenv('USERNAME', 'unknown'))}\n"
        f"{'─' * 60}\n"
    )
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(entry)


def _command_name(value: str) -> str:
    """Return a lower-case executable basename for POSIX or Windows paths."""
    return value.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _parse_shell_commands(command: str) -> list[list[str]]:
    """Tokenize simple commands separated by shell operators (;, &, |, &&, ||).

    Returns a list of tokenized commands. Each command is a list of tokens.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens = list(lexer)
    except ValueError:
        return []

    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        # Shell operators
        if token and all(c in ";&|" for c in token):
            if current:
                commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def _unwrap_command(tokens: list[str]) -> list[str]:
    """Strip wrappers like 'sudo', 'nohup', 'command', env assignments."""
    result = []
    for token in tokens:
        name = _command_name(token)
        # Skip env assignments (FOO=bar)
        if "=" in token and not token.startswith("-"):
            continue
        if name in WRAPPERS:
            continue
        result.append(token)
    return result


def check_command(command: str) -> Tuple[bool, str]:
    """Check a command against blocked patterns.

    Uses shlex-aware parsing to inspect each sub-command in a chain.
    Returns (is_blocked, reason).
    """
    if not command or not isinstance(command, str):
        return False, ""

    # ── Shlex-aware: split into sub-commands ────────────────────────
    sub_commands = _parse_shell_commands(command)

    for tokens in sub_commands:
        if not tokens:
            continue
        unwrapped = _unwrap_command(tokens)
        sub_cmd = " ".join(unwrapped) if unwrapped else " ".join(tokens)

        # Check each sub-command against patterns
        for pattern, reason in BLOCKED_PATTERNS:
            try:
                if re.search(pattern, sub_cmd, re.IGNORECASE):
                    return True, reason
            except re.error:
                continue

    # ── Check full command against patterns ────────────────────────
    for pattern, reason in BLOCKED_PATTERNS:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return True, reason
        except re.error:
            continue

    # ── Additional heuristics ───────────────────────────────────────
    # Check for destructive operations on important files
    dangerous_targets = [
        r"/etc/(?:passwd|shadow|group|hosts|fstab|sudoers)",
        r"/boot/",
        r"/var/log/",
        r"~/.ssh/",
        r"~/.gnupg/",
    ]
    for target in dangerous_targets:
        if re.search(rf"\brm\s+.*{target}", command, re.IGNORECASE):
            return True, f"rm targeting critical path {target} blocked"

    # Check for mass file operations without confirmation
    if re.search(r"\brm\s+.*\*", command):
        return True, "rm with wildcard deletion blocked"

    # Check for kubectl delete all/namespace
    if re.search(r"\bkubectl\s+delete\s+(?:pods?|deploy|svc|namespace|ns)\b", command, re.IGNORECASE):
        return True, "kubectl delete blocked"

    # Check for docker-compose down with volumes
    if re.search(r"\bdocker-compose\s+down\s+-v", command, re.IGNORECASE):
        return True, "docker-compose down -v (volume removal) blocked"

    return False, ""


def _extract_command(tool_input: dict) -> Optional[str]:
    """Extract the command field from a tool-use JSON object.

    Handles multiple possible schemas:
      - {"command": "..."}   (direct)
      - {"input": {"command": "..."}}  (nested)
      - string input
    """
    if not isinstance(tool_input, dict):
        return None

    # Direct command field
    if "command" in tool_input and isinstance(tool_input["command"], str):
        return tool_input["command"]

    # Nested in 'input'
    if "input" in tool_input and isinstance(tool_input["input"], dict):
        return _extract_command(tool_input["input"])

    return None


def main() -> int:
    """Read tool-use JSON from stdin and decide allow/deny."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            # No input → allow
            return 0

        data = json.loads(raw)

        # Only intercept Bash tool calls
        tool_name = data.get("tool_name", data.get("name", ""))
        if tool_name.lower() != "bash":
            return 0  # Allow non-bash tools

        # Extract the command
        tool_input = data.get("tool_input", data.get("input", {}))
        command = _extract_command(tool_input)

        if not command:
            return 0  # No command to check

        # Check against blocked patterns
        is_blocked, reason = check_command(command)

        if is_blocked:
            _log_blocked(command, reason)
            # Write denial message for Claude Code
            msg = json.dumps({
                "decision": "deny",
                "reason": reason,
                "hint": "If this is a legitimate operation, review the command manually.",
            })
            sys.stdout.write(msg)
            return 2  # Deny

        return 0  # Allow

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # On parse error, log and allow (fail-open for safety)
        _get_log_dir()
        log_path = _get_log_dir() / "errors.log"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now(timezone.utc).isoformat()}] Parse error: {e}\n")
        return 0

    except Exception as e:
        # Catch-all: log and allow
        try:
            _get_log_dir()
            log_path = _get_log_dir() / "errors.log"
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(f"[{datetime.now(timezone.utc).isoformat()}] Unexpected error: {e}\n")
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
