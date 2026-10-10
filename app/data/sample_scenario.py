"""Sample demonstration data and scenario definitions for FestivalFlow AI.

Explicit problem statement values:
- ~40,000 festival leavers in 2 hours
- Main Bus Stand: 12 scheduled buses, rapid congestion within 30 mins
- Nearby stop: 2 km away with 4 idle buses
- Fixed fleet constraint: No new buses created

All other supporting parameters (e.g., standard bus capacity, transit speed,
weather modifiers) are clearly flagged as DEMO_ASSUMPTION.
"""

from typing import Any, Dict, List

DEMO_SCENARIO: Dict[str, Any] = {
    "festival": {
        "event_name": "Grand City Lights Music & Cultural Festival",
        "date": "2026-10-10",
        "start_time": "18:00",
        "headline_end_time": "22:00",
        "curfew_time": "00:00",
        "expected_exit_crowd": 40000,  # Given scenario
        "exit_window_hours": 2.0,       # Given scenario (2 hours: 22:00 to 24:00)
        "weather_forecast": {
            "condition": "Clear",        # Supported: Clear, Rain, Heavy Rain
            "rain_probability_pct": 10,
            "temperature_celsius": 26.0,
            "status": "DEMO_ASSUMPTION"
        }
    },
    "network": {
        "fleet_constraint": "STRICTLY_FIXED_FLEET",
        "total_network_buses": 17,  # 12 at Main Stand + 4 Idle at Nearby + 1 Active at Nearby
        "travel_time_between_stops_mins": 12,  # 2 km distance @ ~10 km/h festival traffic (DEMO_ASSUMPTION)
        "distance_km": 2.0,                    # Given scenario
        "standard_bus_capacity": 70,           # 50 seated + 20 standing (DEMO_ASSUMPTION)
        "bus_cycle_turnaround_mins": 25        # Round-trip cycle time per bus (DEMO_ASSUMPTION)
    },
    "stops": [
        {
            "stop_id": "STOP_MAIN",
            "name": "Main Bus Stand (Festival Arena)",
            "is_festival_hub": True,
            "distance_from_festival_km": 0.2,
            "current_scheduled_buses": 12,    # Given scenario
            "idle_buses": 0,
            "min_service_buses": 12,          # Minimum baseline service scheduled
            "capacity_per_bus": 70,
            "status": "GIVEN_SCENARIO"
        },
        {
            "stop_id": "STOP_NEARBY",
            "name": "Tech Hub North Stop (2km away)",
            "is_festival_hub": False,
            "distance_from_festival_km": 2.0, # Given scenario
            "current_scheduled_buses": 1,     # Regular scheduled commuter line
            "idle_buses": 4,                  # Given scenario: 4 idle buses
            "min_service_buses": 1,           # DEMO_ASSUMPTION: Must retain at least 1 bus for regular local riders
            "capacity_per_bus": 70,
            "status": "GIVEN_SCENARIO"
        }
    ],
    "intervals": [
        "21:00", "21:15", "21:30", "21:45",
        "22:00", "22:15", "22:30", "22:45",
        "23:00", "23:15", "23:30", "23:45",
        "00:00", "00:15"
    ],
    # Demonstration baseline 15-minute demand distribution (attendees seeking public transit)
    # Total festival transit demand modeled: ~34,000 at Main Bus Stand + ~2,000 at Nearby Stop (remainder walked/rideshare)
    "baseline_demand_matrix": {
        "STOP_MAIN": [
            300, 500, 1100, 2200,   # 21:00 - 21:45 (Early leavers)
            6500, 8200, 7100, 4800,  # 22:00 - 22:45 (Peak exit surge right after 22:00 finale)
            2600, 1300, 600, 300,   # 23:00 - 23:45 (Tapering tail)
            150, 50                 # 00:00 - 00:15 (Late night)
        ],
        "STOP_NEARBY": [
            80, 90, 110, 140,       # 21:00 - 21:45 (Local commuter baseline)
            260, 420, 490, 380,     # 22:00 - 22:45 (Mild walk-in festival overflow)
            210, 120, 70, 40,       # 23:00 - 23:45 (Local baseline + slight taper)
            20, 10                  # 00:00 - 00:15
        ]
    }
}


def get_default_scenario() -> Dict[str, Any]:
    """Return a deep copy of the default demo scenario."""
    import copy
    return copy.deepcopy(DEMO_SCENARIO)
