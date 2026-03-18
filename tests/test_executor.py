"""Tests for workflow step execution."""

import pytest

from mcp_compose.engine import StepResult, WorkflowResult, execute_workflow
from mcp_compose.models import parse_workflow


class FakeBridge:
    """Mock MCP bridge that returns predictable results."""

    def __init__(self, results: dict[str, dict] | None = None, fail: set[str] | None = None):
        self.results = results or {}
        self.fail = fail or set()
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, tool: str, args: dict) -> dict:
        self.calls.append((tool, args))
        if tool in self.fail:
            raise RuntimeError(f"Tool {tool} failed")
        return self.results.get(tool, {"ok": True})


class TestExecuteWorkflow:
    @pytest.mark.asyncio
    async def test_single_step(self):
        wf = parse_workflow('''
name = "simple"
[steps.only]
tool = "s.greet"
args.name = "world"
''')
        bridge = FakeBridge(results={"s.greet": {"message": "hello world"}})
        result = await execute_workflow(wf, bridge)

        assert result.status == "completed"
        assert result.steps["only"].status == "completed"
        assert result.steps["only"].output == {"message": "hello world"}
        assert len(bridge.calls) == 1
        assert bridge.calls[0] == ("s.greet", {"name": "world"})

    @pytest.mark.asyncio
    async def test_template_data_passing(self):
        wf = parse_workflow('''
name = "chain"
[steps.fetch]
tool = "s.fetch"
[steps.process]
tool = "s.process"
depends_on = ["fetch"]
args.data = "{{steps.fetch.output}}"
''')
        bridge = FakeBridge(results={
            "s.fetch": {"items": [1, 2, 3]},
            "s.process": {"count": 3},
        })
        result = await execute_workflow(wf, bridge)

        assert result.status == "completed"
        assert bridge.calls[1] == ("s.process", {"data": {"items": [1, 2, 3]}})

    @pytest.mark.asyncio
    async def test_parallel_steps_both_called(self):
        wf = parse_workflow('''
name = "par"
[steps.a]
tool = "s.a"
[steps.b]
tool = "s.b"
''')
        bridge = FakeBridge(results={"s.a": {"a": 1}, "s.b": {"b": 2}})
        result = await execute_workflow(wf, bridge)

        assert result.status == "completed"
        assert len(bridge.calls) == 2
        tools_called = {c[0] for c in bridge.calls}
        assert tools_called == {"s.a", "s.b"}

    @pytest.mark.asyncio
    async def test_failed_step_skips_dependents(self):
        wf = parse_workflow('''
name = "fail"
[steps.bad]
tool = "s.bad"
[steps.after_bad]
tool = "s.after"
depends_on = ["bad"]
[steps.independent]
tool = "s.ok"
''')
        bridge = FakeBridge(
            results={"s.ok": {"fine": True}},
            fail={"s.bad"},
        )
        result = await execute_workflow(wf, bridge)

        assert result.status == "partial"
        assert result.steps["bad"].status == "failed"
        assert result.steps["after_bad"].status == "skipped"
        assert result.steps["independent"].status == "completed"

    @pytest.mark.asyncio
    async def test_result_has_duration(self):
        wf = parse_workflow('''
name = "timed"
[steps.only]
tool = "s.t"
''')
        bridge = FakeBridge()
        result = await execute_workflow(wf, bridge)

        assert result.duration_ms >= 0
        assert result.steps["only"].duration_ms >= 0
