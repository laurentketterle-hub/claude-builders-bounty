# PR Reviewer Agent v2.0

Automated PR review agent that analyzes GitHub and GitLab pull requests and posts structured Markdown reviews.

## Features

- **Multi-platform**: Supports both GitHub PRs and GitLab Merge Requests
- **Security scanning**: SQL injection, XSS, hardcoded secrets, race conditions, SSL misconfigurations
- **Dependency integrity**: Detects package.json/requirements.txt changes without lockfile updates
- **Quality scoring**: 0-100 composite score based on risks, tests, size, and description quality
- **JSON output**: Machine-readable output with `--json` flag for CI/CD integration
- **GitHub Action**: Automated review on PR open/sync and `/review` comment trigger

## Usage

### CLI Mode
```bash
export GITHUB_TOKEN=ghp_xxx
python skills/pr-reviewer/pr_review.py --pr https://github.com/owner/repo/pull/123

# GitLab
export GITLAB_TOKEN=glpat-xxx
python skills/pr-reviewer/pr_review.py --pr https://gitlab.com/owner/repo/-/merge_requests/123

# JSON output
python skills/pr-reviewer/pr_review.py --pr https://github.com/owner/repo/pull/123 --json
```

### Claude Code Mode
Load the skill then: `Review PR https://github.com/owner/repo/pull/123`

### GitHub Action

Two modes:
1. **Automatic**: Reviews every new PR and on each push (`pull_request: opened, synchronize`)
2. **On-demand**: Comment `/review` on a PR to trigger a review

## Output Format
```markdown
## 🔍 PR Review: <title>
### 📝 Summary
### ⚠️ Identified Risks
### 💡 Improvement Suggestions
### 🟢 What Looks Good
### 📊 Quality Score (0-100) + Confidence
```

## Security Checks

| Category | Patterns |
|----------|----------|
| SQL Injection | DROP TABLE, DELETE without WHERE, UNION SELECT, query concatenation |
| XSS | innerHTML, dangerouslySetInnerHTML, eval(), document.write() |
| Race Conditions | Threads without locks, shared state without mutex |
| Hardcoded Secrets | API keys, passwords, tokens, private keys |
| Hardcoded IPs | IPv4 addresses in source code |
| SSL/Debug | verify=False, CERT_NONE, DEBUG=True |
| Lockfile | Dependency changes without lockfile updates |

## Quality Score

The 0-100 score considers:
- PR size (penalties for >500 additions, >300 deletions, >10 files)
- Risk count (4 points per risk)
- Suggestion count (2 points per suggestion)
- Tests included (+10 bonus)
- Focused PRs (+10 bonus for ≤3 files, ≤200 additions)

## Setup (3 steps)
1. Copy `skills/pr-reviewer/` to your repo
2. Set `GITHUB_TOKEN` or `GITLAB_TOKEN` env var (or use the Action)
3. Run: `python pr_review.py --pr <URL>`

## Testing

```bash
cd skills/pr-reviewer
python -m pytest tests/ -v
```

The test suite covers:
- URL parsing (GitHub and GitLab URLs)
- Security pattern detection (SQL injection, XSS, hardcoded secrets, SSL/Debug)
- Lockfile mismatch detection (package.json, requirements.txt, etc.)
- Quality score computation (size penalties, risk deductions, test bonuses)
- Markdown output formatting (risk highlighting, score gauge)
- End-to-end analysis with mock PR data
- Edge cases (null body, missing user key, draft PRs)

## Compliance

- ✅ Zero external dependencies — uses only Python stdlib (`json`, `re`, `urllib`)
- ✅ Multi-platform: GitHub and GitLab support
- ✅ Machine-readable JSON output for CI/CD integration
- ✅ Designed for Claude Code skill system
- ✅ All security patterns documented with messages and remediation hints

## Sample Outputs
- `samples/sample-review-tenstorrent.md` — Medium-sized PR (original)
- `samples/sample-review-small-security.md` — Small PR with security risks
- `samples/sample-review-large-risky.md` — Large PR with multiple risks
