# PR Reviewer: Integration Guide

Complete guide for integrating PR Reviewer Agent into your CI/CD pipelines and development workflow.

---

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/pr-review.yml`:

```yaml
name: PR Review
on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  review:
    if: |
      (github.event_name == 'pull_request') ||
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '/review'))
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r skills/pr-reviewer/requirements.txt
      - name: Run PR Reviewer
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_URL: ${{ github.event.pull_request.html_url }}
        run: python skills/pr-reviewer/pr_review.py --pr "$PR_URL" --json
      - name: Post review comment
        if: success()
        run: |
          gh pr comment "$PR_URL" --body-file review-output.md
```

### GitLab CI

```yaml
pr-review:
  image: python:3.11
  stage: review
  only:
    - merge_requests
  script:
    - pip install -r skills/pr-reviewer/requirements.txt
    - python skills/pr-reviewer/pr_review.py --mr "$CI_MERGE_REQUEST_IID" --gitlab --json
  artifacts:
    paths:
      - review-output.json
    expire_in: 30 days
```

### CircleCI

```yaml
version: 2.1
jobs:
  pr-review:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout
      - run:
          name: Run PR Reviewer
          command: |
            pip install -r skills/pr-reviewer/requirements.txt
            python skills/pr-reviewer/pr_review.py \
              --pr "${CIRCLE_PULL_REQUEST}" \
              --output review-output.md
      - store_artifacts:
          path: review-output.md
```

---

## Webhook Integration

### GitHub Webhooks

1. Go to **Repo Settings → Webhooks → Add webhook**
2. Payload URL: `https://your-server.com/webhook/pr-review`
3. Content type: `application/json`
4. Events: **Pull requests** only
5. Secret: generate with `openssl rand -hex 32`

Server handler example (Flask):

```python
from flask import Flask, request
import hmac, hashlib, subprocess

app = Flask(__name__)
WEBHOOK_SECRET = "your-secret"

@app.route("/webhook/pr-review", methods=["POST"])
def pr_review_webhook():
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = request.get_data()
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return "Invalid signature", 403

    payload = request.json
    if payload.get("action") in ("opened", "synchronize"):
        pr_url = payload["pull_request"]["html_url"]
        subprocess.run([
            "python", "skills/pr-reviewer/pr_review.py",
            "--pr", pr_url, "--json"
        ])
    return "OK", 200
```

---

## API Usage

Programmatic invocation without CLI:

```python
from pr_review import PRReviewer, ReviewConfig

config = ReviewConfig(
    token=os.environ["GITHUB_TOKEN"],
    platform="github",       # or "gitlab"
    output_format="json",
    severity_threshold="warning",
    max_files=200
)

reviewer = PRReviewer(config)
result = reviewer.review("https://github.com/owner/repo/pull/123")
print(result.quality_score, result.critical_count)
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | Yes (GitHub) | — | GitHub personal access token |
| `GITLAB_TOKEN` | Yes (GitLab) | — | GitLab personal access token |
| `LLM_API_KEY` | Yes | — | LLM provider API key |
| `LLM_MODEL` | No | `claude-sonnet-4-20250514` | Model to use |
| `LLM_TIMEOUT` | No | `120` | API timeout in seconds |
| `REVIEW_CACHE_DIR` | No | `.cache/pr-reviewer` | Diff cache location |
| `MAX_DIFF_SIZE` | No | `50000` | Max diff lines to process |
| `PARALLEL_REVIEWS` | No | `4` | Concurrent review threads |
| `DEBUG` | No | `false` | Enable verbose logging |

---

## Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Auto-review staged changes before commit
if [ -n "$GITHUB_TOKEN" ]; then
    python skills/pr-reviewer/pr_review.py --diff-stdin --json
fi
```

---

## ChatOps Commands

Trigger reviews from PR/MR comments:

| Command | Action |
|---------|--------|
| `/review` | Full security + quality review |
| `/review --security` | Security scan only |
| `/review --quality` | Code quality only |
| `/review --all` | All checks, max verbosity |

---

## Platform Support Matrix

| Feature | GitHub | GitLab | Bitbucket |
|---------|--------|--------|-----------|
| PR/MR diff fetch | ✅ | ✅ | ❌ |
| Inline comments | ✅ | ✅ | ❌ |
| PR/MR summary comment | ✅ | ✅ | ❌ |
| `/review` command | ✅ | ✅ | ❌ |
| Webhook support | ✅ | ✅ | ❌ |
| CI template | ✅ | ✅ | ❌ |
| JSON output | ✅ | ✅ | ❌ |
| Markdown output | ✅ | ✅ | ❌ |

---

## Best Practices

1. **Always use token environment variables** — never hardcode tokens in config files
2. **Set up CI on default branch first** — GitHub Actions only trigger from `main`
3. **Cache diffs for large repos** — use `REVIEW_CACHE_DIR`
4. **Use JSON output in CI** — parseable, faster than markdown
5. **Limit `max_files` for monorepos** — prevents timeouts on 1000+ file PRs
6. **Rotate tokens regularly** — especially for bot accounts
7. **Monitor rate limits** — 5000 req/h with token, 60 without
8. **Test webhooks locally** — use `ngrok` or similar tunnel

---

## Troubleshooting Integration Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Action doesn't trigger | Workflow on wrong branch | Merge `.github/workflows/` to `main` |
| `403 Forbidden` | Token lacks permissions | Add `repo` scope to GitHub token |
| Empty review output | PR URL malformed | Verify format: `owner/repo/pull/N` |
| Webhook 403 | Secret mismatch | Re-generate and update both sides |
| CI timeout | Large repo / slow LLM | Increase `LLM_TIMEOUT`, enable caching |
