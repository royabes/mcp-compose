"""Template interpolation for workflow step arguments."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

_TEMPLATE_RE = re.compile(r"\{\{(.+?)\}\}")


def _resolve_var(expr: str, steps_output: dict[str, Any]) -> Any:
    """Resolve a single template expression."""
    expr = expr.strip()

    if expr == "today":
        return date.today().isoformat()
    if expr == "tomorrow":
        return (date.today() + timedelta(days=1)).isoformat()
    if expr == "now":
        from datetime import datetime, UTC
        return datetime.now(UTC).isoformat() + "Z"

    if expr.startswith("steps.") and expr.endswith(".output"):
        step_name = expr.removeprefix("steps.").removesuffix(".output")
        if step_name not in steps_output:
            raise KeyError(
                f"Step {step_name!r} not found in completed steps"
            )
        return steps_output[step_name]

    raise ValueError(f"Unknown template expression: {expr!r}")


def _render_value(value: Any, steps_output: dict[str, Any]) -> Any:
    """Render a single value, resolving templates."""
    if isinstance(value, str):
        match = _TEMPLATE_RE.fullmatch(value)
        if match:
            return _resolve_var(match.group(1), steps_output)

        def replace_match(m: re.Match) -> str:
            resolved = _resolve_var(m.group(1), steps_output)
            if isinstance(resolved, (dict, list)):
                return json.dumps(resolved)
            return str(resolved)

        return _TEMPLATE_RE.sub(replace_match, value)

    if isinstance(value, dict):
        return {k: _render_value(v, steps_output) for k, v in value.items()}

    if isinstance(value, list):
        return [_render_value(v, steps_output) for v in value]

    return value


def render_args(
    args: dict[str, Any],
    steps_output: dict[str, Any],
) -> dict[str, Any]:
    """Render all template expressions in step arguments."""
    return _render_value(args, steps_output)
