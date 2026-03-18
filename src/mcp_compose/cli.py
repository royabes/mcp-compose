"""MCP Compose CLI — mc command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from mcp_compose.config import (
    DEFAULT_GLOBAL_DIR,
    discover_workflows,
    find_project_workflows_dir,
    resolve_workflow,
)
from mcp_compose.engine import resolve_waves
from mcp_compose.models import parse_workflow

app = typer.Typer(
    name="mc",
    help="MCP Compose — workflow orchestrator for MCP servers.",
    no_args_is_help=True,
)

console = Console()


def _get_dirs() -> tuple[Path, Path | None]:
    """Get global and project workflow directories."""
    return DEFAULT_GLOBAL_DIR, find_project_workflows_dir()


@app.command()
def run(
    name: Annotated[str, typer.Argument(help="Workflow name to execute")],
    step: Annotated[str | None, typer.Option(help="Run only this step")] = None,
) -> None:
    """Execute a named workflow."""
    global_dir, project_dir = _get_dirs()
    try:
        path = resolve_workflow(name, global_dir=global_dir, project_dir=project_dir)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    wf = parse_workflow(path)
    waves = resolve_waves(wf)

    typer.echo(f"Workflow: {wf.name}")
    typer.echo(f"Description: {wf.description}")
    typer.echo(f"Steps: {len(wf.steps)} in {len(waves)} wave(s)\n")

    for i, wave in enumerate(waves, 1):
        parallel = " (parallel)" if len(wave) > 1 else ""
        typer.echo(f"  Wave {i}{parallel}:")
        for step_name in wave:
            s = wf.steps[step_name]
            deps = f" <- [{', '.join(s.depends_on)}]" if s.depends_on else ""
            typer.echo(f"    {step_name}: {s.tool}{deps}")

    typer.echo("\nPhase 1: Use Claude Code to execute this workflow.")
    typer.echo(f'  Ask: "Run my {name} workflow"')


@app.command("list")
def list_workflows() -> None:
    """List available workflows."""
    global_dir, project_dir = _get_dirs()
    workflows = discover_workflows(global_dir=global_dir, project_dir=project_dir)

    if not workflows:
        typer.echo("No workflows found.")
        typer.echo(f"  Global: {global_dir}")
        if project_dir:
            typer.echo(f"  Project: {project_dir}")
        typer.echo(f"\nCreate one: mc new <name>")
        return

    table = Table(title="Workflows")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Steps", justify="right")
    table.add_column("Source")

    for name, path in sorted(workflows.items()):
        try:
            wf = parse_workflow(path)
            source = "project" if project_dir and path.parent == project_dir else "global"
            table.add_row(name, wf.description, str(len(wf.steps)), source)
        except Exception as e:
            table.add_row(name, f"[red]parse error: {e}[/red]", "-", str(path.parent))

    console.print(table)


@app.command()
def validate(
    name: Annotated[str, typer.Argument(help="Workflow name to validate")],
) -> None:
    """Validate a workflow without executing it."""
    global_dir, project_dir = _get_dirs()
    try:
        path = resolve_workflow(name, global_dir=global_dir, project_dir=project_dir)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    try:
        wf = parse_workflow(path)
        waves = resolve_waves(wf)
        typer.echo(f"OK: {wf.name} — {len(wf.steps)} steps, {len(waves)} waves")
        for i, wave in enumerate(waves, 1):
            typer.echo(f"  Wave {i}: {', '.join(wave)}")
    except Exception as e:
        typer.echo(f"FAIL: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def new(
    name: Annotated[str, typer.Argument(help="Name for the new workflow")],
    project: Annotated[bool, typer.Option("--project", help="Create in project dir")] = False,
) -> None:
    """Scaffold a new workflow TOML file."""
    global_dir, project_dir = _get_dirs()

    if project and project_dir:
        target_dir = project_dir
    else:
        target_dir = global_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}.toml"

    if target.exists():
        typer.echo(f"Error: {target} already exists", err=True)
        raise typer.Exit(code=1)

    template = f'''name = "{name}"
description = ""

[steps.step1]
tool = "server.tool_name"
# args.key = "value"

# [steps.step2]
# tool = "server.other_tool"
# depends_on = ["step1"]
# args.input = "{{{{steps.step1.output}}}}"
'''
    target.write_text(template)
    typer.echo(f"Created: {target}")
