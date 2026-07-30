# 🛡️ Pre-Tool-Use Hook — Block Destructive Bash Commands

A [Claude Code](https://docs.anthropic.com/claude-code/hooks) `PreToolUse` hook that
intercepts dangerous shell commands **before** they execute — no `rm -rf` accidents,
no `DROP TABLE` catastrophes, no force-push regrets.

## What it blocks

| Pattern | Examples blocked |
|---|---|
| **Recursive force delete** | `rm -rf /`, `rm --recursive --force`, `rm -r /` |
| **Filesystem destruction** | `mkfs.ext4`, `dd … of=/dev/sda` |
| **SQL table destruction** | `DROP TABLE`, `DROP DATABASE`, `TRUNCATE` |
| **Unconditional DELETE** | `DELETE FROM users;` (without `WHERE`) |
| **Git force push** | `git push --force`, `git push -f`, `git push --force-with-lease` |
| **Fork bomb** | `:(){ :\|:& };:` |
| **Permission escalation** | `chmod 777 /`, `chown -R root /` |

## How it works

1. **Intercepts** every `Bash` tool call via Claude Code's `PreToolUse` hook
2. **Inspects** the command against 20+ destructive regex patterns
3. **Blocks** dangerous commands and shows Claude **why** they were denied
4. **Logs** every blocked attempt to `~/.claude/hooks/blocked.log` with:
   - UTC timestamp
   - Matched pattern / reason
   - The full attempted command
   - Project working directory
5. **Passes through** safe commands instantly (sub-millisecond overhead)

## Install (1 command)

```bash
cp -r .claude /path/to/your/project/
```

That's it — Claude Code automatically reads `.claude/settings.json` on next invocation.

## Requirements

- **Python 3.10+** (stdlib only — no pip installs needed)
- Claude Code (any recent version)

## Test

```bash
pip install pytest
python -m pytest tests/test_hook.py -v
```

42+ unit tests covering every blocked pattern, edge cases (sudo, docker,
quoted paths, case-insensitive), and safe-command passthrough.

## Log format

Blocked attempts appear as one JSON object per line in `~/.claude/hooks/blocked.log`:

```json
{"timestamp":"2026-07-30T19:30:00+00:00","reason":"rm -rf blocked","command":"rm -rf /data","cwd":"/home/user/project"}
```

## Project structure

```
.claude/
├── settings.json          ← Claude Code hook config
└── hooks/
    └── run-hook.py        ← Entry point called by Claude Code
hooks/
└── pre-tool-use.py        ← Core hook logic (patterns, logging, decision)
tests/
└── test_hook.py           ← 42+ unit tests
```

## License

MIT — same as the parent repository.
