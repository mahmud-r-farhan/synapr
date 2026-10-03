"""Unit tests for configuration loading and validation."""

from pathlib import Path

from synapr.config import SynaprConfig


def test_default_config() -> None:
    """Verify default configuration values."""
    cfg = SynaprConfig()
    assert cfg.gateway.default_provider == "mock"
    assert cfg.worktree.worktree_root == ".worktrees"
    assert cfg.perception.enabled is True
    assert cfg.pipeline.auto_test is True


def test_config_save_and_load(tmp_path: Path) -> None:
    """Test saving and loading configuration from disk."""
    cfg_file = tmp_path / "synapr.config.json"
    cfg = SynaprConfig()
    cfg.gateway.default_provider = "ollama"
    cfg.worktree.base_branch = "develop"
    cfg.save(str(cfg_file))

    assert cfg_file.exists()
    loaded = SynaprConfig.load(str(cfg_file))
    assert loaded.gateway.default_provider == "ollama"
    assert loaded.worktree.base_branch == "develop"


def test_config_env_overrides(monkeypatch) -> None:
    """Test environment variable overrides."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://remote-ollama:11434")

    cfg = SynaprConfig.load()
    assert cfg.gateway.openai_api_key == "test-key-12345"
    assert cfg.gateway.ollama_base_url == "http://remote-ollama:11434"
