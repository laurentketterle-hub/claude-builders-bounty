"""Tests for the n8n weekly dev summary workflow and validation."""
import json, sys, os
import unittest

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestWorkflowJSON(unittest.TestCase):
    """Validate the n8n workflow.json structure and content."""
    
    @classmethod
    def setUpClass(cls):
        workflow_path = os.path.join(os.path.dirname(__file__), "..", "workflow.json")
        with open(workflow_path) as f:
            cls.workflow = json.load(f)
    
    def test_workflow_has_name(self):
        self.assertIn("name", self.workflow)
        self.assertIsInstance(self.workflow["name"], str)
        self.assertGreater(len(self.workflow["name"]), 0)
    
    def test_workflow_has_nodes(self):
        self.assertIn("nodes", self.workflow)
        nodes = self.workflow["nodes"]
        self.assertIsInstance(nodes, list)
        self.assertGreater(len(nodes), 0)
    
    def test_has_cron_trigger(self):
        nodes = self.workflow.get("nodes", [])
        cron_nodes = [n for n in nodes if n.get("type") == "n8n-nodes-base.scheduleTrigger"]
        self.assertGreater(len(cron_nodes), 0, "Workflow must have a schedule trigger")
        # Verify weekly schedule
        cron = cron_nodes[0]
        self.assertIn("rule", cron.get("parameters", {}))
    
    def test_has_github_nodes(self):
        nodes = self.workflow.get("nodes", [])
        github_nodes = [n for n in nodes if "github" in n.get("type", "").lower()]
        self.assertGreater(len(github_nodes), 0, "Workflow must have GitHub API nodes")
    
    def test_has_http_request_nodes(self):
        nodes = self.workflow.get("nodes", [])
        http_nodes = [n for n in nodes if "httpRequest" in n.get("type", "")]
        self.assertGreater(len(http_nodes), 0, "Must have HTTP request nodes for GitHub API")
    
    def test_connections_exist(self):
        self.assertIn("connections", self.workflow)
        connections = self.workflow["connections"]
        self.assertGreater(len(connections), 0, "Workflow must have node connections")
    
    def test_no_hardcoded_tokens(self):
        """Ensure no API tokens are hardcoded in the workflow."""
        workflow_str = json.dumps(self.workflow)
        # Check for common token patterns
        suspicious = ["ghp_", "gho_", "github_pat_", "sk-ant-", "xoxb-"]
        for pattern in suspicious:
            self.assertNotIn(pattern, workflow_str.lower(), 
                           "Found potential hardcoded token: {}".format(pattern))
    
    def test_all_nodes_have_names(self):
        nodes = self.workflow.get("nodes", [])
        for node in nodes:
            self.assertIn("name", node, "All nodes must have a name")
            self.assertIsInstance(node["name"], str)

class TestDryRun(unittest.TestCase):
    """Test the dry_run.py script output."""
    
    @classmethod
    def setUpClass(cls):
        import importlib.util
        dry_run_path = os.path.join(os.path.dirname(__file__), "..", "dry_run.py")
        spec = importlib.util.spec_from_file_location("dry_run", dry_run_path)
        cls.dry_run = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.dry_run)
    
    def test_generate_summary(self):
        summary = self.dry_run.generate_dry_run_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn("period", summary)
        self.assertIn("total_commits", summary)
        self.assertIn("unique_authors", summary)
        self.assertGreater(summary["total_commits"], 0)
    
    def test_format_summary(self):
        summary = self.dry_run.generate_dry_run_summary()
        formatted = self.dry_run.format_summary(summary)
        self.assertIsInstance(formatted, str)
        self.assertGreater(len(formatted), 0)
        self.assertIn("Weekly Dev Summary", formatted)

class TestValidationScript(unittest.TestCase):
    """Test the validate_workflow.py script logic."""
    
    def test_json_loading(self):
        workflow_path = os.path.join(os.path.dirname(__file__), "..", "workflow.json")
        self.assertTrue(os.path.exists(workflow_path), "workflow.json must exist")
        with open(workflow_path) as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

if __name__ == "__main__":
    unittest.main(verbosity=2)
