"""Machine-executable testnet autonomy policy schema (v0.5.0 package P05).

Codifies the autonomy boundary from DECISIONS.md D-20260927-015 /
D-20260927-016 / D-20260928-002: research and testnet actions inside this
policy need no per-step approval; live execution keeps a non-inferable human
gate. The policy file lives at ``configs/policies/testnet_autonomy.toml`` and
takes effect in v0.5.0 phases 2-3 (v0.5.0 itself holds no trading authority).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kronos.common.errors import ConfigError

DEFAULT_POLICY_PATH: Final[str] = "configs/policies/testnet_autonomy.toml"


class LiveTradingGate(BaseModel):
    """Live-execution switch; enabled only together with an explicit human gate."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    human_gate: Literal["explicit_per_session"] = Field(
        description="Non-inferable human gate: live orders require explicit per-session approval.",
    )


class TestnetAutonomyPolicy(BaseModel):
    """Schema for ``configs/policies/testnet_autonomy.toml``.

    Within these bounds (capability, notional cap, daily order cap, symbol
    allowlist, audit requirements) the resident agent acts without per-step
    approval. Anything outside the policy - including any live execution -
    is not autonomous.
    """

    model_config = ConfigDict(extra="forbid")

    capabilities: list[str] = Field(min_length=1)
    max_notional_usdt: float = Field(gt=0.0)
    max_orders_per_day: int = Field(ge=1)
    allowed_symbols: list[str] = Field(min_length=1)
    environment: Literal["testnet_only"]
    audit: list[str] = Field(min_length=1)
    live_trading: LiveTradingGate

    @model_validator(mode="after")
    def _live_requires_explicit_human_gate(self) -> TestnetAutonomyPolicy:
        # D-20260928-002: only live execution retains a non-inferable human
        # gate; enabling it without the explicit per-session gate is invalid.
        if self.live_trading.enabled and self.live_trading.human_gate != "explicit_per_session":
            raise ValueError(
                "live_trading.enabled=true requires the explicit per-session human gate "
                "(human_gate='explicit_per_session')"
            )
        return self

    def live_enabled(self) -> bool:
        """Whether live execution is switched on (must stay False in v0.5.0)."""
        return self.live_trading.enabled


def load_testnet_policy(path: str | Path) -> TestnetAutonomyPolicy:
    """Load and validate one TOML testnet autonomy policy."""
    policy_path = Path(path).expanduser()
    try:
        with policy_path.open("rb") as file:
            raw: dict[str, Any] = tomllib.load(file)
    except FileNotFoundError as exc:
        raise ConfigError(f"Testnet policy file not found: {policy_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {policy_path}: {exc}") from exc
    return TestnetAutonomyPolicy.model_validate(raw)
