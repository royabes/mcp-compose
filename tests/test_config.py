"""Tests for workflow config resolution."""

from pathlib import Path

import pytest

from mcp_compose.config import discover_workflows, resolve_workflow


class TestDiscoverWorkflows:
    def test_finds_global_workflows(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "morning.toml").write_text('name = "morning"\n[steps.a]\ntool = "s.t"')
        (global_dir / "evening.toml").write_text('name = "evening"\n[steps.a]\ntool = "s.t"')

        result = discover_workflows(global_dir=global_dir, project_dir=None)
        assert set(result.keys()) == {"morning", "evening"}

    def test_project_overrides_global(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "deploy.toml").write_text('name = "deploy"\ndescription = "global"\n[steps.a]\ntool = "s.t"')

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "deploy.toml").write_text('name = "deploy"\ndescription = "project"\n[steps.a]\ntool = "s.t"')

        result = discover_workflows(global_dir=global_dir, project_dir=project_dir)
        assert result["deploy"] == project_dir / "deploy.toml"

    def test_ignores_non_toml_files(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "morning.toml").write_text('name = "morning"\n[steps.a]\ntool = "s.t"')
        (global_dir / "readme.md").write_text("not a workflow")

        result = discover_workflows(global_dir=global_dir, project_dir=None)
        assert set(result.keys()) == {"morning"}

    def test_empty_dirs(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        result = discover_workflows(global_dir=global_dir, project_dir=None)
        assert result == {}

    def test_missing_dirs_dont_crash(self, tmp_path):
        result = discover_workflows(
            global_dir=tmp_path / "nonexistent",
            project_dir=tmp_path / "also_nonexistent",
        )
        assert result == {}


class TestResolveWorkflow:
    def test_resolve_by_name(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "morning.toml").write_text('name = "morning"\n[steps.a]\ntool = "s.t"')

        path = resolve_workflow("morning", global_dir=global_dir, project_dir=None)
        assert path == global_dir / "morning.toml"

    def test_resolve_missing_raises(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="morning"):
            resolve_workflow("morning", global_dir=global_dir, project_dir=None)
