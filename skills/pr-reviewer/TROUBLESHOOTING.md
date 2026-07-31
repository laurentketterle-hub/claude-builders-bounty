# Troubleshooting Guide

Common issues and solutions when using PR Reviewer Agent.

---

## Authentication Errors

### `Error: Set GITHUB_TOKEN env var`

The GitHub token is missing. Set it in your environment:

```bash
# Temporary (current session)
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Permanent (add to ~/.bashrc, ~/.zshrc, or ~/.profile)
echo 'export GITHUB_TOKEN=ghp_xxxxxxxxxxxx' >> ~/.bashrc
source ~/.bashrc
```

**For GitLab:**
```bash
export GITLAB_TOKEN=glpat-xxxxxxxxxxxx
```

**Token permissions needed:**
- GitHub: `repo` scope (private repos) or `public_repo` (public repos only)
- GitLab: `read_api` scope

---

## Network Errors

### `urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED]>`

Your system's SSL certificates may be outdated. On macOS:

```bash
# Reinstall certifi certificates
/Applications/Python\ 3.x/Install\ Certificates.command
```

On Linux:
```bash
# Update CA certificates
sudo update-ca-certificates
# Or for Python specifically
pip install --upgrade certifi
```

**Warning:** Do NOT set `verify=False` as a workaround — this disables SSL entirely.

### `Connection timed out` or `HTTP Error 403: rate limit exceeded`

- GitHub API rate limit: 60 req/h unauthenticated, 5000 req/h with token
- Ensure your token is valid: `gh auth status`
- For CI/CD, use a dedicated bot account token

---

## URL Parsing Issues

### `Error: Invalid PR/MR URL`

The URL must match one of these formats:
- GitHub: `https://github.com/OWNER/REPO/pull/NUMBER`
- GitLab: `https://gitlab.com/GROUP/PROJECT/-/merge_requests/NUMBER`

Common mistakes:
- Using the repo URL instead of the PR URL
- Trailing slash missing (`/pull/123` not `/pull/123/`)
- Self-hosted GitLab URLs (not yet supported — use `gitlab.example.com`)

---

## GitLab Specific Issues

### `HTTP Error 404: Project not found`

GitLab encodes project paths differently. If your project has subgroups:

```
Instead of: https://gitlab.com/group/subgroup/project
Use encoded: gitlab.com/api/v4/projects/group%2Fsubgroup%2Fproject
```

The agent handles this automatically — just use the normal GitLab MR URL.

### MR changes are empty or truncated

GitLab's `changes` endpoint has a maximum diff size. For very large MRs (>100 files), some diffs may be omitted. Use `--json` output and check the `changed_files` count.

---

## GitHub Action Issues

### Action doesn't trigger

Check the workflow triggers in `.github/workflows/pr-review.yml`:
- `pull_request: [opened, synchronize]` for auto-review
- `issue_comment: [created]` for `/review` command

Make sure the action file is on the **default branch** (usually `main`).

### `gh: command not found`

The action uses `gh` CLI for PR comments. Ensure:
1. `GITHUB_TOKEN` is available (GitHub Actions provides it automatically as `${{ secrets.GITHUB_TOKEN }}`)
2. The workflow has `permissions: contents: read, pull-requests: write`

---

## Output Issues

### JSON output is empty or malformed

1. Run with `--json` flag
2. Check stderr for error messages: `python pr_review.py --pr <URL> --json 2> error.log`
3. Verify the PR/MR exists and is accessible

### Markdown doesn't render correctly on GitHub

- The agent produces standard GitHub Flavored Markdown
- Ensure the output is posted as a PR comment, not as a file
- Emoji (`🔍`, `⚠️`, `💡`, `🟢`) require Unicode support

---

## Performance

### Review takes too long for large PRs

- Large PRs (>1000 additions, >50 files) can take 30-60 seconds
- The agent fetches all file diffs — there's no pagination limit on diffs
- Consider reviewing large PRs in smaller chunks
- The `--json` flag is slightly faster (skips markdown formatting)

---

## Still stuck?

1. Check the [sample outputs](samples/) for expected format
2. Run with `--json` and inspect the raw data
3. Verify your token has sufficient permissions
4. File an issue with the PR URL (redacted) and error output
