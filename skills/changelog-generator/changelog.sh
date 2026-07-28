#!/bin/bash
# =============================================================================
# changelog.sh — Generate a structured CHANGELOG.md from git history
# =============================================================================
# Usage:
#   ./changelog.sh                          # Auto-detect last tag, output CHANGELOG.md
#   ./changelog.sh --output RELEASE.md      # Custom output path
#   ./changelog.sh --range v1.0.0..HEAD     # Custom commit range
#   ./changelog.sh --range v1.0.0..v2.0.0   # Range between two tags
#   ./changelog.sh --output docs/CHANGELOG.md --range v1.0.0..
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ── Help ────────────────────────────────────────────────────────────────────
show_help() {
    cat << 'EOF'
Usage: changelog.sh [OPTIONS]

Generate a structured CHANGELOG.md from git history.

Options:
  --output FILE     Write output to FILE (default: CHANGELOG.md)
  --range RANGE     Git revision range (e.g., "v1.0.0..HEAD", "abc123..def456")
                    Default: auto-detect latest tag to HEAD
  --help, -h        Show this help message

Examples:
  ./changelog.sh
  ./changelog.sh --output RELEASE_NOTES.md
  ./changelog.sh --range v1.0.0..v2.0.0
  ./changelog.sh --output docs/CHANGELOG.md --range v1.0.0..
EOF
    exit 0
}

# ── Defaults ─────────────────────────────────────────────────────────────────
OUTPUT="CHANGELOG.md"
RANGE=""

# ── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --range)
            RANGE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo "Error: Unknown option '$1'. Use --help for usage." >&2
            exit 1
            ;;
    esac
done

# ── Validate git repository ──────────────────────────────────────────────────
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "Error: Not a git repository. Run this script from within a git repo." >&2
    exit 1
fi

# ── Determine commit range ───────────────────────────────────────────────────
REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || echo "unknown")

if [[ -z "$RANGE" ]]; then
    # Auto-detect: from latest tag to HEAD
    LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    if [[ -n "$LATEST_TAG" ]]; then
        RANGE="${LATEST_TAG}..HEAD"
    else
        # No tags: use the first commit to HEAD
        FIRST_COMMIT=$(git rev-list --max-parents=0 HEAD 2>/dev/null || echo "")
        if [[ -n "$FIRST_COMMIT" ]]; then
            RANGE="${FIRST_COMMIT}..HEAD"
        else
            echo "Error: No commits found in this repository." >&2
            exit 1
        fi
    fi
fi

# ── Collect commits ──────────────────────────────────────────────────────────
COMMITS=$(git log "$RANGE" --pretty=format:"%s" 2>/dev/null || true)

if [[ -z "$COMMITS" ]]; then
    echo "Error: No commits found in range '$RANGE'. Check your range and try again." >&2
    exit 1
fi

# ── Conventional Commits categories ──────────────────────────────────────────
declare -a FEAT=()       # feat:
declare -a FIX=()        # fix:
declare -a CHORE=()      # chore:
declare -a DOCS=()       # docs:
declare -a STYLE=()      # style:
declare -a REFACTOR=()   # refactor:
declare -a PERF=()       # perf:
declare -a TEST=()       # test:
declare -a BUILD=()      # build:, ci:
declare -a SECURITY=()   # security:
declare -a DEPS=()       # deps:, build(deps):
declare -a OTHER=()      # anything else

categorize_commit() {
    local raw="$1"
    local line
    line=$(echo "$raw" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [[ -z "$line" ]] && return

    # Conventional Commits: type(scope): description
    if echo "$line" | grep -qiE '^feat(\([^)]*\))?:'; then
        FEAT+=("$line")
    elif echo "$line" | grep -qiE '^fix(\([^)]*\))?:'; then
        FIX+=("$line")
    elif echo "$line" | grep -qiE '^(deps|bump)(\([^)]*\))?:'; then
        DEPS+=("$line")
    elif echo "$line" | grep -qiE '^build\(deps\):'; then
        DEPS+=("$line")
    elif echo "$line" | grep -qiE '^security(\([^)]*\))?:'; then
        SECURITY+=("$line")
    elif echo "$line" | grep -qiE '^perf(\([^)]*\))?:'; then
        PERF+=("$line")
    elif echo "$line" | grep -qiE '^chore(\([^)]*\))?:'; then
        CHORE+=("$line")
    elif echo "$line" | grep -qiE '^docs(\([^)]*\))?:'; then
        DOCS+=("$line")
    elif echo "$line" | grep -qiE '^style(\([^)]*\))?:'; then
        STYLE+=("$line")
    elif echo "$line" | grep -qiE '^refactor(\([^)]*\))?:'; then
        REFACTOR+=("$line")
    elif echo "$line" | grep -qiE '^test(\([^)]*\))?:'; then
        TEST+=("$line")
    elif echo "$line" | grep -qiE '^(build|ci)(\([^)]*\))?:'; then
        BUILD+=("$line")
    else
        # Fallback: legacy prefix matching
        if echo "$line" | grep -qiE '^(add|feat|new|Add|Feat|New)'; then
            FEAT+=("$line")
        elif echo "$line" | grep -qiE '^(fix|bug|hotfix|patch|Fix|Bug|Hotfix|Patch)'; then
            FIX+=("$line")
        elif echo "$line" | grep -qiE '^(remove|drop|delete|Remove|Drop|Delete)'; then
            OTHER+=("$line")
        else
            OTHER+=("$line")
        fi
    fi
}

while IFS= read -r commit_line; do
    categorize_commit "$commit_line"
done <<< "$COMMITS"

# ── Determine version ────────────────────────────────────────────────────────
DATE=$(date +%Y-%m-%d)
VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "Unreleased")

# If we have a range with two tags, use the second one
if [[ "$RANGE" == *..* ]]; then
    END_REF="${RANGE##*..}"
    END_TAG=$(git describe --tags --abbrev=0 "$END_REF" 2>/dev/null || echo "")
    if [[ -n "$END_TAG" ]] && [[ "$END_TAG" != "$VERSION" ]]; then
        VERSION="$END_TAG"
    fi
fi

# ── Write CHANGELOG ──────────────────────────────────────────────────────────
{
    echo "# $REPO — Changelog"
    echo ""
    echo "## [$VERSION] — $DATE"
    echo ""

    section() {
        local title="$1"
        local -n items=$2
        [[ ${#items[@]} -eq 0 ]] && return
        echo "### $title"
        echo ""
        for item in "${items[@]}"; do
            echo "- $item"
        done
        echo ""
    }

    section "🚀 Features"        FEAT
    section "🐛 Bug Fixes"       FIX
    section "🔒 Security"        SECURITY
    section "⚡ Performance"     PERF
    section "📦 Dependencies"    DEPS
    section "♻️ Refactoring"     REFACTOR
    section "📝 Documentation"   DOCS
    section "🎨 Style"           STYLE
    section "🧪 Tests"           TEST
    section "🏗️ Build / CI"      BUILD
    section "🔧 Chores"          CHORE
    section "📌 Other Changes"   OTHER

    echo "---"
    echo "*Generated by [changelog-generator](https://github.com/laurentketterle-hub/claude-builders-bounty/tree/main/skills/changelog-generator)*"
} > "$OUTPUT"

# ── Summary ──────────────────────────────────────────────────────────────────
TOTAL_COMMITS=$(echo "$COMMITS" | wc -l)
echo "✅ CHANGELOG written to $OUTPUT"
echo "   Range: $RANGE"
echo "   Commits: $TOTAL_COMMITS"
echo "   Categories: Features=${#FEAT[@]} BugFixes=${#FIX[@]} Security=${#SECURITY[@]} Performance=${#PERF[@]} Deps=${#DEPS[@]} Refactoring=${#REFACTOR[@]} Docs=${#DOCS[@]} Style=${#STYLE[@]} Tests=${#TEST[@]} Build=${#BUILD[@]} Chores=${#CHORE[@]} Other=${#OTHER[@]}"
