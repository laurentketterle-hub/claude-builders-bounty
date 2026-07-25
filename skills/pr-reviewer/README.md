# PR Reviewer Agent

Claude Code agent that reviews GitHub pull requests and posts structured Markdown comments.

## Usage

### CLI Mode
```bash
export GITHUB_TOKEN=ghp_xxx
python skills/pr-reviewer/pr_review.py --pr https://github.com/owner/repo/pull/123
```

### Claude Code Mode
Load the skill then: `Review PR https://github.com/owner/repo/pull/123`

### GitHub Action
Comment `/review` on a PR to trigger automated review.

## Output Format
```markdown
## 🔍 PR Review: <title>
### 📝 Summary
### ⚠️ Identified Risks
### 💡 Improvement Suggestions
### 🟢 What Looks Good
### 📊 Confidence Score (Low/Medium/High)
```

## Setup (3 steps)
1. Copy `skills/pr-reviewer/` to your repo
2. Set `GITHUB_TOKEN` env var (or use the Action)
3. Run: `python pr_review.py --pr <URL>`

## Sample Output
See `samples/sample-review-poseguide.md` for a real PR review.
