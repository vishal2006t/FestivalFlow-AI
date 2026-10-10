"""Night Safety Passenger Waiting & Overcrowding Alert System.

Monitors:
1. Night-time hours (20:00 - 05:00) and post-event festival egress windows.
2. Passenger waiting duration: flags queue delays exceeding safety thresholds (> 15-20 mins).
3. Overcrowding in low-visibility or low-frequency night transit zones.
4. Generates prioritized safety recommendations and direct driver dispatch notifications.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


class NightSafetyChecker:
    """Evaluates late-night transit risks and generates night passenger safety alerts."""

    def __init__(self, night_start_hour: int = 20, night_end_hour: int = 5, safety_wait_threshold_mins: int = 15):
        self.night_start_hour = night_start_hour
        self.night_end_hour = night_end_hour
        self.safety_wait_threshold_mins = safety_wait_threshold_mins

    def is_night_window(self, check_time: Optional[datetime] = None) -> bool:
        """Return True if check_time falls within late-night or early-morning operations."""
        t = check_time or datetime.now()
        return t.hour >= self.night_start_hour or t.hour < self.night_end_hour

    def evaluate_stop_safety(
        self,
        stop_id: str,
        stop_name: str,
        crowd_count: int,
        estimated_wait_mins: int,
        is_hub: bool = True,
        check_time: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """Evaluate passenger safety risk at a bus stop during night operations."""
        now = check_time or datetime.now()
        is_night = self.is_night_window(now)

        # Trigger conditions for Night Safety alert:
        # 1. It is night time AND waiting time exceeds safety threshold
        # 2. OR crowd count is high/critical (> 80) at night
        if not is_night and estimated_wait_mins < 30 and crowd_count < 120:
            return None

        # Determine severity
        if (crowd_count >= 100 and estimated_wait_mins >= 20) or estimated_wait_mins >= 30:
            severity = "CRITICAL"
        elif crowd_count >= 60 or estimated_wait_mins >= self.safety_wait_threshold_mins:
            severity = "HIGH"
        else:
            severity = "MEDIUM"

        headline = f"NIGHT SAFETY ALERT: {crowd_count} passengers waiting at {stop_name}"
        if estimated_wait_mins > self.safety_wait_threshold_mins:
            headline += f" (~{estimated_wait_mins} min delay)"

        safety_advisories = [
            f"Passenger wait time of ~{estimated_wait_mins} mins exceeds the {self.safety_wait_threshold_mins}-min night safety standard.",
            "High concentration of late-night festival leavers with reduced ambient visibility.",
            "Queue stagnation increases vulnerability to crowd surges and physical fatigue."
        ]

        action_recommendations = [
            "Proactively stage high-capacity underutilized shuttle (BUS-203 / BUS-204) at Bay 2.",
            "Notify assigned driver immediately to begin expedited boarding.",
            "Ensure station floodlights and passenger information displays remain active."
        ]

        return {
            "alert_type": "NIGHT_SAFETY",
            "severity": severity,
            "stop_id": stop_id,
            "stop_name": stop_name,
            "headline": headline,
            "crowd_count": crowd_count,
            "waiting_time_mins": estimated_wait_mins,
            "safety_wait_threshold_mins": self.safety_wait_threshold_mins,
            "is_night_time": is_night,
            "timestamp": now.isoformat(),
            "safety_advisories": safety_advisories,
            "action_recommendations": action_recommendations,
            "driver_notification_template": {
                "title": f"🚨 URGENT: Night Crowd Clearance at {stop_name}",
                "message": (
                    f"Priority Night Safety Run: {crowd_count} passengers currently waiting at {stop_name} "
                    f"with ~{estimated_wait_mins}m queue delay. Proceed to platform bay for expedited clearance."
                ),
                "severity": severity
            }
        }
