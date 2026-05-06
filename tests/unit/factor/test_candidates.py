"""Unit tests for candidate factor registry."""

from __future__ import annotations

from kronos.factor.candidates import (
    CandidateFactorSpec,
    candidate_store_path,
    clear_candidates,
    list_candidate_factors,
    register_candidate,
)


def _sample_candidate(candidate_id: str, rank: int, impl: str | None = None) -> CandidateFactorSpec:
    return CandidateFactorSpec(
        candidate_id=candidate_id,
        family="trend_momentum",
        title=f"测试策略 {candidate_id}",
        source_strategies=("BTCUSDT",),
        migration_rank=rank,
        implementation_name=impl,
    )


class TestCandidateRegistry:
    def setup_method(self) -> None:
        clear_candidates()

    def teardown_method(self) -> None:
        clear_candidates()

    def test_empty_by_default(self) -> None:
        assert list_candidate_factors() == []

    def test_register_and_list(self) -> None:
        register_candidate(_sample_candidate("strat_a", 1))
        register_candidate(_sample_candidate("strat_b", 2))
        result = list_candidate_factors()
        assert len(result) == 2
        assert result[0].candidate_id == "strat_a"
        assert result[1].candidate_id == "strat_b"

    def test_sorted_by_migration_rank(self) -> None:
        register_candidate(_sample_candidate("b", 10))
        register_candidate(_sample_candidate("a", 1))
        result = list_candidate_factors()
        assert result[0].migration_rank == 1
        assert result[1].migration_rank == 10

    def test_candidate_ids_unique(self) -> None:
        register_candidate(_sample_candidate("a", 1))
        register_candidate(_sample_candidate("b", 2))
        ids = [c.candidate_id for c in list_candidate_factors()]
        assert len(ids) == len(set(ids))

    def test_default_origin_is_user(self) -> None:
        spec = CandidateFactorSpec("test", "trend_momentum", "Test", ("BTCUSDT",), 1)
        assert spec.origin == "user"

    def test_lifecycle_state_defaults_to_none(self) -> None:
        spec = CandidateFactorSpec("test", "trend_momentum", "Test", ("BTCUSDT",), 1)
        assert spec.lifecycle_state is None

    def test_clear_candidates(self) -> None:
        register_candidate(_sample_candidate("a", 1))
        clear_candidates()
        assert list_candidate_factors() == []

    def test_registry_uses_isolated_test_path(self, tmp_path) -> None:
        register_candidate(_sample_candidate("isolated", 1))

        assert candidate_store_path() == tmp_path / ".kronos" / "candidates.json"
        assert candidate_store_path().exists()
