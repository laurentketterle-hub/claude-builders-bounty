# Changelog Generator

Claude Code skill + bash script that generates a structured CHANGELOG.md from git history.

## Usage (3 steps)
1. Copy `skills/changelog-generator/changelog.sh` to your repo
2. Make executable: `chmod +x changelog.sh`
3. Run: `./changelog.sh` or `/generate-changelog` in Claude Code

## Features
- Auto-detects latest git tag
- Categorizes commits: Added / Fixed / Changed / Removed
- Category detection by conventional commit prefixes
- Works on any git repo
- Sample output in `samples/`

## Sample
See `samples/changelog_sample.md` for output generated from gimp-mcp.
