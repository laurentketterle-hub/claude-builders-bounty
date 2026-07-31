# Architecture — n8n + Claude Weekly Dev Summary

## Overview

This workflow is a 13-node n8n pipeline that runs every Friday at 5 PM UTC, fetches GitHub activity for the past 7 days, generates a narrative summary using Claude AI, and delivers it to up to 3 channels simultaneously (Discord, Slack, Email).

## Design Decisions

### Parallel GitHub API Calls

Commits, Issues, and PRs are fetched in **parallel** (3 simultaneous HTTP Request nodes). This reduces total latency from ~9s (sequential) to ~3s in typical cases. Each call uses `continueOnFail: true` so one API failure doesn't block the others.

### Data Aggregation

The **Aggregate & Filter Data** Code node:
- Deduplicates issues/PRs (GitHub's Issues API includes PRs)
- Filters to only items within the 7-day window
- Computes per-author commit stats
- Generates a structured `stats` object

### Claude Prompt Engineering

The **Build Claude Prompt** Code node constructs:
- **System prompt**: Role and formatting instructions (localized EN/FR)
- **User message**: Structured data including stats, contributors, PRs, issues
- **Model**: `claude-sonnet-4-20250514` (explicitly pinned for reproducibility)

The bilingual templates ensure French prompts use native phrasing (not just translated English).

### Multi-Channel Formatting

The **Format Output** Code node produces 3 distinct formats:

1. **Discord** — Markdown message, capped at 2000 characters (Discord webhook limit)
2. **Slack** — Block Kit JSON with structured sections for rich rendering
3. **Email** — Plain text with clear section headers for maximum compatibility

All three channels are sent in parallel from the Format Output node. Each has `continueOnFail: true` so one failing channel doesn't affect the others.

## Error Handling Strategy

| Component | Strategy | Rationale |
|-----------|----------|-----------|
| GitHub API calls | `continueOnFail: true` | One API failure shouldn't block the pipeline |
| Claude API call | `continueOnFail: true` | Summary generation failure → deliver raw stats |
| Delivery channels | `continueOnFail: true` | Discord down? Slack and Email still work |
| dry_run.py | Fixture fallback | Works offline without any credentials |

## Data Flow

```
Cron Trigger
  → Compute Date Window (since/until ISO 8601)
    → [Fetch Commits ∥ Fetch Issues ∥ Fetch PRs]  (parallel)
      → Aggregate & Filter Data (merge, dedupe, stats)
        → Build Claude Prompt (EN/FR templates)
          → Claude API (generate narrative)
            → Format Output (Discord + Slack + Email)
              → [Send Discord ∥ Send Slack ∥ Send Email]  (parallel)
                → Log Summary (console)
```

## Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `REPO_OWNER` | Fetch nodes | GitHub org/user for API calls |
| `REPO_NAME` | Fetch nodes | Repository name |
| `GITHUB_TOKEN` | Fetch nodes | Bearer token for GitHub API |
| `ANTHROPIC_API_KEY` | Claude API node | `x-api-key` header |
| `DISCORD_WEBHOOK` | Send to Discord | Webhook URL |
| `SLACK_WEBHOOK` | Send to Slack | Incoming webhook URL |
| `EMAIL_TO` | Send Email | Recipient address |
| `SMTP_FROM` | Send Email | Sender address |
| `SUMMARY_LANGUAGE` | Build Claude Prompt | `EN` or `FR` |

## Security Considerations

- **API keys** are passed via n8n environment variables, never hardcoded in the workflow JSON
- **GitHub tokens** should use minimal scope (`repo` read-only)
- **Webhook URLs** contain secrets — use environment variables, not plain text
- **dry_run.py** accepts credentials via environment variables only (`GITHUB_TOKEN`, `ANTHROPIC_API_KEY`)

## Testing Architecture

### validate_workflow.py
Static analysis of workflow.json:
- Node count, connection validity, required node types
- Delivery channel detection (Discord/Slack/Email)
- Bilingual support check (EN/FR)
- Error handling (continueOnFail nodes)
- Model version check (claude-sonnet-4-20250514)

### test_workflow_json.py (21+ tests)
Unit tests with unittest framework:
- JSON parsing and structure validation
- Required fields (`id`, `name`, `type`, `position`, `parameters`) per node
- Node type validation against n8n built-in types
- Connection graph integrity (no orphan edges, all targets valid)
- Cron trigger configuration (168h interval)
- Multi-channel delivery verification (Discord + Slack + Email present)
- Bilingual prompt detection
- File existence checks for all deliverables

### dry_run.py
End-to-end simulation:
- Real GitHub API calls → fixture fallback
- Real Claude API calls → mock fallback
- Multi-format output (Discord, Slack, Email)
- JSON mode for CI/programmatic use
- --help, --version, --language flags

## CI/CD Integration

The `.github/workflows/ci.yml` runs on every push and PR:
1. Python syntax check (dry_run.py, validate_workflow.py)
2. workflow.json structural validation via validate_workflow.py
3. Full test suite via pytest (21+ tests)
4. dry_run.py smoke test (JSON mode with fixture)

## Scalability

- Add more repos by duplicating the 3 Fetch nodes and the Aggregate node
- Add more channels (Telegram, Teams, etc.) by adding HTTP Request nodes after Format Output
- Change to daily by setting `hoursInterval` to 24
- Multiple repos in one report: add parallel fetch + aggregation branches
