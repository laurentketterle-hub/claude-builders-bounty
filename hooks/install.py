#!/usr/bin/env python3
"""Install and auto-register the pre-tool-use safety hook in Claude Code.

Usage:
    python hooks/install.py                  # install to ~/.claude/
    python hooks/install.py --project .      # install to current project
    python hooks/install.py --uninstall      # remove the hook

Installs the hook script to ~/.claude/hooks/ and updates
~/.claude/settings.json so Claude Code picks it up automatically.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HOOK_NAME = "pre-tool-use.py"
HOOK_SOURCE = Path(__file__).resolve().parent / HOOK_NAME


def install(target_dir: Path) -> Path:
    """Copy the hook to target_dir/.claude/hooks/ and register it."""
    claude_dir = target_dir / ".claude"
    hooks_dir = claude_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    dest = hooks_dir / HOOK_NAME
    shutil.copy2(HOOK_SOURCE, dest)
    dest.chmod(0o755)
    print(f"✓ Hook installed to: {dest}")

    # Register in settings.json
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    else:
        settings = {}

    hooks_cfg = settings.setdefault("hooks", {})
    pre_tool_use = hooks_cfg.setdefault("PreToolUse", [])

    command = f'"{sys.executable}" "{dest}"'
    entry = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": command}],
    }

    already = any(
        e.get("matcher") == "Bash"
        and any(HOOK_NAME in h.get("command", "") for h in e.get("hooks", []))
        for e in pre_tool_use
    )
    if not already:
        pre_tool_use.append(entry)
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        print(f"✓ Hook registered in: {settings_path}")
    else:
        print("ℹ Hook already registered")

    return dest


def uninstall(target_dir: Path) -> None:
    """Remove the hook registration and script."""
    claude_dir = target_dir / ".claude"
    settings_path = claude_dir / "settings.json"

    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        hooks_cfg = settings.get("hooks", {})
        pre_tool_use = hooks_cfg.get("PreToolUse", [])
        new_list = [
            e for e in pre_tool_use
            if not (e.get("matcher") == "Bash"
                    and any(HOOK_NAME in h.get("command", "") for h in e.get("hooks", [])))
        ]
        if len(new_list) != len(pre_tool_use):
            hooks_cfg["PreToolUse"] = new_list
            settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            print(f"✓ Hook unregistered from: {settings_path}")
        else:
            print("ℹ Hook was not registered")

    hook_path = claude_dir / "hooks" / HOOK_NAME
    if hook_path.exists():
        hook_path.unlink()
        print(f"✓ Hook removed from: {hook_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install/uninstall the pre-tool-use safety hook")
    parser.add_argument("--project", type=Path, help="Target project directory (default: ~/)")
    parser.add_argument("--uninstall", action="store_true", help="Remove the hook")
    args = parser.parse_args()

    target = args.project or Path.home()

    if args.uninstall:
        uninstall(target)
    else:
        install(target)


if __name__ == "__main__":
    main()
