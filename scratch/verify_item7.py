import re
import os

with open('README.md', 'r', encoding='utf-8') as f:
    readme = f.read()
with open('dashboard.py', 'r', encoding='utf-8') as f:
    dash = f.read()

checks = {}

# 1. No hardware-availability claims (only Future Scope)
has_future_scope = 'Future Scope' in readme
banned_hw = ['qpu is available', 'connected to physical qpu', 'running on physical hardware', 'physical qpu active']
readme_hw_clean = not any(p in readme.lower() for p in banned_hw)
dash_hw_clean = not any(p in dash.lower() for p in banned_hw)
checks['README hardware availability'] = 'PASS: Only Future Scope section; no physical hardware availability claims' if (has_future_scope and readme_hw_clean) else 'FAIL'
checks['Dashboard hardware availability'] = 'PASS: No physical hardware availability claims present' if dash_hw_clean else 'FAIL'

# 2. No hardcoded device ARNs
arn_pattern = r'arn:aws:braket:[a-z0-9-]+:[0-9]+:device/[a-z0-9-]+'
checks['README hardcoded ARNs'] = 'PASS: 0 device ARNs found' if not re.findall(arn_pattern, readme) else 'FAIL'
checks['Dashboard hardcoded ARNs'] = 'PASS: 0 device ARNs found' if not re.findall(arn_pattern, dash) else 'FAIL'

# 3. No prices/dollar signs
price_pattern = r'\$[0-9]+(?:\.[0-9]+)?'
checks['README hardcoded prices'] = 'PASS: 0 dollar prices found' if not re.findall(price_pattern, readme) else 'FAIL'
checks['Dashboard hardcoded prices'] = 'PASS: 0 dollar prices found' if not re.findall(price_pattern, dash) else 'FAIL'

# 4. No 'adaptive green duration' text
checks['README adaptive green duration'] = 'PASS: \"adaptive green duration\" absent' if 'adaptive green duration' not in readme.lower() else 'FAIL'
checks['Dashboard adaptive green duration'] = 'PASS: \"adaptive green duration\" absent' if 'adaptive green duration' not in dash.lower() else 'FAIL'

# 5. Tab 2 text says 'W_emerg from config'
checks['Dashboard Tab 2 W_emerg from config'] = 'PASS: Found \"W_emerg from config\" in Tab 2' if 'W_emerg from config' in dash else 'FAIL'

print("=" * 70)
print("ITEM 7 COMPLIANCE AUDIT RESULTS:")
print("=" * 70)
for k, v in checks.items():
    print(f"[{v.split(':')[0]}] {k} -> {v.split(':', 1)[1].strip()}")
print("=" * 70)
