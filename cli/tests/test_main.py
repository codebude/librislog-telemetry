"""Tests for the ltel CLI."""

from typer.testing import CliRunner

from ltel.main import app

runner = CliRunner()


def test_help_shows_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "test" in result.stdout
    assert "docker" in result.stdout
    assert "pr" in result.stdout
    assert "branch" in result.stdout
    assert "run" in result.stdout


def test_test_help():
    result = runner.invoke(app, ["test", "--help"])
    assert result.exit_code == 0
    assert "backend" in result.stdout
    assert "all" in result.stdout


def test_pr_help():
    result = runner.invoke(app, ["pr", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "create" in result.stdout
    assert "merge" in result.stdout


def test_branch_help():
    result = runner.invoke(app, ["branch", "--help"])
    assert result.exit_code == 0
    assert "create" in result.stdout
    assert "delete" in result.stdout
    assert "sync" in result.stdout