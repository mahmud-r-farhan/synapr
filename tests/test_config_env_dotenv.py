"""Tests for dotenv parsing, loading, and updates."""

import os
from pathlib import Path

import pytest

from synapr.config import SynaprConfig, load_env_file, parse_env_text, write_env_file


def test_parse_env_text_handles_quotes_exports_and_comments() -> None:
    parsed = parse_env_text(
        "\n".join(
            [
                "# comment",
                "export SYNAPR_PROVIDER='ollama'",
                'SYNAPR_PLANNER_MODEL="qwen2.5-coder:7b"',
                "EMPTY=",
                "not a pair",
            ]
        )
    )
    assert parsed["SYNAPR_PROVIDER"] == "ollama"
    assert parsed["SYNAPR_PLANNER_MODEL"] == "qwen2.5-coder:7b"
    assert parsed["EMPTY"] == ""
    assert "not a pair" not in parsed


def test_dotenv_file_is_loaded_by_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SYNAPR_PROVIDER=lmstudio\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg = SynaprConfig.load()

    assert cfg.gateway.default_provider == "lmstudio"
    assert cfg.meta.env_file == str((tmp_path / ".env").resolve())


def test_real_environment_beats_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SYNAPR_PROVIDER=lmstudio\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNAPR_PROVIDER", "vllm")

    assert SynaprConfig.load().gateway.default_provider == "vllm"


def test_write_env_file_updates_in_place(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("# header\nSYNAPR_PROVIDER=mock\nOTHER=keep\n", encoding="utf-8")

    write_env_file({"SYNAPR_PROVIDER": "ollama", "SYNAPR_UI_PORT": "9100"}, env_path)
    content = env_path.read_text(encoding="utf-8")

    assert "SYNAPR_PROVIDER=ollama" in content
    assert "OTHER=keep" in content
    assert "SYNAPR_UI_PORT=9100" in content
    assert "# header" in content
    assert content.count("SYNAPR_PROVIDER=") == 1


def test_write_env_file_removes_keys(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("SYNAPR_PROVIDER=ollama\nSYNAPR_UI_PORT=9100\n", encoding="utf-8")

    write_env_file({}, env_path, remove=["SYNAPR_PROVIDER"])

    content = env_path.read_text(encoding="utf-8")
    assert "SYNAPR_PROVIDER" not in content
    assert "SYNAPR_UI_PORT=9100" in content


def test_load_env_file_does_not_override_existing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("SYNAPR_PROVIDER=lmstudio\n", encoding="utf-8")
    monkeypatch.setenv("SYNAPR_PROVIDER", "groq")

    load_env_file(env_path)

    assert os.environ["SYNAPR_PROVIDER"] == "groq"


def test_load_env_file_missing_returns_empty(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "nope.env") == {}
