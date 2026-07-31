# n8n + Claude — Automated Weekly Dev Summary

> **Bounty #5 — $200 USD** | Powered by [Opire](https://opire.dev)

A complete, production-ready n8n workflow that generates weekly narrative summaries of GitHub repository activity using the Claude API.

## 🎯 Features

- **⏰ Weekly Cron** — Runs every Friday at 5 PM UTC
- **📊 GitHub Integration** — Fetches commits, closed issues, and merged PRs
- **🤖 Claude AI** — Generates natural, narrative summaries (model: `claude-sonnet-4-20250514`)
- **📨 Multi-Channel Delivery** — Discord, Slack, or Email
- **🌐 Bilingual** — English (EN) or French (FR) summaries
- **🛡️ Resilient** — Error handling on every node, continues on API failures
- **📝 Detailed Output** — Top contributors, standout PRs, issue summaries, narrative

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
This week the team shipped the long-awaited OAuth2 integration (PR #342),
enabling third-party app authentication. Bob fixed a critical race condition
in the payment confirmation flow. The new rate-limiting middleware went live
on production, capping API requests at 100/min per IP...
```

## 🧪 Validation

Run the validation script to verify workflow integrity:

```bash
python validate_workflow.py
```

Expected output:
```
✅ Valid workflow: 13 nodes, 12 connections
✅ Claude API node configured correctly
✅ Cron trigger present
✅ All connections reference valid nodes
✅ Bilingual prompt support (EN/FR)
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

## 📁 Files

```
submissions/laurentketterle-hub/n8n-weekly-dev-summary/
├── workflow.json          # Complete n8n workflow (13 nodes)
├── README.md              # This file — setup & usage
├── sample-output.md       # Detailed example output
├── validate_workflow.py   # CI validation script
├── architecture.md        # Architecture deep-dive
├── env.template           # Environment variables template
└── screenshot.png         # n8n execution screenshot
```

## 💡 Customization

- **Change schedule**: Edit the Cron node → change `hoursInterval` (168 = weekly, 24 = daily)
- **Different model**: Edit Build Claude Prompt → change `model` field (e.g., `claude-opus-4-20250514`)
- **Add more repos**: Duplicate the Fetch nodes and add another aggregation branch
- **Custom prompt**: Edit the `systemPrompt` and `userMessage` templates in Build Claude Prompt
