# n8n + Claude — Automated Weekly Dev Summary

> **Bounty #5 — $200 USD** | Powered by [Opire](https://opire.dev)

A complete, production-ready n8n workflow that generates weekly narrative summaries of GitHub repository activity using the Claude API. **13 nodes**, **multi-channel delivery** (Discord + Slack + Email), **bilingual** (EN/FR).

## 🎯 Features

- **⏰ Weekly Cron** — Runs every Friday at 5 PM UTC (168h interval)
- **📊 GitHub Integration** — Fetches commits, closed issues, and merged PRs via 3 parallel API calls
- **🤖 Claude AI** — Generates natural, narrative summaries (model: `claude-sonnet-4-20250514`)
- **📨 Multi-Channel Delivery** — Discord webhook, Slack (Block Kit), or SMTP Email
- **🌐 Bilingual** — English (EN) or French (FR) summaries with dedicated prompt templates
- **🛡️ Resilient** — Error handling (`continueOnFail`) on every API node; pipeline continues on failures
- **🧪 Fully Testable** — `dry_run.py` simulates the entire workflow without n8n/Docker; fixture mode for CI
- **✅ Validated** — `validate_workflow.py` checks structure, connections, and semantics; `test_workflow_json.py` has 21+ tests
- **📝 Detailed Output** — Top contributors, standout PRs, issue summaries, Claude-generated narrative

## 📋 Requirements

| Component | Details |
|-----------|---------|
| **n8n** | Self-hosted or cloud instance |
| **Claude API Key** | From [console.anthropic.com](https://console.anthropic.com) |
| **GitHub Token** | Personal access token with `repo` scope |
| **Delivery Channel** | Discord webhook, Slack webhook, or SMTP credentials |

## ⚡ Quick Setup (5 Steps)

### 1. Import the Workflow
```
n8n → Import from File → Select workflow.json
```

### 2. Set Environment Variables
In your n8n instance, configure these variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `REPO_OWNER` | ✅ | GitHub organization or username |
| `REPO_NAME` | ✅ | Repository name |
| `GITHUB_TOKEN` | ✅ | GitHub personal access token |
| `ANTHROPIC_API_KEY` | ✅ | Claude API key (starts with `sk-ant-`) |
| `DISCORD_WEBHOOK` | ⬜ | Discord webhook URL |
| `SLACK_WEBHOOK` | ⬜ | Slack incoming webhook URL |
| `EMAIL_TO` | ⬜ | Destination email address |
| `SMTP_FROM` | ⬜ | Sender email (if using email delivery) |
| `SUMMARY_LANGUAGE` | ⬜ | `EN` (default) or `FR` for French |

### 3. Configure SMTP (if using Email)
In n8n, configure the Email node (SMTP) with your credentials:
- Host, Port, User, Password
- Or use a service like SendGrid/Resend

### 4. Test the Workflow
```
n8n → Workflow → Execute Workflow (manual)
```
Check the execution log for any errors.

### 5. Activate
Toggle the **Active** switch — the workflow will now run every Friday at 5 PM UTC.

## 🏗️ Architecture

```
┌─────────────────┐
│  Cron Trigger   │  Friday 5 PM UTC
│  (168h interval)│
└────────┬────────┘
         ▼
┌─────────────────┐
│ Compute Window   │  Calculate 7-day range
└────────┬────────┘
         ▼
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
┌────────┐ ┌────────┐ ┌────────┐
│Commits │ │ Issues │ │  PRs   │  3 parallel GitHub API calls
│  API   │ │  API   │ │  API   │
└───┬────┘ └───┬────┘ └───┬────┘
    └────┬─────┴──────────┘
         ▼
┌─────────────────┐
│  Aggregate &     │  Filter, dedupe, compute stats
│  Filter Data     │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Build Claude     │  Construct prompt with data
│ Prompt           │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Claude API       │  Generate narrative summary
│ (Sonnet 4)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Format Output    │  Discord/Slack/Email formatting
└────────┬────────┘
    ┌────┼────────────┐
    ▼    ▼            ▼
┌──────┐┌──────┐┌─────────┐
│Discord││Slack ││ Email   │  Multi-channel delivery
└───┬──┘└──┬───┘└────┬────┘
    └──────┴─────────┘
         ▼
┌─────────────────┐
│ Log Summary      │  Console output for debugging
└─────────────────┘
```

### Node Breakdown (13 nodes)

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Weekly Cron (Friday 5pm UTC) | `scheduleTrigger` | Triggers every 168h |
| 2 | Compute Date Window | `code` | Calculates 7-day `since`/`until` dates |
| 3 | Fetch Commits | `httpRequest` | `GET /repos/{o}/{r}/commits` |
| 4 | Fetch Closed Issues | `httpRequest` | `GET /repos/{o}/{r}/issues?state=closed` |
| 5 | Fetch Merged PRs | `httpRequest` | `GET /repos/{o}/{r}/pulls?state=closed` |
| 6 | Aggregate & Filter Data | `code` | Merge, dedupe, compute stats |
| 7 | Build Claude Prompt | `code` | Construct system + user prompts (EN/FR) |
| 8 | Claude API — Generate Summary | `httpRequest` | `POST api.anthropic.com/v1/messages` |
| 9 | Format Output | `code` | Discord/Slack/Email formatting |
| 10 | Send to Discord | `httpRequest` | POST to Discord webhook |
| 11 | Send to Slack | `httpRequest` | POST to Slack webhook (Block Kit) |
| 12 | Send Email | `emailSend` | SMTP email delivery |
| 13 | Log Summary | `code` | Console debug output |

## 📊 Sample Output

```
📊 Weekly Dev Digest — 2026-07-25 → 2026-08-01

🔄 47 commits by 8 contributors
🐛 12 issues closed
✅ 9 PRs merged

👥 Top Contributors
1. alice — 14 commits
2. bob — 9 commits
3. carol — 7 commits

🔀 Merged PRs
- #342 feat: OAuth2 provider integration (@alice)
- #339 fix: race condition in payment confirmation (@bob)
- #335 feat: rate-limiting middleware (@dave)

📝 Narrative
This week the team shipped the long-awaited OAuth2 integration...
```

See [`sample-output.md`](sample-output.md) for Discord, Slack (Block Kit), Email, and French examples.

## 🧪 Testing without n8n (dry_run.py)

`dry_run.py` is a faithful Python re-implementation of every Code/HTTP node in the 13-node workflow. It calls the real GitHub REST API and Anthropic Messages API when credentials are present, and falls back to deterministic mock data when they're not — no n8n or Docker required.

```bash
# 1. Run with defaults (uses fixture mode — no credentials needed)
python dry_run.py

# 2. Run with real GitHub data + mock Claude
python dry_run.py --owner vercel --repo next.js

# 3. Run with real GitHub + real Claude
export GITHUB_TOKEN=ghp_...
export ANTHROPIC_API_KEY=sk-ant-...
python dry_run.py --owner anthropics --repo claude-code

# 4. Bilingual: French output
python dry_run.py --language FR

# 5. JSON output (all 3 formats: Discord + Slack + Email)
python dry_run.py --json

# 6. Run the test suite (21+ tests)
python -m pytest tests/test_workflow_json.py -v

# 7. Validate workflow structure
python validate_workflow.py
```

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| "401 Unauthorized" from GitHub | Check `GITHUB_TOKEN` has `repo` scope and hasn't expired |
| "401 Unauthorized" from Claude | Verify `ANTHROPIC_API_KEY` starts with `sk-ant-` |
| Empty summary | Repo may have no activity this week — check date range |
| Discord message truncated | Discord limits to 2000 chars; summary is capped automatically |
| Timeout on GitHub API | The workflow uses 30s timeouts with `continueOnFail` |
| Email not sending | Configure SMTP credentials in n8n Email node settings |
| dry_run.py fails | Run `python dry_run.py --help` first; fixture mode works offline |

## 📁 Files

```
submissions/laurentketterle-hub/n8n-weekly-dev-summary/
├── workflow.json              # Complete n8n workflow (13 nodes)
├── dry_run.py                 # Python simulator (no n8n required)
├── validate_workflow.py       # CI validation script
├── README.md                  # This file — setup & usage
├── architecture.md            # Architecture deep-dive
├── sample-output.md           # Detailed example output (all formats)
├── troubleshooting.md         # Common issues & solutions
├── env.template               # Environment variables template
├── examples/
│   ├── dry_run_log.txt        # Captured output of dry_run.py + tests
│   └── sample_output.md       # Static example outputs
└── tests/
    ├── __init__.py
    └── test_workflow_json.py  # 21+ structural & semantic tests
```

## 💡 Customization

- **Change schedule**: Edit the Cron node → change `hoursInterval` (168 = weekly, 24 = daily)
- **Different model**: Edit Build Claude Prompt → change `model` field (e.g., `claude-opus-4-20250514`)
- **Add more repos**: Duplicate the Fetch nodes and add another aggregation branch
- **Custom prompt**: Edit the `systemPrompt` and `userMessage` templates in Build Claude Prompt
- **Add channels**: Add another HTTP Request node after Format Output for Telegram, Teams, etc.
- **Change language**: Set `SUMMARY_LANGUAGE=FR` for French output
