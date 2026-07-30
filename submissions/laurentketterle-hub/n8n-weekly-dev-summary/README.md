# Weekly Dev Summary — n8n + Claude Workflow

Automated weekly development summary using n8n workflow automation and Claude Code API.

## Architecture

```
Cron Trigger (Friday 5PM)
  |
  +— GitHub API: Commits (last 7 days)
  +— GitHub API: Closed Issues (last 7 days)  
  +— GitHub API: Merged PRs (last 7 days)
  |
  +— Aggregator: deduplicate, extract authors, calculate stats
  |
  +— Claude API: generate narrative summary (claude-sonnet-4-20250514)
  |
  +— Discord Webhook: post formatted summary
```

## Files

| File | Description |
|------|-------------|
| `workflow.json` | Complete n8n workflow (importable via n8n UI) |
| `dry_run.py` | Local dry-run: simulate GitHub API calls, generate sample output |
| `validate_workflow.py` | CI validation: checks workflow.json structure and integrity |
| `tests/test_workflow.py` | Unit tests for workflow validation and dry-run |
| `sample-output.md` | Example weekly summary from a real run |
| `README.md` | This file — setup guide and documentation |

## Quick Start

### 1. Import into n8n
```bash
# In n8n UI: Workflows → Import from File → select workflow.json
```

### 2. Dry-run (no API keys needed)
```bash
python3 dry_run.py
# Output saved to dry_run_output.md
```

### 3. Configure credentials
In n8n, create credentials for:
- **GitHub**: Personal Access Token with `repo` scope
- **Claude (HTTP Request)**: API key from Anthropic Console  
- **Discord**: Webhook URL from channel settings

### 4. Schedule
The workflow is pre-configured to run every Friday at 5:00 PM UTC.
Adjust the cron expression in the Schedule Trigger node as needed.

## Testing
```bash
python3 -m pytest tests/ -v
# Or:
python3 -m unittest tests/test_workflow.py -v
```

## Acceptance Criteria

- [x] Cron-triggered weekly execution (Friday 5 PM)
- [x] GitHub API integration: commits, issues, PRs
- [x] Claude API for narrative summary generation
- [x] Discord webhook for delivery
- [x] Dry-run mode for local testing (no API keys needed)
- [x] Unit tests covering workflow validation
- [x] CI validation via GitHub Actions
- [x] Sample output demonstrating expected results
