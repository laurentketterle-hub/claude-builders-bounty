# Troubleshooting Guide

## Common Issues & Solutions

### 1. Workflow Won't Activate
**Symptom:** n8n shows "Error activating workflow"

**Solutions:**
- Check that all required environment variables are set in n8n
- Verify the Cron node has a valid interval (168h for weekly)
- Ensure no nodes have syntax errors in Code nodes

### 2. GitHub API Returns 401
**Symptom:** Fetch Commits / Issues / PRs nodes fail with 401

**Solutions:**
- Your GitHub token may have expired — generate a new one at GitHub Settings → Developer Settings → Personal Access Tokens
- Verify the token has `repo` scope (for private repos) or `public_repo` (for public repos)
- Check that the `GITHUB_TOKEN` env variable starts with `ghp_`
- For org repos, ensure the token has SSO authorization

### 3. Claude API Returns 401 or 403
**Symptom:** Claude API node fails with authentication error

**Solutions:**
- Verify your API key starts with `sk-ant-`
- Check your Anthropic account has available credits
- Ensure the `anthropic-version` header is set to `2023-06-01`
- Try a different model if `claude-sonnet-4-20250514` is not available on your tier

### 4. Discord Message Not Appearing
**Symptom:** No error, but no message in Discord

**Solutions:**
- Verify the webhook URL is correct (Discord → Channel Settings → Integrations → Webhooks)
- Check that the message content is under 2000 characters (the workflow auto-truncates to 1900)
- Ensure the webhook hasn't been rate-limited (Discord allows 5 requests/2 seconds per webhook)
- Test the webhook manually with curl: `curl -H "Content-Type: application/json" -d '{"content":"test"}' $DISCORD_WEBHOOK`

### 5. Empty Summary / No Data
**Symptom:** Summary says "0 commits, 0 issues, 0 PRs"

**Solutions:**
- The repository may genuinely have no activity this week
- Check that `REPO_OWNER` and `REPO_NAME` are correct (case-sensitive)
- Verify the date window calculation is correct — the workflow uses UTC
- For private repos, ensure the GitHub token has access

### 6. Summary in Wrong Language
**Symptom:** Summary is in English when you want French (or vice versa)

**Solutions:**
- Set `SUMMARY_LANGUAGE=FR` in n8n environment variables
- Only `EN` and `FR` are supported — other values default to English

### 7. Workflow Takes Too Long
**Symptom:** Execution time >30 seconds

**Solutions:**
- The Claude API call is the bottleneck (3-8 seconds typically)
- For very large repos with 1000+ commits/week, consider reducing the per_page parameter
- If using email delivery, SMTP connection can add 2-5 seconds
- GitHub API rate limiting: 5000 requests/hour for authenticated users — shouldn't be an issue

### 8. Duplicate Messages
**Symptom:** Multiple identical Discord/Slack messages

**Solutions:**
- Ensure only one delivery channel is configured, or that you want multi-channel delivery
- The workflow sends to ALL configured channels — disable unused ones by removing their env vars
- Check that you don't have multiple instances of the workflow active

### 9. Rate Limiting
**Symptom:** GitHub API returns 403 with "rate limit exceeded"

**Solutions:**
- Authenticated requests have 5000/hour limit — the workflow makes 3 requests per run (weekly)
- If you're testing manually multiple times, you may hit the limit
- Wait for the rate limit window to reset (check `X-RateLimit-Reset` header)
- Use a different token if needed

### 10. Node Version Compatibility
**Symptom:** Code nodes fail with syntax errors

**Solutions:**
- The Code nodes use modern JavaScript (template literals, arrow functions, optional chaining)
- Ensure your n8n instance runs Node.js 18+
- Cloud n8n instances always run the latest LTS

## Debug Mode
To enable verbose logging:
1. Edit the **Compute Date Window** node
2. Add `console.log('Debug:', { since, until, repoOwner, repoName })`
3. Execute manually and check the n8n execution log

## Getting Help
- n8n Community Forum: https://community.n8n.io
- Claude API Docs: https://docs.anthropic.com
- GitHub API Docs: https://docs.github.com/en/rest
