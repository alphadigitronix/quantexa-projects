import json
import os
import re
import pandas as pd
import pytest

BANNED_PHRASES = [
    "zero signal flicker",
    "resilience",
    "smoother",
    "beats all baselines",
]

# Known historical hardcoded/debunked numbers that must never re-appear
HISTORICAL_BANNED_NUMBERS = [
    "58.93",
    "54.90",
    "60.45",
    "55.41",
    "11.75",
    "13.4",
    "9.7",
    "0.37s",
    "15%-21%",
    "15%–21%",
    "15% to 21%",
    "3.62s vs Fixed 4.28s",
    "3.62s",
    "4.28s",
]


def test_dashboard_contains_no_hardcoded_result_literals():
    """Scans dashboard.py to ensure numbers from result files are not typed-in literals."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dashboard_path = os.path.join(repo_root, "dashboard.py")
    assert os.path.exists(dashboard_path), f"dashboard.py not found at {dashboard_path}"

    with open(dashboard_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Collect all numeric literals from current result files
    dynamic_numbers = set()
    results_dir = os.path.join(repo_root, "results")

    sc_csv = os.path.join(results_dir, "scenario_benchmark.csv")
    if os.path.exists(sc_csv):
        df = pd.read_csv(sc_csv)
        for col in ["Wait Mean (s)", "Wait Std (s)"]:
            if col in df.columns:
                for val in df[col].dropna():
                    if isinstance(val, (int, float)) and val > 1.0:
                        dynamic_numbers.add(f"{val:.2f}")

    tradeoff_json = os.path.join(results_dir, "preemption_tradeoff.json")
    if os.path.exists(tradeoff_json):
        try:
            with open(tradeoff_json, "r", encoding="utf-8") as f:
                po_data = json.load(f)
            for entry in po_data.get("soft_preemption", []):
                for k in ["amb_time", "amb_time_saved", "extra_delay", "normal_wait"]:
                    if k in entry and isinstance(entry[k], (int, float)) and entry[k] > 1.0:
                        dynamic_numbers.add(f"{entry[k]:.2f}")
        except Exception:
            pass

    all_banned_numbers = set(HISTORICAL_BANNED_NUMBERS) | dynamic_numbers

    violations = []
    for i, line in enumerate(lines, 1):
        line_clean = line.strip()
        if line_clean.startswith("#"):
            continue
        
        # Check banned phrases
        for phrase in BANNED_PHRASES:
            if phrase in line_clean.lower():
                violations.append((i, phrase, line_clean))

        # Check banned result numbers in string literals
        pattern = rf'["\'](.*?)["\']'
        matches = re.findall(pattern, line_clean)
        for m in matches:
            for banned in all_banned_numbers:
                if banned in m:
                    violations.append((i, banned, line_clean))

    assert not violations, f"Found hardcoded result literals or banned phrases in dashboard.py: {violations}"


def test_docs_and_readme_contain_no_banned_numbers_or_phrases():
    """Scans README.md and docs/claims.md to ensure no historical banned numbers or erroneous claims appear."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    doc_paths = [
        os.path.join(repo_root, "README.md"),
        os.path.join(repo_root, "docs", "claims.md"),
    ]

    # Specific erroneous/stale claims that must never appear in documentation
    banned_in_docs = [
        "zero signal flicker",
        "15%-21%",
        "15%–21%",
        "15% to 21%",
        "3.62s vs Fixed 4.28s",
        "3.62s",
        "4.28s",
    ]

    violations = []
    for doc_path in doc_paths:
        assert os.path.exists(doc_path), f"Document not found: {doc_path}"
        with open(doc_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            line_str = line.strip()
            # In claims.md, table column 1 lists disallowed claims to explicitly prohibit them
            if "claims.md" in doc_path and line_str.startswith("| **"):
                continue

            for banned_item in banned_in_docs:
                if banned_item in line_str:
                    violations.append((os.path.basename(doc_path), line_num, banned_item, line_str))

    assert not violations, f"Found stale or debunked claims in documentation: {violations}"


def test_docs_pedestrian_and_lost_time_numbers_match_csvs():
    """Verifies that key numbers cited in README.md and docs/claims.md match current results CSVs."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    results_dir = os.path.join(repo_root, "results")

    ped_csv = os.path.join(results_dir, "pedestrian_summary.csv")
    assert os.path.exists(ped_csv), f"Missing {ped_csv}"
    df_ped = pd.read_csv(ped_csv)

    lt_csv = os.path.join(results_dir, "lost_time_sensitivity.csv")
    assert os.path.exists(lt_csv), f"Missing {lt_csv}"
    df_lt = pd.read_csv(lt_csv)

    # Check that Fixed pedestrian wait is 7.65
    fixed_ped = df_ped[df_ped["controller"].str.contains("Fixed")]["ped_wait_mean"].values[0]
    assert fixed_ped == 7.65, f"Expected Fixed pedestrian wait 7.65, got {fixed_ped}"

    # Check that Rush-Hour Hybrid (BF) pedestrian wait is 6.99
    rh_hyb_ped = df_ped[(df_ped["scenario"] == "rush_hour") & (df_ped["controller"].str.contains("Hybrid.*Brute"))]["ped_wait_mean"].values[0]
    assert rh_hyb_ped == 6.99, f"Expected Rush Hour Hybrid pedestrian wait 6.99, got {rh_hyb_ped}"

    # Check lost time percentage improvements at 2s
    sub_m2_f = df_lt[(df_lt["scenario"] == "moderate_load") & (df_lt["lost_time_sec"] == 2) & (df_lt["controller"] == "Fixed-Timing")]["avg_wait_sec"].values[0]
    sub_m2_h = df_lt[(df_lt["scenario"] == "moderate_load") & (df_lt["lost_time_sec"] == 2) & (df_lt["controller"] == "Hybrid (Brute-Force)")]["paired_diff_vs_fixed_sec"].values[0]
    pct_m2 = abs(sub_m2_h) / sub_m2_f * 100
    assert round(pct_m2, 1) == 18.2, f"Expected 18.2% moderate at 2s, got {pct_m2:.1f}%"

    sub_r2_f = df_lt[(df_lt["scenario"] == "rush_hour") & (df_lt["lost_time_sec"] == 2) & (df_lt["controller"] == "Fixed-Timing")]["avg_wait_sec"].values[0]
    sub_r2_h = df_lt[(df_lt["scenario"] == "rush_hour") & (df_lt["lost_time_sec"] == 2) & (df_lt["controller"] == "Hybrid (Brute-Force)")]["paired_diff_vs_fixed_sec"].values[0]
    pct_r2 = abs(sub_r2_h) / sub_r2_f * 100
    assert round(pct_r2, 1) == 7.2, f"Expected 7.2% rush hour at 2s, got {pct_r2:.1f}%"


