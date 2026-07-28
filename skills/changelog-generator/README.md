# Changelog Generator

Claude Code skill + scripts (Bash & Python) that generate a structured
`CHANGELOG.md` from git history with full [Conventional Commits](https://www.conventionalcommits.org/) support.

## Usage (3 steps)

1. Copy `skills/changelog-generator/` to your repo
2. Make scripts executable: `chmod +x skills/changelog-generator/changelog.sh`
3. Run one of:
   ```bash
   # Bash (any system with git)
   ./skills/changelog-generator/changelog.sh

   # Python (cross-platform)
   python skills/changelog-generator/changelog.py

   # Claude Code
   /generate-changelog
   ```

## Features

- ✅ **Auto-detection** — Finds the latest git tag, falls back to first commit
- ✅ **Conventional Commits** — Full support for `feat:`, `fix:`, `chore:`, `docs:`, `perf:`, `security:`, `deps:`, and more
- ✅ **12 categories** — Features, Bug Fixes, Security, Performance, Dependencies, Refactoring, Docs, Style, Tests, Build/CI, Chores, Other
- ✅ **Custom output** — `--output` flag for custom paths
- ✅ **Custom range** — `--range` flag for specific revision ranges
- ✅ **Clean errors** — Validates the repo is a git repo, clear messages for edge cases
- ✅ **Dual implementation** — Bash (systems with git) + Python 3.8+ (cross-platform)

## Options

| Option | Bash | Python | Description |
|:-------|:----:|:------:|:------------|
| `--output FILE` | ✅ | ✅ | Custom output path (default: `CHANGELOG.md`) |
| `--range RANGE` | ✅ | ✅ | Git revision range (default: auto-detect) |
| `--help` / `-h` | ✅ | ✅ | Show usage help |

## Category Mapping

| Conventional Commit | Category |
|:--------------------|:---------|
| `feat:` | 🚀 Features |
| `fix:` | 🐛 Bug Fixes |
| `security:` | 🔒 Security |
| `perf:` | ⚡ Performance |
| `deps:`, `bump:` | 📦 Dependencies |
| `refactor:` | ♻️ Refactoring |
| `docs:` | 📝 Documentation |
| `style:` | 🎨 Style |
| `test:` | 🧪 Tests |
| `build:`, `ci:` | 🏗️ Build / CI |
| `chore:` | 🔧 Chores |

Commits without a Conventional Commit prefix are categorized by first-word heuristic
(`Add` → Features, `Fix` → Bug Fixes, etc.) or fall into 📌 Other Changes.

## Samples

| Sample | Description |
|:-------|:------------|
| [`samples/changelog_sample.md`](samples/changelog_sample.md) | Simple output from legacy commits |
| [`samples/changelog_cc_sample.md`](samples/changelog_cc_sample.md) | Output with full Conventional Commits |

## Requirements

- **Bash**: `git` installed, Bash 4.0+
- **Python**: `git` installed, Python 3.8+
- Works on Linux, macOS, Windows (Git Bash / WSL)
