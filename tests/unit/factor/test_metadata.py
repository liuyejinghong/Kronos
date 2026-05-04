"""Unit tests for factor metadata hash and version isolation."""

from __future__ import annotations

from kronos.factor.materialize import feature_partition_path
from kronos.factor.registry import compute_params_hash


class TestParamsHash:
    def test_hash_uses_sorted_keys(self) -> None:
        left = compute_params_hash({"window": 5, "lookback": 20})
        right = compute_params_hash({"lookback": 20, "window": 5})
        assert left == right

    def test_hash_is_12_chars(self) -> None:
        assert len(compute_params_hash({"lookback": 20})) == 12


class TestVersionIsolation:
    def test_same_metadata_different_versions_write_to_distinct_paths(self, tmp_path) -> None:
        metadata = {"lookback": 20}
        hash_v1 = compute_params_hash(metadata)
        hash_v2 = compute_params_hash(metadata)

        path_v1 = feature_partition_path(
            tmp_path,
            "cmo_momentum",
            "1.0.0",
            "1h",
            "BTCUSDT",
            2024,
            3,
        )
        path_v2 = feature_partition_path(
            tmp_path,
            "cmo_momentum",
            "1.1.0",
            "1h",
            "BTCUSDT",
            2024,
            3,
        )

        assert hash_v1 == hash_v2
        assert path_v1 != path_v2
        assert "/1.0.0/" in str(path_v1)
        assert "/1.1.0/" in str(path_v2)
