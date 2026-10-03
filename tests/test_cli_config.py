"""Unit tests for the `synapr config` CLI command group."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from synapr.cli.main import main


@pytest.fixture
def runner(workspace: Path) -> CliRunner:
    """CliRunner operating inside an isolated workspace directory."""
    return CliRunner()


def test_init_creates_config_and_env_example(runner: CliRunner, workspace: Path) -> None:
    result = runner.invoke(main, ["init"])

    assert result.exit_code == 0, result.output
    assert (workspace / "synapr.config.json").is_file()
    assert (workspace / ".env.example").is_file()
    assert "SYNAPR_PROVIDER" in (workspace / ".env.example").read_text(encoding="utf-8")


def test_init_refuses_to_overwrite(runner: CliRunner, workspace: Path) -> None:
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["init"])

    assert result.exit_code != 0
    assert "already exists" in result.output


def test_init_force_and_provider(runner: CliRunner, workspace: Path) -> None:
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["init", "--force", "--provider", "ollama", "--no-env-example"])

    assert result.exit_code == 0, result.output
    payload = json.loads((workspace / "synapr.config.json").read_text(encoding="utf-8"))
    assert payload["gateway"]["default_provider"] == "ollama"


def test_config_show_human_readable(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert "Effective Synapr Configuration" in result.output
    assert "[gateway]" in result.output


def test_config_show_json(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config", "show", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["gateway"]["default_provider"] == "mock"


def test_config_show_redacts_secrets(runner: CliRunner) -> None:
    runner.invoke(main, ["config", "set", "gateway.openai_api_key", "sk-cli-secret-1234"])

    redacted = runner.invoke(main, ["config", "show", "--json"]).output
    revealed = runner.invoke(main, ["config", "show", "--json", "--reveal"]).output

    assert "sk-cli-secret-1234" not in redacted
    assert "sk-cli-secret-1234" in revealed


def test_config_set_and_get(runner: CliRunner, workspace: Path) -> None:
    set_result = runner.invoke(main, ["config", "set", "gateway.default_provider", "ollama"])
    assert set_result.exit_code == 0, set_result.output

    get_result = runner.invoke(main, ["config", "get", "gateway.default_provider"])
    assert json.loads(get_result.output) == "ollama"

    payload = json.loads((workspace / "synapr.config.json").read_text(encoding="utf-8"))
    assert payload["gateway"]["default_provider"] == "ollama"


def test_config_set_coerces_types(runner: CliRunner) -> None:
    runner.invoke(main, ["config", "set", "ui.port", "9777"])
    runner.invoke(main, ["config", "set", "pipeline.auto_test", "false"])

    assert json.loads(runner.invoke(main, ["config", "get", "ui.port"]).output) == 9777
    assert json.loads(runner.invoke(main, ["config", "get", "pipeline.auto_test"]).output) is False


def test_config_set_rejects_invalid(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config", "set", "gateway.temperature", "9"])

    assert result.exit_code != 0
    assert "temperature" in result.output


def test_config_set_rejects_unknown_path(runner: CliRunner) -> None:
    assert runner.invoke(main, ["config", "set", "nope.nope", "1"]).exit_code != 0


def test_config_get_unknown_path(runner: CliRunner) -> None:
    assert runner.invoke(main, ["config", "get", "gateway.nope"]).exit_code != 0


def test_config_unset_restores_default(runner: CliRunner) -> None:
    runner.invoke(main, ["config", "set", "gateway.planner_model", "custom:latest"])
    result = runner.invoke(main, ["config", "unset", "gateway.planner_model"])

    assert result.exit_code == 0, result.output
    assert json.loads(
        runner.invoke(main, ["config", "get", "gateway.planner_model"]).output
    ) == "qwen2.5-coder:7b"


def test_config_set_no_save(runner: CliRunner, workspace: Path) -> None:
    result = runner.invoke(main, ["config", "set", "project_name", "Ephemeral", "--no-save"])

    assert result.exit_code == 0, result.output
    assert not (workspace / "synapr.config.json").exists()


def test_config_path(runner: CliRunner, workspace: Path) -> None:
    result = runner.invoke(main, ["config", "path"])

    assert result.exit_code == 0
    assert result.output.strip().endswith("synapr.config.json")


def test_config_validate_ok(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config", "validate"])

    assert result.exit_code == 0
    assert "valid" in result.output


def test_config_validate_reports_broken_file(runner: CliRunner, workspace: Path) -> None:
    (workspace / "synapr.config.json").write_text("{ broken", encoding="utf-8")
    result = runner.invoke(main, ["--config", "synapr.config.json", "config", "validate"])

    assert result.exit_code == 1
    assert "Failed to load" in result.output


def test_config_env_listing(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPR_PROVIDER", "ollama")
    result = runner.invoke(main, ["config", "env"])

    assert result.exit_code == 0, result.output
    assert "SYNAPR_PROVIDER" in result.output
    assert "SET via" in result.output


def test_config_env_all_and_example(runner: CliRunner, workspace: Path) -> None:
    assert "SYNAPR_UI_PORT" in runner.invoke(main, ["config", "env", "--all"]).output
    assert "SYNAPR_OLLAMA_BASE_URL" in runner.invoke(main, ["config", "env", "--example"]).output

    result = runner.invoke(main, ["config", "env", "--write-example", "custom.env"])
    assert result.exit_code == 0
    assert (workspace / "custom.env").is_file()


def test_config_test_provider(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config", "test"])

    assert result.exit_code == 0
    assert "mock" in result.output


def test_config_group_without_subcommand_shows_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config"])

    assert result.exit_code == 0
    assert "Inspect and edit configuration" in result.output


def test_global_config_option_targets_custom_file(runner: CliRunner, workspace: Path) -> None:
    custom = workspace / "custom.config.json"
    result = runner.invoke(
        main, ["--config", str(custom), "config", "set", "project_name", "Custom File"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(custom.read_text(encoding="utf-8"))["project_name"] == "Custom File"


def test_status_reports_config_provenance(repo_workspace: Path) -> None:
    result = CliRunner().invoke(main, ["status"])

    assert result.exit_code == 0, result.output
    assert "Config File" in result.output
    assert "Env Overrides" in result.output
