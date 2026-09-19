"""Test comparing README stated configuration parameters against config.py."""

import os
import re
import pytest
from traffic_quantum.config import DEFAULT_CONFIG


def test_readme_parameters_match_config():
    """Validates that parameters documented in README.md match config.py."""
    readme_path = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")
    assert os.path.exists(readme_path), "README.md not found"

    with open(readme_path, "r", encoding="utf-8") as f:
        readme_text = f.read()

    # 1. Verify Re-optimization interval is stated as 10s (not old 25s)
    assert re.search(r"reopt_interval_sec.*?10", readme_text, re.IGNORECASE), (
        f"README should state reopt_interval_sec as {DEFAULT_CONFIG.hybrid.reopt_interval_sec}s"
    )

    # 2. Verify w_switch is stated as 1.0 (not old 2.5)
    assert re.search(r"w_switch.*?1\.0", readme_text, re.IGNORECASE), (
        f"README should state w_switch as {DEFAULT_CONFIG.qubo.w_switch}"
    )

    # 3. Verify w_coord is 0.2
    assert re.search(r"w_coord.*?0\.2", readme_text, re.IGNORECASE), (
        f"README should state w_coord as {DEFAULT_CONFIG.qubo.w_coord}"
    )

    # 4. Verify w_spillback is 0.5
    assert re.search(r"w_spillback.*?0\.5", readme_text, re.IGNORECASE), (
        f"README should state w_spillback as {DEFAULT_CONFIG.qubo.w_spillback}"
    )

    # 5. Verify w_queue is 1.0
    assert re.search(r"w_queue.*?1\.0", readme_text, re.IGNORECASE), (
        f"README should state w_queue as {DEFAULT_CONFIG.qubo.w_queue}"
    )

    # 6. Verify w_emergency is 50.0
    assert re.search(r"w_emergency.*?50\.0", readme_text, re.IGNORECASE), (
        f"README should state w_emergency as {DEFAULT_CONFIG.qubo.w_emergency}"
    )

    # 7. Verify QAOA p_layers is 2
    assert re.search(r"p_layers.*?2", readme_text, re.IGNORECASE), (
        f"README should state p_layers as {DEFAULT_CONFIG.qaoa.p_layers}"
    )

    # 8. Verify QAOA max_iterations is 35
    assert re.search(r"max_iterations.*?35", readme_text, re.IGNORECASE), (
        f"README should state max_iterations as {DEFAULT_CONFIG.qaoa.max_iterations}"
    )

    # 9. Verify shots is 1000
    assert re.search(r"shots.*?1000", readme_text, re.IGNORECASE), (
        f"README should state shots as {DEFAULT_CONFIG.qaoa.shots}"
    )

    # 10. Verify eta_threshold_sec is 45
    assert re.search(r"eta_threshold_sec.*?45", readme_text, re.IGNORECASE), (
        f"README should state eta_threshold_sec as {DEFAULT_CONFIG.emergency.eta_threshold_sec}"
    )

    # 11. Verify idle fuel rate is 0.8
    assert re.search(r"0\.8\s*L/h", readme_text, re.IGNORECASE), (
        f"README should state idle fuel rate as {DEFAULT_CONFIG.metrics.idle_fuel_rate_l_per_hr} L/hr"
    )

    # 12. Verify CO2 factor is 2.31
    assert re.search(r"2\.31\s*kg", readme_text, re.IGNORECASE), (
        f"README should state CO2 factor as {DEFAULT_CONFIG.metrics.co2_kg_per_l_petrol} kg"
    )

    # 13. Verify NO claim of a 2-second yellow interval exists in the simulator or conflict monitor description
    assert "2-second yellow interval" not in readme_text, (
        "README must not claim a 2-second yellow interval in the simulator"
    )
    assert "2-second yellow clearance interval" not in readme_text, (
        "README must not claim a 2-second yellow clearance interval in the simulator"
    )
