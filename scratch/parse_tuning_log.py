import os
import re
import json

log_path = r"C:\Users\Ashborn\.gemini\antigravity-ide\brain\3dbedc87-ee6b-497e-8a66-1da961f6c6eb\.system_generated\tasks\task-7765.log"
with open(log_path, "r", encoding="utf-8") as f:
    text = f.read()

sweeps = {}
current_sweep_key = None
current_regime = None

lines = text.splitlines()
for line in lines:
    line_s = line.strip()
    if not line_s:
        continue

    m_sweep = re.match(r"STARTING CONTROLLER TUNING SWEEP:\s*LostTime=(\d+)s\s*\|\s*(Headline|Unconstrained)", line_s)
    if m_sweep:
        lt = m_sweep.group(1)
        mode = "headline" if "Headline" in m_sweep.group(2) else "unconstrained"
        current_sweep_key = f"lost_time_{lt}s_{mode}"
        sweeps[current_sweep_key] = {
            "metadata": {
                "lost_time_sec": int(lt),
                "headline_min_green": (mode == "headline"),
                "training_seeds": list(range(1, 11)),
                "sim_duration_sec": 600,
            },
            "fixed": {},
            "fixed_tuned": {},
            "rule_based": {},
            "rule_based_tuned": {},
            "max_pressure": {},
            "max_pressure_tuned": {},
            "hybrid": {},
            "hybrid_tuned": {},
            "boundary_audits": {},
        }
        continue

    m_regime = re.search(r"Tuning Regime:\s*([a-zA-Z0-9_]+)", line_s)
    if m_regime:
        current_regime = m_regime.group(1)
        if current_sweep_key:
            sweeps[current_sweep_key]["boundary_audits"][current_regime] = {}
        continue

    if not current_sweep_key or not current_regime:
        continue

    # [Fixed] Wait: 103.68s | cycle=60s (INTERIOR (60 inside [30, 40, 50, 60, 70, 80, 90])), NS=45s
    if "[Fixed]" in line_s:
        parts = [p.strip() for p in line_s.split("|")]
        wait = float(parts[0].split("Wait:")[1].replace("s", "").strip())
        cycle = int(parts[1].split("cycle=")[1].split("s")[0])
        ns = int(parts[1].split("NS=")[1].replace("s", "").strip())
        # extract status inside ()
        c_status = parts[1].split("(")[1].split(")")[0]
        obj = {"cycle_len_sec": cycle, "ns_green_sec": ns, "mean_wait_training": wait}
        sweeps[current_sweep_key]["fixed"][current_regime] = obj
        sweeps[current_sweep_key]["fixed_tuned"][current_regime] = obj
        sweeps[current_sweep_key]["boundary_audits"][current_regime]["fixed"] = {"cycle_len_sec": c_status}
        continue

    # [Rule-Based] Wait: 124.71s | eval=15s (ON UPPER BOUNDARY (15 == max [2, 5, 10, 15])), min_green=20s (ON UPPER BOUNDARY (20 == max [5, 10, 15, 20])), hyst=0 (ON LOWER BOUNDARY (0 == min [0, 1, 2, 3, 5]))
    if "[Rule-Based]" in line_s:
        parts = [p.strip() for p in line_s.split("|")]
        wait = float(parts[0].split("Wait:")[1].replace("s", "").strip())
        p1 = parts[1]
        eval_sec = int(p1.split("eval=")[1].split("s")[0])
        mg_sec = int(p1.split("min_green=")[1].split("s")[0])
        hyst = int(p1.split("hyst=")[1].split()[0])
        obj = {"eval_interval_sec": eval_sec, "min_green_sec": mg_sec, "hysteresis": hyst, "mean_wait_training": wait}
        sweeps[current_sweep_key]["rule_based"][current_regime] = obj
        sweeps[current_sweep_key]["rule_based_tuned"][current_regime] = obj
        sweeps[current_sweep_key]["boundary_audits"][current_regime]["rule_based"] = {
            "eval_interval": "BOUNDARY" if ("BOUNDARY" in p1.split("eval=")[1].split(",")[0]) else "INTERIOR",
            "min_green": "BOUNDARY" if ("BOUNDARY" in p1.split("min_green=")[1].split(",")[0]) else "INTERIOR",
            "hysteresis": "BOUNDARY" if ("BOUNDARY" in p1.split("hyst=")[1]) else "INTERIOR",
        }
        continue

    # [Max-Pressure] Wait: 120.20s | eval=15s (ON UPPER BOUNDARY (15 == max [2, 5, 10, 15])), min_green=20s (ON UPPER BOUNDARY (20 == max [5, 10, 15, 20])), hyst=2 (INTERIOR (2 inside [0, 1, 2, 3, 5]))
    if "[Max-Pressure]" in line_s:
        parts = [p.strip() for p in line_s.split("|")]
        wait = float(parts[0].split("Wait:")[1].replace("s", "").strip())
        p1 = parts[1]
        eval_sec = int(p1.split("eval=")[1].split("s")[0])
        mg_sec = int(p1.split("min_green=")[1].split("s")[0])
        hyst = int(p1.split("hyst=")[1].split()[0])
        obj = {"eval_interval_sec": eval_sec, "min_green_sec": mg_sec, "hysteresis": hyst, "mean_wait_training": wait}
        sweeps[current_sweep_key]["max_pressure"][current_regime] = obj
        sweeps[current_sweep_key]["max_pressure_tuned"][current_regime] = obj
        sweeps[current_sweep_key]["boundary_audits"][current_regime]["max_pressure"] = {
            "eval_interval": "BOUNDARY" if ("BOUNDARY" in p1.split("eval=")[1].split(",")[0]) else "INTERIOR",
            "min_green": "BOUNDARY" if ("BOUNDARY" in p1.split("min_green=")[1].split(",")[0]) else "INTERIOR",
            "hysteresis": "BOUNDARY" if ("BOUNDARY" in p1.split("hyst=")[1]) else "INTERIOR",
        }
        continue

    # [Hybrid] Wait: 124.14s | reopt=15s (ON UPPER BOUNDARY (15 == max [2, 5, 10, 15])), w_sw=5.0 (ON UPPER BOUNDARY (5.0 == max [0.0, 1.0, 2.5, 5.0])), w_tc=0.5 (ON UPPER BOUNDARY (0.5 == max [0.0, 0.05, 0.1, 0.2, 0.5]))
    if "[Hybrid]" in line_s:
        parts = [p.strip() for p in line_s.split("|")]
        wait = float(parts[0].split("Wait:")[1].replace("s", "").strip())
        p1 = parts[1]
        reopt = int(p1.split("reopt=")[1].split("s")[0])
        w_sw = float(p1.split("w_sw=")[1].split()[0])
        w_tc = float(p1.split("w_tc=")[1].split()[0])
        obj = {"reopt_interval_sec": reopt, "w_switch": w_sw, "w_throughput_coupling": w_tc, "mean_wait_training": wait}
        sweeps[current_sweep_key]["hybrid"][current_regime] = obj
        sweeps[current_sweep_key]["hybrid_tuned"][current_regime] = obj
        sweeps[current_sweep_key]["boundary_audits"][current_regime]["hybrid"] = {
            "reopt_interval": "BOUNDARY" if ("BOUNDARY" in p1.split("reopt=")[1].split(",")[0]) else "INTERIOR",
            "w_switch": "BOUNDARY" if ("BOUNDARY" in p1.split("w_sw=")[1].split(",")[0]) else "INTERIOR",
            "w_coupling": "BOUNDARY" if ("BOUNDARY" in p1.split("w_tc=")[1]) else "INTERIOR",
        }
        continue

print(f"Parsed {len(sweeps)} sweeps: {list(sweeps.keys())}")
for k, v in sweeps.items():
    print(f"  Sweep {k}: {len(v['fixed'])} fixed regimes, {len(v['rule_based'])} rule-based regimes, {len(v['max_pressure'])} max-pressure regimes, {len(v['hybrid'])} hybrid regimes")

import copy
primary = copy.deepcopy(sweeps["lost_time_2s_headline"])
primary["all_sweeps"] = sweeps

out_path = os.path.join("results", "tuned_parameters.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(primary, f, indent=2)

print(f"Successfully wrote {out_path}!")
