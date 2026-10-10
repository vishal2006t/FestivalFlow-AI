"""Reproducible Synthetic Data Generator for FestivalFlow AI.

Generates realistic multi-scenario festival transit datasets with:
- Fixed random seed for strict reproducibility.
- Multiple stops: STOP_MAIN (Hub), STOP_NEARBY (Source), STOP_METRO_LINK, STOP_SOUTH_BAY.
- Distinction between Passenger Departure Demand and Total Area Crowd Density.
- Event delay variations (Normal 21:00, +15m, +30m, +60m).
- Weather conditions (Clear, Light Rain, Heavy Rain).
- Bus telematics (Available, Delayed, Broken down).
- Clear explicit source labels: 'synthetic'.
"""

import os
import csv
import random
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

RANDOM_SEED = 42

STOPS = [
    {"stop_id": "STOP_MAIN", "stop_name": "Main Bus Stand (Festival Arena)", "is_hub": True, "share": 0.82},
    {"stop_id": "STOP_NEARBY", "stop_name": "Tech Hub North Stop (2km away)", "is_hub": False, "share": 0.08},
    {"stop_id": "STOP_METRO_LINK", "stop_name": "East Metro Interchange", "is_hub": False, "share": 0.06},
    {"stop_id": "STOP_SOUTH_BAY", "stop_name": "South Parking Bay", "is_hub": False, "share": 0.04},
]

WEATHER_CONDITIONS = ["Clear", "Light Rain", "Heavy Rain"]
DELAY_SCENARIOS = [0, 15, 30, 60]  # delay in minutes


def generate_synthetic_dataset(output_path: str, seed: int = RANDOM_SEED) -> Dict[str, Any]:
    """Generate reproducible synthetic time-series dataset."""
    random.seed(seed)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    base_date = "2026-10-10"
    records: List[Dict[str, Any]] = []

    # Simulate 4 festival event scenarios
    for delay_mins in DELAY_SCENARIOS:
        event_end_mins = 21 * 60 + delay_mins  # Baseline 21:00 (9:00 PM) + delay
        end_hr = event_end_mins // 60
        end_min = event_end_mins % 60
        end_time_str = f"{end_hr:02d}:{end_min:02d}"

        for weather in WEATHER_CONDITIONS:
            weather_surge_mult = 1.0 if weather == "Clear" else (1.18 if weather == "Light Rain" else 1.35)
            weather_early_mult = 1.0 if weather == "Clear" else (1.25 if weather == "Light Rain" else 1.60)

            # Generate 24 time intervals of 15 minutes each (18:00 to 00:00)
            start_mins = 18 * 60
            for slot_idx in range(25):
                cur_mins = start_mins + (slot_idx * 15)
                cur_hr = cur_mins // 60
                cur_min = cur_mins % 60
                interval_str = f"{cur_hr:02d}:{cur_min:02d}"
                timestamp_iso = f"{base_date}T{interval_str}:00"

                # Delta from event headline end
                delta_mins = cur_mins - event_end_mins

                # Curve formulation: Gamma-like surge peaking 15-30 mins after finale
                if delta_mins < -60:
                    # Early festival phase: minimal exits
                    surge_weight = 0.015
                    crowd_in_venue = random.randint(38000, 40000)
                elif -60 <= delta_mins < 0:
                    # Pre-finale leavers
                    frac = (delta_mins + 60) / 60.0
                    surge_weight = (0.02 + 0.05 * frac) * weather_early_mult
                    crowd_in_venue = int(40000 - (surge_weight * 8000))
                elif 0 <= delta_mins <= 45:
                    # Massive peak surge interval
                    # Peak at ~20 mins post finale
                    peak_curve = math.sin((delta_mins / 45.0) * (math.pi / 2))
                    surge_weight = (0.15 + 0.12 * peak_curve) * weather_surge_mult
                    crowd_in_venue = max(5000, int(35000 - (delta_mins * 600)))
                elif 45 < delta_mins <= 90:
                    # Dispersal winding down
                    decay = (90 - delta_mins) / 45.0
                    surge_weight = (0.05 + 0.08 * decay)
                    crowd_in_venue = max(1000, int(12000 - (delta_mins * 120)))
                else:
                    # Late night residual
                    surge_weight = max(0.005, 0.02 - (delta_mins - 90) * 0.0002)
                    crowd_in_venue = max(100, int(3000 - (delta_mins * 30)))

                total_window_leavers = int(40000 * surge_weight)

                for stop in STOPS:
                    stop_demand = int(total_window_leavers * stop["share"])
                    # Camera crowd density count (distinct from departure queue)
                    # Crowd count at stop includes waiting passengers + passersby
                    density_noise = random.randint(-15, 20)
                    crowd_density = max(10, int(stop_demand * 0.35) + density_noise)

                    # Scheduled capacity
                    if stop["is_hub"]:
                        sched_buses = 12
                        capacity = sched_buses * 70  # 840 seats per wave
                    elif stop["stop_id"] == "STOP_NEARBY":
                        sched_buses = 1  # 4 idle buses available
                        capacity = sched_buses * 70
                    else:
                        sched_buses = 2
                        capacity = sched_buses * 70

                    unmet_demand = max(0, stop_demand - capacity)
                    avg_wait_mins = min(90, int((stop_demand / max(1, capacity)) * 12))

                    record = {
                        "timestamp": timestamp_iso,
                        "date": base_date,
                        "time_slot": interval_str,
                        "scenario_delay_mins": delay_mins,
                        "event_end_time": end_time_str,
                        "weather": weather,
                        "stop_id": stop["stop_id"],
                        "stop_name": stop["stop_name"],
                        "is_hub": 1 if stop["is_hub"] else 0,
                        "venue_total_crowd": crowd_in_venue,
                        "passenger_departure_demand": stop_demand,
                        "stop_crowd_density_count": crowd_density,
                        "scheduled_buses": sched_buses,
                        "bus_capacity": capacity,
                        "unmet_demand": unmet_demand,
                        "est_wait_time_mins": avg_wait_mins,
                        "data_source": "synthetic"
                    }
                    records.append(record)

    # Write CSV
    fieldnames = list(records[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return {
        "status": "SUCCESS",
        "output_file": output_path,
        "record_count": len(records),
        "seed": seed,
        "scenarios_covered": len(DELAY_SCENARIOS) * len(WEATHER_CONDITIONS),
        "stops_count": len(STOPS)
    }


if __name__ == "__main__":
    out_file = os.path.join(os.path.dirname(__file__), "synthetic_festival_demand.csv")
    res = generate_synthetic_dataset(out_file)
    print(f"Generated {res['record_count']} synthetic records at {res['output_file']}")
