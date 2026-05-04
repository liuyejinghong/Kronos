"""Rebalance policy helpers."""

from __future__ import annotations


def should_rebalance(
    *,
    current_timestamp: int,
    last_rebalance_timestamp: int | None,
    rebalance_frequency_ms: int,
) -> bool:
    """Return whether the allocator should issue a new target portfolio."""
    if last_rebalance_timestamp is None:
        return True
    return (current_timestamp - last_rebalance_timestamp) >= rebalance_frequency_ms
