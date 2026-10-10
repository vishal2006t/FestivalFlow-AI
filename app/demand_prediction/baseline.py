"""Transparent, rule-based baseline demand predictor for FestivalFlow AI.

This module explicitly implements an explainable heuristic baseline rather than
falsely claiming to be a trained machine-learning model. It defines modular
hooks so that an XGBoost or LightGBM regression model can be seamlessly integrated
when historical festival datasets become available.
"""

from typing import Any, Dict, List, Optional
from .interface import DemandPredictorInterface


WEATHER_MULTIPLIERS = {
    "Clear": {
        "surge_multiplier": 1.0,
        "early_departure_factor": 1.0,
        "peak_window_shift_mins": 0,
        "description": "Clear skies: Standard exit dispersion over the 2-hour window."
    },
    "Light Rain": {
        "surge_multiplier": 1.15,
        "early_departure_factor": 1.25,
        "peak_window_shift_mins": -15,
        "description": "Light rain accelerates festival departure, shifting peak 15 mins earlier with +15% surge intensity."
    },
    "Heavy Rain": {
        "surge_multiplier": 1.35,
        "early_departure_factor": 1.60,
        "peak_window_shift_mins": -30,
        "description": "Heavy rain forces attendees toward transit immediately (+35% peak surge concentration)."
    }
}


class RuleBasedDemandPredictor(DemandPredictorInterface):
    """Transparent rule-based demand predictor.

    Estimates 15-minute passenger demand using:
    - Festival ending time (22:00 headline act finish)
    - Surge distribution curve (approximated gamma-like curve peaking 15-45 mins after finale)
    - Weather multipliers (accelerates exit timing and compresses queue arrival)
    - Stop proximity split (Main Stand 94%, Nearby 6% walking overflow)
    """

    def __init__(self):
        self.model_name = "RuleBasedExplainableBaseline-v1"
        self.is_ml_model = False

    def predict_demand(
        self,
        festival_info: Dict[str, Any],
        weather_info: Dict[str, Any],
        stops: List[Dict[str, Any]],
        intervals: List[str],
        baseline_matrix: Optional[Dict[str, List[int]]] = None
    ) -> Dict[str, Any]:
        weather_condition = weather_info.get("condition", "Clear")
        weather_params = WEATHER_MULTIPLIERS.get(
            weather_condition,
            WEATHER_MULTIPLIERS["Clear"]
        )

        surge_mult = weather_params["surge_multiplier"]
        early_mult = weather_params["early_departure_factor"]

        predictions: Dict[str, List[int]] = {}
        confidence_intervals: Dict[str, List[Dict[str, int]]] = {}

        # Default fallbacks if baseline matrix is not provided
        total_crowd = festival_info.get("expected_exit_crowd", 40000)

        for stop in stops:
            stop_id = stop["stop_id"]
            is_hub = stop.get("is_festival_hub", False)

            if baseline_matrix and stop_id in baseline_matrix:
                raw_curve = baseline_matrix[stop_id]
                adjusted_curve = []
                conf_curve = []

                for idx, count in enumerate(raw_curve):
                    # Intervals before 22:00 (first 4 slots: 21:00 - 21:45) affected by early_departure
                    if idx < 4:
                        adjusted_val = int(count * early_mult)
                    # Peak intervals 22:00 - 22:45 (slots 4, 5, 6, 7) affected by surge multiplier
                    elif 4 <= idx <= 7:
                        adjusted_val = int(count * surge_mult)
                    else:
                        adjusted_val = count

                    adjusted_curve.append(adjusted_val)
                    # Heuristic uncertainty bounds (±15%)
                    conf_curve.append({
                        "lower": max(0, int(adjusted_val * 0.85)),
                        "upper": int(adjusted_val * 1.15)
                    })

                predictions[stop_id] = adjusted_curve
                confidence_intervals[stop_id] = conf_curve
            else:
                # Synthetic curve generation based on stop role
                if is_hub:
                    hub_share = int(total_crowd * 0.85)  # ~85% take transit at Main stand
                    # Distribution weights across 14 intervals
                    weights = [0.01, 0.02, 0.04, 0.07, 0.18, 0.24, 0.20, 0.13, 0.06, 0.03, 0.01, 0.005, 0.003, 0.002]
                else:
                    hub_share = int(total_crowd * 0.05)  # ~5% walk to nearby stop
                    weights = [0.04, 0.04, 0.05, 0.07, 0.13, 0.20, 0.24, 0.14, 0.05, 0.02, 0.01, 0.005, 0.003, 0.002]

                vals = [int(hub_share * w * (surge_mult if 4 <= i <= 7 else 1.0)) for i, w in enumerate(weights)]
                predictions[stop_id] = vals
                confidence_intervals[stop_id] = [
                    {"lower": max(0, int(v * 0.85)), "upper": int(v * 1.15)} for v in vals
                ]

        return {
            "model_type": self.model_name,
            "is_ml_model": self.is_ml_model,
            "future_upgrade_path": "XGBoostRegressor pipeline with historical passenger taps and weather features",
            "intervals": intervals,
            "predictions": predictions,
            "confidence_intervals": confidence_intervals,
            "explanation": {
                "weather_condition": weather_condition,
                "weather_effect": weather_params["description"],
                "peak_expected_interval": "22:15 - 22:30",
                "surge_multiplier_applied": surge_mult,
                "early_departure_multiplier_applied": early_mult,
                "notes": (
                    "Transparent baseline: Passenger arrival follows expected post-event exit surge. "
                    "Weather modifiers shift peak timing and compress queue arrival rates."
                )
            }
        }
