"""Unit tests for the machine-executable testnet autonomy policy (P05)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kronos.common.errors import ConfigError
from kronos.research.verdict.policy_schema import load_testnet_policy

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = REPO_ROOT / "configs" / "policies" / "testnet_autonomy.toml"


def test_load_repo_policy() -> None:
    policy = load_testnet_policy(POLICY_PATH)

    assert policy.environment == "testnet_only"
    assert policy.capabilities == ["paper_single_order"]
    assert policy.max_notional_usdt == 100.0
    assert policy.max_orders_per_day == 10
    assert policy.allowed_symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert policy.audit == ["client_order_id_ledger", "error_ledger", "report_artifact"]
    assert policy.live_trading.enabled is False
    assert policy.live_trading.human_gate == "explicit_per_session"
    assert policy.live_enabled() is False


def test_unknown_top_level_field_is_rejected(tmp_path: Path) -> None:
    text = POLICY_PATH.read_text(encoding="utf-8")
    tampered = text.replace("[live_trading]", "surprise = true\n\n[live_trading]")
    path = tmp_path / "tampered.toml"
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(ValidationError, match="surprise"):
        load_testnet_policy(path)


def test_live_enabled_tamper_still_loads_and_accessors_work(tmp_path: Path) -> None:
    """Flipping live_trading.enabled=true stays loadable: live remains behind
    the explicit per-session human gate, and the accessor must report True so
    callers can detect the switch deterministically."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    assert "enabled = false" in text
    path = tmp_path / "live_on.toml"
    path.write_text(text.replace("enabled = false", "enabled = true"), encoding="utf-8")

    policy = load_testnet_policy(path)

    assert policy.live_trading.enabled is True
    assert policy.live_trading.human_gate == "explicit_per_session"
    assert policy.live_enabled() is True


def test_live_enabled_requires_explicit_human_gate(tmp_path: Path) -> None:
    """D-20260928-002: enabling live without the explicit per-session human
    gate is invalid; the gate is non-inferable and cannot be dropped."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    tampered = "\n".join(
        line
        for line in text.replace("enabled = false", "enabled = true").splitlines()
        if not line.startswith("human_gate")
    )
    path = tmp_path / "live_no_gate.toml"
    path.write_text(tampered + "\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_testnet_policy(path)

    # Local import: the class name starts with "Test" and pytest would
    # otherwise try to collect the imported model as a test class.
    from kronos.research.verdict.policy_schema import TestnetAutonomyPolicy

    with pytest.raises(ValidationError):
        TestnetAutonomyPolicy.model_validate(
            {
                "capabilities": ["paper_single_order"],
                "max_notional_usdt": 100.0,
                "max_orders_per_day": 10,
                "allowed_symbols": ["BTCUSDT"],
                "environment": "testnet_only",
                "audit": ["client_order_id_ledger"],
                "live_trading": {"enabled": True, "human_gate": "trust_me"},
            }
        )


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_testnet_policy(tmp_path / "absent.toml")


def test_invalid_toml_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text("not [ valid toml", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_testnet_policy(path)
