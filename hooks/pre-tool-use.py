#!/usr/bin/env python3
"""Claude Code PreToolUse hook — intercepts destructive bash commands before execution.

Reads tool-call JSON from stdin, inspects the command field against a curated list
of dangerous patterns, and either denies the call with a clear reason or allows it.

Blocked attempts are logged to ~/.claude/hooks/blocked.log with timestamp,
command, working directory, and the matched pattern.

Features:
  --dry-run        Report what would be blocked without actually denying
  --dry-run-json   Dry-run output as structured JSON
  --config PATH    Load whitelist/blocklist from a YAML/JSON config file
  --provider NAME  Override auto-detected provider (claude-code, cursor, windsurf, copilot)

Config file format (~/.claude/hooks/config.yaml):
  whitelist:
    commands: []      # Exact command strings to always allow
    patterns: []      # Regex patterns to always allow (case-insensitive)
  blocklist_extra:
    patterns: []      # Additional patterns to block
  provider: auto      # auto, claude-code, cursor, windsurf, copilot
  dry_run: false      # Global dry-run mode

Exit codes:
  0 — allow (safe command, non-bash tool, or dry-run report)
  2 — deny  (blocked pattern matched, not in dry-run)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

# ── shlex-aware parsing constants ──────────────────────────────────────
SHELLS: Set[str] = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
SQL_CLIENTS: Set[str] = {
    "psql", "mysql", "mariadb", "sqlite3", "sqlcmd", "duckdb",
    "clickhouse-client", "mongosh", "redis-cli",
}
WRAPPERS: Set[str] = {"command", "builtin", "nohup", "env", "sudo", "su", "doas", "pkexec"}
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# ── Supported AI coding providers ──────────────────────────────────────
PROVIDERS = {
    "claude-code": {
        "hook_event": "PreToolUse",
        "tool_name": "Bash",
        "output_format": "permission_decision",
    },
    "cursor": {
        "hook_event": "PreToolUse",
        "tool_name": "terminal",
        "output_format": "permission_decision",
    },
    "windsurf": {
        "hook_event": "PreToolUse",
        "tool_name": "bash",
        "output_format": "permission_decision",
    },
    "copilot": {
        "hook_event": "PreToolUse",
        "tool_name": "terminal",
        "output_format": "hook_specific",
    },
    "aider": {
        "hook_event": "PreToolUse",
        "tool_name": "run_shell",
        "output_format": "simple_deny",
    },
    "generic": {
        "hook_event": "PreToolUse",
        "tool_name": "",
        "output_format": "simple_deny",
    },
}


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
        r"\b(?:mkfs\.|mke2fs|mkdosfs|mkntfs|newfs|zpool\s+destroy|btrfs\s+device\s+delete)\b",
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
        r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|USER|ROLE)\b",
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
    (
        r"\bgit\s+rebase\s+-[iI]\b",
        "git rebase -i blocked (use with caution)",
    ),
    # ── Fork bomb ───────────────────────────────────────────────────────
    (
        r":\(\)\s*\{\s*:\|:?\s*&\s*\};\s*:",
        "Fork bomb blocked",
    ),
    (
        r"\bperl\s+-e\s+.*fork",
        "Perl fork bomb blocked",
    ),
    (
        r"\bpython\d*\s+-c\s+.*os\.fork",
        "Python fork bomb blocked",
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
        r"\b(?:systemctl|service)\s+(?:stop|disable|mask)\s+(?:ssh|sshd|firewalld|ufw|nginx|apache2|httpd|docker)",
        "Disabling critical service blocked",
    ),
    (
        r"\biptables\s+-F\b",
        "iptables flush blocked",
    ),
    (
        r"\biptables\s+-P\s+(?:INPUT|OUTPUT|FORWARD)\s+(?:ACCEPT|DROP)",
        "iptables default policy change blocked",
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
    (
        r"\bnc\s+-[lL]\s+\d+\s+-[eE]\s+/",
        "netcat reverse shell blocked",
    ),
    (
        r"\b(?:nc|ncat)\s+-[eE]\s+/bin/",
        "netcat reverse shell blocked",
    ),
    # ── Docker destructive ──────────────────────────────────────────────
    (
        r"\bdocker\s+(?:rm|rmi|system\s+prune|volume\s+prune|builder\s+prune)\s+-[a-zA-Z]*[fF]",
        "docker force remove/prune blocked",
    ),
    (
        r"\bdocker\s+container\s+prune\s+-[fF]",
        "docker container prune -f blocked",
    ),
    (
        r"\bdocker\s+compose\s+down\s+-[a-zA-Z]*[vV]",
        "docker compose down with volume removal blocked",
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
    (
        r"\bsudo\s+bash\b",
        "sudo bash (privilege escalation) blocked",
    ),
    # ── Environment destruction ─────────────────────────────────────────
    (
        r"\bexport\s+PATH=/dev/null",
        "PATH destruction blocked",
    ),
    (
        r"\bunset\s+(?:PATH|HOME|USER|SHELL|LANG|LD_PRELOAD|LD_LIBRARY_PATH)\b",
        "Critical env var unset blocked",
    ),
    (
        r"\bexport\s+LD_PRELOAD=",
        "LD_PRELOAD injection blocked",
    ),
    # ── npm/pip destructive ─────────────────────────────────────────────
    (
        r"\bnpm\s+(?:unpublish|deprecate)\b",
        "npm unpublish/deprecate blocked",
    ),
    (
        r"\bpip\s+uninstall\s+-y\s+-r\s+requirements",
        "pip mass uninstall blocked",
    ),
    # ── Terraform destruction ───────────────────────────────────────────
    (
        r"\bterraform\s+destroy\b",
        "terraform destroy blocked",
    ),
    (
        r"\bterraform\s+apply\s+-destroy\b",
        "terraform apply -destroy blocked",
    ),
    # ── Kubernetes destruction ──────────────────────────────────────────
    (
        r"\bkubectl\s+delete\s+(?:namespace|ns|cluster)\b",
        "kubectl delete namespace/cluster blocked",
    ),
    (
        r"\bkubectl\s+drain\b",
        "kubectl drain blocked",
    ),
    (
        r"\bkubectl\s+taint\b",
        "kubectl taint blocked",
    ),
    # ── DNS/hosts sabotage ──────────────────────────────────────────────
    (
        r"\becho\s+.*>>\s*/etc/hosts",
        "Writing to /etc/hosts blocked",
    ),
    (
        r"\btee\s+-a\s+/etc/hosts",
        "Appending to /etc/hosts blocked",
    ),
    # ── Data exfiltration ───────────────────────────────────────────────
    (
        r"\btar\s+-c[a-z]*f\s+\S+\s+/(?:etc|home|var|root)",
        "tar archive of system directory blocked",
    ),
    (
        r"\bscp\s+-r\s+/(?:etc|home|var)\b",
        "scp recursive from system directory blocked",
    ),
    # ── Cryptominer / malware download ──────────────────────────────────
    (
        r"\b(?:wget|curl)\s+.*\|\s*(?:python|python3|node|ruby|perl)\s*$",
        "curled content piped to interpreter blocked",
    ),
]


# ---------------------------------------------------------------------------
# Config management
# ---------------------------------------------------------------------------

class HookConfig:
    """Configuration for the pre-tool-use hook.

    Loads from .claude/hooks/config.yaml or .claude/hooks/config.json.
    Supports whitelist patterns, extra blocklist patterns, dry-run, and
    provider selection.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        dry_run: bool = False,
        provider: str = "auto",
    ):
        self.dry_run = dry_run
        self.provider = provider
        self.whitelist_patterns: List[str] = []
        self.whitelist_commands: Set[str] = set()
        self.extra_blocklist: List[Tuple[str, str]] = []
        self._config_path = config_path or self._default_config_path()
        self._loaded = False

    @staticmethod
    def _default_config_path() -> Path:
        return Path.home() / ".claude" / "hooks" / "config.yaml"

    def load(self) -> None:
        """Load configuration from file, falling back gracefully."""
        if self._loaded:
            return
        self._loaded = True

        # Try project-local config first, then global
        for cfg_path in [
            Path(os.getenv("CLAUDE_PROJECT_DIR", "")) / ".claude" / "hooks" / "config.yaml",
            self._config_path,
            Path.home() / ".claude" / "hooks" / "config.json",
        ]:
            if not cfg_path.exists():
                continue
            try:
                self._parse_config_file(cfg_path)
                break
            except Exception:
                continue

    def _parse_config_file(self, path: Path) -> None:
        """Parse a YAML or JSON config file."""
        raw = path.read_text(encoding="utf-8")

        if path.suffix in (".yaml", ".yml"):
            data = self._parse_yaml(raw)
        elif path.suffix == ".json":
            data = json.loads(raw)
        else:
            return

        if not isinstance(data, dict):
            return

        # Global settings
        if data.get("dry_run") and not self.dry_run:
            self.dry_run = True
        if data.get("provider") and self.provider == "auto":
            self.provider = data["provider"]

        # Whitelist
        whitelist = data.get("whitelist", {})
        if isinstance(whitelist, dict):
            for cmd in whitelist.get("commands", []):
                if isinstance(cmd, str):
                    self.whitelist_commands.add(cmd.strip())
            for pat in whitelist.get("patterns", []):
                if isinstance(pat, str):
                    self.whitelist_patterns.append(pat)

        # Extra blocklist
        blocklist = data.get("blocklist_extra", {})
        if isinstance(blocklist, dict):
            for entry in blocklist.get("patterns", []):
                if isinstance(entry, dict) and "pattern" in entry:
                    self.extra_blocklist.append((
                        entry["pattern"],
                        entry.get("reason", "Custom blocked pattern"),
                    ))
                elif isinstance(entry, str):
                    self.extra_blocklist.append((entry, "Custom blocked pattern"))

    @staticmethod
    def _parse_yaml(raw: str) -> dict:
        """Parse YAML without external dependencies (simple subset)."""
        # Try PyYAML first if available
        try:
            import yaml  # type: ignore
            return yaml.safe_load(raw) or {}
        except ImportError:
            pass

        # Fallback: parse a simple YAML subset (flat keys, lists)
        result: dict = {}
        current_key: Optional[str] = None
        current_list: list = []

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Top-level key: value
            if not line.startswith(" ") and ":" in stripped:
                if current_key and current_list:
                    result[current_key] = current_list
                    current_list = []
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if val:
                    if val.lower() == "true":
                        result[key] = True
                    elif val.lower() == "false":
                        result[key] = False
                    else:
                        result[key] = val.strip('"').strip("'")
                else:
                    current_key = key

            # List item
            elif stripped.startswith("- "):
                item = stripped[2:].strip().strip('"').strip("'")
                if current_key in ("dry_run", "provider"):
                    result[current_key] = True if item.lower() == "true" else item
                else:
                    current_list.append(item)

        if current_key and current_list:
            result[current_key] = current_list

        # Restructure: handle nested whitelist/blocklist_extra
        commands = [c for c in result.pop("commands", []) if isinstance(c, str)]
        patterns = [p for p in result.pop("patterns", []) if isinstance(p, str)]
        if commands or patterns:
            result["whitelist"] = {"commands": commands, "patterns": patterns}

        return result

    def is_whitelisted(self, command: str) -> bool:
        """Check if a command is in the whitelist."""
        self.load()
        if command.strip() in self.whitelist_commands:
            return True
        for pattern in self.whitelist_patterns:
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False

    def get_effective_patterns(self) -> List[Tuple[str, str]]:
        """Return patterns to check: built-in + extra blocklist."""
        self.load()
        return BLOCKED_PATTERNS + self.extra_blocklist


# ── Global config instance ─────────────────────────────────────────────
_config: Optional[HookConfig] = None


def get_config() -> HookConfig:
    global _config
    if _config is None:
        _config = HookConfig()
    return _config


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

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


def _log_dry_run(command: str, reason: str) -> None:
    """Log a dry-run report (would-block)."""
    log_path = _get_log_dir() / "dry-run.log"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = (
        f"[{timestamp}] WOULD-BLOCK (dry-run)\n"
        f"  Reason:   {reason}\n"
        f"  Command:  {command}\n"
        f"{'─' * 60}\n"
    )
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(entry)


# ---------------------------------------------------------------------------
# Command parsing utilities
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Nested shell detection (bash -c "...", sh -c "...")
# ---------------------------------------------------------------------------

def _extract_nested_shell_command(tokens: list[str]) -> Optional[str]:
    """Extract the command string from nested shell invocations like 'bash -c ...'"""
    for i, token in enumerate(tokens):
        name = _command_name(token)
        if name in SHELLS:
            # Look for -c flag
            for j in range(i + 1, min(i + 4, len(tokens))):
                arg = tokens[j]
                if arg == "-c" and j + 1 < len(tokens):
                    return tokens[j + 1]
                if arg.startswith("-c") and len(arg) > 2:
                    return arg[2:]
                if arg == "--":
                    break
            # Also check combined flags like -ic
            for j in range(i + 1, min(i + 4, len(tokens))):
                arg = tokens[j]
                if arg.startswith("-") and "c" in arg[1:] and arg != "-c" and j + 1 < len(tokens):
                    # Combined flag like -ic, the next token is the command
                    idx = arg.index("c")
                    if idx + 1 < len(arg):
                        return arg[idx + 1:]
                    return tokens[j + 1]
    return None


# ---------------------------------------------------------------------------
# SQL comment/literal stripper (from tomlycett's approach, adapted)
# ---------------------------------------------------------------------------

def _strip_sql_comments_and_literals(sql: str) -> str:
    """Mask SQL comments and single-quoted string literals for pattern matching."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\r\n]*", " ", sql)

    output: list[str] = []
    index = 0
    in_string = False
    while index < len(sql):
        character = sql[index]
        if not in_string:
            if character == "'":
                in_string = True
                output.append(" ")
            else:
                output.append(character)
            index += 1
            continue

        if character == "'" and index + 1 < len(sql) and sql[index + 1] == "'":
            output.extend((" ", " "))
            index += 2
        elif character == "'":
            in_string = False
            output.append(" ")
            index += 1
        else:
            output.append(" ")
            index += 1

    return "".join(output)


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------

def check_command(
    command: str,
    config: Optional[HookConfig] = None,
) -> Tuple[bool, str]:
    """Check a command against blocked patterns.

    Uses shlex-aware parsing to inspect each sub-command in a chain.
    Returns (is_blocked, reason).
    """
    if not command or not isinstance(command, str):
        return False, ""

    cfg = config or get_config()
    cfg.load()

    # ── Check whitelist first ───────────────────────────────────────
    if cfg.is_whitelisted(command):
        return False, ""

    # Get effective patterns
    patterns = cfg.get_effective_patterns()

    # ── Shlex-aware: split into sub-commands ────────────────────────
    sub_commands = _parse_shell_commands(command)

    for tokens in sub_commands:
        if not tokens:
            continue

        # ── Check nested shell commands ────────────────────────────
        nested = _extract_nested_shell_command(tokens)
        if nested:
            is_blocked_nested, reason_nested = check_command(nested, cfg)
            if is_blocked_nested:
                return True, f"[nested shell] {reason_nested}"

        unwrapped = _unwrap_command(tokens)
        sub_cmd = " ".join(unwrapped) if unwrapped else " ".join(tokens)

        # Check each sub-command against patterns
        for pattern, reason in patterns:
            try:
                if re.search(pattern, sub_cmd, re.IGNORECASE):
                    return True, reason
            except re.error:
                continue

    # ── Check full command against patterns ────────────────────────
    for pattern, reason in patterns:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return True, reason
        except re.error:
            continue

    # ── Additional heuristics ───────────────────────────────────────
    # Check for destructive operations on important files
    dangerous_targets = [
        r"/etc/(?:passwd|shadow|group|hosts|fstab|sudoers|crontab)",
        r"/boot/",
        r"/var/log/",
        r"~/.ssh/",
        r"~/.gnupg/",
        r"~/.aws/",
        r"~/.config/",
    ]
    for target in dangerous_targets:
        if re.search(rf"\brm\s+.*{target}", command, re.IGNORECASE):
            return True, f"rm targeting critical path {target} blocked"

    # Check for mass file operations without confirmation
    if re.search(r"\brm\s+.*\*", command):
        return True, "rm with wildcard deletion blocked"

    # Check for kubectl delete
    if re.search(
        r"\bkubectl\s+delete\s+(?:pods?|deploy|svc|service|statefulset|daemonset|configmap|secret|ingress)\b",
        command, re.IGNORECASE,
    ):
        return True, "kubectl delete blocked"

    # Check for docker-compose down with volumes
    if re.search(r"\bdocker-compose\s+down\s+-v", command, re.IGNORECASE):
        return True, "docker-compose down -v (volume removal) blocked"

    # Check for npm unpublish
    if re.search(r"\bnpm\s+unpublish\b", command, re.IGNORECASE):
        return True, "npm unpublish blocked"

    # Check for helm delete
    if re.search(r"\bhelm\s+(?:uninstall|delete|del)\b", command, re.IGNORECASE):
        return True, "helm uninstall/delete blocked"

    # Check for destructive ssh operations
    if re.search(r"\bssh-keygen\s+-[Rr]\b", command, re.IGNORECASE):
        return True, "ssh-keygen key removal blocked"

    return False, ""


# ---------------------------------------------------------------------------
# Tool input extraction
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Provider detection and output formatting
# ---------------------------------------------------------------------------

def _detect_provider(payload: dict, config: HookConfig) -> str:
    """Auto-detect the AI coding provider from the payload structure."""
    if config.provider != "auto":
        return config.provider

    hook_event = payload.get("hook_event_name", payload.get("event", ""))
    tool_name = payload.get("tool_name", payload.get("name", ""))

    # Claude Code: hook_event_name=PreToolUse, tool_name=Bash
    if hook_event == "PreToolUse" and tool_name.lower() in ("bash",):
        return "claude-code"

    # Cursor: has cursor-specific fields
    if "cursor" in str(payload).lower():
        return "cursor"

    # Windsurf
    if "windsurf" in str(payload).lower():
        return "windsurf"

    # Fall back to generic
    return "generic"


def _format_denial_output(reason: str, provider: str) -> str:
    """Format the denial output according to the provider's expected format."""
    provider_cfg = PROVIDERS.get(provider, PROVIDERS["generic"])
    fmt = provider_cfg["output_format"]

    if fmt == "permission_decision":
        return json.dumps({
            "decision": "deny",
            "reason": reason,
            "hint": "If this is a legitimate operation, review the command manually.",
        })
    elif fmt == "hook_specific":
        return json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Command blocked: {reason}.",
            }
        })
    else:
        return json.dumps({
            "decision": "deny",
            "reason": reason,
        })


def _format_dry_run_output(
    command: str,
    is_blocked: bool,
    reason: str,
) -> str:
    """Format dry-run output as structured JSON."""
    return json.dumps({
        "mode": "dry-run",
        "command": command,
        "would_block": is_blocked,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, indent=2)


def _format_dry_run_text(
    command: str,
    is_blocked: bool,
    reason: str,
) -> str:
    """Format dry-run output as human-readable text."""
    status = "WOULD BLOCK" if is_blocked else "WOULD ALLOW"
    lines = [
        f"[DRY-RUN] {status}",
        f"  Command: {command}",
    ]
    if reason:
        lines.append(f"  Reason:  {reason}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Read tool-use JSON from stdin and decide allow/deny."""
    parser = argparse.ArgumentParser(
        description="Pre-tool-use safety hook for Claude Code and compatible AI tools",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be blocked without actually denying",
    )
    parser.add_argument(
        "--dry-run-json", action="store_true",
        help="Dry-run output as structured JSON (implies --dry-run)",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to config file (YAML or JSON)",
    )
    parser.add_argument(
        "--provider", type=str, default="auto",
        choices=["auto", "claude-code", "cursor", "windsurf", "copilot", "aider", "generic"],
        help="Override auto-detected AI coding provider",
    )
    parser.add_argument(
        "--validate-config", action="store_true",
        help="Validate the config file and exit",
    )
    args, _ = parser.parse_known_args()

    # ── Config validation mode ──────────────────────────────────────
    if args.validate_config:
        from pathlib import Path as _Path
        cfg_path = args.config or HookConfig._default_config_path()
        result = validate_config_file(cfg_path)
        if result["valid"]:
            print(json.dumps(result, indent=2))
            return 0
        else:
            print(json.dumps(result, indent=2), file=sys.stderr)
            return 1

    # ── Dry-run implies dry_run mode ─────────────────────────────────
    dry_run = args.dry_run or args.dry_run_json
    dry_run_json = args.dry_run_json

    # ── Initialize config ───────────────────────────────────────────
    config = HookConfig(
        config_path=args.config,
        dry_run=dry_run,
        provider=args.provider,
    )
    config.load()

    # Update global config
    global _config
    _config = config

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            # No input → allow
            return 0

        data = json.loads(raw)

        # Detect provider
        provider = _detect_provider(data, config)
        provider_cfg = PROVIDERS.get(provider, PROVIDERS["generic"])

        # Only intercept the configured tool name
        tool_name = data.get("tool_name", data.get("name", ""))
        expected_tool = provider_cfg["tool_name"].lower()

        if expected_tool and tool_name.lower() != expected_tool:
            return 0  # Allow non-target tools

        # Extract the command
        tool_input = data.get("tool_input", data.get("input", {}))
        command = _extract_command(tool_input)

        if not command:
            return 0  # No command to check

        # Check against blocked patterns
        is_blocked, reason = check_command(command, config)

        # ── Dry-run mode: report only ───────────────────────────────
        if dry_run:
            if is_blocked:
                _log_dry_run(command, reason)
            if dry_run_json:
                sys.stdout.write(_format_dry_run_output(command, is_blocked, reason))
                sys.stdout.write("\n")
            else:
                sys.stdout.write(_format_dry_run_text(command, is_blocked, reason))
                sys.stdout.write("\n")
            return 0  # Never deny in dry-run mode

        if is_blocked:
            _log_blocked(command, reason)
            # Write denial message for the provider
            msg = _format_denial_output(reason, provider)
            sys.stdout.write(msg)
            sys.stdout.write("\n")
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


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def validate_config_file(config_path: Path) -> dict:
    """Validate a config file and return a report.

    Returns a dict with:
      - valid: bool
      - errors: list of error messages
      - warnings: list of warning messages
      - patterns_count: number of whitelist patterns
      - commands_count: number of whitelist commands
      - extra_blocklist_count: number of extra blocklist patterns
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not config_path.exists():
        return {
            "valid": False,
            "errors": [f"Config file not found: {config_path}"],
            "warnings": [],
            "patterns_count": 0,
            "commands_count": 0,
            "extra_blocklist_count": 0,
        }

    try:
        raw = config_path.read_text(encoding="utf-8")
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Cannot read config file: {e}"],
            "warnings": [],
            "patterns_count": 0,
            "commands_count": 0,
            "extra_blocklist_count": 0,
        }

    # Parse
    if config_path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(raw) or {}
        except ImportError:
            try:
                data = HookConfig._parse_yaml(raw)
            except Exception as e:
                return {
                    "valid": False,
                    "errors": [f"YAML parse error: {e}"],
                    "warnings": [],
                    "patterns_count": 0,
                    "commands_count": 0,
                    "extra_blocklist_count": 0,
                }
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"YAML parse error: {e}"],
                "warnings": [],
                "patterns_count": 0,
                "commands_count": 0,
                "extra_blocklist_count": 0,
            }
    elif config_path.suffix == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "errors": [f"JSON parse error: {e}"],
                "warnings": [],
                "patterns_count": 0,
                "commands_count": 0,
                "extra_blocklist_count": 0,
            }
    else:
        return {
            "valid": False,
            "errors": [f"Unsupported config format: {config_path.suffix}"],
            "warnings": [],
            "patterns_count": 0,
            "commands_count": 0,
            "extra_blocklist_count": 0,
        }

    if not isinstance(data, dict):
        return {
            "valid": False,
            "errors": ["Config must be a dictionary/object"],
            "warnings": [],
            "patterns_count": 0,
            "commands_count": 0,
            "extra_blocklist_count": 0,
        }

    whitelist = data.get("whitelist", {})
    patterns_count = 0
    commands_count = 0
    extra_blocklist_count = 0

    if isinstance(whitelist, dict):
        # Validate whitelist patterns
        for i, pat in enumerate(whitelist.get("patterns", [])):
            if not isinstance(pat, str):
                errors.append(f"whitelist.patterns[{i}]: must be a string")
                continue
            try:
                re.compile(pat)
                patterns_count += 1
            except re.error as e:
                errors.append(f"whitelist.patterns[{i}] '{pat}': invalid regex — {e}")

        # Validate whitelist commands
        for i, cmd in enumerate(whitelist.get("commands", [])):
            if not isinstance(cmd, str):
                errors.append(f"whitelist.commands[{i}]: must be a string")
                continue
            commands_count += 1
    else:
        warnings.append("whitelist should be a dictionary with 'patterns' and 'commands' keys")

    # Validate extra blocklist
    blocklist = data.get("blocklist_extra", {})
    if isinstance(blocklist, dict):
        for i, entry in enumerate(blocklist.get("patterns", [])):
            if isinstance(entry, dict):
                pat = entry.get("pattern", "")
                if not pat:
                    errors.append(f"blocklist_extra.patterns[{i}]: missing 'pattern' key")
                    continue
                try:
                    re.compile(pat)
                    extra_blocklist_count += 1
                except re.error as e:
                    errors.append(f"blocklist_extra.patterns[{i}] '{pat}': invalid regex — {e}")
            elif isinstance(entry, str):
                try:
                    re.compile(entry)
                    extra_blocklist_count += 1
                except re.error as e:
                    errors.append(f"blocklist_extra.patterns[{i}] '{entry}': invalid regex — {e}")
            else:
                errors.append(f"blocklist_extra.patterns[{i}]: must be string or object with 'pattern' key")
    else:
        warnings.append("blocklist_extra should be a dictionary with 'patterns' key")

    # Validate provider
    provider = data.get("provider", "auto")
    if provider not in ("auto", "claude-code", "cursor", "windsurf", "copilot", "aider", "generic"):
        warnings.append(f"Unknown provider '{provider}'; using 'auto'")

    # Validate dry_run
    dry_run = data.get("dry_run")
    if dry_run is not None and not isinstance(dry_run, bool):
        warnings.append("dry_run should be a boolean (true/false)")

    valid = len(errors) == 0

    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "patterns_count": patterns_count,
        "commands_count": commands_count,
        "extra_blocklist_count": extra_blocklist_count,
        "config_path": str(config_path),
    }


if __name__ == "__main__":
    sys.exit(main())
