"""Workflow execution engine — DAG resolution and step execution."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from mcp_compose.models import Workflow
from mcp_compose.templates import render_args


class Bridge(Protocol):
    """Protocol for MCP tool execution bridges."""

    async def call_tool(self, tool: str, args: dict) -> dict: ...


@dataclass
class StepResult:
    """Result of executing a single step."""

    status: str  # completed, failed, skipped
    output: Any = None
    error: str | None = None
    duration_ms: int = 0


@dataclass
class WorkflowResult:
    """Result of executing a complete workflow."""

    workflow: str
    status: str  # completed, partial, failed
    steps: dict[str, StepResult] = field(default_factory=dict)
    duration_ms: int = 0


def resolve_waves(workflow: Workflow) -> list[list[str]]:
    """Resolve workflow steps into execution waves.

    Steps with no unresolved dependencies run in the same wave (parallel).
    Returns a list of waves, each wave is a list of step names.
    """
    remaining = set(workflow.steps.keys())
    completed: set[str] = set()
    waves: list[list[str]] = []

    while remaining:
        ready = [
            name
            for name in sorted(remaining)
            if all(dep in completed for dep in workflow.steps[name].depends_on)
        ]

        if not ready:
            raise RuntimeError(
                f"Deadlock: no ready steps among {remaining}"
            )

        waves.append(ready)
        completed.update(ready)
        remaining -= set(ready)

    return waves


async def _execute_step(
    name: str,
    step_def: Any,
    bridge: Bridge,
    steps_output: dict[str, Any],
) -> StepResult:
    """Execute a single step with template resolution."""
    start = time.monotonic()
    try:
        args = render_args(step_def.args, steps_output)
        output = await bridge.call_tool(step_def.tool, args)
        elapsed = int((time.monotonic() - start) * 1000)
        return StepResult(status="completed", output=output, duration_ms=elapsed)
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return StepResult(status="failed", error=str(e), duration_ms=elapsed)


async def execute_workflow(
    workflow: Workflow,
    bridge: Bridge,
) -> WorkflowResult:
    """Execute a workflow using the given bridge."""
    start = time.monotonic()
    waves = resolve_waves(workflow)
    steps_output: dict[str, Any] = {}
    step_results: dict[str, StepResult] = {}
    failed_steps: set[str] = set()

    for wave in waves:
        runnable = []
        for name in wave:
            deps = workflow.steps[name].depends_on
            if any(d in failed_steps for d in deps):
                step_results[name] = StepResult(status="skipped")
                failed_steps.add(name)
            else:
                runnable.append(name)

        if runnable:
            tasks = {
                name: _execute_step(name, workflow.steps[name], bridge, steps_output)
                for name in runnable
            }
            results = await asyncio.gather(*tasks.values())

            for name, result in zip(tasks.keys(), results):
                step_results[name] = result
                if result.status == "completed":
                    steps_output[name] = result.output
                else:
                    failed_steps.add(name)

    elapsed = int((time.monotonic() - start) * 1000)

    statuses = {r.status for r in step_results.values()}
    if statuses == {"completed"}:
        overall = "completed"
    elif "completed" in statuses:
        overall = "partial"
    else:
        overall = "failed"

    return WorkflowResult(
        workflow=workflow.name,
        status=overall,
        steps=step_results,
        duration_ms=elapsed,
    )
