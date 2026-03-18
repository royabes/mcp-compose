"""Workflow discovery and config resolution."""

from __future__ import annotations

from pathlib import Path

DEFAULT_GLOBAL_DIR = Path.home() / ".claude" / "workflows"
DEFAULT_PROJECT_DIR_NAME = ".claude/workflows"


def discover_workflows(
    global_dir: Path | None = None,
    project_dir: Path | None = None,
) -> dict[str, Path]:
    """Discover available workflows. Project-local overrides global.

    Returns a dict of workflow_name -> file_path.
    """
    workflows: dict[str, Path] = {}

    if global_dir and global_dir.is_dir():
        for f in sorted(global_dir.glob("*.toml")):
            workflows[f.stem] = f

    if project_dir and project_dir.is_dir():
        for f in sorted(project_dir.glob("*.toml")):
            workflows[f.stem] = f

    return workflows


def resolve_workflow(
    name: str,
    global_dir: Path | None = None,
    project_dir: Path | None = None,
) -> Path:
    """Resolve a workflow name to its file path.

    Raises FileNotFoundError if not found.
    """
    workflows = discover_workflows(global_dir=global_dir, project_dir=project_dir)
    if name not in workflows:
        available = ", ".join(sorted(workflows.keys())) or "(none)"
        raise FileNotFoundError(
            f"Workflow {name!r} not found. Available: {available}"
        )
    return workflows[name]


def find_project_workflows_dir() -> Path | None:
    """Walk up from cwd to find .claude/workflows/ in a project."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / DEFAULT_PROJECT_DIR_NAME
        if candidate.is_dir():
            return candidate
        if parent == Path.home():
            break
    return None
