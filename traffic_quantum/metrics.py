"""Environmental and performance metrics engine.

Computes:
- Average and maximum waiting time (seconds)
- Throughput (completed vehicles per minute)
- Average and maximum queue length
- Estimated idle fuel consumption: (idle_seconds / 3600) * idle_fuel_rate (default 0.8 L/hr)
- Estimated CO2 emissions: fuel_litres * 2.31 kg/L (petrol combustion estimate)
- Comparative percentage improvements relative to classical baselines
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.simulator import TrafficSimulator


class MetricsEngine:
    """Calculates operational and environmental sustainability metrics from simulation history."""

    def __init__(self, config: Optional[MasterConfig] = None):
        self.config = config or DEFAULT_CONFIG

    def compute_run_metrics(self, simulator: TrafficSimulator) -> Dict[str, float]:
        """Calculates comprehensive performance metrics for a completed simulation run."""
        sim_ticks = max(1, simulator.current_tick)
        sim_minutes = sim_ticks / 60.0

        # Collect waiting times across completed vehicles and currently queued vehicles
        all_waits = [v.waiting_ticks for v in simulator.completed_vehicles]
        for node_dict in simulator.queues.values():
            for app_queue in node_dict.values():
                all_waits.extend(v.waiting_ticks for v in app_queue)

        total_idle_delay_sec = float(sum(all_waits))
        avg_wait_sec = float(np.mean(all_waits)) if all_waits else 0.0
        max_wait_sec = float(np.max(all_waits)) if all_waits else 0.0

        # Throughput
        completed_cars = len(simulator.completed_vehicles)
        throughput_cpm = completed_cars / sim_minutes

        # Queues across all ticks
        all_total_queues_per_tick = [
            sum(tick_data.values()) for tick_data in simulator.queue_length_history
        ]
        avg_queue = float(np.mean(all_total_queues_per_tick)) if all_total_queues_per_tick else 0.0
        max_queue = float(np.max(all_total_queues_per_tick)) if all_total_queues_per_tick else 0.0

        # Fuel and CO2 estimations
        fuel_rate_lph = self.config.metrics.idle_fuel_rate_l_per_hr
        co2_factor = self.config.metrics.co2_kg_per_l_petrol

        # Formula: idle_hours * 0.8 L/hour
        est_fuel_liters = (total_idle_delay_sec / 3600.0) * fuel_rate_lph
        est_co2_kg = est_fuel_liters * co2_factor

        # Pedestrian wait times
        avg_ped_wait = (
            simulator.get_average_pedestrian_wait_time()
            if hasattr(simulator, "get_average_pedestrian_wait_time")
            else 0.0
        )
        completed_peds = (
            len(simulator.completed_pedestrians)
            if hasattr(simulator, "completed_pedestrians")
            else 0
        )

        return {
            "completed_vehicles": completed_cars,
            "throughput_cars_per_min": round(throughput_cpm, 2),
            "avg_wait_sec": round(avg_wait_sec, 2),
            "max_wait_sec": round(max_wait_sec, 2),
            "avg_queue_cars": round(avg_queue, 2),
            "max_queue_cars": round(max_queue, 2),
            "total_idle_delay_sec": round(total_idle_delay_sec, 1),
            "estimated_fuel_liters": round(est_fuel_liters, 3),
            "estimated_co2_kg": round(est_co2_kg, 3),
            "spillback_events": simulator.spillback_events_count,
            "avg_pedestrian_wait_sec": round(avg_ped_wait, 2),
            "completed_pedestrians": completed_peds,
            "total_phase_switches": getattr(simulator, "total_phase_switches", 0),
        }

    def generate_comparison_table(
        self,
        results_by_controller: Dict[str, Dict[str, float]],
        baseline_key: str = "Fixed-Timing Baseline",
    ) -> pd.DataFrame:
        """Generates a comparative DataFrame with percentage improvements over the baseline."""
        rows = []
        base_data = results_by_controller.get(baseline_key, None)

        for name, metrics in results_by_controller.items():
            row = {
                "Controller": name,
                "Avg Wait (s)": metrics["avg_wait_sec"],
                "Avg Ped Wait (s)": metrics.get("avg_pedestrian_wait_sec", 0.0),
                "Cars Finished": metrics.get("total_vehicles_completed", 0),
                "Throughput (cars/min)": metrics["throughput_cars_per_min"],
                "Avg Queue (cars)": metrics["avg_queue_cars"],
                "Est. Fuel (L)*": metrics["estimated_fuel_liters"],
                "Est. CO2 (kg)*": metrics["estimated_co2_kg"],
            }

            if base_data and name != baseline_key:
                # Wait reduction: positive is improvement
                wait_delta = ((base_data["avg_wait_sec"] - metrics["avg_wait_sec"]) / base_data["avg_wait_sec"]) * 100.0
                # Fuel reduction
                fuel_delta = ((base_data["estimated_fuel_liters"] - metrics["estimated_fuel_liters"]) / base_data["estimated_fuel_liters"]) * 100.0
                row["Wait Diff (%)"] = f"+{wait_delta:.1f}%" if wait_delta >= 0 else f"{wait_delta:.1f}%"
                row["Fuel Saved Diff (%)"] = f"+{fuel_delta:.1f}%" if fuel_delta >= 0 else f"{fuel_delta:.1f}%"
            else:
                row["Wait Diff (%)"] = "Baseline"
                row["Fuel Saved Diff (%)"] = "Baseline"

            rows.append(row)

        df = pd.DataFrame(rows)
        return df
