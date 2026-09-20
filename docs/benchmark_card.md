# Quantum Traffic Brain — Benchmark Model Card

This model card provides an exhaustive, scientifically rigorous audit of the Quantum Traffic Brain platform.
Every figure reported in this document is generated dynamically from result files in `results/`.

---

## 1. Experimental Methodology & Rigor
- **Evaluation Seeds**: 20 independent pseudorandom seeds (`100` through `119`).
- **QAOA Evaluation Seeds**: 5 independent seeds (`100` through `104`) evaluated with PennyLane statevector simulation.
- **Training Seeds (Hyperparameter Tuning Only)**: Seeds `1` through `10` (strictly separated; no data leakage into evaluation).
- **Equal Tuning Budget**: All controllers (Fixed tuned, Rule-Based tuned, Max-Pressure tuned, Hybrid) received comparable grid sizes and the exact same tuning budget (600s simulation runs on training seeds 1–10).
- **Headline Constraints**: Switch lost time set to realistic values of $2\text{s}$ and $3\text{s}$ with $\text{min\_green} \ge 10\text{s}$. Unconstrained minimums ($0\text{s}, 2\text{s}, 3\text{s}$) reported separately.
- **Network Topography**: 6-intersection urban grid (2x3 topology, 150m edge lengths, free-flow travel time 12.0s, saturation flow 0.5 cars/s/lane).
- **Statistical Significance**: All paired comparisons report sample mean difference, standard error, and 95% Student's t-distribution confidence intervals ($n=20$, $t_{crit}=2.093$).
- **Hardware Status**: **Future Scope**. All quantum results are computed via state-vector simulation (`braket.local.qubit` / PennyLane `default.qubit`). Physical QPU execution is documented as future architectural scope.

---

## 2. Headline Benchmark Results (Switch Lost Time = 2s, min_green >= 10s)

### Per-Regime Delay Summary (Average Wait Time in Seconds per Vehicle, 20 Evaluation Seeds)

| Traffic Regime | Fixed (30/30) | Fixed (Tuned) | Rule-Based (Tuned) | Max-Pressure (Tuned) | Hybrid (BF) | QAOA Raw (5 seeds) | QAOA Polish (5 seeds) | Lowest Wait Winner |
|---|---|---|---|---|---|---|---|---|
| **Balanced Flow (Uniform Demand)** | 116.19s | 103.34s | 123.03s | 119.47s | 123.17s | 128.50s | 114.25s | **Fixed (tuned)** |
| **Moderate Load (75-80% Saturation)** | 32.52s | 31.42s | 22.34s | 18.92s | 25.61s | 30.16s | 26.67s | **Max-Pressure (tuned)** |
| **Directional Moderate (Lopsided Bounded)** | 69.36s | 34.77s | 29.58s | 35.68s | 32.77s | 37.53s | 31.72s | **Rule-Based (tuned)** |
| **Incident Moderate (Moderate + Lane Closure)** | 35.40s | 33.89s | 26.14s | 22.48s | 29.22s | 29.71s | 29.10s | **Max-Pressure (tuned)** |
| **Shifting Demand (Dynamic Corridor Swap)** | 58.63s | 54.68s | 29.98s | 34.80s | 31.92s | 35.18s | 31.26s | **Rule-Based (tuned)** |
| **Surge Moderate (Moderate + 3x Arterial Burst)** | 55.17s | 50.96s | 52.45s | 48.75s | 56.42s | 63.00s | 56.84s | **Max-Pressure (tuned)** |
| **Rush-Hour (3x Arterial Demand)** | 113.72s | 88.12s | 104.67s | 101.96s | 96.44s | 108.09s | 95.87s | **Fixed (tuned)** |
| **Surge + Incident (Lane Closure)** | 112.63s | 107.02s | 140.63s | 130.21s | 122.10s | 128.39s | 119.75s | **Fixed (tuned)** |

### Paired-Seed Differences vs Tuned Baselines (Headline Lost Time = 2s)

Differences are defined as $\Delta = \text{Hybrid (BF)} - \text{Baseline}$. Negative $\Delta$ indicates Hybrid reduction in delay.

| Traffic Regime | Baseline Comparison | Paired Mean Diff ($\Delta$) | 95% Confidence Interval | Result / Statistical Status |
|---|---|---|---|---|
| Balanced Flow (Uniform Demand) | vs Fixed (tuned) | -19.83s | [-20.98s, -18.69s] | Hybrid Improvement |
| Moderate Load (75-80% Saturation) | vs Fixed (tuned) | +5.81s | [+5.30s, +6.31s] | Fixed (tuned) Outperforms Hybrid |
| Directional Moderate (Lopsided Bounded) | vs Fixed (tuned) | +2.00s | [+1.43s, +2.58s] | Fixed (tuned) Outperforms Hybrid |
| Incident Moderate (Moderate + Lane Closure) | vs Fixed (tuned) | +4.67s | [+4.05s, +5.29s] | Fixed (tuned) Outperforms Hybrid |
| Shifting Demand (Dynamic Corridor Swap) | vs Fixed (tuned) | +22.76s | [+21.63s, +23.89s] | Fixed (tuned) Outperforms Hybrid |
| Surge Moderate (Moderate + 3x Arterial Burst) | vs Fixed (tuned) | -5.47s | [-6.32s, -4.62s] | Hybrid Improvement |
| Rush-Hour (3x Arterial Demand) | vs Fixed (tuned) | -8.31s | [-9.19s, -7.43s] | Hybrid Improvement |
| Surge + Incident (Lane Closure) | vs Fixed (tuned) | -15.07s | [-16.23s, -13.91s] | Hybrid Improvement |

---

## 3. Secondary Headline Results (Switch Lost Time = 3s, min_green >= 10s)

| Traffic Regime | Fixed (30/30) | Fixed (Tuned) | Rule-Based (Tuned) | Max-Pressure (Tuned) | Hybrid (BF) | Lowest Wait Winner |
|---|---|---|---|---|---|---|
| **Balanced Flow (Uniform Demand)** | 129.85s | 107.36s | 134.82s | 129.68s | 131.92s | **Fixed (tuned)** |
| **Moderate Load (75-80% Saturation)** | 38.84s | 34.65s | 29.87s | 27.93s | 34.64s | **Max-Pressure (tuned)** |
| **Directional Moderate (Lopsided Bounded)** | 80.83s | 37.37s | 39.36s | 46.77s | 41.47s | **Fixed (tuned)** |
| **Incident Moderate (Moderate + Lane Closure)** | 42.38s | 37.48s | 35.30s | 34.89s | 42.42s | **Max-Pressure (tuned)** |
| **Shifting Demand (Dynamic Corridor Swap)** | 70.81s | 57.86s | 39.29s | 45.25s | 39.55s | **Rule-Based (tuned)** |
| **Surge Moderate (Moderate + 3x Arterial Burst)** | 63.38s | 54.37s | 60.20s | 59.76s | 66.74s | **Fixed (tuned)** |
| **Rush-Hour (3x Arterial Demand)** | 122.49s | 93.75s | 111.94s | 111.06s | 104.50s | **Fixed (tuned)** |
| **Surge + Incident (Lane Closure)** | 121.82s | 111.49s | 148.24s | 141.34s | 129.02s | **Fixed (tuned)** |

---

## 4. Unconstrained Minimum Green Comparison (Lost Time = 0s, 2s, 3s)

When minimum green constraints are not restricted to $\ge 10\text{s}$, controllers tune to their natural unconstrained minimums (e.g., $5\text{s}$):

| Lost Time | Traffic Regime | Controller | Avg Wait (s) | 95% CI | Throughput (cpm) | Switches |
|---|---|---|---|---|---|---|
| 0s | balanced | Fixed (tuned) | 86.97s | [85.34, 88.61] | 147.5 | 234 |
| 0s | balanced | Fixed-Timing Baseline | 102.45s | [100.35, 104.55] | 138.4 | 114 |
| 0s | balanced | Hybrid (uncoupled) | 100.45s | [97.72, 103.18] | 133.5 | 1195 |
| 0s | balanced | Hybrid Controller (Brute-Force) | 89.62s | [87.58, 91.66] | 144.4 | 1457 |
| 0s | balanced | Max-Pressure (tuned) | 97.93s | [95.64, 100.21] | 137.7 | 479 |
| 0s | balanced | Rule-Based (tuned) | 101.16s | [98.35, 103.97] | 133.2 | 492 |
| 2s | balanced | Fixed (tuned) | 103.34s | [102.58, 104.11] | 136.2 | 114 |
| 2s | balanced | Fixed-Timing Baseline | 116.19s | [114.84, 117.55] | 129.0 | 114 |
| 2s | balanced | Hybrid (QAOA Polish, 5 seeds) | 114.25s | [108.21, 120.28] | 130.0 | 110 |
| 2s | balanced | Hybrid (QAOA Raw, 5 seeds) | 128.50s | [122.09, 134.91] | 121.2 | 112 |
| 2s | balanced | Hybrid (uncoupled) | 133.65s | [131.72, 135.59] | 111.9 | 125 |
| 2s | balanced | Hybrid Controller (Brute-Force) | 123.17s | [121.61, 124.74] | 124.6 | 182 |
| 2s | balanced | Max-Pressure (tuned) | 119.47s | [117.91, 121.03] | 126.4 | 104 |
| 2s | balanced | Rule-Based (tuned) | 123.03s | [121.26, 124.79] | 121.4 | 102 |
| 3s | balanced | Fixed (tuned) | 107.36s | [106.48, 108.25] | 133.9 | 114 |
| 3s | balanced | Fixed-Timing Baseline | 129.85s | [128.54, 131.15] | 119.6 | 114 |
| 3s | balanced | Hybrid (uncoupled) | 142.36s | [140.13, 144.58] | 104.7 | 118 |
| 3s | balanced | Hybrid Controller (Brute-Force) | 131.92s | [130.49, 133.34] | 118.6 | 176 |
| 3s | balanced | Max-Pressure (tuned) | 129.68s | [128.29, 131.06] | 119.0 | 102 |
| 3s | balanced | Rule-Based (tuned) | 134.82s | [132.99, 136.64] | 113.4 | 98 |
| 0s | directional_moderate | Fixed (tuned) | 24.55s | [23.95, 25.15] | 100.4 | 234 |
| 0s | directional_moderate | Fixed-Timing Baseline | 58.20s | [56.27, 60.12] | 88.9 | 114 |
| 0s | directional_moderate | Hybrid (uncoupled) | 9.77s | [9.38, 10.16] | 103.4 | 938 |
| 0s | directional_moderate | Hybrid Controller (Brute-Force) | 9.77s | [9.38, 10.16] | 103.4 | 938 |
| 0s | directional_moderate | Max-Pressure (tuned) | 18.24s | [17.72, 18.77] | 101.5 | 333 |
| 0s | directional_moderate | Rule-Based (tuned) | 13.93s | [13.36, 14.50] | 102.6 | 323 |
| 2s | directional_moderate | Fixed (tuned) | 34.77s | [34.14, 35.41] | 98.2 | 90 |
| 2s | directional_moderate | Fixed-Timing Baseline | 69.36s | [68.03, 70.69] | 85.0 | 114 |
| 2s | directional_moderate | Hybrid (QAOA Polish, 5 seeds) | 31.72s | [29.32, 34.12] | 97.7 | 208 |
| 2s | directional_moderate | Hybrid (QAOA Raw, 5 seeds) | 37.53s | [34.20, 40.86] | 96.3 | 193 |
| 2s | directional_moderate | Hybrid (uncoupled) | 33.43s | [32.49, 34.37] | 98.2 | 208 |
| 2s | directional_moderate | Hybrid Controller (Brute-Force) | 32.77s | [31.92, 33.62] | 98.3 | 208 |
| 2s | directional_moderate | Max-Pressure (tuned) | 35.68s | [34.81, 36.56] | 96.9 | 230 |
| 2s | directional_moderate | Rule-Based (tuned) | 29.58s | [28.73, 30.43] | 99.0 | 205 |
| 3s | directional_moderate | Fixed (tuned) | 37.37s | [36.69, 38.04] | 97.7 | 90 |
| 3s | directional_moderate | Fixed-Timing Baseline | 80.83s | [79.51, 82.15] | 80.9 | 114 |
| 3s | directional_moderate | Hybrid (uncoupled) | 43.30s | [41.93, 44.67] | 96.0 | 153 |
| 3s | directional_moderate | Hybrid Controller (Brute-Force) | 41.47s | [40.09, 42.85] | 96.5 | 162 |
| 3s | directional_moderate | Max-Pressure (tuned) | 46.77s | [45.55, 47.99] | 93.9 | 194 |
| 3s | directional_moderate | Rule-Based (tuned) | 39.36s | [38.09, 40.63] | 96.2 | 187 |
| 0s | incident_moderate | Fixed (tuned) | 25.30s | [24.54, 26.06] | 99.7 | 174 |
| 0s | incident_moderate | Fixed-Timing Baseline | 29.25s | [28.39, 30.11] | 99.1 | 114 |
| 0s | incident_moderate | Hybrid (uncoupled) | 7.40s | [7.17, 7.63] | 103.3 | 1255 |
| 0s | incident_moderate | Hybrid Controller (Brute-Force) | 7.36s | [7.10, 7.63] | 103.3 | 1265 |
| 0s | incident_moderate | Max-Pressure (tuned) | 12.36s | [12.03, 12.70] | 102.4 | 478 |
| 0s | incident_moderate | Rule-Based (tuned) | 9.60s | [9.17, 10.02] | 102.8 | 534 |
| 2s | incident_moderate | Fixed (tuned) | 33.89s | [33.19, 34.59] | 98.2 | 138 |
| 2s | incident_moderate | Fixed-Timing Baseline | 35.40s | [34.69, 36.12] | 98.0 | 114 |
| 2s | incident_moderate | Hybrid (QAOA Polish, 5 seeds) | 29.10s | [26.21, 32.00] | 97.7 | 334 |
| 2s | incident_moderate | Hybrid (QAOA Raw, 5 seeds) | 29.71s | [26.54, 32.88] | 96.9 | 317 |
| 2s | incident_moderate | Hybrid (uncoupled) | 28.84s | [27.98, 29.69] | 98.9 | 334 |
| 2s | incident_moderate | Hybrid Controller (Brute-Force) | 29.22s | [28.32, 30.12] | 98.7 | 335 |
| 2s | incident_moderate | Max-Pressure (tuned) | 22.48s | [21.47, 23.50] | 100.3 | 272 |
| 2s | incident_moderate | Rule-Based (tuned) | 26.14s | [24.89, 27.40] | 99.5 | 279 |
| 3s | incident_moderate | Fixed (tuned) | 37.48s | [36.74, 38.22] | 98.0 | 102 |
| 3s | incident_moderate | Fixed-Timing Baseline | 42.38s | [41.54, 43.21] | 96.4 | 114 |
| 3s | incident_moderate | Hybrid (uncoupled) | 45.23s | [43.00, 47.46] | 95.4 | 152 |
| 3s | incident_moderate | Hybrid Controller (Brute-Force) | 42.42s | [40.71, 44.13] | 96.0 | 162 |
| 3s | incident_moderate | Max-Pressure (tuned) | 34.89s | [33.78, 36.01] | 97.0 | 248 |
| 3s | incident_moderate | Rule-Based (tuned) | 35.30s | [33.91, 36.70] | 97.2 | 224 |
| 0s | moderate_load | Fixed (tuned) | 24.28s | [24.00, 24.55] | 99.9 | 234 |
| 0s | moderate_load | Fixed-Timing Baseline | 27.49s | [27.13, 27.85] | 99.2 | 114 |
| 0s | moderate_load | Hybrid (uncoupled) | 7.17s | [6.98, 7.36] | 103.4 | 1258 |
| 0s | moderate_load | Hybrid Controller (Brute-Force) | 7.17s | [6.98, 7.36] | 103.4 | 1258 |
| 0s | moderate_load | Max-Pressure (tuned) | 11.98s | [11.74, 12.22] | 102.5 | 478 |
| 0s | moderate_load | Rule-Based (tuned) | 9.44s | [9.14, 9.73] | 102.8 | 535 |
| 2s | moderate_load | Fixed (tuned) | 31.42s | [30.93, 31.91] | 98.5 | 174 |
| 2s | moderate_load | Fixed-Timing Baseline | 32.52s | [32.14, 32.89] | 98.4 | 114 |
| 2s | moderate_load | Hybrid (+DownstreamSpace) | 26.53s | [25.91, 27.15] | 99.7 | 206 |
| 2s | moderate_load | Hybrid (+Lookahead) | 26.74s | [26.19, 27.30] | 99.7 | 219 |
| 2s | moderate_load | Hybrid (+WaitWeighted) | 26.59s | [25.91, 27.28] | 99.5 | 205 |
| 2s | moderate_load | Hybrid (QAOA Polish, 5 seeds) | 26.67s | [24.56, 28.77] | 99.1 | 204 |
| 2s | moderate_load | Hybrid (QAOA Raw, 5 seeds) | 30.16s | [28.64, 31.68] | 98.3 | 217 |
| 2s | moderate_load | Hybrid (uncoupled) | 25.61s | [25.08, 26.15] | 99.8 | 209 |
| 2s | moderate_load | Hybrid Controller (Brute-Force) | 25.61s | [25.08, 26.15] | 99.8 | 209 |
| 2s | moderate_load | Max-Pressure (tuned) | 18.92s | [18.34, 19.50] | 101.2 | 249 |
| 2s | moderate_load | Rule-Based (tuned) | 22.34s | [21.93, 22.76] | 100.6 | 197 |
| 3s | moderate_load | Fixed (tuned) | 34.65s | [34.25, 35.05] | 98.4 | 102 |
| 3s | moderate_load | Fixed-Timing Baseline | 38.84s | [38.29, 39.40] | 97.1 | 114 |
| 3s | moderate_load | Hybrid (uncoupled) | 34.64s | [33.41, 35.86] | 97.7 | 176 |
| 3s | moderate_load | Hybrid Controller (Brute-Force) | 34.64s | [33.41, 35.86] | 97.7 | 176 |
| 3s | moderate_load | Max-Pressure (tuned) | 27.93s | [27.31, 28.56] | 99.3 | 198 |
| 3s | moderate_load | Rule-Based (tuned) | 29.87s | [29.14, 30.59] | 98.7 | 203 |
| 0s | rush_hour | Fixed (tuned) | 70.85s | [68.78, 72.92] | 124.0 | 174 |
| 0s | rush_hour | Fixed-Timing Baseline | 105.20s | [103.68, 106.71] | 105.2 | 114 |
| 0s | rush_hour | Hybrid (uncoupled) | 70.60s | [67.90, 73.30] | 121.2 | 753 |
| 0s | rush_hour | Hybrid Controller (Brute-Force) | 65.62s | [63.03, 68.21] | 124.3 | 760 |
| 0s | rush_hour | Max-Pressure (tuned) | 72.52s | [70.06, 74.98] | 121.4 | 267 |
| 0s | rush_hour | Rule-Based (tuned) | 74.41s | [71.63, 77.19] | 119.8 | 256 |
| 2s | rush_hour | Fixed (tuned) | 88.12s | [86.82, 89.43] | 117.0 | 78 |
| 2s | rush_hour | Fixed-Timing Baseline | 113.72s | [112.73, 114.71] | 101.1 | 114 |
| 2s | rush_hour | Hybrid (+DownstreamSpace) | 96.51s | [93.84, 99.17] | 111.3 | 111 |
| 2s | rush_hour | Hybrid (+Lookahead) | 96.44s | [93.60, 99.27] | 111.4 | 108 |
| 2s | rush_hour | Hybrid (+WaitWeighted) | 96.44s | [93.72, 99.16] | 111.5 | 111 |
| 2s | rush_hour | Hybrid (QAOA Polish, 5 seeds) | 95.87s | [92.84, 98.90] | 110.3 | 107 |
| 2s | rush_hour | Hybrid (QAOA Raw, 5 seeds) | 108.09s | [102.51, 113.66] | 104.6 | 97 |
| 2s | rush_hour | Hybrid (uncoupled) | 106.81s | [104.69, 108.94] | 104.7 | 111 |
| 2s | rush_hour | Hybrid Controller (Brute-Force) | 96.44s | [94.61, 98.27] | 111.5 | 111 |
| 2s | rush_hour | Max-Pressure (tuned) | 101.96s | [100.38, 103.54] | 107.1 | 103 |
| 2s | rush_hour | Rule-Based (tuned) | 104.67s | [102.61, 106.73] | 105.0 | 94 |
| 3s | rush_hour | Fixed (tuned) | 93.75s | [92.56, 94.94] | 113.9 | 90 |
| 3s | rush_hour | Fixed-Timing Baseline | 122.49s | [121.53, 123.45] | 96.8 | 114 |
| 3s | rush_hour | Hybrid (uncoupled) | 113.23s | [111.15, 115.31] | 100.8 | 106 |
| 3s | rush_hour | Hybrid Controller (Brute-Force) | 104.50s | [102.82, 106.17] | 107.2 | 108 |
| 3s | rush_hour | Max-Pressure (tuned) | 111.06s | [109.62, 112.50] | 102.6 | 81 |
| 3s | rush_hour | Rule-Based (tuned) | 111.94s | [110.02, 113.85] | 102.7 | 75 |
| 0s | shifting_demand | Fixed (tuned) | 46.49s | [45.44, 47.54] | 96.7 | 114 |
| 0s | shifting_demand | Fixed-Timing Baseline | 48.24s | [46.71, 49.76] | 101.7 | 114 |
| 0s | shifting_demand | Hybrid (uncoupled) | 9.59s | [9.15, 10.04] | 114.9 | 928 |
| 0s | shifting_demand | Hybrid Controller (Brute-Force) | 9.59s | [9.15, 10.04] | 114.9 | 928 |
| 0s | shifting_demand | Max-Pressure (tuned) | 16.45s | [15.87, 17.04] | 114.0 | 328 |
| 0s | shifting_demand | Rule-Based (tuned) | 13.21s | [12.61, 13.81] | 114.2 | 327 |
| 2s | shifting_demand | Fixed (tuned) | 54.68s | [53.75, 55.61] | 98.9 | 90 |
| 2s | shifting_demand | Fixed-Timing Baseline | 58.63s | [57.44, 59.82] | 99.1 | 114 |
| 2s | shifting_demand | Hybrid (QAOA Polish, 5 seeds) | 31.26s | [29.40, 33.12] | 108.4 | 215 |
| 2s | shifting_demand | Hybrid (QAOA Raw, 5 seeds) | 35.18s | [32.40, 37.96] | 107.2 | 200 |
| 2s | shifting_demand | Hybrid (uncoupled) | 32.17s | [31.13, 33.20] | 109.8 | 202 |
| 2s | shifting_demand | Hybrid Controller (Brute-Force) | 31.92s | [30.86, 32.97] | 109.8 | 202 |
| 2s | shifting_demand | Max-Pressure (tuned) | 34.80s | [33.78, 35.82] | 108.7 | 228 |
| 2s | shifting_demand | Rule-Based (tuned) | 29.98s | [29.11, 30.85] | 109.9 | 210 |
| 3s | shifting_demand | Fixed (tuned) | 57.86s | [56.95, 58.77] | 96.7 | 90 |
| 3s | shifting_demand | Fixed-Timing Baseline | 70.81s | [69.54, 72.08] | 95.6 | 114 |
| 3s | shifting_demand | Hybrid (uncoupled) | 42.66s | [41.08, 44.25] | 106.9 | 155 |
| 3s | shifting_demand | Hybrid Controller (Brute-Force) | 39.55s | [38.11, 40.99] | 107.6 | 167 |
| 3s | shifting_demand | Max-Pressure (tuned) | 45.25s | [44.25, 46.25] | 105.1 | 200 |
| 3s | shifting_demand | Rule-Based (tuned) | 39.29s | [38.08, 40.50] | 107.6 | 171 |
| 0s | surge_accident | Fixed (tuned) | 88.83s | [86.82, 90.84] | 127.4 | 234 |
| 0s | surge_accident | Fixed-Timing Baseline | 103.67s | [102.33, 105.01] | 118.8 | 114 |
| 0s | surge_accident | Hybrid (uncoupled) | 97.58s | [94.91, 100.24] | 118.0 | 876 |
| 0s | surge_accident | Hybrid Controller (Brute-Force) | 88.15s | [86.00, 90.30] | 125.9 | 950 |
| 0s | surge_accident | Max-Pressure (tuned) | 97.66s | [95.13, 100.18] | 119.2 | 326 |
| 0s | surge_accident | Rule-Based (tuned) | 103.49s | [100.98, 106.01] | 114.5 | 310 |
| 2s | surge_accident | Fixed (tuned) | 107.02s | [106.06, 107.98] | 117.9 | 114 |
| 2s | surge_accident | Fixed-Timing Baseline | 112.63s | [111.76, 113.49] | 114.0 | 114 |
| 2s | surge_accident | Hybrid (QAOA Polish, 5 seeds) | 119.75s | [114.08, 125.43] | 109.8 | 128 |
| 2s | surge_accident | Hybrid (QAOA Raw, 5 seeds) | 128.39s | [120.69, 136.08] | 104.3 | 115 |
| 2s | surge_accident | Hybrid (uncoupled) | 141.20s | [139.59, 142.81] | 95.0 | 129 |
| 2s | surge_accident | Hybrid Controller (Brute-Force) | 122.10s | [120.55, 123.65] | 109.9 | 134 |
| 2s | surge_accident | Max-Pressure (tuned) | 130.21s | [128.32, 132.09] | 99.2 | 119 |
| 2s | surge_accident | Rule-Based (tuned) | 140.63s | [138.70, 142.56] | 92.5 | 108 |
| 3s | surge_accident | Fixed (tuned) | 111.49s | [110.36, 112.61] | 116.8 | 78 |
| 3s | surge_accident | Fixed-Timing Baseline | 121.82s | [120.97, 122.68] | 109.0 | 114 |
| 3s | surge_accident | Hybrid (uncoupled) | 152.46s | [150.68, 154.25] | 85.3 | 136 |
| 3s | surge_accident | Hybrid Controller (Brute-Force) | 129.02s | [127.49, 130.54] | 104.9 | 163 |
| 3s | surge_accident | Max-Pressure (tuned) | 141.34s | [139.65, 143.02] | 92.9 | 108 |
| 3s | surge_accident | Rule-Based (tuned) | 148.24s | [146.05, 150.44] | 88.7 | 81 |
| 0s | surge_moderate | Fixed (tuned) | 43.02s | [41.89, 44.15] | 111.4 | 174 |
| 0s | surge_moderate | Fixed-Timing Baseline | 47.75s | [46.87, 48.63] | 109.3 | 114 |
| 0s | surge_moderate | Hybrid (uncoupled) | 25.09s | [23.90, 26.28] | 116.8 | 1168 |
| 0s | surge_moderate | Hybrid Controller (Brute-Force) | 24.00s | [22.89, 25.12] | 116.9 | 1245 |
| 0s | surge_moderate | Max-Pressure (tuned) | 29.52s | [28.51, 30.52] | 115.3 | 456 |
| 0s | surge_moderate | Rule-Based (tuned) | 28.31s | [27.14, 29.48] | 116.2 | 481 |
| 2s | surge_moderate | Fixed (tuned) | 50.96s | [50.14, 51.78] | 110.1 | 90 |
| 2s | surge_moderate | Fixed-Timing Baseline | 55.17s | [54.57, 55.78] | 106.2 | 114 |
| 2s | surge_moderate | Hybrid (QAOA Polish, 5 seeds) | 56.84s | [54.81, 58.88] | 106.7 | 195 |
| 2s | surge_moderate | Hybrid (QAOA Raw, 5 seeds) | 63.00s | [59.90, 66.09] | 104.4 | 158 |
| 2s | surge_moderate | Hybrid (uncoupled) | 62.15s | [61.07, 63.23] | 105.7 | 195 |
| 2s | surge_moderate | Hybrid Controller (Brute-Force) | 56.42s | [55.41, 57.44] | 107.3 | 203 |
| 2s | surge_moderate | Max-Pressure (tuned) | 48.75s | [47.98, 49.53] | 108.6 | 187 |
| 2s | surge_moderate | Rule-Based (tuned) | 52.45s | [51.42, 53.48] | 107.7 | 187 |
| 3s | surge_moderate | Fixed (tuned) | 54.37s | [53.49, 55.24] | 109.2 | 90 |
| 3s | surge_moderate | Fixed-Timing Baseline | 63.38s | [62.71, 64.04] | 102.6 | 114 |
| 3s | surge_moderate | Hybrid (uncoupled) | 69.60s | [68.61, 70.58] | 103.5 | 117 |
| 3s | surge_moderate | Hybrid Controller (Brute-Force) | 66.74s | [65.19, 68.30] | 103.2 | 146 |
| 3s | surge_moderate | Max-Pressure (tuned) | 59.76s | [58.87, 60.65] | 103.9 | 187 |
| 3s | surge_moderate | Rule-Based (tuned) | 60.20s | [58.97, 61.43] | 105.3 | 141 |

---

## 5. Winner Table Across Traffic Regimes

### Headline 2s Lost Time Winners
| Traffic Regime | Saturation Level | Best Controller (Avg Delay) | Value | Hybrid Delay | Best on P95 Wait | Best Throughput |
|---|---|---|---|---|---|---|
| **Balanced Flow (Uniform Demand)** | Oversaturated (Unbounded Queues) | **Fixed (tuned)** | 103.34s | 123.17s | Fixed-Timing Baseline (214.99s) | Fixed (tuned) (136.22 cpm) |
| **Moderate Load (75-80% Saturation)** | Bounded (75-80% Saturation) | **Max-Pressure (tuned)** | 18.92s | 25.61s | Max-Pressure (tuned) (41.13s) | Max-Pressure (tuned) (101.16 cpm) |
| **Directional Moderate (Lopsided Bounded)** | Bounded (75-85% Saturation, Asymmetric) | **Rule-Based (tuned)** | 29.58s | 32.77s | Rule-Based (tuned) (56.55s) | Rule-Based (tuned) (99.04 cpm) |
| **Incident Moderate (Moderate + Lane Closure)** | Bounded + Bottleneck Incident | **Max-Pressure (tuned)** | 22.48s | 29.22s | Max-Pressure (tuned) (56.62s) | Max-Pressure (tuned) (100.3 cpm) |
| **Shifting Demand (Dynamic Corridor Swap)** | Bounded (Dynamic Split Swap) | **Rule-Based (tuned)** | 29.98s | 31.92s | Rule-Based (tuned) (67.71s) | Rule-Based (tuned) (109.94 cpm) |
| **Surge Moderate (Moderate + 3x Arterial Burst)** | Bounded + Transient Burst | **Max-Pressure (tuned)** | 48.75s | 56.42s | Hybrid Controller (Brute-Force) (113.68s) | Fixed (tuned) (110.13 cpm) |
| **Rush-Hour (3x Arterial Demand)** | Oversaturated (Arterial Dominance) | **Fixed (tuned)** | 88.12s | 96.44s | Fixed (tuned) (160.51s) | Fixed (tuned) (116.95 cpm) |
| **Surge + Incident (Lane Closure)** | Oversaturated + Bottleneck Incident | **Fixed (tuned)** | 107.02s | 122.1s | Hybrid Controller (Brute-Force) (241.38s) | Fixed (tuned) (117.88 cpm) |

### Headline 3s Lost Time Winners
| Traffic Regime | Saturation Level | Best Controller (Avg Delay) | Value | Hybrid Delay | Best on P95 Wait | Best Throughput |
|---|---|---|---|---|---|---|
| **Balanced Flow (Uniform Demand)** | Oversaturated (Unbounded Queues) | **Fixed (tuned)** | 107.36s | 131.92s | Fixed-Timing Baseline (239.76s) | Fixed (tuned) (133.89 cpm) |
| **Moderate Load (75-80% Saturation)** | Bounded (75-80% Saturation) | **Max-Pressure (tuned)** | 27.93s | 34.64s | Max-Pressure (tuned) (56.82s) | Max-Pressure (tuned) (99.28 cpm) |
| **Directional Moderate (Lopsided Bounded)** | Bounded (75-85% Saturation, Asymmetric) | **Fixed (tuned)** | 37.37s | 41.47s | Rule-Based (tuned) (77.24s) | Fixed (tuned) (97.65 cpm) |
| **Incident Moderate (Moderate + Lane Closure)** | Bounded + Bottleneck Incident | **Max-Pressure (tuned)** | 34.89s | 42.42s | Fixed (tuned) (81.01s) | Fixed (tuned) (97.96 cpm) |
| **Shifting Demand (Dynamic Corridor Swap)** | Bounded (Dynamic Split Swap) | **Rule-Based (tuned)** | 39.29s | 39.55s | Rule-Based (tuned) (90.69s) | Rule-Based (tuned) (107.59 cpm) |
| **Surge Moderate (Moderate + 3x Arterial Burst)** | Bounded + Transient Burst | **Fixed (tuned)** | 54.37s | 66.74s | Fixed (tuned) (124.55s) | Fixed (tuned) (109.16 cpm) |
| **Rush-Hour (3x Arterial Demand)** | Oversaturated (Arterial Dominance) | **Fixed (tuned)** | 93.75s | 104.5s | Fixed (tuned) (175.15s) | Fixed (tuned) (113.92 cpm) |
| **Surge + Incident (Lane Closure)** | Oversaturated + Bottleneck Incident | **Fixed (tuned)** | 111.49s | 129.02s | Fixed (tuned) (235.25s) | Fixed (tuned) (116.84 cpm) |

---

## 6. Ablation Study & Component Contributions

### 1. Network Coupling Interactions ($J_{ij}$ Terms)
- **Uncoupled QUBO**: 7 non-zero interaction terms.
- **Coupled QUBO**: 7 non-zero interaction terms across 7 physical network links.

### 2. Algorithmic Feature Ablations
| Traffic Regime | Hybrid Base Delay | + Lookahead | Delta | + Downstream Space | Delta | + Wait-Weighted Queue | Delta |
|---|---|---|---|---|---|---|---|
| moderate_load | 25.61s | 26.74s | +1.13s | 26.53s | +0.92s | 26.59s | +0.98s |
| rush_hour | 96.44s | 96.44s | -0.00s | 96.51s | +0.07s | 96.44s | +0.00s |

### 3. QAOA Optimization Quality vs Brute-Force Ground Truth (5 Evaluation Seeds)
| Traffic Regime | Mean QAOA Approximation Ratio | Exact Ground State Hit Rate | Total Optimizations Sampled |
|---|---|---|---|
| balanced | 0.9165 (91.6%) | 0.5375 (53.8%) | 400 |
| moderate_load | 0.9653 (96.5%) | 0.7200 (72.0%) | 600 |
| directional_moderate | 0.9551 (95.5%) | 0.6783 (67.8%) | 600 |
| incident_moderate | 0.9840 (98.4%) | 0.9000 (90.0%) | 600 |
| shifting_demand | 0.9611 (96.1%) | 0.7000 (70.0%) | 600 |
| surge_moderate | 0.9424 (94.2%) | 0.6350 (63.5%) | 400 |
| rush_hour | 0.9250 (92.5%) | 0.6000 (60.0%) | 400 |
| surge_accident | 0.9382 (93.8%) | 0.6200 (62.0%) | 400 |

---

## 7. Emergency Preemption & Ambulance Fairness

- **Ambulance Route**: Ingress Node 0 $\to$ 1 $\to$ 2 $\to$ Egress Node 5 (450m total).
- **Free-Flow Travel Time**: 24.0s (at $1.5\times$ speed multiplier = $18.75\text{ m/s}$).
- **Dispatch Ingress**: Warm-up tick `120` inside the active simulation loop, entering pre-loaded network queues.

### Ambulance Travel Time and Civilian Penalty ($n=20$ Evaluation Seeds)

| Scenario | Controller Mode | Ambulance Travel Time (s) | 95% CI | Civilian Vehicle Delay (s) |
|---|---|---|---|---|
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |
|  |  | 0.00 ± 0.00s | [0.00, 0.00]s | 0.00s |

---

## 8. Hardware Roadmap (Future Scope)

Real quantum hardware (QPUs from AWS Braket or IBM Quantum) is explicitly classified as **Future Scope**:
1. **Circuit Depth vs Coherence**: Current 2-layer QAOA circuits compile to 13 two-qubit CZ/CNOT gates. On existing NISQ processors, two-qubit gate error rates (0.5%–1.0%) accumulate substantial total variation distance.
2. **Latency Limitations**: Cloud QPU submission latency (queue wait + compilation + readout $\approx 3\text{s}$ to $45\text{s}$) exceeds the real-time traffic control budget (re-optimization interval $\le 10\text{s}$).
3. **Production Read-Only Infrastructure**: The repository provides an audited offline runner (`scripts/run_on_qpu.py`) equipped with pre-flight dry-run validation, shots ceiling checks, and cost caps.