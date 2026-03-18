"""Tests for the workflow execution engine."""

import pytest

from mcp_compose.engine import resolve_waves
from mcp_compose.models import parse_workflow


class TestResolveWaves:
    def test_single_step(self):
        wf = parse_workflow('''
name = "single"
[steps.only]
tool = "s.t"
''')
        waves = resolve_waves(wf)
        assert waves == [["only"]]

    def test_two_independent_steps_same_wave(self):
        wf = parse_workflow('''
name = "parallel"
[steps.a]
tool = "s.t"
[steps.b]
tool = "s.t"
''')
        waves = resolve_waves(wf)
        assert len(waves) == 1
        assert set(waves[0]) == {"a", "b"}

    def test_sequential_chain(self):
        wf = parse_workflow('''
name = "chain"
[steps.a]
tool = "s.t"
[steps.b]
tool = "s.t"
depends_on = ["a"]
[steps.c]
tool = "s.t"
depends_on = ["b"]
''')
        waves = resolve_waves(wf)
        assert waves == [["a"], ["b"], ["c"]]

    def test_fan_in(self, parallel_workflow_toml):
        wf = parse_workflow(parallel_workflow_toml)
        waves = resolve_waves(wf)
        assert len(waves) == 2
        assert set(waves[0]) == {"fast", "slow"}
        assert waves[1] == ["combine"]

    def test_diamond_dag(self):
        wf = parse_workflow('''
name = "diamond"
[steps.source]
tool = "s.t"
[steps.left]
tool = "s.t"
depends_on = ["source"]
[steps.right]
tool = "s.t"
depends_on = ["source"]
[steps.sink]
tool = "s.t"
depends_on = ["left", "right"]
''')
        waves = resolve_waves(wf)
        assert len(waves) == 3
        assert waves[0] == ["source"]
        assert set(waves[1]) == {"left", "right"}
        assert waves[2] == ["sink"]
