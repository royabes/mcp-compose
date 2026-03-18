"""MCP Compose server — workflow orchestration tools for Claude Code."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from mcp_compose.config import (
    DEFAULT_GLOBAL_DIR,
    discover_workflows,
    find_project_workflows_dir,
    resolve_workflow as _resolve,
)
from mcp_compose.engine import resolve_waves
from mcp_compose.models import parse_workflow

mcp = FastMCP(
    "mcp-compose",
    instructions=(
        "MCP Compose orchestrates workflows across MCP servers. "
        "Use list_workflows to see available workflows, "
        "run_workflow to get an execution plan, "
        "then execute each step's tool call in order.\n\n"
        "EXECUTION FLOW: Call run_workflow(name) to get the step-by-step plan. "
        "Execute each wave's tools in parallel, passing results to dependent steps "
        "using the template mappings provided."
    ),
)


def _global_dir() -> Path:
    return DEFAULT_GLOBAL_DIR


def _project_dir() -> Path | None:
    return find_project_workflows_dir()


@mcp.tool()
def list_workflows_tool() -> list[dict]:
    """List all available workflows with name, description, step count, and source."""
    workflows = discover_workflows(
        global_dir=_global_dir(), project_dir=_project_dir()
    )
    result = []
    for name, path in sorted(workflows.items()):
        try:
            wf = parse_workflow(path)
            source = "project" if _project_dir() and path.parent == _project_dir() else "global"
            result.append({
                "name": name,
                "description": wf.description,
                "steps": len(wf.steps),
                "source": source,
            })
        except Exception as e:
            result.append({"name": name, "error": str(e)})
    return result


@mcp.tool()
def get_workflow(name: str) -> dict:
    """Get the full DAG for a workflow: steps, dependencies, and execution waves."""
    try:
        path = _resolve(name, global_dir=_global_dir(), project_dir=_project_dir())
    except FileNotFoundError as e:
        return {"error": str(e)}

    try:
        wf = parse_workflow(path)
        waves = resolve_waves(wf)
        return {
            "name": wf.name,
            "description": wf.description,
            "steps": {
                step_name: {
                    "tool": step.tool,
                    "args": step.args,
                    "depends_on": step.depends_on,
                }
                for step_name, step in wf.steps.items()
            },
            "waves": [[s for s in wave] for wave in waves],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def validate_workflow(name: str) -> dict:
    """Validate a workflow: check TOML syntax, DAG validity, and template references."""
    try:
        path = _resolve(name, global_dir=_global_dir(), project_dir=_project_dir())
    except FileNotFoundError as e:
        return {"valid": False, "error": str(e)}

    try:
        wf = parse_workflow(path)
        waves = resolve_waves(wf)
        return {
            "valid": True,
            "name": wf.name,
            "steps": len(wf.steps),
            "waves": len(waves),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


@mcp.tool()
def run_workflow(name: str, overrides: dict | None = None) -> dict:
    """Get an execution plan for a workflow.

    Returns the step-by-step plan with tools, args, and wave ordering.
    Execute each wave's tools, then pass results to the next wave using
    the template mappings.
    """
    try:
        path = _resolve(name, global_dir=_global_dir(), project_dir=_project_dir())
    except FileNotFoundError as e:
        return {"error": str(e)}

    try:
        wf = parse_workflow(path)
        waves = resolve_waves(wf)

        wave_plans = []
        for wave in waves:
            wave_steps = []
            for step_name in wave:
                step = wf.steps[step_name]
                wave_steps.append({
                    "name": step_name,
                    "tool": step.tool,
                    "args": step.args,
                    "depends_on": step.depends_on,
                })
            wave_plans.append(wave_steps)

        return {
            "workflow": wf.name,
            "description": wf.description,
            "waves": wave_plans,
            "instructions": (
                "Execute each wave in order. Steps within a wave can run in parallel. "
                "After each step completes, its output replaces {{steps.<name>.output}} "
                "in subsequent steps' args. If a step fails, skip all steps that depend on it."
            ),
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
