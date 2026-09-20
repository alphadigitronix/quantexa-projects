import json
bench = json.load(open('results/benchmark_results.json'))

for regime in ['balanced', 'moderate_load', 'directional_moderate']:
    d = bench[regime]['controllers']
    rb_keys = [k for k in d.keys() if 'rule' in k.lower() or 'Rule' in k]
    print(f'{regime}: Rule-Based keys: {rb_keys}')
    for k in rb_keys:
        val = d[k].get('avg_wait_mean', 'N/A')
        print(f'  {k}: avg_wait_mean={val}')

# Also check the generate_docs script to understand why RB shows 0.00
print()
print('All controller keys in balanced:')
for k in bench['balanced']['controllers'].keys():
    v = bench['balanced']['controllers'][k]
    print(f'  {k}: avg_wait_mean={v.get("avg_wait_mean","N/A")}')
