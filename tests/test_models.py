"""Tests for workflow model parsing and validation."""

import pytest

from mcp_compose.models import Step, Workflow, parse_workflow


class TestStepModel:
    def test_minimal_step(self):
        step = Step(tool="server.tool_name")
        assert step.tool == "server.tool_name"
        assert step.args == {}
        assert step.depends_on == []

    def test_step_with_args_and_deps(self):
        step = Step(
            tool="server.tool_name",
            args={"query": "test", "limit": 10},
            depends_on=["other_step"],
        )
        assert step.args == {"query": "test", "limit": 10}
        assert step.depends_on == ["other_step"]

    def test_step_tool_must_have_dot(self):
        """Tool names must be 'server.tool' format."""
        with pytest.raises(ValueError, match="server.tool"):
            Step(tool="no_dot_here")


class TestWorkflowModel:
    def test_minimal_workflow(self):
        wf = Workflow(
            name="test",
            description="A test",
            steps={"a": Step(tool="s.t")},
        )
        assert wf.name == "test"
        assert len(wf.steps) == 1

    def test_workflow_requires_at_least_one_step(self):
        with pytest.raises(ValueError, match="at least one step"):
            Workflow(name="empty", description="No steps", steps={})

    def test_workflow_rejects_unknown_depends_on(self):
        with pytest.raises(ValueError, match="unknown step"):
            Workflow(
                name="bad",
                description="Bad deps",
                steps={
                    "a": Step(tool="s.t", depends_on=["nonexistent"]),
                },
            )

    def test_workflow_rejects_circular_deps(self):
        with pytest.raises(ValueError, match="[Cc]ircular"):
            Workflow(
                name="loop",
                description="Circular",
                steps={
                    "a": Step(tool="s.t", depends_on=["b"]),
                    "b": Step(tool="s.t", depends_on=["a"]),
                },
            )

    def test_workflow_rejects_self_dep(self):
        with pytest.raises(ValueError, match="[Cc]ircular|itself"):
            Workflow(
                name="self",
                description="Self dep",
                steps={
                    "a": Step(tool="s.t", depends_on=["a"]),
                },
            )


class TestParseWorkflow:
    def test_parse_from_toml_string(self, sample_workflow_toml):
        wf = parse_workflow(sample_workflow_toml)
        assert wf.name == "test-workflow"
        assert "step_a" in wf.steps
        assert "step_b" in wf.steps
        assert wf.steps["step_b"].depends_on == ["step_a"]

    def test_parse_from_file(self, tmp_workflows, sample_workflow_toml):
        path = tmp_workflows / "test.toml"
        path.write_text(sample_workflow_toml)
        wf = parse_workflow(path)
        assert wf.name == "test-workflow"

    def test_parse_parallel_workflow(self, parallel_workflow_toml):
        wf = parse_workflow(parallel_workflow_toml)
        assert wf.steps["fast"].depends_on == []
        assert wf.steps["slow"].depends_on == []
        assert set(wf.steps["combine"].depends_on) == {"fast", "slow"}
