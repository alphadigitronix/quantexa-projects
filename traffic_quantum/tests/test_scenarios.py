"""Test suite for traffic scenario suite (Balanced, Rush-Hour 3x, Surge + Incident)."""

import pytest
from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.controllers.fixed import FixedController
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.network import RoadNetwork
from traffic_quantum.scenarios import SCENARIO_SPECS, run_scenario_trial


def test_scenario_specs_integrity():
    """Verify all 3 required scenarios are registered with valid specs."""
    assert "balanced" in SCENARIO_SPECS
    assert "rush_hour" in SCENARIO_SPECS
    assert "surge_accident" in SCENARIO_SPECS

    # Check rush_hour 3x ratio: W and E are 3x N and S
    rh = SCENARIO_SPECS["rush_hour"]
    assert rh.boundary_rates is not None
    assert rh.boundary_rates["W"] == pytest.approx(3 * rh.boundary_rates["N"])
    assert rh.boundary_rates["E"] == pytest.approx(3 * rh.boundary_rates["S"])

    # Check surge_accident has active accident edge
    sa = SCENARIO_SPECS["surge_accident"]
    assert sa.accident_edge == (1, 2)
    assert sa.accident_start == 50
    assert sa.accident_duration > 0


def test_scenario_trial_execution_and_metrics():
    """Verify single trial execution produces non-zero valid metrics across controllers."""
    for sc_id in ["balanced", "rush_hour", "surge_accident"]:
        res_fixed = run_scenario_trial(
            scenario_id=sc_id,
            ctrl_name="Fixed",
            ctrl_factory=lambda net: FixedController(net),
            seed=42,
            duration=30,
        )
        assert res_fixed["avg_wait_sec"] > 0
        assert res_fixed["throughput_cpm"] >= 0
        assert "total_switches" in res_fixed

        res_hybrid = run_scenario_trial(
            scenario_id=sc_id,
            ctrl_name="Hybrid",
            ctrl_factory=lambda net: HybridController(net, solver_mode="brute_force"),
            seed=42,
            duration=30,
        )
        assert res_hybrid["avg_wait_sec"] > 0
        assert res_hybrid["throughput_cpm"] >= 0
        assert "total_switches" in res_hybrid
