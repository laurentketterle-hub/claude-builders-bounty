#!/usr/bin/env python3
# Wrapper script called by Claude Code from .claude/settings.json
# Delegates to hooks/pre-tool-use.py relative to project root.
import subprocess
import sys
from pathlib import Path

hook = Path(__file__).resolve().parent.parent.parent / "hooks" / "pre-tool-use.py"
result = subprocess.run(
    [sys.executable, str(hook)],
    input=sys.stdin.read(),
    capture_output=True,
    text=True,
)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
