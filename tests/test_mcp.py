"""Tests for MCP server tools."""

from pathlib import Path

import pytest

from mcp_compose.mcp_server import (
    get_workflow,
    list_workflows_tool,
    run_workflow,
    validate_workflow,
)


@pytest.fixture(autouse=True)
def _patch_dirs(tmp_path, monkeypatch):
    """Patch workflow directories for all MCP tests."""
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    monkeypatch.setattr("mcp_compose.mcp_server._global_dir", lambda: global_dir)
    monkeypatch.setattr("mcp_compose.mcp_server._project_dir", lambda: None)
    return global_dir


@pytest.fixture
def workflow_dir(_patch_dirs):
    return _patch_dirs


class TestListWorkflows:
    def test_empty(self, workflow_dir):
        result = list_workflows_tool()
        assert result == []

    def test_lists_available(self, workflow_dir):
        (workflow_dir / "morning.toml").write_text(
            'name = "morning"\ndescription = "Daily"\n[steps.a]\ntool = "s.t"'
        )
        result = list_workflows_tool()
        assert len(result) == 1
        assert result[0]["name"] == "morning"


class TestGetWorkflow:
    def test_returns_dag(self, workflow_dir):
        (workflow_dir / "test.toml").write_text('''
name = "test"
description = "Test workflow"
[steps.a]
tool = "s.t"
[steps.b]
tool = "s.t"
depends_on = ["a"]
''')
        result = get_workflow("test")
        assert result["name"] == "test"
        assert len(result["steps"]) == 2
        assert len(result["waves"]) == 2

    def test_not_found(self, workflow_dir):
        result = get_workflow("missing")
        assert "error" in result


class TestValidateWorkflow:
    def test_valid(self, workflow_dir):
        (workflow_dir / "ok.toml").write_text(
            'name = "ok"\n[steps.a]\ntool = "s.t"'
        )
        result = validate_workflow("ok")
        assert result["valid"] is True

    def test_invalid(self, workflow_dir):
        (workflow_dir / "bad.toml").write_text('name = "bad"')
        result = validate_workflow("bad")
        assert result["valid"] is False


class TestRunWorkflow:
    def test_returns_execution_plan(self, workflow_dir):
        (workflow_dir / "morning.toml").write_text('''
name = "morning"
description = "Daily briefing"
[steps.briefing]
tool = "tech-radar.get_latest_briefing"
[steps.emails]
tool = "google-workspace.gmail_search"
args.query = "is:unread"
[steps.plan]
tool = "daily-routine.plan"
depends_on = ["briefing", "emails"]
args.briefing = "{{steps.briefing.output}}"
args.emails = "{{steps.emails.output}}"
''')
        result = run_workflow("morning")
        assert result["workflow"] == "morning"
        assert len(result["waves"]) == 2
        assert "instructions" in result
