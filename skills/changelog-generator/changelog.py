#!/usr/bin/env python3
"""
changelog.py — Generate a structured CHANGELOG.md from git history.

Supports Conventional Commits (feat:, fix:, chore:, docs:, etc.),
auto-detection of the previous tag, custom output paths, and custom
commit ranges.

Usage:
    python changelog.py                          # Auto-detect, output CHANGELOG.md
    python changelog.py --output RELEASE.md      # Custom output path
    python changelog.py --range v1.0.0..HEAD     # Custom commit range
    python changelog.py --range v1.0.0..v2.0.0   # Range between two tags
    python changelog.py -h                       # Show help
"""

import argparse
import subprocess
import sys
import os
from datetime import date
from collections import defaultdict
from typing import Dict, List, Optional


# ── Conventional Commits categories (emoji + label) ──────────────────────────
CATEGORIES = [
    ("🚀 Features",      ["feat"]),
    ("🐛 Bug Fixes",     ["fix"]),
    ("🔒 Security",      ["security"]),
    ("⚡ Performance",   ["perf"]),
    ("📦 Dependencies",  ["deps", "bump"]),
    ("♻️ Refactoring",   ["refactor"]),
    ("📝 Documentation", ["docs"]),
    ("🎨 Style",         ["style"]),
    ("🧪 Tests",         ["test"]),
    ("🏗️ Build / CI",    ["build", "ci"]),
    ("🔧 Chores",        ["chore"]),
    ("📌 Other Changes", []),  # fallback
]


def run_git(*args: str) -> str:
    """Run a git command and return stdout, or raise an error."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Git error: {e.stderr.strip()}" if e.stderr else str(e))
    except FileNotFoundError:
        raise SystemExit("Error: 'git' command not found. Is git installed?")


def is_git_repo() -> bool:
    """Check if the current directory is inside a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_repo_name() -> str:
    """Get the repository name from the top-level directory."""
    try:
        toplevel = run_git("rev-parse", "--show-toplevel")
        return os.path.basename(toplevel) or "unknown"
    except SystemExit:
        return "unknown"


def detect_range() -> str:
    """Auto-detect the commit range: latest tag → HEAD, or root commit → HEAD."""
    try:
        tag = run_git("describe", "--tags", "--abbrev=0")
        return f"{tag}..HEAD"
    except SystemExit:
        pass

    try:
        root = run_git("rev-list", "--max-parents=0", "HEAD")
        return f"{root}..HEAD"
    except SystemExit:
        raise SystemExit("Error: No commits found in this repository.")


def parse_conventional_commit(line: str) -> Optional[str]:
    """
    Parse a Conventional Commit prefix like 'feat:' or 'fix(scope):'.
    Returns the type string (lowercase), or None if not a conventional commit.
    """
    import re
    match = re.match(r'^(\w+)(\([^)]*\))?!?:\s', line)
    if match:
        return match.group(1).lower()
    return None


def categorize_legacy(line: str) -> str:
    """Fallback categorization for non-conventional commits."""
    import re
    lower = line.lower()
    if re.match(r'^(add|feat|new)\b', lower):
        return "feat"
    if re.match(r'^(fix|bug|hotfix|patch)\b', lower):
        return "fix"
    if re.match(r'^security\b', lower):
        return "security"
    if re.match(r'^perf\b', lower):
        return "perf"
    if re.match(r'^(deps|bump)\b', lower):
        return "deps"
    if re.match(r'^refactor\b', lower):
        return "refactor"
    if re.match(r'^docs\b', lower):
        return "docs"
    if re.match(r'^style\b', lower):
        return "style"
    if re.match(r'^test\b', lower):
        return "test"
    if re.match(r'^(build|ci)\b', lower):
        return "build"
    if re.match(r'^chore\b', lower):
        return "chore"
    return ""


def categorize_commits(commits: List[str]) -> Dict[str, List[str]]:
    """
    Categorize commits by their Conventional Commit type.
    Returns a dict mapping category label → list of commit messages.
    """
    buckets: Dict[str, List[str]] = defaultdict(list)

    for raw in commits:
        line = raw.strip()
        if not line:
            continue

        cc_type = parse_conventional_commit(line)
        if cc_type:
            # Map type to category label
            matched = False
            for label, types in CATEGORIES:
                if cc_type in types:
                    buckets[label].append(line)
                    matched = True
                    break
            if not matched:
                buckets["📌 Other Changes"].append(line)
        else:
            # Fallback to legacy detection
            legacy = categorize_legacy(line)
            if legacy:
                for label, types in CATEGORIES:
                    if legacy in types:
                        buckets[label].append(line)
                        break
            else:
                buckets["📌 Other Changes"].append(line)

    return dict(buckets)


def get_version_info(range_spec: str) -> tuple:
    """Determine version string and date."""
    today = date.today().isoformat()

    # Try to get the end tag from the range
    if ".." in range_spec:
        end_ref = range_spec.split("..")[-1].strip()
        if end_ref and end_ref != "HEAD":
            try:
                tag = run_git("describe", "--tags", "--abbrev=0", end_ref)
                return tag, today
            except SystemExit:
                pass

    # Fallback: latest tag
    try:
        tag = run_git("describe", "--tags", "--abbrev=0")
        return tag, today
    except SystemExit:
        return "Unreleased", today


def write_changelog(
    output_path: str,
    repo_name: str,
    version: str,
    date_str: str,
    buckets: Dict[str, List[str]],
    total_commits: int,
) -> None:
    """Write the structured CHANGELOG.md file."""
    lines = []
    lines.append(f"# {repo_name} — Changelog")
    lines.append("")
    lines.append(f"## [{version}] — {date_str}")
    lines.append("")

    for label, _types in CATEGORIES:
        if label not in buckets or not buckets[label]:
            continue
        lines.append(f"### {label}")
        lines.append("")
        for commit in buckets[label]:
            lines.append(f"- {commit}")
        lines.append("")

    lines.append("---")
    lines.append(
        "*Generated by [changelog-generator]"
        "(https://github.com/laurentketterle-hub/claude-builders-bounty"
        "/tree/main/skills/changelog-generator)*"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Summary
    counts = "  ".join(
        f"{label.split(' ', 1)[1] if ' ' in label else label}={len(buckets.get(label, []))}"
        for label, _ in CATEGORIES
        if buckets.get(label)
    )
    print(f"✅ CHANGELOG written to {output_path}")
    print(f"   Commits: {total_commits} | Categories: {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a structured CHANGELOG.md from git history.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python changelog.py
  python changelog.py --output RELEASE_NOTES.md
  python changelog.py --range v1.0.0..v2.0.0
  python changelog.py --output docs/CHANGELOG.md --range v1.0.0..
        """,
    )
    parser.add_argument(
        "--output", "-o",
        default="CHANGELOG.md",
        help="Output file path (default: CHANGELOG.md)",
    )
    parser.add_argument(
        "--range", "-r",
        default="",
        help='Git revision range (e.g., "v1.0.0..HEAD"). Auto-detected if omitted.',
    )
    args = parser.parse_args()

    # Validate git repo
    if not is_git_repo():
        print("Error: Not a git repository. Run this script from within a git repo.", file=sys.stderr)
        sys.exit(1)

    # Determine range
    range_spec = args.range or detect_range()
    print(f"   Range: {range_spec}")

    # Collect commits
    try:
        raw_commits = run_git("log", range_spec, "--pretty=format:%s")
    except SystemExit:
        raw_commits = ""

    commits = [c for c in raw_commits.split("\n") if c.strip()]
    if not commits:
        print(f"Error: No commits found in range '{range_spec}'. Check your range and try again.", file=sys.stderr)
        sys.exit(1)

    # Categorize
    buckets = categorize_commits(commits)
    total = len(commits)

    # Version info
    repo_name = get_repo_name()
    version, date_str = get_version_info(range_spec)

    # Write output
    write_changelog(args.output, repo_name, version, date_str, buckets, total)


if __name__ == "__main__":
    main()
