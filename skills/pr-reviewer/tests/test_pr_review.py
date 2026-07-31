#!/usr/bin/env python3
"""Unit tests for PR Review Agent — test security patterns, URL parsing, scoring."""

import json
import os
import sys
import tempfile
import unittest

# Add parent directory to path to import pr_review
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pr_review import (
    SQL_INJECTION_PATTERNS,
    XSS_PATTERNS,
    RACE_CONDITION_PATTERNS,
    HARDCODED_SECRETS_PATTERNS,
    HARDCODED_IP_PATTERNS,
    SSL_DEBUG_PATTERNS,
    LOCKFILE_PATTERNS,
    _scan_patterns,
    _detect_lockfile_mismatch,
    compute_quality_score,
    parse_pr_url,
    analyze_pr,
    format_markdown,
)


class TestURLParsing(unittest.TestCase):
    """Test GitHub and GitLab URL parsing."""

    def test_github_url(self):
        platform, owner, repo, pr_num = parse_pr_url(
            "https://github.com/owner/repo/pull/123"
        )
        self.assertEqual(platform, "github")
        self.assertEqual(owner, "owner")
        self.assertEqual(repo, "repo")
        self.assertEqual(pr_num, 123)

    def test_gitlab_url(self):
        platform, owner, repo, pr_num = parse_pr_url(
            "https://gitlab.com/group/project/-/merge_requests/456"
        )
        self.assertEqual(platform, "gitlab")
        self.assertEqual(owner, "group")
        self.assertEqual(repo, "project")
        self.assertEqual(pr_num, 456)

    def test_invalid_url(self):
        platform, owner, repo, pr_num = parse_pr_url("https://not-valid.com/x/y")
        self.assertIsNone(platform)

    def test_github_url_with_query_params(self):
        """URLs with query strings should still parse."""
        platform, owner, repo, pr_num = parse_pr_url(
            "https://github.com/owner/repo/pull/789?tab=files"
        )
        self.assertEqual(pr_num, 789)

    def test_github_org_repo_with_dots(self):
        """Repos/orgs with dots in name are valid."""
        platform, owner, repo, pr_num = parse_pr_url(
            "https://github.com/org.name/repo.name/pull/42"
        )
        self.assertEqual(owner, "org.name")
        self.assertEqual(repo, "repo.name")


class TestSecurityPatterns(unittest.TestCase):
    """Test security pattern detection."""

    def test_sql_injection_detected(self):
        diff = "cursor.execute('DELETE FROM users')\n"
        findings = _scan_patterns(diff, SQL_INJECTION_PATTERNS)
        self.assertTrue(
            any("DELETE" in f for f in findings),
            f"Should detect DELETE without WHERE: {findings}",
        )

    def test_xss_innerhtml_detected(self):
        diff = "element.innerHTML = userInput;\n"
        findings = _scan_patterns(diff, XSS_PATTERNS)
        self.assertTrue(
            any("innerHTML" in f for f in findings),
            f"Should detect innerHTML: {findings}",
        )

    def test_hardcoded_secret_detected(self):
        diff = 'API_KEY = "sk-1234567890abcdef"\n'
        findings = _scan_patterns(diff, HARDCODED_SECRETS_PATTERNS)
        self.assertTrue(
            any("API key" in f for f in findings),
            f"Should detect hardcoded API key: {findings}",
        )

    def test_hardcoded_ip_detected(self):
        diff = "HOST = '192.168.1.100'\n"
        findings = _scan_patterns(diff, HARDCODED_IP_PATTERNS)
        self.assertTrue(
            any("IP" in f for f in findings),
            f"Should detect hardcoded IP: {findings}",
        )

    def test_ssl_verify_false_detected(self):
        diff = "requests.get(url, verify=False)\n"
        findings = _scan_patterns(diff, SSL_DEBUG_PATTERNS)
        self.assertTrue(
            any("SSL" in f for f in findings),
            f"Should detect verify=False: {findings}",
        )

    def test_race_condition_thread_no_lock(self):
        diff = "threading.Thread(target=worker).start()\n"
        findings = _scan_patterns(diff, RACE_CONDITION_PATTERNS)
        self.assertTrue(
            any("Thread" in f or "race" in f for f in findings),
            f"Should detect thread without lock: {findings}",
        )

    def test_no_false_positive_clean_code(self):
        """Clean code without security issues should produce no findings."""
        clean_diff = """
def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
"""
        all_patterns = (
            SQL_INJECTION_PATTERNS
            + XSS_PATTERNS
            + HARDCODED_SECRETS_PATTERNS
            + HARDCODED_IP_PATTERNS
            + SSL_DEBUG_PATTERNS
            + RACE_CONDITION_PATTERNS
        )
        findings = _scan_patterns(clean_diff, all_patterns)
        self.assertEqual(
            len(findings), 0, f"Clean code should not trigger any security patterns: {findings}"
        )

    def test_deduplication_same_pattern(self):
        """Multiple occurrences of the same pattern should be deduplicated."""
        diff = "element.innerHTML = a;\nelement.innerHTML = b;\nelement.innerHTML = c;\n"
        findings = _scan_patterns(diff, XSS_PATTERNS)
        # Should only report each message once
        self.assertEqual(
            len(findings), 1,
            f"Duplicate patterns should be deduplicated, got {len(findings)}: {findings}"
        )


class TestLockfileDetection(unittest.TestCase):
    """Test lockfile mismatch detection."""

    def test_package_json_without_lock(self):
        files = [{"filename": "package.json", "additions": 5, "deletions": 2}]
        findings = _detect_lockfile_mismatch(files)
        self.assertTrue(
            any("package-lock.json" in f for f in findings),
            f"Should detect missing lockfile: {findings}",
        )

    def test_package_json_with_lock(self):
        files = [
            {"filename": "package.json", "additions": 5, "deletions": 2},
            {"filename": "package-lock.json", "additions": 100, "deletions": 80},
        ]
        findings = _detect_lockfile_mismatch(files)
        self.assertEqual(
            len(findings), 0,
            f"Should not report when lockfile present: {findings}"
        )

    def test_requirements_txt_without_lock(self):
        files = [{"filename": "requirements.txt", "additions": 3, "deletions": 1}]
        findings = _detect_lockfile_mismatch(files)
        self.assertTrue(
            any("requirements.lock" in f for f in findings),
            f"Should detect missing requirements.lock: {findings}",
        )

    def test_no_dependency_files(self):
        files = [{"filename": "src/main.py", "additions": 10, "deletions": 2}]
        findings = _detect_lockfile_mismatch(files)
        self.assertEqual(
            len(findings), 0,
            f"Non-dependency file should produce no lockfile findings: {findings}"
        )


class TestQualityScore(unittest.TestCase):
    """Test quality score computation."""

    def test_perfect_score(self):
        score = compute_quality_score(
            risks=[],
            suggestions=[],
            positives=["Small, focused change"],
            additions=50,
            deletions=5,
            changed_files=2,
            has_tests=True,
        )
        self.assertGreaterEqual(score, 90, f"Clean small PR with tests should score >=90, got {score}")

    def test_risky_large_pr(self):
        score = compute_quality_score(
            risks=["SQL injection", "XSS", "Hardcoded secret", "No lockfile"],
            suggestions=["Add tests", "Split PR"],
            positives=[],
            additions=1200,
            deletions=600,
            changed_files=25,
            has_tests=False,
        )
        self.assertLess(score, 50, f"Very risky large PR should score <50, got {score}")

    def test_score_bounded_0_to_100(self):
        """Score should always be clamped to [0, 100]."""
        # Test upper bound
        score_high = compute_quality_score([], [], ["Good" for _ in range(20)], 10, 0, 1, True)
        self.assertLessEqual(score_high, 100)

        # Test lower bound
        score_low = compute_quality_score(
            ["Risk" for _ in range(30)], ["Suggestion" for _ in range(20)], [], 2000, 1000, 50, False
        )
        self.assertGreaterEqual(score_low, 0)

    def test_test_bonus(self):
        score_with = compute_quality_score([], [], [], 100, 10, 5, has_tests=True)
        score_without = compute_quality_score([], [], [], 100, 10, 5, has_tests=False)
        self.assertEqual(
            score_with - score_without, 10,
            f"Test bonus should be exactly 10, got {score_with - score_without}"
        )


class TestMarkdownOutput(unittest.TestCase):
    """Test Markdown formatting."""

    def test_basic_output(self):
        data = {
            "title": "Test PR",
            "user": "testuser",
            "changed_files": 3,
            "additions": 50,
            "deletions": 10,
            "platform": "github",
            "url": "https://github.com/test/repo/pull/1",
            "risks": ["Security risk"],
            "suggestions": ["Add tests"],
            "positives": ["Clean code"],
            "confidence": "High",
            "quality_score": 85,
            "has_tests": True,
            "security_issues": 1,
        }
        output = format_markdown(data)
        self.assertIn("Test PR", output)
        self.assertIn("@testuser", output)
        self.assertIn("85/100", output)
        self.assertIn("Security risk", output)

    def test_no_risks_no_suggestions(self):
        """Output should still be valid with no risks/suggestions."""
        data = {
            "title": "Clean PR",
            "user": "dev",
            "changed_files": 1,
            "additions": 10,
            "deletions": 0,
            "platform": "github",
            "url": "https://github.com/x/y/pull/1",
            "risks": [],
            "suggestions": [],
            "positives": [],
            "confidence": "High — clean, focused change",
            "quality_score": 95,
            "has_tests": False,
            "security_issues": 0,
        }
        output = format_markdown(data)
        self.assertIn("## 🔍 PR Review: Clean PR", output)
        self.assertNotIn("### ⚠️", output)
        self.assertNotIn("### 💡", output)


class TestAnalyzePR(unittest.TestCase):
    """Integration-style tests for analyze_pr."""

    def test_small_clean_pr(self):
        pr_data = {
            "pr": {
                "title": "fix: typo in README",
                "body": "Fixes a small typo in the installation section.\n\nCloses #42",
                "user": {"login": "dev"},
                "html_url": "https://github.com/x/y/pull/1",
                "draft": False,
            },
            "diff": "-Old text\n+Corrected text",
            "files": [{"filename": "README.md", "additions": 1, "deletions": 1}],
            "platform": "github",
        }
        result = analyze_pr(pr_data)
        self.assertEqual(result["title"], "fix: typo in README")
        self.assertEqual(result["changed_files"], 1)
        self.assertIn("Small, focused change", result["positives"])
        self.assertIn("Clear bug-fix intent in title", result["positives"])

    def test_pr_with_security_issues(self):
        pr_data = {
            "pr": {
                "title": "Add user endpoint",
                "body": "New endpoint to fetch user data.",
                "user": {"login": "dev2"},
                "html_url": "https://github.com/x/y/pull/2",
                "draft": False,
            },
            "diff": """
cursor.execute("SELECT * FROM users WHERE id = " + user_id)
element.innerHTML = response.data;
API_KEY = "sk-proj-deadbeef12345678"
            """,
            "files": [
                {"filename": "src/api.py", "additions": 30, "deletions": 0},
            ],
            "platform": "github",
        }
        result = analyze_pr(pr_data)
        self.assertGreater(len(result["risks"]), 0, "Should detect security risks")
        self.assertGreater(result["security_issues"], 0, "Should count security issues")

    def test_pr_with_short_description(self):
        pr_data = {
            "pr": {
                "title": "WIP",
                "body": "fix",
                "user": {"login": "dev3"},
                "html_url": "https://github.com/x/y/pull/3",
                "draft": False,
            },
            "diff": "+print('debug')\n",
            "files": [{"filename": "main.py", "additions": 1, "deletions": 0}],
            "platform": "github",
        }
        result = analyze_pr(pr_data)
        suggestion_texts = " ".join(result["suggestions"])
        self.assertIn("description is brief", suggestion_texts)


class TestEdgeCases(unittest.TestCase):
    """Edge case and boundary tests."""

    def test_empty_diff(self):
        findings = _scan_patterns("", SQL_INJECTION_PATTERNS)
        self.assertEqual(len(findings), 0, "Empty diff should produce no findings")

    def test_empty_files_list(self):
        findings = _detect_lockfile_mismatch([])
        self.assertEqual(len(findings), 0, "Empty files list should produce no findings")

    def test_none_body(self):
        """PR with None body should not crash."""
        pr_data = {
            "pr": {
                "title": "Update deps",
                "body": None,
                "user": {"login": "bot"},
                "html_url": "https://github.com/x/y/pull/5",
                "draft": False,
            },
            "diff": "+requests==2.31.0",
            "files": [{"filename": "requirements.txt", "additions": 1, "deletions": 1}],
            "platform": "github",
        }
        result = analyze_pr(pr_data)
        self.assertEqual(result["user"], "bot")

    def test_unicode_in_diff(self):
        """Non-ASCII characters in diff should not break."""
        pr_data = {
            "pr": {
                "title": "Add emoji support",
                "body": "ついに日本語対応 🎉",
                "user": {"login": "dev"},
                "html_url": "https://github.com/x/y/pull/6",
                "draft": False,
            },
            "diff": "+print('こんにちは')",
            "files": [{"filename": "main.py", "additions": 1, "deletions": 0}],
            "platform": "github",
        }
        result = analyze_pr(pr_data)
        output = format_markdown(result)
        self.assertIn("Add emoji support", output)

    def test_gitlab_platform_flag(self):
        pr_data = {
            "pr": {
                "title": "GitLab MR",
                "body": "Merge request from GitLab",
                "user": {"login": "gitlabber"},
                "html_url": "https://gitlab.com/x/y/-/merge_requests/10",
                "draft": False,
            },
            "diff": "+new feature",
            "files": [{"filename": "feature.py", "additions": 20, "deletions": 0}],
            "platform": "gitlab",
        }
        result = analyze_pr(pr_data)
        self.assertEqual(result["platform"], "gitlab")


if __name__ == "__main__":
    unittest.main()
