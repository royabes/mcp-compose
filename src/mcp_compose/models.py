"""Workflow and step models for MCP Compose."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator, model_validator


class Step(BaseModel):
    """A single step in a workflow — one MCP tool call."""

    tool: str
    args: dict[str, Any] = {}
    depends_on: list[str] = []

    @field_validator("tool")
    @classmethod
    def tool_must_be_qualified(cls, v: str) -> str:
        if "." not in v:
            raise ValueError(
                f"Tool name must be in 'server.tool' format, got: {v!r}"
            )
        return v


class Workflow(BaseModel):
    """A named workflow — a DAG of steps."""

    name: str
    description: str = ""
    steps: dict[str, Step]

    @model_validator(mode="after")
    def validate_dag(self) -> Workflow:
        if not self.steps:
            raise ValueError("Workflow must have at least one step")

        step_names = set(self.steps.keys())

        # Check all depends_on reference existing steps
        for name, step in self.steps.items():
            for dep in step.depends_on:
                if dep not in step_names:
                    raise ValueError(
                        f"Step {name!r} depends on unknown step {dep!r}"
                    )

        # Check for circular dependencies via topological sort
        _topo_sort(self.steps)

        return self


def _topo_sort(steps: dict[str, Step]) -> list[str]:
    """Topological sort of steps. Raises ValueError on cycles."""
    visited: set[str] = set()
    temp: set[str] = set()
    order: list[str] = []

    def visit(name: str) -> None:
        if name in temp:
            raise ValueError(f"Circular dependency detected involving {name!r}")
        if name in visited:
            return
        temp.add(name)
        for dep in steps[name].depends_on:
            visit(dep)
        temp.remove(name)
        visited.add(name)
        order.append(name)

    for name in steps:
        visit(name)

    return order


def parse_workflow(source: str | Path) -> Workflow:
    """Parse a workflow from a TOML string or file path.

    If source is a Path, reads the file directly.
    If source is a string, tries TOML parsing first; falls back to
    reading it as a file path only if TOML parsing fails.
    """
    if isinstance(source, Path):
        raw = source.read_text()
    else:
        # Try parsing as TOML first
        try:
            data = tomllib.loads(source)
        except tomllib.TOMLDecodeError:
            # Not valid TOML — try as file path
            path = Path(source)
            if path.is_file():
                raw = path.read_text()
            else:
                raise
        else:
            return _build_workflow(data)
        # If we got here, we read a file path into raw
        data = tomllib.loads(raw)
        return _build_workflow(data)

    data = tomllib.loads(raw)
    return _build_workflow(data)


def _build_workflow(data: dict[str, Any]) -> Workflow:
    """Build a Workflow from parsed TOML data."""
    steps_raw = data.pop("steps", {})
    steps = {}
    for step_name, step_data in steps_raw.items():
        steps[step_name] = Step(**step_data)

    return Workflow(
        name=data.get("name", "unnamed"),
        description=data.get("description", ""),
        steps=steps,
    )
