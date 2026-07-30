#!/usr/bin/env python3
"""Dry-run the n8n weekly dev summary workflow locally for testing.

Simulates all GitHub API calls and generates a sample weekly summary
without requiring n8n or Claude API access during development.
"""
import json, os, sys
from datetime import datetime, timedelta

# Simulated GitHub data
SAMPLE_COMMITS = [
    {"sha": "abc123", "author": "alice", "message": "feat: add user authentication", "date": "2026-07-28"},
    {"sha": "def456", "author": "bob", "message": "fix: resolve login timeout", "date": "2026-07-27"},
    {"sha": "ghi789", "author": "alice", "message": "docs: update API documentation", "date": "2026-07-26"},
    {"sha": "jkl012", "author": "carol", "message": "refactor: extract auth middleware", "date": "2026-07-25"},
    {"sha": "mno345", "author": "bob", "message": "test: add auth integration tests", "date": "2026-07-24"},
]

SAMPLE_ISSUES = [
    {"number": 42, "title": "Login page not rendering on Safari", "state": "closed", "closed_by": "alice"},
    {"number": 43, "title": "Add dark mode support", "state": "open", "labels": ["enhancement"]},
    {"number": 44, "title": "Memory leak in WebSocket handler", "state": "closed", "closed_by": "bob"},
]

SAMPLE_PRS = [
    {"number": 101, "title": "feat: OAuth2 provider integration", "author": "alice", "merged_at": "2026-07-29"},
    {"number": 102, "title": "fix: CORS headers for API v2", "author": "bob", "merged_at": "2026-07-28"},
]

def simulate_github_api(endpoint):
    """Simulate GitHub API calls for dry-run testing."""
    if "commits" in endpoint:
        return SAMPLE_COMMITS
    elif "issues" in endpoint and "state=closed" in endpoint:
        return SAMPLE_ISSUES
    elif "pulls" in endpoint:
        return SAMPLE_PRS
    return []

def generate_dry_run_summary():
    """Generate a sample weekly summary without API access."""
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    commits = simulate_github_api("commits")
    issues = simulate_github_api("issues")
    prs = simulate_github_api("pulls")
    
    # Calculate stats
    authors = set(c["author"] for c in commits)
    merged_prs = [p for p in prs if p.get("merged_at")]
    closed_issues = [i for i in issues if i.get("state") == "closed"]
    
    summary = {
        "period": "{} to {}".format(week_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")),
        "total_commits": len(commits),
        "unique_authors": len(authors),
        "merged_prs": len(merged_prs),
        "closed_issues": len(closed_issues),
        "top_contributors": {},
        "commits": commits,
        "prs": merged_prs,
        "issues_closed": closed_issues,
    }
    
    # Count per author
    for c in commits:
        author = c["author"]
        if author not in summary["top_contributors"]:
            summary["top_contributors"][author] = 0
        summary["top_contributors"][author] += 1
    
    return summary

def format_summary(summary):
    """Format summary as markdown."""
    lines = [
        "# Weekly Dev Summary",
        "Period: {}".format(summary["period"]),
        "",
        "## Stats",
        "- **Commits:** {}".format(summary["total_commits"]),
        "- **Contributors:** {}".format(summary["unique_authors"]),
        "- **Merged PRs:** {}".format(summary["merged_prs"]),
        "- **Closed Issues:** {}".format(summary["closed_issues"]),
        "",
        "## Top Contributors",
    ]
    
    sorted_authors = sorted(summary["top_contributors"].items(), key=lambda x: x[1], reverse=True)
    for author, count in sorted_authors:
        lines.append("- **{}**: {} commits".format(author, count))
    
    return "\n".join(lines)

if __name__ == "__main__":
    summary = generate_dry_run_summary()
    output = format_summary(summary)
    print(output)
    
    # Save to file
    out_path = os.path.join(os.path.dirname(__file__), "dry_run_output.md")
    with open(out_path, "w") as f:
        f.write(output)
    print("\nDry-run output saved to {}".format(out_path))
