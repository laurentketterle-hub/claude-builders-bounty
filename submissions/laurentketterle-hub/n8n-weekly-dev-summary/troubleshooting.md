# Troubleshooting Guide

## Common Issues

### "401 Unauthorized" from GitHub API

**Symptoms:** GitHub fetch nodes fail with HTTP 401.

**Solutions:**
1. Verify `GITHUB_TOKEN` environment variable is set
2. Check the token hasn't expired (go to [GitHub Settings → Tokens](https://github.com/settings/tokens))
3. Ensure token has `repo` scope (at minimum)
4. In n8n, check that the credential is assigned to all 3 GitHub HTTP Request nodes
5. Test the token manually: `curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/repos/owner/repo/commits`

### "401 Unauthorized" from Claude API

**Symptoms:** Claude API node fails with HTTP 401.

**Solutions:**
1. Verify `ANTHROPIC_API_KEY` starts with `sk-ant-`
2. Check API key validity at [console.anthropic.com](https://console.anthropic.com)
3. Ensure the header name is `x-api-key` (not `Authorization`)
4. Check rate limits on your Anthropic account

### Empty or No Summary Generated

**Symptoms:** Workflow runs but summary is empty or minimal.

**Solutions:**
1. The repository may genuinely have no activity in the past 7 days — check manually
2. Verify `REPO_OWNER` and `REPO_NAME` are correct
3. Check the date range calculation in "Compute Date Window" node
4. Run with `dry_run.py` locally to test: `python dry_run.py --owner your-org --repo your-repo`
5. Set `GITHUB_TOKEN` in dry_run to test with real data

### Discord Message Truncated

**Symptoms:** Discord message is cut off mid-sentence.

**Solutions:**
1. Discord webhook limit is 2000 characters — the workflow caps output at 2000 chars
2. Check if the narrative from Claude is unusually long
3. Reduce `max_tokens` in Claude API call to produce shorter summaries
4. The Slack and Email formats don't have this limitation

### Slack Message Not Rendering Properly

**Symptoms:** Slack message appears as raw JSON or plain text.

**Solutions:**
1. Ensure the Slack webhook URL is correct and the app is installed in the channel
2. The workflow sends Block Kit format — verify the webhook supports blocks
3. Check that `SLACK_WEBHOOK` env var is set correctly
4. The node uses `continueOnFail: true` — check execution logs for the Slack node specifically

### Email Not Sending

**Symptoms:** Email node shows success but no email received.

**Solutions:**
1. Configure SMTP credentials in n8n → Settings → Credentials → SMTP
2. Verify `EMAIL_TO` and `SMTP_FROM` environment variables
3. Check spam/junk folder
4. Test SMTP connection: use n8n's test button on the SMTP credential
5. For Gmail: use an App Password (not your regular password)
6. Alternative: use SendGrid, Resend, or Mailgun SMTP relay

### dry_run.py Fails

**Symptoms:** `python dry_run.py` throws errors.

**Solutions:**
1. Check Python version: `python --version` (needs 3.9+)
2. dry_run.py uses only stdlib — no pip install needed
3. Run `python dry_run.py --help` to verify the script parses
4. The script falls back to fixture mode without credentials — should never fail
5. If GitHub API is blocked (corporate firewall), fixture mode should still work
6. Run with `--json` flag for structured output debugging

### Workflow Import Fails in n8n

**Symptoms:** n8n says "Invalid workflow" when importing.

**Solutions:**
1. Ensure you're importing `workflow.json` (not `n8n-weekly-summary.json`)
2. Check the file is valid JSON: `python -m json.tool workflow.json`
3. n8n version must be 1.0+ (supports the node types used)
4. Run `python validate_workflow.py` to check for structural issues

### Timeouts on GitHub API

**Symptoms:** GitHub fetch nodes timeout.

**Solutions:**
1. The workflow uses 30-second timeouts — this is usually sufficient
2. Large repos may have many commits; increase `per_page` from 100 if needed
3. GitHub API rate limits: unauthenticated = 60/hr, authenticated = 5000/hr
4. Nodes have `continueOnFail: true` — the workflow continues even if one fetch times out
5. Check network connectivity from your n8n instance

### Cron Not Firing

**Symptoms:** Workflow is "Active" but doesn't run on schedule.

**Solutions:**
1. The cron fires at 5 PM UTC on Fridays (168h interval)
2. Toggle "Active" off and on again to reset the trigger
3. Check n8n server timezone: the workflow is set to UTC
4. For testing: use "Execute Workflow" manually instead of waiting for cron
5. n8n self-hosted: check the server's system time is correct

## Diagnostic Checklist

Run these in order to isolate issues:

```bash
# 1. Validate workflow structure
python validate_workflow.py

# 2. Run full test suite
python -m pytest tests/test_workflow_json.py -v

# 3. Test dry-run with fixture (no credentials needed)
python dry_run.py

# 4. Test dry-run with JSON output for CI
python dry_run.py --json

# 5. Test with real GitHub data (optional)
export GITHUB_TOKEN=ghp_...
python dry_run.py --owner your-org --repo your-repo

# 6. Test with real Claude API (optional)
export ANTHROPIC_API_KEY=sk-ant-...
python dry_run.py --owner your-org --repo your-repo
```

## Getting Help

- [n8n Community Forum](https://community.n8n.io)
- [Anthropic API Docs](https://docs.anthropic.com)
- [GitHub REST API Docs](https://docs.github.com/en/rest)
- File an issue on the [claude-builders-bounty](https://github.com/laurentketterle-hub/claude-builders-bounty/issues) repository
