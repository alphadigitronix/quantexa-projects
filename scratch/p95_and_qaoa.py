import json, pandas as pd, numpy as np, ast
from scipy import stats

raw_df = pd.read_csv('results/benchmark_runs_raw.csv')
bench = json.load(open('results/benchmark_results.json'))

print('=== P95 PAIRED DIFFS: Hybrid (BF) vs Fixed (tuned), ALL 8 REGIMES at 2s ===')
regimes = ['balanced', 'moderate_load', 'directional_moderate', 'incident_moderate',
           'shifting_demand', 'surge_moderate', 'rush_hour', 'surge_accident']

df_2s = raw_df[raw_df['lost_time_sec'] == 2]
p95_comparisons = 0
p95_results = []

for sc in regimes:
    df_sc = df_2s[df_2s['scenario'] == sc]
    h = df_sc[df_sc['controller'] == 'Hybrid Controller (Brute-Force)'].set_index('seed')['p95_wait_sec']
    ft = df_sc[df_sc['controller'] == 'Fixed (tuned)'].set_index('seed')['p95_wait_sec']
    common = h.index.intersection(ft.index)
    if len(common) >= 2:
        diffs = (ft.loc[common] - h.loc[common]).tolist()
        n = len(diffs)
        m = np.mean(diffs)
        se = stats.sem(diffs)
        t = stats.t.ppf(0.975, df=n-1)
        ci_l, ci_u = m - t*se, m + t*se
        is_tie = ci_l <= 0 <= ci_u
        status = 'TIE(CI spans 0)' if is_tie else ('H wins P95' if m > 0 else 'Fixed(t) wins P95')
        p95_comparisons += 1
        p95_results.append((sc, n, m, ci_l, ci_u, status))
        print(f'  {sc:<28} n={n}  delta={m:+.2f}s [{ci_l:+.2f},{ci_u:+.2f}]  {status}')

print(f'\nTotal P95 regime x metric comparisons: {p95_comparisons}')
print('\n=== QAOA Solves Provenance ===')
qaoa_rows = raw_df[raw_df['ctrl_key'] == 'hybrid_qaoa']
print(f'Total QAOA rows in raw CSV: {len(qaoa_rows)}')
print(f'Controllers: {qaoa_rows["controller"].unique().tolist()}')
print(f'Seeds: {sorted(qaoa_rows["seed"].unique().tolist())}')
print(f'Regimes: {sorted(qaoa_rows["scenario"].unique().tolist())}')

# Parse qaoa_ratios lists
total_solves = 0
total_wall = 0
raw_ratios = []
polish_ratios = []
for _, row in qaoa_rows.iterrows():
    try:
        ratios = ast.literal_eval(row['qaoa_ratios']) if isinstance(row['qaoa_ratios'], str) else []
    except Exception:
        ratios = []
    if row['controller'] == 'Hybrid (QAOA Raw, 5 seeds)':
        raw_ratios.extend(ratios)
    else:
        polish_ratios.extend(ratios)
    total_solves += len(ratios)

print(f'\nTotal individual QAOA solves (from qaoa_ratios lists): {total_solves}')
print(f'  Raw variant: {len(raw_ratios)} solves, mean ratio={np.mean(raw_ratios):.4f}' if raw_ratios else '  Raw: 0 solves')
print(f'  Polish variant: {len(polish_ratios)} solves, mean ratio={np.mean(polish_ratios):.4f}' if polish_ratios else '  Polish: 0 solves')

# Check ablation n_solves
ablation = json.load(open('results/ablation_study.json'))
print('\nAblation n_solves per regime (from ablation_study.json):')
for sc, q in ablation['qaoa_quality'].items():
    print(f'  {sc}: n_solves={q["total_optimizations_sampled"]}, ratio={q["mean_approximation_ratio"]:.4f}, exact_hit={q["exact_optimum_hit_rate"]:.4f}')
