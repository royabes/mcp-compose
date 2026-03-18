"""Tests for template interpolation."""

from datetime import date

import pytest

from mcp_compose.templates import render_args


class TestRenderArgs:
    def test_no_templates_passthrough(self):
        args = {"query": "hello", "limit": 10}
        result = render_args(args, steps_output={})
        assert result == {"query": "hello", "limit": 10}

    def test_step_output_reference(self):
        args = {"input": "{{steps.fetch.output}}"}
        steps_output = {"fetch": {"data": [1, 2, 3]}}
        result = render_args(args, steps_output=steps_output)
        assert result == {"input": {"data": [1, 2, 3]}}

    def test_builtin_today(self):
        args = {"date": "{{today}}"}
        result = render_args(args, steps_output={})
        assert result["date"] == date.today().isoformat()

    def test_builtin_tomorrow(self):
        args = {"date": "{{tomorrow}}"}
        result = render_args(args, steps_output={})
        tomorrow = (date.today().replace(day=date.today().day) + __import__('datetime').timedelta(days=1)).isoformat()
        assert result["date"] == tomorrow

    def test_mixed_template_and_literal(self):
        args = {
            "context": "{{steps.briefing.output}}",
            "limit": 5,
            "flag": True,
        }
        steps_output = {"briefing": {"summary": "good morning"}}
        result = render_args(args, steps_output=steps_output)
        assert result["context"] == {"summary": "good morning"}
        assert result["limit"] == 5
        assert result["flag"] is True

    def test_missing_step_raises(self):
        args = {"input": "{{steps.nonexistent.output}}"}
        with pytest.raises(KeyError, match="nonexistent"):
            render_args(args, steps_output={})

    def test_nested_dict_args_rendered(self):
        args = {"options": {"data": "{{steps.a.output}}", "static": "keep"}}
        steps_output = {"a": "resolved_value"}
        result = render_args(args, steps_output=steps_output)
        assert result["options"]["data"] == "resolved_value"
        assert result["options"]["static"] == "keep"

    def test_string_with_embedded_template(self):
        """Templates that are part of a larger string stay as strings."""
        args = {"msg": "Result: {{steps.a.output}}"}
        steps_output = {"a": "42"}
        result = render_args(args, steps_output=steps_output)
        assert result["msg"] == "Result: 42"
