import json

ablation = json.load(open('results/ablation_study.json'))
tuned = json.load(open('results/tuned_parameters.json'))
sw_2s = tuned['all_sweeps']['lost_time_2s_headline']

print('Inferred reopt from n_solves:')
for sc, q in ablation['qaoa_quality'].items():
    n = q['total_optimizations_sampled']
    per_run = n / 10  # 5 seeds x 2 variants (raw+polish)
    reopt = 600 / per_run if per_run > 0 else 0
    print(f'  {sc}: total_solves={n}, per_run={per_run:.0f}, implied_reopt={reopt:.0f}s')

print()
print('Tuned reopt_interval_sec from lost_time_2s_headline:')
ht = sw_2s.get('hybrid_tuned', {})
for sc in ['balanced','moderate_load','directional_moderate','incident_moderate',
           'shifting_demand','surge_moderate','rush_hour','surge_accident']:
    h = ht.get(sc, {})
    reopt = h.get('reopt_interval_sec', '?')
    wswitch = h.get('w_switch', '?')
    wtc = h.get('w_throughput_coupling', '?')
    print(f'  {sc}: reopt={reopt}s  w_switch={wswitch}  w_tc={wtc}')
