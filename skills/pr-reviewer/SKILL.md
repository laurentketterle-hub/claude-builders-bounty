---
name: pr-reviewer
description: Claude Code agent that reviews a PR diff and posts a structured Markdown review comment.
version: 1.0
---

# PR Reviewer Agent

Review a GitHub pull request and post a structured Markdown comment.

## Usage

```bash
# Via CLI
python pr_review.py --pr https://github.com/owner/repo/pull/123

# Via Claude Code
# Load this skill then: "Review PR https://github.com/owner/repo/pull/123"
```

## Workflow

1. **Fetch PR data** — Use `gh pr view <url> --json title,body,diff,files,comments` or the GitHub API
2. **Analyze the diff** — Look for:
   - Logic changes that could introduce bugs
   - Missing error handling
   - Security concerns (unvalidated input, hardcoded secrets)
   - Performance issues (N+1 queries, blocking calls)
   - Test coverage gaps
3. **Generate structured review** — Output in this format:

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

### 📊 Confidence Score
**<Low/Medium/High>** — <brief justification>
```

4. **Post as comment** — Use `gh pr comment <url> --body "$REVIEW"` or the GitHub API

## Requirements

- `gh` CLI authenticated or `GITHUB_TOKEN` env var set
- Access to the PR's repository

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

### 📊 Confidence Score
**Medium** — heuristics are sound but language-dependence of connector detection limits generalizability.
