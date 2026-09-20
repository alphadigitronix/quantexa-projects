import json, pandas as pd, numpy as np
from scipy import stats

bench = json.load(open('results/benchmark_results.json'))
winner_2s = json.load(open('results/winner_table.json'))
winner_3s = json.load(open('results/winner_table_3s.json'))
ablation = json.load(open('results/ablation_study.json'))
lt_df = pd.read_csv('results/lost_time_sensitivity.csv')
raw_df = pd.read_csv('results/benchmark_runs_raw.csv')

# ===== PAIRED DIFFS FOR ALL 8 REGIMES AT 2s AND 3s =====
print('=== PAIRED DIFFS: Hybrid (BF) vs Fixed (tuned) and RuleBased (tuned), 2s and 3s ===')
regimes = ['balanced', 'moderate_load', 'directional_moderate', 'incident_moderate',
           'shifting_demand', 'surge_moderate', 'rush_hour', 'surge_accident']

for lt in [2, 3]:
    if lt == 2:
        df_sub = raw_df[raw_df['lost_time_sec'] == lt]
    else:
        df_sub = raw_df[raw_df['lost_time_sec'] == lt]
    print(f'\n--- Lost Time = {lt}s ---')
    print(f'{"Regime":<28} {"vs Fixed(t) Delta":>18} {"95% CI":>22} {"vs RB(t) Delta":>16} {"95% CI":>22}')
    for sc in regimes:
        df_sc = df_sub[df_sub['scenario'] == sc]
        h = df_sc[df_sc['controller'] == 'Hybrid Controller (Brute-Force)'].set_index('seed')['avg_wait_sec']
        ft = df_sc[df_sc['controller'] == 'Fixed (tuned)'].set_index('seed')['avg_wait_sec']
        rb = df_sc[df_sc['controller'].str.contains('Rule-Based', na=False)].set_index('seed')['avg_wait_sec']

        # vs Fixed tuned
        common_ft = h.index.intersection(ft.index)
        if len(common_ft) >= 2:
            diffs_ft = (ft.loc[common_ft] - h.loc[common_ft]).tolist()
            n = len(diffs_ft)
            m = np.mean(diffs_ft)
            se = stats.sem(diffs_ft)
            t = stats.t.ppf(0.975, df=n-1)
            ci_l, ci_u = m - t*se, m + t*se
            ft_str = f'{m:+.2f}s [{ci_l:+.2f},{ci_u:+.2f}]'
        else:
            ft_str = 'N/A'

        # vs RuleBased tuned
        common_rb = h.index.intersection(rb.index)
        if len(common_rb) >= 2:
            diffs_rb = (rb.loc[common_rb] - h.loc[common_rb]).tolist()
            n = len(diffs_rb)
            m = np.mean(diffs_rb)
            se = stats.sem(diffs_rb)
            t = stats.t.ppf(0.975, df=n-1)
            ci_l, ci_u = m - t*se, m + t*se
            rb_str = f'{m:+.2f}s [{ci_l:+.2f},{ci_u:+.2f}]'
        else:
            rb_str = 'N/A'

        print(f'  {sc:<28} {ft_str:<40} {rb_str}')
