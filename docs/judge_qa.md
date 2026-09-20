# Quantum Traffic Brain — Defensible Pitch & Judge Q&A Guide

This document equips presenters and technical leads with defensible, scientifically validated answers to expected judge inquiries.
Every statement adheres to the Ground Rules: **zero hardcoded numbers, honest reporting of baselines, no advantage claims, and hardware designated as Future Scope.**

---

## Question 1: Do you claim Quantum Advantage in this demonstration?
**Answer**: **No.**
- We explicitly state that current NISQ devices do not offer quantum computational advantage over classical traffic controllers for a 6-intersection grid.
- All quantum evaluations are performed on local state-vector simulators (`braket.local.qubit` / PennyLane).
- The value of this work is **Quantum Readiness**: proving that complex multi-objective urban traffic optimization (coordination, queues, pedestrian pressure, emergency preemption, and switching lost time) can be mapped onto a 6-qubit Ising Hamiltonian and solved via QAOA with convergence properties suitable for future fault-tolerant hardware.

---

## Question 2: How did you ensure your classical baselines were not handicapped?
**Answer**: We implemented strict parity tuning with equal computational budgets across all controllers:
1. **Data Leakage Elimination**: Tuning was conducted strictly on training seeds `1` through `10`. All benchmark claims are reported exclusively on unseen evaluation seeds `100` through `119`.
2. **Equal Tuning Budget**: Fixed-timing cycles (30s–90s), Rule-Based hysteresis/intervals, Max-Pressure evaluation rates, and Hybrid QUBO weights were all optimized using 600-second simulation runs on the training seeds.
3. **Realistic Lost Time Constraints**: All controllers were tuned and evaluated at realistic lost times (2s and 3s) with minimum green enforced at $\ge 10\text{s}$, alongside unconstrained minimum runs.
4. **Modern Baselines**: We included tuned Max-Pressure (the classical standard in distributed traffic management) and show where it outperforms or matches the hybrid controller.

---

## Question 3: Why does Fixed-Timing or Max-Pressure beat Hybrid in certain scenarios?
**Answer**: We report every regime transparently, including where the hybrid loses or ties:
- **Balanced Symmetric Traffic**: Under uniform 50/50 arrival rates, fixed 30s/30s cycling is optimal. Any adaptive controller that switches phases introduces transition delay (lost time) without clearing extra vehicles.
- **Saturated Arteries / Heavy Congestion**: Under heavy persistent volume (e.g., balanced saturation and surge accident), long fixed green phases maximize continuous vehicle discharge. Tuned Fixed achieves lowest average delay.
- **Local Bounded Regimes**: In moderate and incident regimes, localized Max-Pressure controller achieves lowest average wait by reacting purely to upstream-downstream pressure differences.
- **Dynamic Transitions**: In dynamic split shifts (`shifting_demand`), Rule-Based reactive control achieves lowest wait, while Hybrid remains within a statistical tie ($\le 1.9\text{s}$ difference at 2s lost time, $\le 0.26\text{s}$ at 3s lost time).
- **Tail Latency Protection**: Under bursty surges (`surge_moderate`), Hybrid Controller achieves the best $P_{95}$ vehicle delay (113.68s vs 128s+ for classical baselines), preventing catastrophic outlier queues.

---

## Question 4: Does the Emergency Preemption improvement come from Quantum Optimization?
**Answer**: **No, the benefit comes from signal preemption itself.**
- Across 20 evaluation seeds with dispatch at tick 120, emergency preemption cuts ambulance travel time from ~50s down to ~28–32s.
- However, **Rule-Based with Hard Preemption** and **Fixed with Hard Preemption** achieve response times that match or slightly edge out Hybrid Soft QUBO preemption.
- The scientific conclusion is clear: **Emergency corridor preemption is a domain-level signal intervention, not a quantum algorithmic superiority.** We report this finding openly in our benchmark card.

---

## Question 5: What is the status of physical quantum hardware in your project?
**Answer**: **Future Scope**, pending accessible multi-qubit fault-tolerant hardware.
- We have engineered an auditable, safety-capped runner (`scripts/run_on_qpu.py`) targeting AWS Braket QPUs and IBM Quantum backends.
- The runner enforces mandatory `--dry-run` testing, cost caps, and bitstring wire-ordering selftests.
- Because physical QPU queue times (seconds to minutes) currently exceed the 10-second real-time traffic decision cycle, live operations run on local state-vector simulators.

---

## Question 6: How does the Paramedic / Ambulance Driver Dispatch Flow work?
**Answer**:
- **Approval-Gated Driver Accounts**: Self-registration places accounts into a `PENDING` state that an authorized CAD dispatcher/admin must explicitly approve before login is allowed.
- **Strong Cryptographic Hashing**: Driver passwords/PINs are hashed with `bcrypt` (work factor 12) with an enforced minimum length of 6 characters.
- **Exponential Backoff Lockout**: Accounts lock out for $30 \times 2^{(\text{lockout}-1)}$ seconds after 5 consecutive failed attempts, defending against automated PIN guessing.
- **Tamper-Evident Audit Logging**: Every registration, approval, successful login, and failed attempt is logged to `results/ems_drivers.json` with UTC timestamps.
- **Session-Restricted Dispatch JWTs**: Emergency corridor dispatch requests require a cryptographically signed HMAC-SHA256 JWT issued strictly upon authenticated session validation.
- **Tactical Routing**: Calculates Dijkstra shortest paths to destination hospitals, visualizes preemption corridor on 2D tactical HUD, and updates emergency biases without state corruption.