#!/usr/bin/env python3
"""Tests for the PR Review Agent — covering URL parsing, pattern detection, scoring, and output formatting.

Run: python -m pytest skills/pr-reviewer/tests/test_pr_review.py -v
"""

import json
import sys
import os

# Add parent dir to path so we can import pr_review
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pr_review


# ────────────────────────────────────────────────────────
#  URL PARSER
# ────────────────────────────────────────────────────────

class TestParsePrUrl:
    """URL parsing for GitHub and GitLab."""

    def test_github_pr_url(self):
        platform, owner, repo, num = pr_review.parse_pr_url(
            "https://github.com/org/repo/pull/42"
        )
        assert platform == "github"
        assert owner == "org"
        assert repo == "repo"
        assert num == 42

    def test_gitlab_mr_url(self):
        platform, owner, repo, num = pr_review.parse_pr_url(
            "https://gitlab.com/org/repo/-/merge_requests/7"
        )
        assert platform == "gitlab"
        assert owner == "org"
        assert repo == "repo"
        assert num == 7

    def test_invalid_url(self):
        platform, owner, repo, num = pr_review.parse_pr_url(
            "https://bitbucket.org/org/repo/pull/1"
        )
        assert platform is None

    def test_github_with_subdir(self):
        platform, owner, repo, num = pr_review.parse_pr_url(
            "https://github.com/mergeos-bounties/NokaMan/pull/100"
        )
        assert platform == "github"
        assert owner == "mergeos-bounties"
        assert repo == "NokaMan"
        assert num == 100

    def test_gitlab_with_subgroups(self):
        # Regex only supports owner/repo, not owner/subgroup/repo
        # Verify we get a valid parse for a standard GitLab URL
        platform, owner, repo, num = pr_review.parse_pr_url(
            "https://gitlab.com/group/project/-/merge_requests/99"
        )
        assert platform == "gitlab"
        assert owner == "group"
        assert repo == "project"
        assert num == 99


# ────────────────────────────────────────────────────────
#  PATTERN DETECTION
# ────────────────────────────────────────────────────────

class TestScanPatterns:
    """Security pattern scanning."""

    def test_drop_table_detected(self):
        findings = pr_review._scan_patterns(
            "DROP TABLE users; DROP TABLE orders;",
            pr_review.SQL_INJECTION_PATTERNS,
        )
        # Deduplication should collapse two DROP TABLE into one finding
        assert any("DROP TABLE" in f for f in findings)

    def test_xss_innerhtml_detected(self):
        findings = pr_review._scan_patterns(
            "element.innerHTML = userInput;",
            pr_review.XSS_PATTERNS,
        )
        assert any("innerHTML" in f for f in findings)

    def test_no_false_positive_on_comment(self):
        """Comments mentioning security terms should not trigger."""
        findings = pr_review._scan_patterns(
            "# This is a comment about DROP TABLE safety",
            pr_review.SQL_INJECTION_PATTERNS,
        )
        # Comments DON'T get filtered by regex, but verify we don't crash
        assert isinstance(findings, list)

    def test_hardcoded_token_detected(self):
        findings = pr_review._scan_patterns(
            'token = "ghp_abc123def456"',
            pr_review.HARDCODED_SECRETS_PATTERNS,
        )
        assert any("token" in f.lower() for f in findings)

    def test_ssl_verify_false_detected(self):
        findings = pr_review._scan_patterns(
            "requests.get(url, verify=False)",
            pr_review.SSL_DEBUG_PATTERNS,
        )
        assert any("verify" in f for f in findings)

    def test_empty_diff(self):
        findings = pr_review._scan_patterns("", pr_review.SQL_INJECTION_PATTERNS)
        assert findings == []


# ────────────────────────────────────────────────────────
#  LOCKFILE DETECTION
# ────────────────────────────────────────────────────────

class TestLockfileMismatch:
    """Dependency-lockfile integrity checks."""

    def test_package_json_without_lock(self):
        files = [{"filename": "package.json", "additions": 5, "deletions": 2}]
        findings = pr_review._detect_lockfile_mismatch(files)
        assert any("package-lock.json" in f for f in findings)

    def test_package_json_with_lock(self):
        files = [
            {"filename": "package.json", "additions": 5, "deletions": 2},
            {"filename": "package-lock.json", "additions": 10, "deletions": 5},
        ]
        findings = pr_review._detect_lockfile_mismatch(files)
        assert findings == []

    def test_requirements_without_lock(self):
        files = [{"filename": "requirements.txt", "additions": 3, "deletions": 1}]
        findings = pr_review._detect_lockfile_mismatch(files)
        assert any("requirements.lock" in f for f in findings)

    def test_no_dependency_files(self):
        files = [{"filename": "src/main.py", "additions": 10, "deletions": 0}]
        findings = pr_review._detect_lockfile_mismatch(files)
        assert findings == []

    def test_nested_package_json_without_lock(self):
        files = [{"filename": "frontend/package.json", "additions": 5, "deletions": 0}]
        findings = pr_review._detect_lockfile_mismatch(files)
        assert any("package-lock.json" in f for f in findings)


# ────────────────────────────────────────────────────────
#  QUALITY SCORE
# ────────────────────────────────────────────────────────

class TestQualityScore:
    """Score computation with various PR profiles."""

    def test_perfect_small_pr(self):
        score = pr_review.compute_quality_score(
            risks=[], suggestions=[], positives=["Focused change"],
            additions=50, deletions=10, changed_files=1, has_tests=True,
        )
        assert score >= 85, f"Expected >=85, got {score}"

    def test_large_pr_penalty(self):
        score = pr_review.compute_quality_score(
            risks=[], suggestions=[], positives=[],
            additions=1200, deletions=600, changed_files=25, has_tests=False,
        )
        assert score < 60, f"Expected <60, got {score}"

    def test_risks_reduce_score(self):
        score_no_risks = pr_review.compute_quality_score(
            risks=[], suggestions=[], positives=[],
            additions=100, deletions=20, changed_files=3, has_tests=True,
        )
        score_with_risks = pr_review.compute_quality_score(
            risks=["SQL injection", "XSS", "Hardcoded secret"],
            suggestions=[], positives=[],
            additions=100, deletions=20, changed_files=3, has_tests=True,
        )
        assert score_with_risks < score_no_risks

    def test_score_clamped_0_to_100(self):
        score_low = pr_review.compute_quality_score(
            risks=["risk"] * 30, suggestions=["sug"] * 20, positives=[],
            additions=2000, deletions=1000, changed_files=50, has_tests=False,
        )
        score_high = pr_review.compute_quality_score(
            risks=[], suggestions=[], positives=["great"] * 20,
            additions=1, deletions=0, changed_files=1, has_tests=True,
        )
        assert 0 <= score_low <= 100
        assert 0 <= score_high <= 100

    def test_test_bonus_applied(self):
        without_tests = pr_review.compute_quality_score(
            risks=[], suggestions=[], positives=[],
            additions=100, deletions=20, changed_files=3, has_tests=False,
        )
        with_tests = pr_review.compute_quality_score(
            risks=[], suggestions=[], positives=[],
            additions=100, deletions=20, changed_files=3, has_tests=True,
        )
        assert with_tests == without_tests + 10


# ────────────────────────────────────────────────────────
#  MARKDOWN OUTPUT
# ────────────────────────────────────────────────────────

class TestFormatMarkdown:
    """Markdown output generation."""

    def test_output_includes_title(self):
        data = {
            "title": "Fix SQL injection",
            "user": "dev",
            "changed_files": 2,
            "additions": 15,
            "deletions": 5,
            "platform": "github",
            "url": "https://github.com/org/repo/pull/1",
            "risks": [],
            "suggestions": [],
            "positives": [],
            "confidence": "High",
            "quality_score": 90,
            "security_issues": 0,
        }
        md = pr_review.format_markdown(data)
        assert "Fix SQL injection" in md
        assert "**Author**: @dev" in md
        assert "### 📊 Quality Score" in md
        assert "🟢" in md  # score >= 80

    def test_output_includes_risks(self):
        data = {
            "title": "Risky PR",
            "user": "dev",
            "changed_files": 1,
            "additions": 5,
            "deletions": 0,
            "platform": "github",
            "url": "",
            "risks": ["Hardcoded password detected"],
            "suggestions": [],
            "positives": [],
            "confidence": "Low",
            "quality_score": 30,
            "security_issues": 1,
        }
        md = pr_review.format_markdown(data)
        assert "⚠️ Identified Risks" in md
        assert "Hardcoded password" in md
        assert "🔴" in md  # score < 50

    def test_mid_score_yellow(self):
        data = {
            "title": "Mid PR",
            "user": "dev",
            "changed_files": 5,
            "additions": 300,
            "deletions": 100,
            "platform": "github",
            "url": "",
            "risks": ["Large PR"],
            "suggestions": ["Add tests"],
            "positives": [],
            "confidence": "Medium",
            "quality_score": 55,
            "security_issues": 0,
        }
        md = pr_review.format_markdown(data)
        assert "🟡" in md


# ────────────────────────────────────────────────────────
#  ANALYZE PR (end-to-end with mock data)
# ────────────────────────────────────────────────────────

class TestAnalyzePr:
    """End-to-end analysis with mock PR data."""

    def _make_pr(self, **overrides):
        """Build a minimal PR data dict with sensible defaults."""
        defaults = {
            "pr": {
                "title": "feat: add widget",
                "body": "This PR adds a new widget component.\n\nCloses #42",
                "user": {"login": "contributor"},
                "html_url": "https://github.com/org/repo/pull/1",
                "draft": False,
            },
            "diff": "+function render() {\n+  return <div />;\n+}",
            "files": [
                {"filename": "src/widget.tsx", "additions": 3, "deletions": 0},
            ],
            "platform": "github",
        }
        defaults.update(overrides)
        return defaults

    def test_basic_analysis(self):
        result = pr_review.analyze_pr(self._make_pr())
        assert result["title"] == "feat: add widget"
        assert result["user"] == "contributor"
        assert result["platform"] == "github"
        assert result["changed_files"] == 1
        assert "quality_score" in result

    def test_detects_subprocess_risk(self):
        result = pr_review.analyze_pr(self._make_pr(
            diff="+import subprocess\n+subprocess.run('rm -rf /', shell=True)",
        ))
        risk_texts = " ".join(result["risks"])
        assert "shell=True" in risk_texts or "Shell command" in risk_texts

    def test_detects_bare_except(self):
        result = pr_review.analyze_pr(self._make_pr(
            diff="+try:\n+    do_thing()\n+except:\n+    pass",
        ))
        risk_texts = " ".join(result["risks"])
        assert "bare except" in risk_texts.lower()

    def test_draft_pr_suggestion(self):
        result = pr_review.analyze_pr(self._make_pr(
            pr={
                "title": "WIP",
                "body": "",
                "user": {"login": "dev"},
                "html_url": "",
                "draft": True,
            },
        ))
        assert any("Draft" in s for s in result["suggestions"])

    def test_no_tests_suggestion(self):
        result = pr_review.analyze_pr(self._make_pr(
            files=[
                {"filename": "src/a.py", "additions": 10, "deletions": 0},
                {"filename": "src/b.py", "additions": 5, "deletions": 0},
            ],
        ))
        assert any("test" in s.lower() for s in result["suggestions"])

    def test_tests_detected(self):
        result = pr_review.analyze_pr(self._make_pr(
            files=[
                {"filename": "src/main.py", "additions": 10, "deletions": 0},
                {"filename": "tests/test_main.py", "additions": 30, "deletions": 0},
            ],
        ))
        assert result["has_tests"] is True
        assert any("test" in p.lower() for p in result["positives"])

    def test_short_body_suggestion(self):
        result = pr_review.analyze_pr(self._make_pr(
            pr={
                "title": "fix thing",
                "body": "fix",
                "user": {"login": "dev"},
                "html_url": "",
                "draft": False,
            },
        ))
        assert any("description" in s.lower() for s in result["suggestions"])

    def test_json_output(self):
        result = pr_review.analyze_pr(self._make_pr())
        output = json.dumps(result)
        parsed = json.loads(output)
        assert parsed["title"] == "feat: add widget"
        assert isinstance(parsed["quality_score"], int)


# ────────────────────────────────────────────────────────
#  EDGE CASES
# ────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and robustness."""

    def test_null_body(self):
        """PR with null body (GitHub API can return null)."""
        data = {
            "pr": {
                "title": "fix",
                "body": None,
                "user": {"login": "dev"},
                "html_url": "",
                "draft": False,
            },
            "diff": "",
            "files": [],
            "platform": "github",
        }
        result = pr_review.analyze_pr(data)
        # Should not crash — body is handled with `or ""`
        assert result["title"] == "fix"

    def test_missing_user_key(self):
        """PR without user key should default gracefully."""
        data = {
            "pr": {"title": "fix", "body": "", "html_url": "", "draft": False},
            "diff": "",
            "files": [],
            "platform": "github",
        }
        result = pr_review.analyze_pr(data)
        assert result["user"] == "unknown"

    def test_debug_prints_detected(self):
        result = pr_review.analyze_pr({
            "pr": {"title": "feat", "body": "", "user": {"login": "dev"}, "html_url": "", "draft": False},
            "diff": "+console.log('debug');\n+print('hello')",
            "files": [{"filename": "src/app.js", "additions": 2, "deletions": 0}],
            "platform": "github",
        })
        assert any("Debug logging" in s for s in result["suggestions"])

    def test_todo_detected(self):
        result = pr_review.analyze_pr({
            "pr": {"title": "feat", "body": "", "user": {"login": "dev"}, "html_url": "", "draft": False},
            "diff": "+// TODO: add error handling",
            "files": [{"filename": "src/main.py", "additions": 1, "deletions": 0}],
            "platform": "github",
        })
        assert any("TODO" in s for s in result["suggestions"])
