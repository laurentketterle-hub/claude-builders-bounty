#!/usr/bin/env python3
"""
dry_run.py — Simulates the n8n weekly-dev-summary workflow in Python.

Faithful re-implementation of the 13-node n8n workflow so the deliverable
can be tested without a live n8n / Docker / real webhooks. It:

  1. Pulls commits / closed issues / merged PRs from the GitHub REST API
     (or falls back to a deterministic offline fixture when no network /
     no token is available).
  2. Normalises & merges the three streams exactly as the n8n "Aggregate
     & Filter Data" Code node does.
  3. Calls the Anthropic Messages API with claude-sonnet-4-20250514, using
     the same system + user prompt template baked into the n8n workflow.
     Falls back to a mock narrative when ANTHROPIC_API_KEY is missing.
  4. Formats the response into Discord, Slack, and Email formats exactly
     like the "Format Output" n8n node and prints all three.
  5. Supports bilingual output (EN/FR) via --language flag.

Run it:
    python3 dry_run.py                              # uses defaults
    python3 dry_run.py --owner vercel --repo next.js
    python3 dry_run.py --language FR
    GITHUB_TOKEN=ghp_...  ANTHROPIC_API_KEY=sk-ant-...  python3 dry_run.py

Exit code 0 == success.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any


# --------------------------------------------------------------------------- #
# Config (mirrors the "Compute Date Window" Code node in the n8n workflow)   #
# --------------------------------------------------------------------------- #

DEFAULT_OWNER = "laurentketterle-hub"
DEFAULT_REPO = "claude-builders-bounty"
DEFAULT_LANGUAGE = "EN"
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_MAX_ITEMS = 100
DEFAULT_DISCORD_WEBHOOK = "https://discord.com/api/webhooks/REPLACE_ME"
DEFAULT_SLACK_WEBHOOK = "https://hooks.slack.com/services/REPLACE_ME"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
VERSION = "2.1.0"


# --------------------------------------------------------------------------- #
# Step 1+2: GitHub fetch (mirrors the 3 parallel HTTP Request nodes)         #
# --------------------------------------------------------------------------- #

def _github_get(path: str, token: str | None, timeout: int = 15) -> Any:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "weekly-dev-summary-dryrun/2.1")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))


def _fixture() -> dict[str, list[dict]]:
    """Deterministic offline data so the dry-run works without credentials."""
    now = datetime.now(timezone.utc)
    return {
        "commits": [
            {
                "sha": "a1b2c3d4e5f60718293a4b5c6d7e8f9001020304",
                "html_url": "https://github.com/o/r/commit/a1b2c3d",
                "commit": {
                    "author": {"name": "Alice", "date": now.isoformat()},
                    "message": "feat: add weekly summary workflow\n",
                },
            },
            {
                "sha": "b2c3d4e5f60718293a4b5c6d7e8f9001020304a1",
                "html_url": "https://github.com/o/r/commit/b2c3d4e",
                "commit": {
                    "author": {"name": "Bob", "date": (now - timedelta(days=1)).isoformat()},
                    "message": "fix: correct date math in dry-run\n",
                },
            },
            {
                "sha": "c3d4e5f60718293a4b5c6d7e8f9001020304a1b2",
                "html_url": "https://github.com/o/r/commit/c3d4e5f",
                "commit": {
                    "author": {"name": "Alice", "date": (now - timedelta(days=2)).isoformat()},
                    "message": "docs: add README setup section\n",
                },
            },
            {
                "sha": "d4e5f60718293a4b5c6d7e8f9001020304a1b2c3",
                "html_url": "https://github.com/o/r/commit/d4e5f60",
                "commit": {
                    "author": {"name": "Carol", "date": (now - timedelta(days=3)).isoformat()},
                    "message": "feat: multi-channel delivery (Discord + Slack + Email)\n",
                },
            },
            {
                "sha": "e5f60718293a4b5c6d7e8f9001020304a1b2c3d4",
                "html_url": "https://github.com/o/r/commit/e5f6071",
                "commit": {
                    "author": {"name": "Dave", "date": (now - timedelta(days=4)).isoformat()},
                    "message": "fix: bilingual FR prompt template\n",
                },
            },
        ],
        "issues": [
            {
                "number": 5,
                "title": "[BOUNTY $200] WORKFLOW: n8n + Claude Code — automated weekly dev summary",
                "user": {"login": "maintainer"},
                "html_url": "https://github.com/o/r/issues/5",
                "closed_at": now.isoformat(),
                "pull_request": None,
            },
            {
                "number": 12,
                "title": "bug: cron fires twice on DST boundary",
                "user": {"login": "carol"},
                "html_url": "https://github.com/o/r/issues/12",
                "closed_at": (now - timedelta(days=1)).isoformat(),
                "pull_request": None,
            },
            {
                "number": 18,
                "title": "feat: add Slack webhook support to summary workflow",
                "user": {"login": "bob"},
                "html_url": "https://github.com/o/r/issues/18",
                "closed_at": (now - timedelta(days=3)).isoformat(),
                "pull_request": None,
            },
        ],
        "pulls": [
            {
                "number": 42,
                "title": "feat: Claude API integration",
                "user": {"login": "Alice"},
                "html_url": "https://github.com/o/r/pull/42",
                "merged_at": now.isoformat(),
                "additions": 240,
                "deletions": 18,
            },
            {
                "number": 43,
                "title": "chore: bump deps",
                "user": {"login": "Bob"},
                "html_url": "https://github.com/o/r/pull/43",
                "merged_at": (now - timedelta(days=2)).isoformat(),
                "additions": 12,
                "deletions": 12,
            },
            {
                "number": 44,
                "title": "feat: multi-channel delivery (Discord + Slack + Email)",
                "user": {"login": "Carol"},
                "html_url": "https://github.com/o/r/pull/44",
                "merged_at": (now - timedelta(days=1)).isoformat(),
                "additions": 156,
                "deletions": 8,
            },
        ],
    }


def fetch_github(owner: str, repo: str, lookback_days: int, max_items: int,
                 token: str | None) -> tuple[dict, str]:
    """Return (data, source) where source is 'live' or 'fixture'."""
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    qs = urllib.parse.urlencode({
        "since": since,
        "per_page": max_items,
    })
    try:
        commits = _github_get(f"/repos/{owner}/{repo}/commits?{qs}", token)
        issues = _github_get(f"/repos/{owner}/{repo}/issues?{qs}&state=closed", token)
        prs = _github_get(
            f"/repos/{owner}/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page={max_items}",
            token,
        )
        return {"commits": commits, "issues": issues, "pulls": prs}, "live"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        print(f"[dry-run] GitHub fetch failed ({exc.__class__.__name__}: {exc}); using fixture.",
              file=sys.stderr)
        return _fixture(), "fixture"


# --------------------------------------------------------------------------- #
# Step 3: Merge & format (mirrors "Aggregate & Filter Data" Code node)       #
# --------------------------------------------------------------------------- #

def merge_and_format(raw: dict, config: dict) -> dict:
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=config["lookback_days"])).isoformat()
    commits_raw = raw.get("commits") or []
    issues_raw = raw.get("issues") or []
    prs_raw = raw.get("pulls") or []
    closed_issues = [i for i in issues_raw if not i.get("pull_request")]
    merged_prs = [p for p in prs_raw if p.get("merged_at") and p["merged_at"] >= cutoff]

    def _commit(c):
        return {
            "hash": (c.get("sha") or "")[:7],
            "message": (c.get("commit", {}).get("message") or "").split("\n")[0][:200],
            "author": (c.get("commit", {}).get("author", {}).get("name")
                       or c.get("author", {}).get("login") or "unknown"),
            "login": c.get("author", {}).get("login") or "unknown",
            "url": c.get("html_url", ""),
            "date": c.get("commit", {}).get("author", {}).get("date", ""),
        }

    def _issue(i):
        return {
            "number": i.get("number"),
            "title": i.get("title", ""),
            "author": (i.get("user") or {}).get("login", "unknown"),
            "url": i.get("html_url", ""),
            "closedAt": i.get("closed_at", ""),
            "labels": [l.get("name", "") for l in (i.get("labels") or [])],
        }

    def _pr(p):
        return {
            "number": p.get("number"),
            "title": p.get("title", ""),
            "author": (p.get("user") or {}).get("login", "unknown"),
            "url": p.get("html_url", ""),
            "mergedAt": p.get("merged_at", ""),
            "additions": p.get("additions", 0),
            "deletions": p.get("deletions", 0),
        }

    # Author stats from commits
    author_map = {}
    for c in commits_raw:
        login = (c.get("author", {}).get("login")
                 or c.get("commit", {}).get("author", {}).get("name") or "unknown")
        if login not in author_map:
            author_map[login] = {"login": login, "commits": 0}
        author_map[login]["commits"] += 1

    top_contributors = sorted(author_map.values(),
                              key=lambda x: x["commits"], reverse=True)[:10]

    return {
        "owner": config["owner"],
        "repo": config["repo"],
        "language": config.get("language", "EN"),
        "lookbackDays": config["lookback_days"],
        "weekEnding": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "windowStart": cutoff,
        "periodStart": (datetime.now(timezone.utc) - timedelta(days=config["lookback_days"])).strftime("%Y-%m-%d"),
        "periodEnd": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "commits": [_commit(c) for c in commits_raw],
        "closedIssues": [_issue(i) for i in closed_issues],
        "mergedPRs": [_pr(p) for p in merged_prs],
        "topContributors": top_contributors,
        "stats": {
            "totalCommits": len(commits_raw),
            "totalIssuesClosed": len(closed_issues),
            "totalPRsMerged": len(merged_prs),
            "uniqueAuthors": len(author_map),
        },
    }


# --------------------------------------------------------------------------- #
# Step 4: Claude call (mirrors "Build Claude Prompt" + "Claude API" nodes)   #
# --------------------------------------------------------------------------- #

def _claude_prompt(data: dict) -> dict:
    """Body of POST https://api.anthropic.com/v1/messages — mirrors the workflow."""
    is_french = data.get("language", "EN").upper() == "FR"

    system = (
        "Tu es un assistant qui résume l'activité hebdomadaire de développement "
        "d'un dépôt GitHub. Génère un résumé narratif concis, engageant et "
        "informatif en français. Structure : résumé global, contributeurs "
        "notables, PRs marquantes, issues résolues, tendances. Maximum 500 mots. "
        "Sois précis et factuel."
    ) if is_french else (
        "You are an assistant that summarizes weekly development activity for a "
        "GitHub repository. Generate a concise, engaging, informative narrative "
        "summary in English. Structure: overall summary, notable contributors, "
        "standout PRs, resolved issues, trends. Maximum 500 words. Be precise "
        "and factual."
    )

    def _section(title: str, items: list[str], empty: str = "(aucune)" if is_french else "(none)") -> list[str]:
        return [title, *(items if items else [empty]), ""]

    pr_list = [f"- #{p['number']}: {p['title']} ({p['author']})"
               for p in data["mergedPRs"][:15]]
    issue_list = [f"- #{i['number']}: {i['title']} ({i['author']})"
                  for i in data["closedIssues"][:15]]
    contributor_list = [f"- {c['login']}: {c['commits']} commits"
                        for c in data["topContributors"][:10]]

    repo_ref = f"{data['owner']}/{data['repo']}"
    s = data["stats"]

    if is_french:
        user_lines = [
            f"Période : {data['periodStart']} → {data['periodEnd']}",
            "",
            f"Statistiques :",
            f"- {s['totalCommits']} commits par {s['uniqueAuthors']} contributeurs",
            f"- {s['totalIssuesClosed']} issues fermées",
            f"- {s['totalPRsMerged']} PRs mergées",
            "",
        ]
        user_lines += _section("Contributeurs :", contributor_list)
        user_lines += _section("PRs mergées :", pr_list)
        user_lines += _section("Issues fermées :", issue_list)
        user_lines += ["Génère un résumé narratif de cette semaine."]
    else:
        user_lines = [
            f"Period: {data['periodStart']} → {data['periodEnd']}",
            "",
            f"Statistics:",
            f"- {s['totalCommits']} commits by {s['uniqueAuthors']} contributors",
            f"- {s['totalIssuesClosed']} issues closed",
            f"- {s['totalPRsMerged']} PRs merged",
            "",
        ]
        user_lines += _section("Contributors:", contributor_list)
        user_lines += _section("Merged PRs:", pr_list)
        user_lines += _section("Closed Issues:", issue_list)
        user_lines += ["Generate a narrative summary of this week."]

    return {
        "model": CLAUDE_MODEL,
        "max_tokens": 2048,
        "system": system,
        "messages": [{"role": "user", "content": "\n".join(user_lines)}],
    }


def _mock_narrative(data: dict) -> str:
    """Deterministic mock used when ANTHROPIC_API_KEY is missing."""
    s = data["stats"]
    lang = data.get("language") or "EN"
    is_french = lang.upper() == "FR"

    top_authors = sorted(
        {c["author"] for c in data["commits"]}
        | {i["author"] for i in data["closedIssues"]}
        | {p["author"] for p in data["mergedPRs"]}
    )

    if s["totalCommits"] == 0 and s["totalIssuesClosed"] == 0 and s["totalPRsMerged"] == 0:
        if is_french:
            return ("Semaine calme sur le dépôt — aucun commit, issue fermée "
                    "ou PR mergée enregistré durant cette période.")
        return ("It was a quiet week on the repository — no commits, closed issues, "
                "or merged PRs were recorded in the lookback window.")

    if is_french:
        return (
            f"Cette semaine, **{data['owner']}/{data['repo']}** a enregistré "
            f"{s['totalCommits']} commits, {s['totalIssuesClosed']} issues fermées "
            f"et {s['totalPRsMerged']} PRs mergées. "
            f"Contributeurs actifs : {', '.join(top_authors) if top_authors else 'aucun'}. "
            f"(Résumé simulé — définissez ANTHROPIC_API_KEY pour appeler {CLAUDE_MODEL}.)"
        )
    return (
        f"This week **{data['owner']}/{data['repo']}** saw {s['totalCommits']} commits, "
        f"{s['totalIssuesClosed']} issues closed and {s['totalPRsMerged']} PRs merged. "
        f"Active contributors included {', '.join(top_authors) if top_authors else 'no one'}. "
        f"Themes this week centred on the merged work captured in PRs, with bug-fix and "
        f"documentation commits rounding out the picture. (Mock narrative — set "
        f"ANTHROPIC_API_KEY to call the real {CLAUDE_MODEL} model. Output language: {lang}.)"
    )


def call_claude(data: dict, api_key: str | None) -> tuple[str, str]:
    """Return (narrative_text, source) where source is 'api' or 'mock'."""
    body = _claude_prompt(data)
    if not api_key:
        return _mock_narrative(data), "mock"

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
    )
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            payload = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        print(f"[dry-run] Claude call failed ({exc.__class__.__name__}: {exc}); using mock.",
              file=sys.stderr)
        return _mock_narrative(data), "mock"

    parts = []
    for block in payload.get("content") or []:
        if block.get("type") == "text" and block.get("text"):
            parts.append(block["text"])
    return ("\n".join(parts) if parts else _mock_narrative(data),
            "api" if parts else "mock")


# --------------------------------------------------------------------------- #
# Step 5: Format output — Discord, Slack, Email (mirrors "Format Output")    #
# --------------------------------------------------------------------------- #

def _format_contributors(data: dict) -> str:
    return "\n".join(
        f"{i + 1}. **{c['login']}** — {c['commits']} commits"
        for i, c in enumerate(data.get("topContributors", [])[:10])
    )

def _format_prs(data: dict) -> str:
    return "\n".join(
        f"- **#{p['number']}** {p['title']} (@{p['author']})"
        for p in data.get("mergedPRs", [])[:5]
    )

def _format_issues(data: dict) -> str:
    return "\n".join(
        f"- **#{i['number']}** {i['title']}"
        for i in data.get("closedIssues", [])[:5]
    )


def format_discord(data: dict, narrative: str) -> str:
    """Discord-compatible markdown (max 2000 chars)."""
    s = data["stats"]
    period = f"{data['periodStart']} → {data['periodEnd']}"
    return (
        f"📊 **Weekly Dev Digest — {period}**\n\n"
        f"🔄 **{s['totalCommits']} commits** by **{s['uniqueAuthors']}** contributors\n"
        f"🐛 **{s['totalIssuesClosed']} issues** closed\n"
        f"✅ **{s['totalPRsMerged']} PRs** merged\n\n"
        f"**👥 Top Contributors**\n{_format_contributors(data)}\n\n"
        f"**🔀 Merged PRs**\n{_format_prs(data)}\n\n"
        f"**📝 Narrative**\n{narrative}"
    )[:2000]


def format_slack(data: dict, narrative: str) -> dict:
    """Slack Block Kit format."""
    s = data["stats"]
    period = f"{data['periodStart']} → {data['periodEnd']}"
    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📊 Weekly Dev Digest — {period}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"🔄 *{s['totalCommits']} commits* by *{s['uniqueAuthors']}* contributors\n"
                        f"🐛 *{s['totalIssuesClosed']} issues* closed\n"
                        f"✅ *{s['totalPRsMerged']} PRs* merged"
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*👥 Top Contributors*\n{_format_contributors(data)}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔀 Merged PRs*\n{_format_prs(data)}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📝 Narrative*\n{narrative[:2500]}",
                },
            },
        ]
    }


def format_email(data: dict, narrative: str) -> str:
    """Plain-text email format."""
    s = data["stats"]
    period = f"{data['periodStart']} → {data['periodEnd']}"
    return (
        f"Weekly Dev Digest — {period}\n"
        f"{'=' * 50}\n\n"
        f"REPOSITORY: {data['owner']}/{data['repo']}\n"
        f"PERIOD: {period}\n\n"
        f"STATISTICS:\n"
        f"  Commits: {s['totalCommits']} by {s['uniqueAuthors']} contributors\n"
        f"  Issues closed: {s['totalIssuesClosed']}\n"
        f"  PRs merged: {s['totalPRsMerged']}\n\n"
        f"TOP CONTRIBUTORS:\n{_format_contributors(data)}\n\n"
        f"MERGED PRs:\n{_format_prs(data)}\n\n"
        f"NARRATIVE:\n{narrative}\n"
    )


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def main() -> int:
    p = argparse.ArgumentParser(
        description="Simulate the n8n weekly dev summary workflow (13 nodes).",
        epilog="Exit code 0 == success.",
    )
    p.add_argument("--owner", default=os.environ.get("GH_OWNER", DEFAULT_OWNER))
    p.add_argument("--repo", default=os.environ.get("GH_REPO", DEFAULT_REPO))
    p.add_argument("--language", default=os.environ.get("SUMMARY_LANGUAGE", DEFAULT_LANGUAGE),
                   choices=["EN", "FR"])
    p.add_argument("--lookback-days", type=int,
                   default=int(os.environ.get("LOOKBACK_DAYS", DEFAULT_LOOKBACK_DAYS)))
    p.add_argument("--max-items", type=int,
                   default=int(os.environ.get("MAX_ITEMS", DEFAULT_MAX_ITEMS)))
    p.add_argument("--discord-webhook",
                   default=os.environ.get("DISCORD_WEBHOOK", DEFAULT_DISCORD_WEBHOOK))
    p.add_argument("--slack-webhook",
                   default=os.environ.get("SLACK_WEBHOOK", DEFAULT_SLACK_WEBHOOK))
    p.add_argument("--json", action="store_true",
                   help="Emit output as JSON (all 3 formats).")
    p.add_argument("--version", action="version", version=f"dry_run.py v{VERSION}")
    args = p.parse_args()

    config = {
        "owner": args.owner,
        "repo": args.repo,
        "language": args.language,
        "lookback_days": args.lookback_days,
        "max_items": args.max_items,
    }

    # Step 1+2: Fetch
    print(f"[1/5] Fetching GitHub activity for {config['owner']}/{config['repo']} "
          f"(last {config['lookback_days']} days)…")
    raw, gh_source = fetch_github(config["owner"], config["repo"],
                                  config["lookback_days"], config["max_items"],
                                  os.environ.get("GITHUB_TOKEN"))
    print(f"      source: {gh_source}")

    # Step 3: Merge
    print("[2/5] Aggregating & normalising data…")
    data = merge_and_format(raw, config)
    print(f"      stats: {data['stats']}")

    # Step 4: Claude
    print(f"[3/5] Calling {CLAUDE_MODEL}…")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    narrative, claude_source = call_claude(data, api_key)
    print(f"      source: {claude_source}")

    # Step 5: Format
    print("[4/5] Formatting output (Discord + Slack + Email)…")
    discord_msg = format_discord(data, narrative)
    slack_blocks = format_slack(data, narrative)
    email_text = format_email(data, narrative)

    # Step 6: Print results
    print("[5/5] Complete!")
    print()
    print("=" * 72)

    if args.json:
        print(json.dumps({
            "discord": {"webhookUrl": args.discord_webhook, "content": discord_msg},
            "slack": {"webhookUrl": args.slack_webhook, "blocks": slack_blocks["blocks"]},
            "email": {"subject": f"Weekly Dev Digest — {data['periodStart']} → {data['periodEnd']}",
                      "body": email_text},
            "meta": {
                "source": {"github": gh_source, "claude": claude_source},
                "stats": data["stats"],
                "language": config["language"],
                "model": CLAUDE_MODEL,
            },
        }, indent=2, ensure_ascii=False))
    else:
        print("─── DISCORD ───")
        print(discord_msg)
        print()
        print("─── SLACK (block count) ───")
        print(f"Blocks: {len(slack_blocks['blocks'])}")
        print()
        print("─── EMAIL ───")
        print(email_text[:500] + ("..." if len(email_text) > 500 else ""))

    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
