import json, pandas as pd, numpy as np

bench = json.load(open('results/benchmark_results.json'))
winner_2s = json.load(open('results/winner_table.json'))
winner_3s = json.load(open('results/winner_table_3s.json'))
ablation = json.load(open('results/ablation_study.json'))
lt_df = pd.read_csv('results/lost_time_sensitivity.csv')
raw_df = pd.read_csv('results/benchmark_runs_raw.csv')

print('=== REGIMES ===')
print([k for k in bench.keys() if k != 'headline_3s'])

print('\n=== moderate_load vs incident_moderate (2s headline) ===')
for regime in ['moderate_load', 'incident_moderate']:
    d = bench[regime]['controllers']
    fixed = d.get('Fixed-Timing Baseline', {}).get('avg_wait_mean', 'N/A')
    fixed_t = d.get('Fixed (tuned)', {}).get('avg_wait_mean', 'N/A')
    rb = d.get('Rule-Based (Longest Queue)', {}).get('avg_wait_mean', 'N/A')
    mp = d.get('Max-Pressure (tuned)', {}).get('avg_wait_mean', 'N/A')
    hyb = d.get('Hybrid Controller (Brute-Force)', {}).get('avg_wait_mean', 'N/A')
    print(f'  {regime}: Fixed={fixed}s  FixedT={fixed_t}s  RB={rb}s  MP={mp}s  Hybrid={hyb}s')

print('\n=== QAOA Quality ===')
for regime, q in ablation['qaoa_quality'].items():
    print(f'  {regime}: ratio={q["mean_approximation_ratio"]:.4f}, exact_hit={q["exact_optimum_hit_rate"]:.4f}, n_solves={q["total_optimizations_sampled"]}')

print('\n=== QAOA rows in raw CSV ===')
qaoa_rows = raw_df[raw_df['ctrl_key'] == 'hybrid_qaoa']
print(f'  Total QAOA rows: {len(qaoa_rows)}')
print(f'  Controllers: {qaoa_rows["controller"].unique().tolist()}')
print(f'  Seeds: {sorted(qaoa_rows["seed"].unique().tolist())}')
print(f'  Regimes: {sorted(qaoa_rows["scenario"].unique().tolist())}')

print('\n=== QAOA raw wall-time per solve ===')
if 'qaoa_wall_time_mean' in qaoa_rows.columns:
    print(f'  mean qaoa_wall_time_mean: {qaoa_rows["qaoa_wall_time_mean"].mean():.4f}s')
else:
    print(f'  Columns with qaoa: {[c for c in raw_df.columns if "qaoa" in c.lower()]}')
    print(f'  All columns: {list(raw_df.columns)}')
