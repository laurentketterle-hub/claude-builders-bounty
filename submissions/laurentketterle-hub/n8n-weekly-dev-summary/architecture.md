# Architecture Deep-Dive — n8n Weekly Dev Summary

## Overview

The workflow implements a 13-node pipeline that transforms raw GitHub activity data into a polished narrative summary delivered to team communication channels.

## Node Breakdown

### Layer 1: Trigger & Configuration
| Node | Type | Purpose |
|------|------|---------|
| **Weekly Cron** | `scheduleTrigger` | Fires every 168 hours (weekly) |
| **Compute Date Window** | `code` | Calculates 7-day ISO date range, reads environment variables |

### Layer 2: Data Fetching (Parallel)
| Node | Type | Endpoint |
|------|------|----------|
| **Fetch Commits** | `httpRequest` | `GET /repos/{owner}/{repo}/commits` |
| **Fetch Closed Issues** | `httpRequest` | `GET /repos/{owner}/{repo}/issues?state=closed` |
| **Fetch Merged PRs** | `httpRequest` | `GET /repos/{owner}/{repo}/pulls?state=closed` |

All three nodes execute in parallel after the date window is computed. Each node has `continueOnFail: true` to prevent a single API failure from blocking the entire pipeline.

### Layer 3: Processing
| Node | Type | Purpose |
|------|------|---------|
| **Aggregate & Filter** | `code` | Deduplicates, filters by date, computes author stats |
| **Build Claude Prompt** | `code` | Constructs system prompt + user message with GitHub data |

The Aggregate node receives 3 inputs (one from each fetch) and merges them. Key processing:
1. Filter commits/PRs/issues to the 7-day window
2. Separate issues from PRs (PRs have a `pull_request` key in the GitHub API)
3. Compute author statistics with commit counts
4. Extract top 15 PRs and 15 issues for the prompt

The Build Claude Prompt node:
1. Reads the `SUMMARY_LANGUAGE` variable (EN or FR)
2. Constructs a bilingual system prompt
3. Formats GitHub data into a structured user message
4. Builds the complete Claude API request body

### Layer 4: AI Generation
| Node | Type | Purpose |
|------|------|---------|
| **Claude API** | `httpRequest` | `POST https://api.anthropic.com/v1/messages` |

Uses `claude-sonnet-4-20250514` with 1024 max tokens. The API call has a 60-second timeout for longer summaries. On failure, the error message is captured and included in the output.

### Layer 5: Output Formatting
| Node | Type | Purpose |
|------|------|---------|
| **Format Output** | `code` | Converts Claude response to Discord/Slack/Email formats |

Generates three output formats:
- **Discord**: Markdown with 1900-char cap (Discord limit is 2000)
- **Slack**: Block Kit JSON with header + sections
- **Email**: Plain text with full content

### Layer 6: Delivery (Parallel)
| Node | Type | Purpose |
|------|------|---------|
| **Send to Discord** | `httpRequest` | POST to Discord webhook |
| **Send to Slack** | `httpRequest` | POST to Slack webhook |
| **Send Email** | `emailSend` | SMTP email delivery |

All three delivery nodes execute in parallel with `continueOnFail: true`. Only channels with configured credentials will succeed.

### Layer 7: Logging
| Node | Type | Purpose |
|------|------|---------|
| **Log Summary** | `code` | Console output for debugging and execution history |

## Data Flow

```
Cron → Date Window → [Commits API, Issues API, PRs API] → Aggregate → Prompt → Claude → Format → [Discord, Slack, Email] → Log
```

## Error Handling Strategy

1. **HTTP nodes**: All `continueOnFail: true` — failures are logged but don't halt the pipeline
2. **Missing data**: Empty arrays are handled gracefully (zero commits/PRs won't crash)
3. **Claude API failure**: Error message is captured and included in the output instead of crashing
4. **Delivery failures**: Each channel is independent — Discord failing won't affect Slack

## Performance

| Phase | Typical Duration |
|-------|-----------------|
| GitHub API (3 parallel calls) | 1-3 seconds |
| Data aggregation | <100ms |
| Claude API inference | 3-8 seconds |
| Delivery (3 parallel) | 1-2 seconds |
| **Total** | **5-13 seconds** |

## Security

- **No hardcoded secrets**: All credentials are environment variables
- **Header-based auth**: GitHub Bearer token, Claude x-api-key
- **Webhook URLs**: Stored in environment variables, not in the workflow JSON
- **Email**: SMTP credentials managed by n8n's built-in credential store

## Scaling

For repositories with >100 commits/week:
- The GitHub API returns max 100 items per page
- The Aggregate node handles this gracefully by processing whatever is returned
- For production use with very large repos, add pagination nodes using the `Link` header
