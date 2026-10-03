"""Unit tests for Click CLI commands."""

from click.testing import CliRunner
from synapr.cli.main import main


def test_cli_version() -> None:
    """Test synapr --version."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "synapr" in result.output


def test_cli_scan() -> None:
    """Test synapr scan command."""
    runner = CliRunner()
    result = runner.invoke(main, ["scan"])
    assert result.exit_code == 0
    assert "Discovered" in result.output


def test_cli_status() -> None:
    """Test synapr status command."""
    runner = CliRunner()
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "Synapr Swarm Status" in result.output


def test_cli_plan() -> None:
    """Test synapr plan command."""
    runner = CliRunner()
    result = runner.invoke(main, ["plan", "Build user profile caching"])
    assert result.exit_code == 0
    assert "Plan Verified" in result.output


def test_cli_run_dry_run() -> None:
    """Test synapr run --dry-run command."""
    runner = CliRunner()
    result = runner.invoke(main, ["run", "Build database migrations", "--dry-run"])
    assert result.exit_code == 0
    assert "Swarm Execution Complete" in result.output
