# n8n + Claude Weekly Dev Summary Workflow

## Overview
Automated weekly developer digest that fetches GitHub activity (commits, issues, PRs) and generates a narrative summary using Claude API, delivered via Discord webhook.

## Requirements
- **n8n** instance (self-hosted or cloud)
- **Claude API key** (Anthropic)
- **GitHub personal access token** (read:org, repo)
- **Discord webhook URL** (or email/Slack webhook)

## Setup
1. Import `workflow.json` into your n8n instance
2. Configure the **HTTP Request Auth** credentials:
   - GitHub: Header Auth with `Authorization: Bearer <token>`
   - Anthropic: Header Auth with `x-api-key: <key>`
3. Set workflow variables:
   - `repo_owner`: GitHub org/user
   - `repo_name`: Repository name
   - `discord_webhook_url`: Your Discord webhook
4. Activate the workflow

## How It Works
1. **Weekly Cron Trigger** — runs every Friday at 5 PM
2. **Fetch GitHub Data** — commits, closed issues, merged PRs from the past 7 days
3. **Aggregate** — deduplicate, count, extract unique authors
4. **Claude API** — generates a narrative summary (model: claude-sonnet-4-20250514)
5. **Discord Delivery** — sends the formatted summary to your team channel

## Sample Output
```
📊 Weekly Dev Digest — Jul 23-30, 2026

🔄 47 commits by 8 contributors
🐛 12 issues closed
✅ 9 PRs merged

Top Contributors:
• alice (14 commits) — refactored auth module
• bob (9 commits) — fixed payment edge cases

Highlights:
• New OAuth2 integration landed (PR #342)
• Rate-limiting middleware deployed to production
• Dependency bumps: express 4.18→4.19, typescript 5.4→5.5
```

## CI
Automated validation via GitHub Actions (`.github/workflows/ci.yml`):
- Validates workflow.json structure
- Checks README completeness
