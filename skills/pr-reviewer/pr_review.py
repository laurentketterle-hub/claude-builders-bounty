#!/usr/bin/env python3
"""PR Review Agent — Structured Markdown/JSON PR review via GitHub/GitLab API.

Usage:
    python pr_review.py --pr https://github.com/owner/repo/pull/123
    python pr_review.py --pr https://gitlab.com/owner/repo/-/merge_requests/123
    python pr_review.py --pr https://github.com/owner/repo/pull/123 --token ghp_xxx --json

Requirements: Python 3.8+, GITHUB_TOKEN/GITLAB_TOKEN env var or --token flag.
"""

import argparse, json, os, re, sys, urllib.request, urllib.parse


# ──────────────────────────────────────────────────────────────
#  API FETCHING
# ──────────────────────────────────────────────────────────────

def fetch_github_pr(owner: str, repo: str, pr_num: int, token: str) -> dict:
    """Fetch PR data from GitHub API."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PR-Review-Agent",
    }
    base = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"

    # PR details
    req = urllib.request.Request(base, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        pr = json.loads(resp.read())

    # Diff
    req2 = urllib.request.Request(base, headers={**headers, "Accept": "application/vnd.github.v3.diff"})
    with urllib.request.urlopen(req2, timeout=15) as resp:
        diff = resp.read().decode(errors="replace")

    # Files (max 100 per page)
    files = []
    page = 1
    while True:
        url = f"{base}/files?per_page=100&page={page}"
        req3 = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req3, timeout=15) as resp:
            batch = json.loads(resp.read())
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1

    return {"pr": pr, "diff": diff, "files": files, "platform": "github"}


def fetch_gitlab_mr(owner: str, repo: str, mr_num: int, token: str) -> dict:
    """Fetch MR data from GitLab API."""
    headers = {
        "PRIVATE-TOKEN": token,
        "User-Agent": "PR-Review-Agent",
    }
    project_path = urllib.parse.quote(f"{owner}/{repo}", safe="")
    base = f"https://gitlab.com/api/v4/projects/{project_path}/merge_requests/{mr_num}"

    # MR details
    req = urllib.request.Request(base, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        mr = json.loads(resp.read())

    # Build a GitHub-compatible PR shape
    pr = {
        "title": mr.get("title", "Untitled"),
        "body": mr.get("description", "") or "",
        "user": {"login": mr.get("author", {}).get("username", "unknown")},
        "html_url": mr.get("web_url", ""),
        "state": mr.get("state", "unknown"),
        "draft": mr.get("draft", False),
    }

    # Changes (diffs per file)
    changes_url = f"{base}/changes"
    req2 = urllib.request.Request(changes_url, headers=headers)
    with urllib.request.urlopen(req2, timeout=15) as resp:
        changes = json.loads(resp.read())

    files = []
    diff_parts = []
    for ch in changes.get("changes", []):
        files.append({
            "filename": ch.get("new_path", ch.get("old_path", "")),
            "additions": ch.get("additions", 0),
            "deletions": ch.get("deletions", 0),
            "status": "modified" if ch.get("new_file") else ("added" if ch.get("new_file") else "removed"),
        })
        diff_parts.append(ch.get("diff", ""))

    diff = "\n".join(diff_parts)

    return {"pr": pr, "diff": diff, "files": files, "platform": "gitlab"}


# ──────────────────────────────────────────────────────────────
#  SECURITY PATTERN DETECTION
# ──────────────────────────────────────────────────────────────

SQL_INJECTION_PATTERNS = [
    (r"(?i)\bDROP\s+TABLE\b", "SQL DROP TABLE — destructive operation, ensure it's parameterized"),
    (r"(?i)\bDELETE\s+FROM\s+\w+(?!\s+WHERE)", "DELETE without WHERE clause — may delete all rows unintentionally"),
    (r"(?i)\bINSERT\s+INTO\s+\w+(?!.*\bWHERE\b).*['\"]?\s*\+", "INSERT with string concatenation — SQL injection risk"),
    (r"(?i)\bUNION\s+SELECT\b", "UNION SELECT detected — verify it's not user-injectable"),
    (r"(?i)\.execute\s*\(\s*['\"].*%s", "SQL query with %s placeholder — use parameterized queries instead"),
    (r"(?i)\.execute\s*\(\s*['\"].*\{", "SQL query with f-string/format — SQL injection risk"),
    (r"(?i)\.execute\s*\(\s*.*\+\s*", "SQL query built with string concatenation — SQL injection risk"),
]

XSS_PATTERNS = [
    (r"(?i)\.innerHTML\s*=", "innerHTML assignment — XSS risk, prefer textContent or DOM APIs"),
    (r"(?i)dangerouslySetInnerHTML", "dangerouslySetInnerHTML in React — XSS vector, use with extreme caution"),
    (r"(?i)\beval\s*\(.+\)", "eval() call — arbitrary code execution risk"),
    (r"(?i)document\.write\s*\(.+\)", "document.write() — XSS vector and blocks rendering"),
    (r"(?i)setInnerHTML\b", "setInnerHTML usage — potential XSS vector"),
    (r"(?i)v-html\s*=", "Vue v-html directive — XSS risk, prefer v-text"),
    (r"(?i)\bunsafe\b.*\bhtml\b", "Unsafe HTML usage detected — XSS risk"),
]

RACE_CONDITION_PATTERNS = [
    (r"(?i)threading\.(?!.*\bLock\b).*\bstart\s*\(\s*\)", "Thread started without visible lock acquisition — potential race condition"),
    (r"(?i)asyncio\.create_task\b(?!.*\basyncio\.Lock\b)", "Async task created without async Lock — potential race condition"),
    (r"(?i)global\s+\w+.*\n.*\b=\b(?!.*\bLock\b)", "Global variable mutation without lock protection — race condition risk"),
    (r"(?i)self\.\w+\s*=\s*.*\n(?!.*\bthreading\.Lock\b).*\bstart\b", "Shared instance state modified in thread — race condition risk"),
    (r"(?i)multiprocessing\.(?!.*\bLock\b).*\bValue\b", "Shared multiprocessing.Value without Lock — race condition"),
    (r"(?i)concurrent\.futures\.ThreadPoolExecutor\b(?!.*\bLock\b)", "ThreadPoolExecutor without lock — shared state at risk"),
]

HARDCODED_SECRETS_PATTERNS = [
    (r"(?i)(?:api[_-]?key|apikey|api[_-]?secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{8,}['\"]", "Hardcoded API key/secret — move to environment variables"),
    (r"(?i)(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{3,}['\"]", "Hardcoded password — use secrets manager or env var"),
    (r"(?i)(?:token|jwt|bearer)\s*[:=]\s*['\"][A-Za-z0-9_\-.]+['\"]", "Hardcoded token — move to environment variables"),
    (r'(?i)(?:private[_-]?key|privatekey)\s*[:=]\s*[\'"][A-Za-z0-9+/]{20,}', "Hardcoded private key — critical security risk"),
]

HARDCODED_IP_PATTERNS = [
    (r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
     "Hardcoded IP address — use DNS/hostname or config for portability"),
]

SSL_DEBUG_PATTERNS = [
    (r"(?i)verify\s*=\s*False", "SSL verification disabled (verify=False) — man-in-the-middle risk"),
    (r"(?i)ssl\.CERT_NONE\b", "SSL CERT_NONE — accepts all certificates, insecure"),
    (r"(?i)check_hostname\s*=\s*False", "SSL hostname check disabled — MITM risk"),
    (r"(?i)CURLOPT_SSL_VERIFYPEER\s*,\s*false\b", "cURL SSL verification disabled"),
    (r"(?i)DEBUG\s*=\s*True\b", "DEBUG flag set to True — disable in production"),
    (r"(?i)NODE_ENV\s*=\s*['\"]development['\"]", "NODE_ENV=development in config — production risk"),
    (r"(?i)debug\s*:\s*true\b", "debug:true in config — disable in production"),
]

LOCKFILE_PATTERNS = {
    "package.json": "package-lock.json",
    "requirements.txt": "requirements.lock",
    "Pipfile": "Pipfile.lock",
    "pyproject.toml": "poetry.lock",
    "Gemfile": "Gemfile.lock",
    "Cargo.toml": "Cargo.lock",
    "composer.json": "composer.lock",
    "go.mod": "go.sum",
}


# ──────────────────────────────────────────────────────────────
#  ANALYSIS ENGINE
# ──────────────────────────────────────────────────────────────

def _scan_patterns(diff: str, pattern_list: list) -> list:
    """Scan diff for security patterns, return list of findings (deduplicated)."""
    findings = set()
    results = []
    for pattern, message in pattern_list:
        matches = re.findall(pattern, diff, re.MULTILINE)
        if matches:
            key = message[:80]
            if key not in findings:
                findings.add(key)
                results.append(message)
    return results


def _detect_lockfile_mismatch(files: list) -> list:
    """Detect changes to dependency files without corresponding lockfile changes."""
    findings = []
    changed_filenames = {f.get("filename", "") for f in files}
    for dep_file, lock_file in LOCKFILE_PATTERNS.items():
        for fname in changed_filenames:
            if fname.endswith(dep_file) or dep_file in fname:
                # Check if lockfile was also changed
                lock_changed = any(
                    lf in cf or cf.endswith(lf)
                    for cf in changed_filenames
                    for lf in [lock_file]
                )
                if not lock_changed:
                    # Also check root-level lockfile
                    root_lock_changed = any(
                        cf == lock_file or cf.endswith("/" + lock_file)
                        for cf in changed_filenames
                    )
                    if not root_lock_changed:
                        findings.append(
                            f"{fname} changed but {lock_file} not updated — dependencies may be inconsistent"
                        )
    return findings


def compute_quality_score(risks: list, suggestions: list, positives: list, additions: int,
                          deletions: int, changed_files: int, has_tests: bool) -> int:
    """Compute a quality score from 0 to 100."""
    score = 70  # baseline

    # Size penalties
    if additions > 1000:
        score -= 20
    elif additions > 500:
        score -= 10
    if deletions > 500:
        score -= 10
    elif deletions > 300:
        score -= 5
    if changed_files > 20:
        score -= 15
    elif changed_files > 10:
        score -= 5

    # Risk penalties
    score -= len(risks) * 4

    # Suggestion penalties (more suggestions = less polished)
    score -= len(suggestions) * 2

    # Test bonus
    if has_tests:
        score += 10

    # Focused PR bonus
    if changed_files <= 3 and additions <= 200:
        score += 10

    # Positives bonus
    score += len(positives) * 2

    return max(0, min(100, score))


def analyze_pr(pr_data: dict) -> dict:
    """Analyze PR and return structured review data."""
    pr = pr_data["pr"]
    diff = pr_data["diff"]
    files = pr_data["files"]
    platform = pr_data.get("platform", "github")

    title = pr.get("title", "Untitled")
    body = pr.get("body", "") or ""
    additions = sum(f.get("additions", 0) for f in files)
    deletions = sum(f.get("deletions", 0) for f in files)
    changed_files = len(files)
    user = pr.get("user", {}).get("login", "unknown")
    url = pr.get("html_url", "")

    risks = []
    suggestions = []
    positives = []

    # ── Size heuristics ──
    if additions > 1000:
        risks.append(f"Very large PR: {additions} additions across {changed_files} files — must be split")
    elif additions > 500:
        risks.append(f"Large PR: {additions} additions across {changed_files} files — consider splitting")
    if deletions > 500:
        risks.append(f"Substantial deletions ({deletions} lines) — verify no functionality removed unintentionally")
    elif deletions > 300:
        risks.append(f"Substantial deletions ({deletions} lines) — verify no functionality removed unintentionally")

    # ── Code quality patterns ──
    if "TODO" in diff or "FIXME" in diff:
        suggestions.append("Outstanding TODOs/FIXMEs found — address before merging")
    if "console.log" in diff or "print(" in diff or "System.out.println" in diff:
        suggestions.append("Debug logging found — remove before production merge")
    if "XXX" in diff or "HACK" in diff:
        suggestions.append("XXX/HACK markers found — clean up before merging")
    if "except:" in diff:
        risks.append("Bare except clauses found — may silently swallow errors")
    if "except Exception:" in diff and "pass" in diff:
        risks.append("Exception caught with pass — errors silently ignored")

    # ── Security: hardcoded credentials ──
    cred_findings = _scan_patterns(diff, HARDCODED_SECRETS_PATTERNS)
    if cred_findings:
        risks.extend(cred_findings)

    # ── Security: SQL injection ──
    sql_findings = _scan_patterns(diff, SQL_INJECTION_PATTERNS)
    if sql_findings:
        risks.extend(sql_findings)

    # ── Security: XSS ──
    xss_findings = _scan_patterns(diff, XSS_PATTERNS)
    if xss_findings:
        risks.extend(xss_findings)

    # ── Security: race conditions ──
    race_findings = _scan_patterns(diff, RACE_CONDITION_PATTERNS)
    if race_findings:
        risks.extend(race_findings)

    # ── Security: hardcoded IPs ──
    ip_findings = _scan_patterns(diff, HARDCODED_IP_PATTERNS)
    if ip_findings:
        risks.extend(ip_findings)

    # ── Security: SSL/debug ──
    ssl_findings = _scan_patterns(diff, SSL_DEBUG_PATTERNS)
    if ssl_findings:
        risks.extend(ssl_findings)

    # ── Shell command execution ──
    if "subprocess" in diff or "os.system" in diff or "exec(" in diff or "os.popen" in diff:
        risks.append("Shell command execution detected — review for injection risks")
    if "shell=True" in diff:
        risks.append("subprocess with shell=True — command injection risk")

    # ── Lockfile check ──
    lockfile_findings = _detect_lockfile_mismatch(files)
    if lockfile_findings:
        risks.extend(lockfile_findings)

    # ── PR description quality ──
    if not body or len(body) < 50:
        suggestions.append("PR description is brief — add context about what and why")

    # ── Test detection ──
    test_files = [
        f for f in files
        if "test" in f.get("filename", "").lower()
        or "spec" in f.get("filename", "").lower()
        or f.get("filename", "").startswith("__tests__")
        or ".test." in f.get("filename", "")
    ]
    has_tests = bool(test_files)
    if not has_tests and changed_files > 1:
        suggestions.append(f"No test files detected among {changed_files} changed files — consider adding tests")

    # ── File type heuristics ──
    config_files = [f for f in files if f.get("filename", "").endswith((".yml", ".yaml", ".toml", ".json", ".env"))]
    if config_files:
        suggestions.append(f"Configuration files changed ({len(config_files)} files) — verify all environments")

    # ── Draft PR check (GitHub only) ──
    if platform == "github" and pr.get("draft", False):
        suggestions.append("PR is marked as Draft — ready for review?")

    # ── Positives ──
    if changed_files <= 3 and additions <= 200:
        positives.append("Small, focused change — easy to review")
    if has_tests:
        positives.append(f"Tests included ({len(test_files)} test files)")
    if "fix" in title.lower() or "bug" in title.lower():
        positives.append("Clear bug-fix intent in title")
    if body and len(body) > 200:
        positives.append("Detailed PR description — good context for reviewers")
    if "close" in body.lower() or "resolve" in body.lower() or "fixes" in body.lower():
        positives.append("References linked issues — good traceability")
    if not risks:
        positives.append("No security or quality risks detected automatically")

    # ── Confidence ──
    security_risk_count = len(sql_findings) + len(xss_findings) + len(cred_findings)
    if len(risks) >= 5 or security_risk_count >= 2 or additions > 1000:
        confidence = "Low — significant scope or multiple security risks"
    elif len(risks) >= 2:
        confidence = "Medium — some concerns but generally sound"
    else:
        confidence = "High — clean, focused change"

    # ── Quality Score ──
    quality_score = compute_quality_score(risks, suggestions, positives, additions, deletions, changed_files, has_tests)

    return {
        "title": title,
        "user": user,
        "changed_files": changed_files,
        "additions": additions,
        "deletions": deletions,
        "platform": platform,
        "url": url,
        "risks": risks,
        "suggestions": suggestions,
        "positives": positives,
        "confidence": confidence,
        "quality_score": quality_score,
        "has_tests": has_tests,
        "security_issues": security_risk_count,
    }


# ──────────────────────────────────────────────────────────────
#  OUTPUT FORMATTERS
# ──────────────────────────────────────────────────────────────

def format_markdown(data: dict) -> str:
    """Format review as Markdown."""
    lines = [
        f"## 🔍 PR Review: {data['title']}",
        "",
        f"**Author**: @{data['user']} | **Files**: {data['changed_files']} | **+{data['additions']} −{data['deletions']} | **Platform**: {data['platform']}",
        "",
        f"### 📝 Summary",
        f"This PR changes {data['changed_files']} file(s) with {data['additions']} additions and {data['deletions']} deletions.",
    ]

    if data["risks"]:
        lines.append("")
        lines.append("### ⚠️ Identified Risks")
        for r in data["risks"]:
            lines.append(f"- {r}")

    if data["suggestions"]:
        lines.append("")
        lines.append("### 💡 Improvement Suggestions")
        for s in data["suggestions"]:
            lines.append(f"- {s}")

    if data["positives"]:
        lines.append("")
        lines.append("### 🟢 What Looks Good")
        for p in data["positives"]:
            lines.append(f"- {p}")

    # Quality score gauge
    score = data["quality_score"]
    if score >= 80:
        emoji = "🟢"
    elif score >= 50:
        emoji = "🟡"
    else:
        emoji = "🔴"
    score_bar = "█" * (score // 10) + "░" * (10 - score // 10)

    lines.append("")
    lines.append("### 📊 Quality Score")
    lines.append(f"{emoji} **{score}/100**  `{score_bar}`")
    lines.append(f"**Confidence**: {data['confidence']}")

    if data["security_issues"] > 0:
        lines.append(f"**Security issues detected**: {data['security_issues']}")

    lines.append("")
    lines.append("---")
    lines.append("*Automated review by PR Reviewer Agent — always verify manually.*")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
#  URL PARSER
# ──────────────────────────────────────────────────────────────

def parse_pr_url(url: str) -> tuple:
    """Parse a GitHub or GitLab PR/MR URL. Returns (platform, owner, repo, pr_num)."""
    # GitHub: https://github.com/owner/repo/pull/123
    gh_match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if gh_match:
        return ("github", gh_match.group(1), gh_match.group(2), int(gh_match.group(3)))

    # GitLab: https://gitlab.com/owner/repo/-/merge_requests/123
    gl_match = re.match(r"https://gitlab\.com/([^/]+)/([^/]+)/-/merge_requests/(\d+)", url)
    if gl_match:
        return ("gitlab", gl_match.group(1), gl_match.group(2), int(gl_match.group(3)))

    return (None, None, None, None)


# ──────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PR Review Agent — GitHub & GitLab support")
    parser.add_argument("--pr", required=True, help="GitHub PR URL or GitLab MR URL")
    parser.add_argument("--token", help="GitHub/GitLab token (or set GITHUB_TOKEN/GITLAB_TOKEN env var)")
    parser.add_argument("--json", action="store_true", help="Output review as structured JSON instead of Markdown")
    args = parser.parse_args()

    platform, owner, repo, pr_num = parse_pr_url(args.pr)
    if not platform:
        print("Error: Invalid PR/MR URL. Expected github.com/.../pull/N or gitlab.com/.../-/merge_requests/N",
              file=sys.stderr)
        sys.exit(1)

    # Token resolution
    token = args.token
    if not token:
        if platform == "github":
            token = os.environ.get("GITHUB_TOKEN")
        else:
            token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(f"Error: Set {'GITLAB_TOKEN' if platform == 'gitlab' else 'GITHUB_TOKEN'} env var or use --token",
              file=sys.stderr)
        sys.exit(1)

    print(f"🔍 Reviewing {owner}/{repo}#{pr_num} on {platform}...", file=sys.stderr)

    # Fetch
    if platform == "github":
        pr_data = fetch_github_pr(owner, repo, pr_num, token)
    else:
        pr_data = fetch_gitlab_mr(owner, repo, pr_num, token)

    # Analyze
    review_data = analyze_pr(pr_data)

    # Output
    if args.json:
        print(json.dumps(review_data, indent=2, ensure_ascii=False))
    else:
        print(format_markdown(review_data))


if __name__ == "__main__":
    main()
