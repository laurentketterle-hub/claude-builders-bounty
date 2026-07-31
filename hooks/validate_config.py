#!/usr/bin/env python3
"""Config validation utility for the pre-tool-use safety hook.

Validates hook configuration files (YAML or JSON) and reports errors.
Can be used standalone or imported as a module.

Usage:
    python hooks/validate_config.py                          # validate default config
    python hooks/validate_config.py --config path/to/config.yaml
    python hooks/validate_config.py --generate               # generate a safe template
    python hooks/validate_config.py --check-pattern "rm -rf" # test a pattern
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Pattern validation
# ---------------------------------------------------------------------------

def validate_pattern(pattern: str) -> Tuple[bool, str]:
    """Validate a single regex pattern.

    Returns (is_valid, error_message).
    """
    if not pattern or not isinstance(pattern, str):
        return False, "Pattern must be a non-empty string"

    # Check for catastrophic backtracking patterns
    if _has_catastrophic_backtracking(pattern):
        return False, f"Pattern may cause catastrophic backtracking: {pattern!r}"

    try:
        re.compile(pattern)
        return True, ""
    except re.error as e:
        return False, f"Invalid regex: {e}"


def _has_catastrophic_backtracking(pattern: str) -> bool:
    """Heuristic check for patterns prone to catastrophic backtracking.

    Detects patterns like (a+)+, (a*)*, (.+)+, etc.
    """
    nested_quantifiers = [
        r"\(\s*(?:\.[*+]|\w+[*+])\s*\)\s*[*+]",
        r"\[[^\]]*\][*+]\s*[*+]",
        r"\(\?:.*\)\s*[*+]\s*[*+]",
    ]
    for danger in nested_quantifiers:
        if re.search(danger, pattern):
            return True
    return False


def validate_whitelist(whitelist: dict) -> List[str]:
    """Validate a whitelist config section.

    Returns a list of error messages (empty if valid).
    """
    errors = []
    if not isinstance(whitelist, dict):
        return ["whitelist must be a dictionary"]

    # Validate patterns
    for i, pat in enumerate(whitelist.get("patterns", [])):
        if not isinstance(pat, str):
            errors.append(f"whitelist.patterns[{i}]: must be a string")
            continue
        valid, msg = validate_pattern(pat)
        if not valid:
            errors.append(f"whitelist.patterns[{i}]: {msg}")

    # Validate commands
    for i, cmd in enumerate(whitelist.get("commands", [])):
        if not isinstance(cmd, str):
            errors.append(f"whitelist.commands[{i}]: must be a string")
        elif not cmd.strip():
            errors.append(f"whitelist.commands[{i}]: empty command")

    return errors


def validate_blocklist_extra(blocklist: dict) -> List[str]:
    """Validate an extra blocklist config section."""
    errors = []
    if not isinstance(blocklist, dict):
        return ["blocklist_extra must be a dictionary"]

    for i, entry in enumerate(blocklist.get("patterns", [])):
        if isinstance(entry, dict):
            pat = entry.get("pattern", "")
            reason = entry.get("reason", "")
            if not pat:
                errors.append(f"blocklist_extra.patterns[{i}]: missing 'pattern' key")
                continue
            if not isinstance(reason, str):
                errors.append(f"blocklist_extra.patterns[{i}]: 'reason' must be a string")
        elif isinstance(entry, str):
            pat = entry
        else:
            errors.append(f"blocklist_extra.patterns[{i}]: must be a string or object")
            continue

        valid, msg = validate_pattern(pat)
        if not valid:
            errors.append(f"blocklist_extra.patterns[{i}]: {msg}")

    return errors


def validate_config(data: dict) -> Dict[str, any]:
    """Validate a complete config dict.

    Returns a report with errors, warnings, and counts.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(data, dict):
        return {
            "valid": False,
            "errors": ["Config must be a dictionary/object"],
            "warnings": [],
            "patterns_valid": 0,
            "patterns_invalid": 0,
            "commands_count": 0,
            "extra_patterns_valid": 0,
            "extra_patterns_invalid": 0,
        }

    # Validate whitelist
    whitelist = data.get("whitelist", {})
    whitelist_errors = validate_whitelist(whitelist)
    errors.extend(whitelist_errors)

    # Validate blocklist_extra
    blocklist = data.get("blocklist_extra", {})
    blocklist_errors = validate_blocklist_extra(blocklist)
    errors.extend(blocklist_errors)

    # Validate provider
    valid_providers = {"auto", "claude-code", "cursor", "windsurf", "copilot", "aider", "generic"}
    provider = data.get("provider", "auto")
    if provider not in valid_providers:
        warnings.append(f"Unknown provider '{provider}'; valid: {', '.join(sorted(valid_providers))}")

    # Validate dry_run
    dry_run = data.get("dry_run")
    if dry_run is not None and not isinstance(dry_run, bool):
        warnings.append("dry_run must be a boolean (true/false)")

    # Count valid/invalid patterns
    whitelist_patterns = whitelist.get("patterns", []) if isinstance(whitelist, dict) else []
    patterns_valid = sum(
        1 for p in whitelist_patterns if isinstance(p, str) and validate_pattern(p)[0]
    )
    patterns_invalid = len([e for e in whitelist_errors if "whitelist.patterns" in e])

    blocklist_patterns = blocklist.get("patterns", []) if isinstance(blocklist, dict) else []
    extra_valid = 0
    extra_invalid = 0
    for entry in blocklist_patterns:
        pat = entry.get("pattern", "") if isinstance(entry, dict) else entry
        if isinstance(pat, str) and validate_pattern(pat)[0]:
            extra_valid += 1
        else:
            extra_invalid += 1

    commands_count = len(whitelist.get("commands", [])) if isinstance(whitelist, dict) else 0

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "patterns_valid": patterns_valid,
        "patterns_invalid": patterns_invalid,
        "commands_count": commands_count,
        "extra_patterns_valid": extra_valid,
        "extra_patterns_invalid": extra_invalid,
    }


def validate_config_file(path: Path) -> Dict[str, any]:
    """Load and validate a config file."""
    errors = []
    if not path.exists():
        return {
            "valid": False,
            "errors": [f"File not found: {path}"],
            "warnings": [],
            "file": str(path),
        }

    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Cannot read file: {e}"],
            "warnings": [],
            "file": str(path),
        }

    data = None
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(raw)
        except ImportError:
            try:
                from hooks.pre_tool_use import HookConfig
                data = HookConfig._parse_yaml(raw)
            except Exception:
                return {
                    "valid": False,
                    "errors": ["Cannot parse YAML (PyYAML not installed, fallback failed)"],
                    "warnings": [],
                    "file": str(path),
                }
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"YAML parse error: {e}"],
                "warnings": [],
                "file": str(path),
            }
    elif path.suffix == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "errors": [f"JSON parse error: {e}"],
                "warnings": [],
                "file": str(path),
            }
    else:
        return {
            "valid": False,
            "errors": [f"Unsupported format: {path.suffix} (use .yaml, .yml, or .json)"],
            "warnings": [],
            "file": str(path),
        }

    if data is None:
        return {
            "valid": False,
            "errors": ["Config is empty"],
            "warnings": [],
            "file": str(path),
        }

    report = validate_config(data)
    report["file"] = str(path)
    return report


# ---------------------------------------------------------------------------
# Config template generation
# ---------------------------------------------------------------------------

SAFE_CONFIG_TEMPLATE_YAML = """# Pre-tool-use safety hook configuration
# See hooks/README.md for full documentation

# Whitelist: commands and patterns that should ALWAYS be allowed
whitelist:
  # Exact command strings to allow (overrides all blocklists)
  commands:
    # - "git push --force origin feature/my-sandbox-branch"
    # - "terraform destroy -auto-approve"

  # Regex patterns that bypass blocking (case-insensitive)
  patterns:
    # - "git push --force origin feature/"
    # - "rm -rf /tmp/safe-"

# Extra blocklist: additional patterns to block beyond the built-in 60+
blocklist_extra:
  patterns:
    # Option 1: simple string patterns
    # - "gh pr close --delete-branch"
    # - "gh repo delete"

    # Option 2: pattern + reason (more descriptive)
    # - pattern: "gh secret delete"
    #   reason: "GitHub secret deletion can break CI/CD"

# Provider: auto-detect or force a specific AI coding tool
# Valid: auto, claude-code, cursor, windsurf, copilot, aider, generic
provider: auto

# Dry-run mode: report what WOULD be blocked without actually denying
# Useful for testing before enabling the hook
dry_run: false
"""


def generate_config_template(output_path: Path, overwrite: bool = False) -> str:
    """Generate a safe config template.

    Returns the path to the generated file (as string).
    """
    if output_path.exists() and not overwrite:
        return f"File already exists: {output_path} (use --overwrite to replace)"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(SAFE_CONFIG_TEMPLATE_YAML, encoding="utf-8")
    return f"Config template generated: {output_path}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate hook configuration for the pre-tool-use safety hook",
    )
    parser.add_argument(
        "--config", "-c", type=Path,
        default=Path.home() / ".claude" / "hooks" / "config.yaml",
        help="Path to config file (default: ~/.claude/hooks/config.yaml)",
    )
    parser.add_argument(
        "--generate", "-g", action="store_true",
        help="Generate a safe config template",
    )
    parser.add_argument(
        "--output", "-o", type=Path,
        help="Output path for generated template (default: same as --config)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing config when generating",
    )
    parser.add_argument(
        "--check-pattern", type=str,
        help="Test a single regex pattern for validity",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output validation report as JSON",
    )
    args = parser.parse_args()

    # Pattern test mode
    if args.check_pattern:
        valid, msg = validate_pattern(args.check_pattern)
        if valid:
            print(f"✓ Pattern is valid: {args.check_pattern}")
            return 0
        else:
            print(f"✗ {msg}")
            return 1

    # Generate mode
    if args.generate:
        output = args.output or args.config
        result = generate_config_template(output, args.overwrite)
        print(result)
        return 0

    # Validate mode (default)
    report = validate_config_file(args.config)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report)

    return 0 if report["valid"] else 1


def _print_report(report: dict) -> None:
    """Print a human-readable validation report."""
    file_path = report.get("file", "unknown")
    print(f"Config: {file_path}")
    print(f"Status: {'✓ VALID' if report['valid'] else '✗ INVALID'}")

    if report.get("warnings"):
        print(f"\n  Warnings ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"    ⚠ {w}")

    if report.get("errors"):
        print(f"\n  Errors ({len(report['errors'])}):")
        for e in report["errors"]:
            print(f"    ✗ {e}")

    # Stats
    print(f"\n  Whitelist patterns valid:   {report.get('patterns_valid', 0)}")
    print(f"  Whitelist patterns invalid: {report.get('patterns_invalid', 0)}")
    print(f"  Whitelist commands:         {report.get('commands_count', 0)}")
    print(f"  Extra blocklist valid:      {report.get('extra_patterns_valid', 0)}")
    print(f"  Extra blocklist invalid:    {report.get('extra_patterns_invalid', 0)}")


if __name__ == "__main__":
    sys.exit(main())
