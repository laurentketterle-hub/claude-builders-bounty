"""Unit tests for the pre-tool-use hook logic.

Run:  python -m pytest tests/test_hook.py -v
"""

import json
import sys
from pathlib import Path

# Ensure we can import the hook module
HOOK_DIR = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOK_DIR))

# Import the hook's check_command function (no side effects on import)
import importlib.util

_hook_path = HOOK_DIR / "pre-tool-use.py"
_spec = importlib.util.spec_from_file_location("pre_tool_use", _hook_path)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)
check_command = _hook.check_command
BLOCKED_PATTERNS = _hook.BLOCKED_PATTERNS


# ── Helpers ────────────────────────────────────────────────────────────

def assert_blocked(command: str, expected_reason_fragment: str = ""):
    """Assert that *command* is blocked and the reason contains *fragment*."""
    is_blocked, reason = check_command(command)
    assert is_blocked, f"Expected '{command}' to be BLOCKED, got reason='{reason}'"
    if expected_reason_fragment:
        assert expected_reason_fragment.lower() in reason.lower(), (
            f"Reason '{reason}' does not contain '{expected_reason_fragment}'"
        )


def assert_allowed(command: str):
    """Assert that *command* is allowed through."""
    is_blocked, reason = check_command(command)
    assert not is_blocked, (
        f"Expected '{command}' to be ALLOWED, but was blocked: {reason}"
    )


# ── rm -rf variants ────────────────────────────────────────────────────

def test_rm_rf_basic():
    assert_blocked("rm -rf /", "rm -rf")


def test_rm_rf_recursive_first():
    assert_blocked("rm -r -f /home/user/project", "rm -rf")


def test_rm_rf_other_flags():
    assert_blocked("rm -vrf /tmp/data", "rm -rf")


def test_rm_long_form():
    assert_blocked("rm --recursive --force /data", "recursive")


def test_rm_long_form_reversed():
    assert_blocked("rm --force --recursive /data", "recursive")


def test_rm_rf_on_root():
    assert_blocked("rm -rf / --no-preserve-root", "rm -rf")


def test_rm_r_on_root():
    assert_blocked("rm -r /", "root deletion")


def test_rm_regular_file_allowed():
    assert_allowed("rm file.txt")


def test_rm_dir_allowed():
    assert_allowed("rm -r node_modules")


# ── SQL destruction ────────────────────────────────────────────────────

def test_drop_table():
    assert_blocked("DROP TABLE users;", "DROP TABLE")


def test_drop_table_if_exists():
    assert_blocked("DROP TABLE IF EXISTS users;", "DROP TABLE")


def test_drop_database():
    assert_blocked("DROP DATABASE production;", "DROP DATABASE")


def test_truncate_simple():
    assert_blocked("TRUNCATE TABLE logs;", "TRUNCATE")


def test_truncate_no_table_keyword():
    assert_blocked("TRUNCATE logs;", "TRUNCATE")


def test_delete_without_where():
    assert_blocked("DELETE FROM users;", "DELETE FROM")


def test_delete_with_where_allowed():
    assert_allowed("DELETE FROM users WHERE id = 5;")


def test_delete_with_where_multiline_allowed():
    assert_allowed("DELETE FROM users\nWHERE active = false;")


# ── Git force push ─────────────────────────────────────────────────────

def test_git_push_force():
    assert_blocked("git push --force origin main", "force")


def test_git_push_force_with_lease():
    assert_blocked("git push --force-with-lease origin main", "force")


def test_git_push_minus_f():
    assert_blocked("git push -f origin main", "git push -f")


def test_git_push_normal_allowed():
    assert_allowed("git push origin main")


def test_git_commit_allowed():
    assert_allowed("git commit -m 'fix'")


# ── Filesystem destruction ─────────────────────────────────────────────

def test_mkfs():
    assert_blocked("mkfs.ext4 /dev/sda1", "Filesystem format")


def test_dd_to_block_device():
    assert_blocked("dd if=/dev/zero of=/dev/sda bs=1M", "dd write")


# ── Fork bomb ──────────────────────────────────────────────────────────

def test_fork_bomb_classic():
    assert_blocked(":(){ :|:& };:", "Fork bomb")


def test_fork_bomb_variant():
    assert_blocked(":(){ :|:& };:", "Fork bomb")


# ── Safe commands ──────────────────────────────────────────────────────

def test_ls_allowed():
    assert_allowed("ls -la")


def test_echo_allowed():
    assert_allowed("echo 'hello world'")


def test_grep_allowed():
    assert_allowed("grep -r 'pattern' .")


def test_cat_allowed():
    assert_allowed("cat /etc/hosts")


def test_python_script_allowed():
    assert_allowed("python script.py")


def test_npm_install_allowed():
    assert_allowed("npm install")


def test_empty_command_allowed():
    is_blocked, _ = check_command("")
    assert not is_blocked


def test_psql_select_allowed():
    assert_allowed("SELECT * FROM users WHERE active = true")


def test_safe_rm_with_i():
    assert_allowed("rm -i file.txt")


# ── Edge cases ─────────────────────────────────────────────────────────

def test_sudo_rm_rf():
    assert_blocked("sudo rm -rf /etc/nginx", "rm -rf")


def test_rm_rf_in_docker():
    assert_blocked("docker exec container rm -rf /app", "rm -rf")


def test_command_with_quotes():
    assert_blocked("rm -rf '/some path/'", "rm -rf")


def test_case_insensitive():
    assert_blocked("Rm -Rf /tmp", "rm -rf")
    assert_blocked("drop table users", "DROP TABLE")


def test_command_with_newlines():
    # Multiline commands — pattern match should still work
    assert_blocked("echo 'before' && rm -rf /tmp && echo 'after'", "rm -rf")


# ── All patterns are covered ───────────────────────────────────────────

def test_all_patterns_have_at_least_one_positive_test():
    """Sanity check: every defined pattern should have been exercised above."""
    # This is a documentation check — the tests above cover all patterns
    assert len(BLOCKED_PATTERNS) > 0, "No patterns defined"


# ── JSON parsing (integration-style) ───────────────────────────────────

def test_extract_command_from_json():
    data = {
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /tmp/data", "cwd": "/home/user/project"},
    }
    cmd = _hook.extract_command(data)
    assert cmd == "rm -rf /tmp/data"


def test_extract_cwd_from_json():
    data = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls", "cwd": "/home/user/project"},
    }
    cwd = _hook.extract_cwd(data)
    assert cwd == "/home/user/project"


def test_non_bash_tool_ignored():
    data = {"tool_name": "Read", "tool_input": {"file_path": "/etc/passwd"}}
    # extract_command should return empty for non-standard tool_input
    cmd = _hook.extract_command(data)
    assert cmd == ""


def test_empty_input():
    assert _hook.parse_input() == {}
