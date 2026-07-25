---
name: changelog-generator
description: Generate a structured CHANGELOG.md from git history since the last tag.
version: 1.0
---

# Changelog Generator

Generate a structured `CHANGELOG.md` from git history. Auto-categorizes commits into Added/Fixed/Changed/Removed.

## Usage

### CLI
```bash
./skills/changelog-generator/changelog.sh [since_tag] [output_file]
```

### Claude Code
Load this skill then: `/generate-changelog`

## Auto-categorization
| Prefix match | Category |
|:-------------|:---------|
| `add`, `feat` | **Added** |
| `fix`, `bug`, `hotfix` | **Fixed** |
| `remove`, `drop`, `delete` | **Removed** |
| Everything else | **Changed** |

## Output Format
```markdown
# repo-name — Changelog

## [v1.0.0] — 2026-07-25

### Added
- feat: new feature description
### Fixed
- fix: bug description
### Changed
- refactor: code improvement
### Removed
- drop: deprecated API
```
