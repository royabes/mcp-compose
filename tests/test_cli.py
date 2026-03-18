"""Tests for the mc CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcp_compose.cli import app

runner = CliRunner()


class TestList:
    def test_list_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mcp_compose.cli._get_dirs",
            lambda: (tmp_path / "global", None),
        )
        (tmp_path / "global").mkdir()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No workflows found" in result.stdout

    def test_list_shows_workflows(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "morning.toml").write_text(
            'name = "morning"\ndescription = "Daily briefing"\n[steps.a]\ntool = "s.t"'
        )
        monkeypatch.setattr(
            "mcp_compose.cli._get_dirs",
            lambda: (global_dir, None),
        )
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "morning" in result.stdout


class TestValidate:
    def test_validate_valid_workflow(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "good.toml").write_text(
            'name = "good"\n[steps.a]\ntool = "s.t"\n[steps.b]\ntool = "s.t"\ndepends_on = ["a"]'
        )
        monkeypatch.setattr(
            "mcp_compose.cli._get_dirs",
            lambda: (global_dir, None),
        )
        result = runner.invoke(app, ["validate", "good"])
        assert result.exit_code == 0
        assert "OK" in result.stdout or "valid" in result.stdout.lower()

    def test_validate_missing_workflow(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setattr(
            "mcp_compose.cli._get_dirs",
            lambda: (global_dir, None),
        )
        result = runner.invoke(app, ["validate", "nonexistent"])
        assert result.exit_code != 0


class TestNew:
    def test_new_creates_file(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setattr(
            "mcp_compose.cli._get_dirs",
            lambda: (global_dir, None),
        )
        result = runner.invoke(app, ["new", "deploy"])
        assert result.exit_code == 0
        assert (global_dir / "deploy.toml").exists()

    def test_new_refuses_existing(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "deploy.toml").write_text("existing")
        monkeypatch.setattr(
            "mcp_compose.cli._get_dirs",
            lambda: (global_dir, None),
        )
        result = runner.invoke(app, ["new", "deploy"])
        assert result.exit_code != 0
