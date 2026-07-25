#!/usr/bin/env python3
"""PR Review Agent — Structured Markdown PR review via GitHub API.

Usage:
    python pr_review.py --pr https://github.com/owner/repo/pull/123
    python pr_review.py --pr https://github.com/owner/repo/pull/123 --token ghp_xxx

Requirements: Python 3.8+, GITHUB_TOKEN env var or --token flag.
"""

import argparse, json, os, re, sys, urllib.request


def fetch_pr(owner: str, repo: str, pr_num: int, token: str) -> dict:
    """Fetch PR data from GitHub API."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    # PR details
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        pr = json.loads(resp.read())

    # PR diff
    req2 = urllib.request.Request(url, headers={**headers, "Accept": "application/vnd.github.v3.diff"})
    with urllib.request.urlopen(req2, timeout=15) as resp:
        diff = resp.read().decode()

    # PR files
    url3 = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}/files?per_page=100"
    req3 = urllib.request.Request(url3, headers=headers)
    with urllib.request.urlopen(req3, timeout=15) as resp:
        files = json.loads(resp.read())

    return {"pr": pr, "diff": diff, "files": files}


def analyze_pr(pr_data: dict) -> str:
    """Analyze PR and generate structured review."""
    pr = pr_data["pr"]
    diff = pr_data["diff"]
    files = pr_data["files"]

    title = pr.get("title", "Untitled")
    body = pr.get("body", "") or ""
    additions = sum(f.get("additions", 0) for f in files)
    deletions = sum(f.get("deletions", 0) for f in files)
    changed_files = len(files)
    user = pr.get("user", {}).get("login", "unknown")

    risks = []
    suggestions = []
    positives = []

    # Heuristic analysis
    if additions > 500:
        risks.append(f"Large PR: {additions} additions across {changed_files} files — consider splitting")
    if deletions > 300:
        risks.append(f"Substantial deletions ({deletions} lines) — verify no functionality removed unintentionally")

    # Check for common issues in diff
    if "TODO" in diff or "FIXME" in diff:
        suggestions.append("Outstanding TODOs/FIXMEs found — address before merging")
    if "console.log" in diff or "print(" in diff:
        suggestions.append("Debug logging found — remove before production merge")
    if "password" in diff.lower() or "secret" in diff.lower() or "token" in diff.lower():
        risks.append("Potential hardcoded credentials detected — verify")
    if "except:" in diff or "except Exception:" in diff and "pass" in diff:
        risks.append("Bare except clauses found — may silently swallow errors")

    # Check file types
    test_files = [f for f in files if "test" in f.get("filename", "").lower()]
    if not test_files and changed_files > 1:
        suggestions.append(f"No test files detected among {changed_files} changed files — consider adding tests")

    # Security patterns
    if "subprocess" in diff or "os.system" in diff or "exec(" in diff:
        risks.append("Shell command execution detected — review for injection risks")

    if not body or len(body) < 50:
        suggestions.append("PR description is brief — add context about what and why")

    if changed_files <= 3 and additions <= 200:
        positives.append("Small, focused change — easy to review")
    if test_files:
        positives.append(f"Tests included ({len(test_files)} test files)")
    if "fix" in title.lower() or "bug" in title.lower():
        positives.append("Clear bug-fix intent in title")

    # Build review
    lines = [
        f"## 🔍 PR Review: {title}",
        f"",
        f"**Author**: @{user} | **Files**: {changed_files} | **+{additions} −{deletions}",
        f"",
        f"### 📝 Summary",
        f"This PR changes {changed_files} file(s) with {additions} additions and {deletions} deletions.",
    ]

    if risks:
        lines.append("")
        lines.append("### ⚠️ Identified Risks")
        for r in risks:
            lines.append(f"- {r}")

    if suggestions:
        lines.append("")
        lines.append("### 💡 Improvement Suggestions")
        for s in suggestions:
            lines.append(f"- {s}")

    if positives:
        lines.append("")
        lines.append("### 🟢 What Looks Good")
        for p in positives:
            lines.append(f"- {p}")

    # Confidence
    if len(risks) >= 3 or additions > 1000:
        confidence = "Low — significant scope or multiple risks"
    elif len(risks) >= 1:
        confidence = "Medium — some concerns but generally sound"
    else:
        confidence = "High — clean, focused change"

    lines.append("")
    lines.append(f"### 📊 Confidence Score")
    lines.append(f"**{confidence}**")
    lines.append("")
    lines.append("---")
    lines.append("*Automated review by PR Reviewer Agent — always verify manually.*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="PR Review Agent")
    parser.add_argument("--pr", required=True, help="GitHub PR URL")
    parser.add_argument("--token", help="GitHub token (or set GITHUB_TOKEN env var)")
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: Set GITHUB_TOKEN env var or use --token", file=sys.stderr)
        sys.exit(1)

    # Parse PR URL
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", args.pr)
    if not match:
        print("Error: Invalid PR URL format", file=sys.stderr)
        sys.exit(1)

    owner, repo, pr_num = match.group(1), match.group(2), int(match.group(3))
    print(f"🔍 Reviewing {owner}/{repo}#{pr_num}...", file=sys.stderr)

    pr_data = fetch_pr(owner, repo, pr_num, token)
    review = analyze_pr(pr_data)
    print(review)


if __name__ == "__main__":
    main()
