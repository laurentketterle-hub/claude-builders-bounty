# Claude Code Pre-Tool-Use Safety Hook

A [Claude Code](https://docs.anthropic.com/claude-code/hooks) `PreToolUse` hook that
intercepts dangerous shell commands **before** they execute — no `rm -rf` accidents,
no `DROP TABLE` catastrophes, no force-push regrets.

## What It Blocks

| Category | Examples |
|----------|----------|
| **Force delete** | `rm -rf /`, `rm --recursive --force` |
| **Filesystem destruction** | `mkfs.ext4`, `dd … of=/dev/sda` |
| **SQL destruction** | `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`, unconditional `DELETE` |
| **Git force operations** | `git push --force`, `git push --delete`, `git reset --hard` |
| **Fork bombs** | `:(){ :|:& };:`, perl fork |
| **Permission escalation** | `chmod 777 /etc`, `chown -R root /usr` |
| **System takeover** | `shutdown`, `reboot`, `iptables -F` |
| **Dangerous pipes** | `curl … \| sh`, `wget … \| bash` |
| **Docker destruction** | `docker rm -f`, `docker system prune -f` |
| **Environment sabotage** | `export PATH=/dev/null`, `unset HOME` |

## How It Works

1. **Intercepts** every `Bash` tool call via Claude Code's `PreToolUse` hook
2. **Inspects** the command against 35+ destructive regex patterns
3. **Blocks** dangerous commands and shows Claude **why** they were denied
4. **Logs** every blocked attempt to `~/.claude/hooks/blocked.log` with:
   - UTC timestamp
   - Matched pattern / reason
   - The full attempted command
   - Project working directory
5. **Passes through** safe commands instantly (sub-millisecond overhead)
6. **Fails open** — parse errors or unexpected exceptions allow the command

## Install

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

60+ unit tests covering every blocked pattern, edge cases (sudo, docker,
quoted paths, case-insensitive, non-bash tools, empty input), and
safe-command passthrough.

## Log Format

Blocked attempts appear as one-line-per-attempt in `~/.claude/hooks/blocked.log`:

```
[2026-07-31T12:00:00+00:00] BLOCKED
  Reason:   rm -rf blocked
  Command:  rm -rf /important/data
  Project:  /home/user/my-project
  User:     myuser
────────────────────────────────────────────────────────────
```

## Architecture

```
.claude/
├── hooks/
│   └── run-hook.py       # Wrapper called by Claude Code
├── settings.json          # Hook configuration
hooks/
├── pre-tool-use.py        # Main hook logic (35+ patterns)
└── README.md              # This file
tests/
└── test_hook.py           # 60+ unit tests
```

## Security Considerations

- **Fail-open design**: If the hook crashes or can't parse input, the command is allowed through
- **No network calls**: All checks are local regex matches
- **Zero dependencies**: Uses Python stdlib only
- **Immutable log**: Blocked attempts append-only, never deleted by the hook

## License

MIT — see repository root LICENSE file.
