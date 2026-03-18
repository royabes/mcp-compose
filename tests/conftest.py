"""Shared fixtures for MCP Compose tests."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_workflows(tmp_path: Path) -> Path:
    """Create a temporary workflows directory."""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    return workflows_dir


@pytest.fixture
def sample_workflow_toml() -> str:
    """A minimal valid workflow TOML string."""
    return '''
name = "test-workflow"
description = "A test workflow"

[steps.step_a]
tool = "test-server.tool_a"

[steps.step_b]
tool = "test-server.tool_b"
depends_on = ["step_a"]
args.input = "{{steps.step_a.output}}"
'''


@pytest.fixture
def parallel_workflow_toml() -> str:
    """A workflow with parallel steps and a fan-in."""
    return '''
name = "parallel-test"
description = "Parallel steps with fan-in"

[steps.fast]
tool = "test-server.fast"

[steps.slow]
tool = "test-server.slow"

[steps.combine]
tool = "test-server.combine"
depends_on = ["fast", "slow"]
args.fast_result = "{{steps.fast.output}}"
args.slow_result = "{{steps.slow.output}}"
'''
