"""Unit tests for structured candidate factor hypotheses."""

from __future__ import annotations

from kronos.factor.candidates import list_candidate_factors


class TestCandidateFactors:
    def test_legacy_candidates_are_structured(self) -> None:
        candidates = list_candidate_factors()
        assert len(candidates) == 12
        assert candidates[0].initial_status == "candidate"

    def test_candidate_ids_are_unique(self) -> None:
        candidates = list_candidate_factors()
        ids = [candidate.candidate_id for candidate in candidates]
        assert len(ids) == len(set(ids))

    def test_candidates_cover_expected_families(self) -> None:
        families = {candidate.family for candidate in list_candidate_factors()}
        assert {"trend_momentum", "volatility_path", "volume_liquidity", "mean_reversion"} <= families

    def test_some_candidates_are_now_backed_by_implementations(self) -> None:
        mapped = {
            candidate.candidate_id: candidate.implementation_name
            for candidate in list_candidate_factors()
            if candidate.implementation_name is not None
        }
        assert len(mapped) == 12
        assert mapped["body_energy"] == "body_energy"
        assert mapped["signal_persistence_density"] == "signal_persistence_density"
        assert mapped["range_chop_filter"] == "range_chop_filter"
        assert mapped["band_position_conditioning"] == "band_position_conditioning"
        assert mapped["trend_pullback_tolerance"] == "trend_pullback_tolerance"
        assert mapped["trend_pullback_entry"] == "trend_pullback_entry"
        assert mapped["multi_timeframe_confirmation"] == "multi_timeframe_confirmation"
        assert mapped["volume_drought"] == "volume_drought"
        assert mapped["move_density"] == "move_density"
