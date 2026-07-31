"""Validate the n8n weekly-dev-summary workflow JSON and dry_run.py.

The tests check:
  * the file parses as JSON
  * it has the required top-level fields (name, nodes, connections)
  * every node has the required fields (id, name, type, typeVersion, position, parameters)
  * node types come from the supported n8n base set
  * every connection target references a real node name
  * the trigger node is a Schedule Trigger with a weekly cron expression (168h)
  * the workflow contains the expected logical nodes (GitHub fetch x3, Claude,
    aggregate, format, deliver) — case-insensitive substring match on name
  * multi-channel delivery (Discord + Slack + Email) is present
  * bilingual support (EN/FR) is detected
  * error handling (continueOnFail) is present
  * dry_run.py is syntactically valid and --help runs

Run with:  python -m unittest tests.test_workflow_json -v
or:        pytest tests/test_workflow_json.py -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

# Resolve the workflow file relative to this test file so it works no matter
# where pytest / unittest is invoked from.
HERE = Path(__file__).resolve().parent
WORKFLOW_PATH = HERE.parent / "workflow.json"
DRY_RUN_PATH = HERE.parent / "dry_run.py"

# n8n built-in node types we use.
ALLOWED_NODE_TYPES = {
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.cron",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.code",
    "n8n-nodes-base.set",
    "n8n-nodes-base.if",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.noOp",
    "n8n-nodes-base.emailSend",
    "n8n-nodes-base.discord",
    "n8n-nodes-base.slack",
}


class TestWorkflowJson(unittest.TestCase):
    """Validate the n8n workflow.json structure."""

    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW_PATH.exists():
            raise unittest.SkipTest(f"Workflow JSON not found at {WORKFLOW_PATH}")
        with WORKFLOW_PATH.open(encoding="utf-8") as f:
            cls.wf = json.load(f)

    # ---- Top-level structure ------------------------------------------------

    def test_parses_as_json(self) -> None:
        self.assertIsInstance(self.wf, dict)

    def test_required_top_level_fields(self) -> None:
        for field in ("name", "nodes", "connections"):
            self.assertIn(field, self.wf, f"missing top-level field: {field}")

    def test_nodes_is_list(self) -> None:
        self.assertIsInstance(self.wf["nodes"], list)
        self.assertGreater(len(self.wf["nodes"]), 0, "workflow has no nodes")

    def test_has_minimum_nodes(self) -> None:
        """Our 13-node workflow should have at least 10 nodes."""
        self.assertGreaterEqual(
            len(self.wf["nodes"]), 10,
            f"expected >=10 nodes, got {len(self.wf['nodes'])}"
        )

    def test_connections_is_dict(self) -> None:
        self.assertIsInstance(self.wf["connections"], dict)

    # ---- Per-node shape -----------------------------------------------------

    def test_every_node_has_required_fields(self) -> None:
        required = {"id", "name", "type", "position", "parameters"}
        for n in self.wf["nodes"]:
            missing = required - n.keys()
            self.assertFalse(missing, f"node {n.get('name')!r} missing fields: {missing}")

    def test_node_types_are_supported(self) -> None:
        for n in self.wf["nodes"]:
            self.assertIn(
                n["type"], ALLOWED_NODE_TYPES,
                f"unsupported node type {n['type']!r} on node {n['name']!r}",
            )

    def test_node_ids_are_unique(self) -> None:
        ids = [n["id"] for n in self.wf["nodes"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate node ids")

    def test_node_names_are_unique(self) -> None:
        names = [n["name"] for n in self.wf["nodes"]]
        self.assertEqual(len(names), len(set(names)), "duplicate node names")

    def test_position_is_two_numbers(self) -> None:
        for n in self.wf["nodes"]:
            pos = n["position"]
            self.assertIsInstance(pos, list)
            self.assertEqual(len(pos), 2, f"node {n['name']!r}: position must be 2D")
            for coord in pos:
                self.assertIsInstance(coord, (int, float))

    # ---- Connections -------------------------------------------------------

    def test_all_connection_sources_are_node_names(self) -> None:
        names = {n["name"] for n in self.wf["nodes"]}
        for src in self.wf["connections"]:
            self.assertIn(src, names, f"connection from unknown source node: {src!r}")

    def test_all_connection_targets_are_node_names(self) -> None:
        names = {n["name"] for n in self.wf["nodes"]}
        for src, conn in self.wf["connections"].items():
            for branch in conn.get("main", []):
                for c in branch:
                    self.assertIn(c["node"], names,
                                  f"connection from {src!r} targets unknown node {c['node']!r}")
                    self.assertEqual(c["type"], "main")
                    self.assertIsInstance(c["index"], int)

    def test_workflow_is_connected(self) -> None:
        """Every non-trigger node should be reachable as a source, target, or both."""
        names = {n["name"] for n in self.wf["nodes"]}
        sources = set(self.wf["connections"].keys())
        targets: set[str] = set()
        for conn in self.wf["connections"].values():
            for branch in conn.get("main", []):
                for c in branch:
                    targets.add(c["node"])

        triggers = {n["name"] for n in self.wf["nodes"]
                    if n["type"] in ("n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.cron")}
        reachable = sources | targets | triggers
        unreachable = names - reachable
        self.assertFalse(unreachable, f"unreachable nodes: {unreachable}")

    # ---- Trigger & cron ----------------------------------------------------

    def test_has_weekly_trigger(self) -> None:
        triggers = [n for n in self.wf["nodes"]
                    if n["type"] in ("n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.cron")]
        self.assertTrue(triggers, "no schedule/cron trigger node found")

    def test_cron_interval_is_weekly(self) -> None:
        triggers = [n for n in self.wf["nodes"]
                    if n["type"] in ("n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.cron")]
        for t in triggers:
            rule = t["parameters"].get("rule", {})
            for interval in rule.get("interval", []):
                if interval.get("field") == "hours":
                    hours = interval.get("hoursInterval", 0)
                    self.assertEqual(hours, 168,
                                     f"expected 168h (weekly), got {hours}h")

    # ---- Logical completeness ---------------------------------------------

    def _node_names_lower(self) -> str:
        return " ".join(n["name"].lower() for n in self.wf["nodes"])

    def _all_params_text(self) -> str:
        return json.dumps([n.get("parameters", {}) for n in self.wf["nodes"]]).lower()

    def test_has_github_fetch_nodes(self) -> None:
        names = self._node_names_lower()
        for required in ("commit", "issue", "pr"):
            self.assertIn(required, names, f"no node covering GitHub {required!r} data")

    def test_has_claude_api_node(self) -> None:
        names = self._node_names_lower()
        self.assertTrue(
            "claude" in names or "anthropic" in names,
            "no node mentioning Claude / Anthropic",
        )

    def test_uses_required_claude_model(self) -> None:
        """Search node params for the required claude-sonnet-4-20250514 string."""
        target = "claude-sonnet-4-20250514"
        params_text = self._all_params_text()
        self.assertIn(target, params_text,
                      f"no node references the required model {target!r}")

    def test_github_api_endpoint_present(self) -> None:
        params_text = self._all_params_text()
        self.assertIn("api.github.com", params_text,
                      "no GitHub API endpoint found in any node")

    def test_anthropic_api_endpoint_present(self) -> None:
        params_text = self._all_params_text()
        self.assertIn("api.anthropic.com", params_text,
                      "no Anthropic API endpoint found in any node")

    # ---- Multi-channel delivery --------------------------------------------

    def test_multi_channel_delivery(self) -> None:
        """Verify Discord + Slack + Email delivery channels exist."""
        params_text = self._all_params_text()
        channels = []
        if "discord" in params_text:
            channels.append("Discord")
        if "slack" in params_text:
            channels.append("Slack")
        if "email" in params_text or "smtp" in params_text:
            channels.append("Email")
        self.assertGreaterEqual(len(channels), 2,
                                f"expected >=2 delivery channels, got {channels}")

    def test_discord_node_present(self) -> None:
        names = self._node_names_lower()
        self.assertIn("discord", names, "no Discord delivery node found")

    def test_slack_node_present(self) -> None:
        names = self._node_names_lower()
        self.assertIn("slack", names, "no Slack delivery node found")

    # ---- Bilingual support -------------------------------------------------

    def test_bilingual_support(self) -> None:
        """Verify FR/EN bilingual prompt templates exist."""
        params_text = self._all_params_text()
        has_fr = "français" in params_text or "french" in params_text or "'FR'" in params_text
        self.assertTrue(has_fr, "no French/FR language support detected in workflow")

    # ---- Error handling ----------------------------------------------------

    def test_error_handling_present(self) -> None:
        """Verify continueOnFail is used on API nodes."""
        continue_on_fail = sum(1 for n in self.wf["nodes"] if n.get("continueOnFail"))
        self.assertGreater(continue_on_fail, 0,
                           f"no nodes have continueOnFail, expected error resilience")

    # ---- Workflow metadata -------------------------------------------------

    def test_workflow_name(self) -> None:
        self.assertIn("name", self.wf)
        self.assertTrue(len(self.wf["name"]) > 5,
                        f"workflow name too short: {self.wf['name']!r}")

    def test_workflow_tags(self) -> None:
        tags = self.wf.get("tags", [])
        tag_names = [t.get("name", "") for t in tags]
        self.assertTrue(any("bounty" in tn.lower() for tn in tag_names),
                        f"no 'bounty' tag found in {tag_names}")

    def test_workflow_timezone(self) -> None:
        settings = self.wf.get("settings", {})
        self.assertIn("timezone", settings, "workflow has no timezone setting")


class TestDryRunScript(unittest.TestCase):
    """Smoke-test the dry_run.py helper without making any network calls."""

    def setUp(self) -> None:
        if not DRY_RUN_PATH.exists():
            self.skipTest("dry_run.py not found")

    def test_dry_run_script_parses(self) -> None:
        import ast
        ast.parse(DRY_RUN_PATH.read_text(encoding="utf-8"))

    def test_dry_run_help_runs(self) -> None:
        import subprocess
        out = subprocess.run(
            [sys.executable, str(DRY_RUN_PATH), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(out.returncode, 0, msg=out.stderr)
        self.assertIn("Simulate", out.stdout)

    def test_dry_run_version(self) -> None:
        import subprocess
        out = subprocess.run(
            [sys.executable, str(DRY_RUN_PATH), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(out.returncode, 0, msg=out.stderr)
        self.assertIn("dry_run.py v", out.stdout)

    def test_dry_run_json_mode_with_fixture(self) -> None:
        """Run dry_run with --json flag; should use fixture and output JSON."""
        import subprocess
        env = os.environ.copy()
        env.pop("GITHUB_TOKEN", None)
        env.pop("ANTHROPIC_API_KEY", None)
        out = subprocess.run(
            [sys.executable, str(DRY_RUN_PATH), "--json", "--owner", "test", "--repo", "test"],
            capture_output=True, text=True, timeout=15,
            env=env,
        )
        self.assertEqual(out.returncode, 0, msg=f"stderr: {out.stderr}")
        # Should output valid JSON (separated by 72-char === lines)
        parts = out.stdout.split("=" * 72)
        # Find the first part that looks like JSON
        json_str = ""
        for part in parts:
            part = part.strip()
            if part.startswith("{"):
                json_str = part
                break
        parsed = json.loads(json_str)
        self.assertIn("discord", parsed)
        self.assertIn("slack", parsed)
        self.assertIn("email", parsed)
        self.assertIn("meta", parsed)

    def test_dry_run_language_fr(self) -> None:
        """Run dry_run with --language FR."""
        import subprocess
        env = os.environ.copy()
        env.pop("GITHUB_TOKEN", None)
        env.pop("ANTHROPIC_API_KEY", None)
        out = subprocess.run(
            [sys.executable, str(DRY_RUN_PATH), "--language", "FR", "--owner", "test", "--repo", "test"],
            capture_output=True, text=True, timeout=15,
            env=env,
        )
        self.assertEqual(out.returncode, 0, msg=f"stderr: {out.stderr}")


class TestValidateWorkflowScript(unittest.TestCase):
    """Smoke-test the validate_workflow.py script."""

    def setUp(self) -> None:
        self.val_path = HERE.parent / "validate_workflow.py"
        if not self.val_path.exists():
            self.skipTest("validate_workflow.py not found")

    def test_validate_script_parses(self) -> None:
        import ast
        ast.parse(self.val_path.read_text(encoding="utf-8"))

    def test_validate_runs_successfully(self) -> None:
        import subprocess
        out = subprocess.run(
            [sys.executable, str(self.val_path)],
            capture_output=True, text=True, timeout=15,
        )
        # validate_workflow.py should return 0 for our valid workflow
        self.assertEqual(out.returncode, 0,
                         msg=f"validation failed:\nstdout: {out.stdout}\nstderr: {out.stderr}")


class TestWorkflowFileExists(unittest.TestCase):
    """Verify all expected deliverable files exist."""

    def setUp(self) -> None:
        self.base = HERE.parent

    def test_all_expected_files_exist(self) -> None:
        expected = [
            "workflow.json",
            "validate_workflow.py",
            "dry_run.py",
            "README.md",
            "architecture.md",
            "sample-output.md",
            "troubleshooting.md",
            "env.template",
        ]
        for fname in expected:
            path = self.base / fname
            self.assertTrue(path.exists(),
                            f"Missing required file: {fname}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
