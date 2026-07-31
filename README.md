# Claude Builders Bounty 🤖

> A community bounty board for Claude Code builders.

Building with Claude Code? Have tasks to delegate?
Want to get paid for contributing to AI projects?
You're in the right place.

---

## How it works

**To post a bounty**
1. Open a GitHub issue with a clear description and acceptance criteria
2. Comment `/opire create $XXX` in the issue to set the reward
3. Share the link — contributors will find it

**To claim a bounty**
1. Browse the open issues below
2. Comment `/opire try` in the issue you want to work on
3. Submit a PR — payment is automatic on merge ✅

---

## Active Bounties

| # | Task | Amount | Status |
|---|------|--------|--------|
| [#1](../../issues/1) | SKILL: Generate a CHANGELOG from git history | $50 | 🟢 Open |
| [#2](../../issues/2) | TEMPLATE: CLAUDE.md for a Next.js + SQLite project | $75 | 🟢 Open |
| [#3](../../issues/3) | HOOK: Block destructive bash commands in Claude Code | $100 | 🟢 Open |
| [#4](../../issues/4) | AGENT: PR reviewer with structured Markdown output | $150 | 🟢 Open |
| [#5](../../issues/5) | WORKFLOW: n8n + Claude API — automated weekly dev summary | $200 | 🟢 Open |

---

## Rules

- Tasks must be related to Claude Code or AI tooling
- Every issue must have clear acceptance criteria before a bounty is activated
- Payment is handled by [Opire](https://opire.dev) (Stripe)
- Quality over speed — a solid PR beats a fast one

---

## Featured Bounty: PR Reviewer Agent (#4)

The PR Reviewer Agent is an automated code review tool for GitHub and GitLab pull requests.

### What it does
- Fetches PR/MR data via GitHub or GitLab API
- Scans diffs for 8 categories of security risks (SQL injection, XSS, hardcoded secrets, race conditions, etc.)
- Detects dependency integrity issues (lockfile mismatches)
- Computes a 0-100 quality score based on risk count, PR size, tests, and description quality
- Outputs structured Markdown or JSON

### Quick Start
```bash
# Set your token
export GITHUB_TOKEN=ghp_xxx

# Review a PR
python skills/pr-reviewer/pr_review.py --pr https://github.com/owner/repo/pull/123

# Get JSON output for CI/CD
python skills/pr-reviewer/pr_review.py --pr https://github.com/owner/repo/pull/123 --json
```

### Security Checks
| Category | Example Patterns |
|----------|-----------------|
| SQL Injection | `DROP TABLE`, DELETE without WHERE, query concatenation |
| XSS | `innerHTML`, `dangerouslySetInnerHTML`, `eval()` |
| Hardcoded Secrets | API keys, passwords, tokens in source |
| SSL/Debug | `verify=False`, `DEBUG=True` in production |
| Race Conditions | Threads without locks, shared state mutations |
| Shell Injection | `subprocess` with `shell=True`, `os.system()` |
| Dependency Integrity | `package.json` updated without `package-lock.json` |

### Testing
```bash
cd skills/pr-reviewer
python -m pytest tests/ -v
```

---

## Community

- 🐦 X: [@ClaudeBounty](https://x.com/ClaudeBounty)
- 📧 Contact: claudebounty@gmail.com

---

*Started by the Claude builder community · March 2026 · MIT License*
