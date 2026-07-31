# Sample Output — Weekly Dev Digest

Example output from the n8n workflow (actual execution).

## Discord Message

```
📊 **Weekly Dev Digest — 2026-07-25 → 2026-08-01**

🔄 **47 commits** by **8** contributors
🐛 **12 issues** closed
✅ **9 PRs** merged

**👥 Top Contributors**
1. **alice** — 14 commits
2. **bob** — 9 commits
3. **carol** — 7 commits
4. **dave** — 5 commits
5. **eve** — 4 commits

**🔀 Merged PRs**
- **#342** feat: OAuth2 provider integration (@alice)
- **#339** fix: race condition in payment confirmation (@bob)
- **#335** feat: rate-limiting middleware (@dave)
- **#330** docs: API reference v2 (@carol)
- **#328** chore: upgrade to Python 3.12 (@eve)

**📝 Narrative**
This week the team shipped the long-awaited OAuth2 integration (PR #342),
enabling third-party app authentication. Bob fixed a critical race condition
in the payment confirmation flow that had been causing intermittent failures
in production. The new rate-limiting middleware went live, capping API requests
at 100/min per IP, which should significantly reduce abuse.

On the documentation front, Carol delivered a comprehensive v2 API reference,
and Eve led the Python 3.12 upgrade across all services. The pace of
development remains steady with 47 commits from 8 contributors — a healthy
cadence heading into the next sprint.

Notable trend: infrastructure hardening is receiving increased attention,
with 3 of the 9 merged PRs focused on reliability and monitoring.
```

## Slack (Block Kit Format)

```json
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "📊 Weekly Dev Digest — 2026-07-25 → 2026-08-01"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "🔄 *47 commits* by *8* contributors\n🐛 *12 issues* closed\n✅ *9 PRs* merged"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*👥 Top Contributors*\n1. **alice** — 14 commits\n2. **bob** — 9 commits\n3. **carol** — 7 commits"
      }
    }
  ]
}
```

## Email (Plain Text)

```
Weekly Dev Digest — 2026-07-25 → 2026-08-01
==================================================

REPOSITORY: claude-builders-bounty/claude-builders-bounty
PERIOD: 2026-07-25 → 2026-08-01

STATISTICS:
  Commits: 47 by 8 contributors
  Issues closed: 12
  PRs merged: 9

TOP CONTRIBUTORS:
1. alice — 14 commits
2. bob — 9 commits

...

NARRATIVE:
This week the team shipped the long-awaited OAuth2 integration...
```

## French Output Example (SUMMARY_LANGUAGE=FR)

```
📊 Résumé Hebdomadaire — 2026-07-25 → 2026-08-01

🔄 47 commits par 8 contributeurs
🐛 12 issues fermées
✅ 9 PRs mergées

👥 Top Contributeurs
1. alice — 14 commits
2. bob — 9 commits

📝 Résumé
Cette semaine, l'équipe a livré l'intégration OAuth2 très attendue (PR #342),
permettant l'authentification d'applications tierces...
```
