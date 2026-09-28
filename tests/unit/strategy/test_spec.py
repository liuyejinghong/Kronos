"""Unit tests for the frozen StrategySpec protocol (P01)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from kronos.strategy.spec import (
    TEMPLATE_VERSION,
    VARIANT_LABEL_ZH,
    PositionPolicy,
    StrategySpec,
    VariantParams,
    compute_spec_hash,
    derive_revision_id,
    make_revision,
    spec_identity_content,
)


def spec_content(**overrides: Any) -> dict[str, Any]:
    """Minimal valid StrategySpec content; identity fields auto-derive."""
    content: dict[str, Any] = {
        "symbols": ["BTCUSDT"],
        "signal_timeframe": "15m",
        "params": {"atr_period": 14, "volatility_multiplier": 1.0},
    }
    content.update(overrides)
    return content


class TestStrategySpecValidation:
    def test_rejects_unknown_field_and_names_it(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            StrategySpec.model_validate(spec_content(bogus_field=1))
        assert "bogus_field" in str(excinfo.value)

    def test_rejects_unknown_nested_params_field_and_names_it(self) -> None:
        content = spec_content()
        assert isinstance(content["params"], dict)
        content["params"]["volatility_multipliers"] = 1.0
        with pytest.raises(ValidationError) as excinfo:
            StrategySpec.model_validate(content)
        assert "volatility_multipliers" in str(excinfo.value)

    def test_symbols_normalized_and_deduped(self) -> None:
        spec = StrategySpec.model_validate(
            spec_content(symbols=["btcusdt", " BTCUSDT ", "ethusdt", "ETHUSDT"])
        )
        assert spec.symbols == ["BTCUSDT", "ETHUSDT"]

    def test_rejects_more_than_three_distinct_symbols(self) -> None:
        with pytest.raises(ValidationError, match="at most 3"):
            StrategySpec.model_validate(
                spec_content(symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
            )

    def test_rejects_empty_symbols(self) -> None:
        with pytest.raises(ValidationError, match="at least one symbol"):
            StrategySpec.model_validate(spec_content(symbols=[]))

    def test_rejects_invalid_symbol_format(self) -> None:
        with pytest.raises(ValidationError, match="invalid: \\['BTC-USDT!'\\]"):
            StrategySpec.model_validate(spec_content(symbols=["BTC-USDT!"]))

    def test_signal_timeframe_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            StrategySpec.model_validate(spec_content(signal_timeframe="5m"))
        for timeframe in ("15m", "1h"):
            spec = StrategySpec.model_validate(spec_content(signal_timeframe=timeframe))
            assert spec.signal_timeframe == timeframe  # type: ignore[comparison-overlap]

    def test_execution_timeframe_must_be_1m_for_next_1m_open_fill(self) -> None:
        with pytest.raises(ValidationError, match="execution_timeframe"):
            StrategySpec.model_validate(spec_content(execution_timeframe="5m"))

    def test_invalid_params_rejected(self) -> None:
        bad_params = [
            {"atr_period": 1},
            {"atr_period": 1001},
            {"volatility_multiplier": 0.0},
            {"volatility_multiplier": 20.5},
        ]
        for params in bad_params:
            with pytest.raises(ValidationError):
                StrategySpec.model_validate(spec_content(params=params))

    def test_equity_fraction_bounds(self) -> None:
        with pytest.raises(ValidationError):
            StrategySpec.model_validate(
                spec_content(position_policy=PositionPolicy(equity_fraction=0.0))
            )
        with pytest.raises(ValidationError):
            StrategySpec.model_validate(
                spec_content(position_policy=PositionPolicy(equity_fraction=1.5))
            )
        spec = StrategySpec.model_validate(
            spec_content(position_policy=PositionPolicy(equity_fraction=0.5))
        )
        assert spec.position_policy.equity_fraction == 0.5

    def test_template_version_and_variant_label_frozen_defaults(self) -> None:
        spec = StrategySpec.model_validate(spec_content())
        assert spec.template_version == TEMPLATE_VERSION == "kronos_threshold_v1"
        assert spec.variant_label_zh == VARIANT_LABEL_ZH == "Kronos 变体"
        with pytest.raises(ValidationError, match="template_version is frozen"):
            StrategySpec.model_validate(spec_content(template_version="r_breaker_classic"))

    def test_cost_policy_id_pinned(self) -> None:
        spec = StrategySpec.model_validate(spec_content())
        assert spec.cost_policy_id == "default_taker"
        with pytest.raises(ValidationError, match="cost_policy_id is frozen"):
            StrategySpec.model_validate(spec_content(cost_policy_id="vip_maker"))

    def test_created_at_must_be_utc_iso(self) -> None:
        spec = StrategySpec.model_validate(spec_content(created_at="2026-09-28T00:00:00Z"))
        assert spec.created_at == "2026-09-28T00:00:00Z"
        with pytest.raises(ValidationError, match="UTC"):
            StrategySpec.model_validate(spec_content(created_at="2026-09-28T08:00:00+08:00"))
        with pytest.raises(ValidationError, match="ISO-8601"):
            StrategySpec.model_validate(spec_content(created_at="not-a-date"))

    def test_tampered_spec_hash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="spec_hash does not match"):
            StrategySpec.model_validate(spec_content(spec_hash="0" * 64))

    def test_tampered_revision_id_rejected(self) -> None:
        content = spec_content(strategy_revision_id="ffffffffffff")
        with pytest.raises(ValidationError, match="strategy_revision_id does not match"):
            StrategySpec.model_validate(content)


class TestSpecIdentity:
    def test_identity_fields_auto_derive(self) -> None:
        spec = StrategySpec.model_validate(spec_content())
        assert spec.spec_hash
        assert len(spec.spec_hash) == 64
        assert spec.strategy_revision_id == spec.spec_hash[:12]
        assert spec.parent_revision_id is None
        assert spec.created_at.endswith("Z")

    def test_same_content_same_hash_and_revision_identity(self) -> None:
        first = StrategySpec.model_validate(spec_content(created_at="2026-01-01T00:00:00Z"))
        second = StrategySpec.model_validate(spec_content(created_at="2027-06-01T12:00:00Z"))
        assert first.created_at != second.created_at
        assert first.spec_hash == second.spec_hash
        assert first.strategy_revision_id == second.strategy_revision_id

    def test_different_multiplier_produces_different_hash_and_revision(self) -> None:
        low = StrategySpec.model_validate(
            spec_content(params={"atr_period": 14, "volatility_multiplier": 1.0})
        )
        high = StrategySpec.model_validate(
            spec_content(params={"atr_period": 14, "volatility_multiplier": 2.0})
        )
        assert low.spec_hash != high.spec_hash
        assert low.strategy_revision_id != high.strategy_revision_id

    def test_compute_spec_hash_is_deterministic_hex(self) -> None:
        content = spec_identity_content(StrategySpec.model_validate(spec_content()))
        first = compute_spec_hash(content)
        second = compute_spec_hash(dict(reversed(list(content.items()))))
        assert first == second
        assert len(first) == 64
        int(first, 16)  # must be hex

    def test_spec_identity_content_excludes_only_identity_fields(self) -> None:
        spec = StrategySpec.model_validate(spec_content())
        content = spec_identity_content(spec)
        assert set(content) == {
            "template_version",
            "variant_label_zh",
            "symbols",
            "signal_timeframe",
            "execution_timeframe",
            "params",
            "position_policy",
            "fill_policy",
            "cost_policy_id",
        }

    def test_derive_revision_id_root_and_child_rules(self) -> None:
        parent_hash = "a" * 64
        child_hash = "b" * 64
        parent_id = derive_revision_id(parent_hash, None)
        child_id = derive_revision_id(child_hash, parent_id)
        assert parent_id == "a" * 12
        assert child_id == f"{parent_id}-{'b' * 8}"

    def test_same_content_under_different_parents_shares_hash_not_id(self) -> None:
        parent_a = StrategySpec.model_validate(spec_content())
        parent_b = make_revision(parent_a, {"atr_period": 30})
        content_kwargs = {"params": {"atr_period": 14, "volatility_multiplier": 2.0}}
        child_a = StrategySpec.model_validate(
            spec_content(parent_revision_id=parent_a.strategy_revision_id, **content_kwargs)
        )
        child_b = StrategySpec.model_validate(
            spec_content(parent_revision_id=parent_b.strategy_revision_id, **content_kwargs)
        )
        assert child_a.spec_hash == child_b.spec_hash  # lineage is not hashed
        assert child_a.strategy_revision_id != child_b.strategy_revision_id
        assert child_a.parent_revision_id == parent_a.strategy_revision_id
        assert child_b.parent_revision_id == parent_b.strategy_revision_id


class TestMakeRevision:
    def test_child_overrides_params_and_keeps_rest(self) -> None:
        parent = StrategySpec.model_validate(
            spec_content(symbols=["BTCUSDT", "ETHUSDT"], signal_timeframe="1h")
        )
        child = make_revision(parent, {"volatility_multiplier": 3.0})
        assert child.params.volatility_multiplier == 3.0
        assert child.params.atr_period == parent.params.atr_period
        assert child.symbols == parent.symbols
        assert child.signal_timeframe == parent.signal_timeframe
        assert child.template_version == TEMPLATE_VERSION
        assert child.parent_revision_id == parent.strategy_revision_id
        assert child.strategy_revision_id == f"{parent.strategy_revision_id}-{child.spec_hash[:8]}"

    def test_parent_is_untouched(self) -> None:
        parent = StrategySpec.model_validate(spec_content())
        before = parent.model_dump_json()
        make_revision(parent, {"atr_period": 30})
        assert parent.model_dump_json() == before

    def test_unknown_param_name_rejected_with_name(self) -> None:
        parent = StrategySpec.model_validate(spec_content())
        with pytest.raises(ValueError, match="leverage"):
            make_revision(parent, {"leverage": 10})

    def test_out_of_range_value_rejected(self) -> None:
        parent = StrategySpec.model_validate(spec_content())
        with pytest.raises(ValidationError):
            make_revision(parent, {"volatility_multiplier": 99.0})

    def test_identity_override_still_creates_new_revision(self) -> None:
        parent = StrategySpec.model_validate(spec_content())
        child = make_revision(
            parent, {"volatility_multiplier": parent.params.volatility_multiplier}
        )
        assert child.spec_hash == parent.spec_hash
        assert child.strategy_revision_id != parent.strategy_revision_id
        assert child.parent_revision_id == parent.strategy_revision_id

    def test_chained_revisions_accumulate_suffixes(self) -> None:
        root = StrategySpec.model_validate(spec_content())
        child = make_revision(root, {"atr_period": 30})
        grandchild = make_revision(child, {"atr_period": 50})
        assert grandchild.strategy_revision_id.startswith(f"{child.strategy_revision_id}-")
        assert grandchild.parent_revision_id == child.strategy_revision_id

    def test_variant_params_defaults(self) -> None:
        params = VariantParams.model_validate({})
        assert params.atr_period == 14
        assert params.volatility_multiplier == 1.0
