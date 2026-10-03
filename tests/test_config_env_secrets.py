"""Tests for secret redaction and safe partial configuration updates."""

import pytest
from pydantic import ValidationError

from synapr.config import SECRET_MASK, SynaprConfig, redact_secret


def test_redaction_keeps_last_four_characters() -> None:
    assert redact_secret(None) is None
    assert redact_secret("abc") == SECRET_MASK
    assert redact_secret("sk-super-secret-1234").endswith("1234")


def test_to_dict_redacts_secrets() -> None:
    cfg = SynaprConfig()
    cfg.gateway.openai_api_key = "sk-super-secret-1234"

    assert cfg.to_dict(redact=True)["gateway"]["openai_api_key"].startswith(SECRET_MASK)
    assert cfg.to_dict()["gateway"]["openai_api_key"] == "sk-super-secret-1234"
    assert cfg.secret_status()["gateway.openai_api_key"] is True


def test_apply_updates_ignores_masked_secret() -> None:
    cfg = SynaprConfig()
    cfg.gateway.openai_api_key = "sk-super-secret-1234"
    masked = cfg.to_dict(redact=True)

    updated = cfg.apply_updates({"gateway": {"openai_api_key": masked["gateway"]["openai_api_key"]}})

    assert updated.gateway.openai_api_key == "sk-super-secret-1234"


def test_apply_updates_can_clear_a_secret() -> None:
    cfg = SynaprConfig()
    cfg.gateway.openai_api_key = "sk-super-secret-1234"

    assert cfg.apply_updates({"gateway": {"openai_api_key": ""}}).gateway.openai_api_key is None


def test_apply_updates_validates() -> None:
    with pytest.raises(ValidationError):
        SynaprConfig().apply_updates({"gateway": {"temperature": 11}})


def test_apply_updates_is_a_deep_merge() -> None:
    cfg = SynaprConfig()
    updated = cfg.apply_updates({"gateway": {"planner_model": "x"}})

    assert updated.gateway.planner_model == "x"
    assert updated.gateway.arbiter_model == cfg.gateway.arbiter_model
