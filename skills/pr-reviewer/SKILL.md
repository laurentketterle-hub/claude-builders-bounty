---
name: pr-reviewer
description: Claude Code agent that reviews a PR diff and posts a structured Markdown review comment.
version: 2.0
---

# PR Reviewer Agent

Review a GitHub or GitLab pull request and post a structured Markdown review comment.

## Usage

```bash
# GitHub PR
python pr_review.py --pr https://github.com/owner/repo/pull/123

# GitLab MR
python pr_review.py --pr https://gitlab.com/owner/repo/-/merge_requests/123

# JSON output (for programmatic consumption)
python pr_review.py --pr https://github.com/owner/repo/pull/123 --json

# Via Claude Code
# Load this skill then: "Review PR https://github.com/owner/repo/pull/123"
```

## Workflow

1. **Fetch PR data** — Use `gh pr view <url> --json title,body,diff,files,comments` or the GitHub/GitLab API
2. **Analyze the diff** — Look for:
   - **SQL Injection**: DROP TABLE, DELETE without WHERE, UNION SELECT, string concatenation in queries
   - **XSS**: innerHTML, dangerouslySetInnerHTML, eval(), document.write()
   - **Race Conditions**: threads without locks, shared state without protection, async tasks without synchronization
   - **Dependency Integrity**: package.json/requirements.txt changes without lockfile updates
   - **Security**: hardcoded secrets, hardcoded IPs, disabled SSL, debug flags left on
   - Logic changes that could introduce bugs
   - Missing error handling
   - Performance issues (N+1 queries, blocking calls)
   - Test coverage gaps
3. **Generate structured review** — Output in Markdown or JSON format:

```markdown
## 🔍 PR Review: <title>

### 📝 Summary
<2-3 sentences describing what this PR changes>

### ⚠️ Identified Risks
- <risk 1>
- <risk 2>

### 💡 Improvement Suggestions
- <suggestion 1>
- <suggestion 2>

### 🟢 What Looks Good
- <positive observation>

### 📊 Quality Score
🟡 **65/100**  `██████░░░░`
**Confidence**: Medium — some concerns but generally sound
```

## Security Analysis

The agent performs automated security scanning for:

| Category | Patterns Detected |
|----------|------------------|
| SQL Injection | DROP TABLE, DELETE without WHERE, UNION SELECT, string concatenation in queries |
| XSS | innerHTML, dangerouslySetInnerHTML, eval(), document.write(), v-html |
| Race Conditions | Threads without locks, shared state without mutex, async tasks without synchronization |
| Hardcoded Secrets | API keys, passwords, tokens, private keys |
| Hardcoded IPs | IPv4 addresses in code |
| SSL/Debug | verify=False, CERT_NONE, DEBUG=True, NODE_ENV=development |
| Lockfile | Dependency file changes without corresponding lockfile updates |
| Shell Injection | subprocess with shell=True, os.system, exec() |

## Quality Score (0-100)

The agent computes a composite quality score based on:
- PR size (additions, deletions, number of files)
- Number and severity of identified risks
- Presence of tests
- PR description quality
- Security issue count

## JSON Output

Use `--json` for machine-readable output with all fields:

```json
{
  "title": "...",
  "user": "...",
  "changed_files": 5,
  "additions": 230,
  "deletions": 45,
  "platform": "github",
  "url": "https://...",
  "risks": ["..."],
  "suggestions": ["..."],
  "positives": ["..."],
  "confidence": "Medium — some concerns but generally sound",
  "quality_score": 65,
  "has_tests": true,
  "security_issues": 2
}
```

## Requirements

- `gh` CLI authenticated or `GITHUB_TOKEN`/`GITLAB_TOKEN` env var set
- Access to the PR/MR's repository

## Example Output

Tested on https://github.com/mergeos-bounties/NokaMan/pull/100:

### 📝 Summary
Adds writing cohesion/coherence offline dimensions to the NokaMan rubric module, mirroring the existing speaking fluency pattern. Two new scoring functions with deterministic heuristics.

### ⚠️ Identified Risks
- `_cohesion_score` connector regex is English-only; non-English texts get scored as 0 for connector density
- No upper bound on paragraph count in `_coherence_score` — extremely long documents could skew the score

### 💡 Improvement Suggestions
- Add a language-detection pre-check to warn when connector detection may be inaccurate
- Cap paragraph count at a reasonable maximum (e.g., 20) in coherence scoring
- Consider adding a sample JSON test fixture alongside the Python doctests

### 🟢 What Looks Good
- Clean separation of cohesion and coherence dimensions with independent scoring
- Proper error handling (empty text raises ValueError)
- Limitations documented in the return object — good transparency for offline heuristics

### 📊 Quality Score
🟢 **82/100** `████████░░`
**Confidence**: **Medium** — heuristics are sound but language-dependence of connector detection limits generalizability.
