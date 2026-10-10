"""Constraint and optimization validation tests for FestivalFlow AI.

Verifies:
1. Fleet Conservation: Total fleet size is strictly unchanged.
2. Minimum Service: Source stop never falls below minimum required buses.
3. Travel Time: Reallocation departure time allows arrival BEFORE demand peak.
4. Trade-off Disclosure: Source stop service impact is explicitly quantified.
5. Feasibility & Unmet Demand: Warnings are surfaced when fixed capacity cannot clear peak surge.
"""

import pytest
from app.data.sample_scenario import get_default_scenario
from app.demand_prediction.baseline import RuleBasedDemandPredictor
from app.bus_optimization.optimizer import BusReallocationOptimizer


@pytest.fixture
def optimizer():
    return BusReallocationOptimizer()


@pytest.fixture
def predictor():
    return RuleBasedDemandPredictor()


def test_strict_fleet_conservation(optimizer, predictor):
    """Total buses in the network before must exactly equal total buses after."""
    scenario = get_default_scenario()
    demand = predictor.predict_demand(
        festival_info=scenario["festival"],
        weather_info=scenario["festival"]["weather_forecast"],
        stops=scenario["stops"],
        intervals=scenario["intervals"],
        baseline_matrix=scenario["baseline_demand_matrix"]
    )

    result = optimizer.optimize_reallocation(scenario, demand)

    before = result["fleet_conservation"]["total_fleet_before"]
    after = result["fleet_conservation"]["total_fleet_after"]
    assert before == after, f"Fleet not conserved! before={before}, after={after}"
    assert result["fleet_conservation"]["is_conserved"] is True


def test_minimum_service_constraint_respected(optimizer, predictor):
    """Source stop must never be stripped below min_service_buses."""
    scenario = get_default_scenario()
    # Find nearby stop
    nearby_stop = next(s for s in scenario["stops"] if s["stop_id"] == "STOP_NEARBY")
    min_required = nearby_stop["min_service_buses"]

    demand = predictor.predict_demand(
        festival_info=scenario["festival"],
        weather_info=scenario["festival"]["weather_forecast"],
        stops=scenario["stops"],
        intervals=scenario["intervals"],
        baseline_matrix=scenario["baseline_demand_matrix"]
    )

    result = optimizer.optimize_reallocation(scenario, demand)
    source_stats = result["before_and_after_comparison"]["source_stop"]

    assert source_stats["buses_after"] >= min_required
    assert source_stats["service_level_status"] == "COMPLIANT_WITH_MINIMUM"


def test_proactive_departure_before_peak(optimizer, predictor):
    """Bus departure must be scheduled early enough to reach Main Stand before peak."""
    scenario = get_default_scenario()
    demand = predictor.predict_demand(
        festival_info=scenario["festival"],
        weather_info=scenario["festival"]["weather_forecast"],
        stops=scenario["stops"],
        intervals=scenario["intervals"],
        baseline_matrix=scenario["baseline_demand_matrix"]
    )

    result = optimizer.optimize_reallocation(scenario, demand)
    assert len(result["reallocations"]) > 0

    realloc = result["reallocations"][0]
    dep_time = realloc["recommended_departure_time"]
    arr_time = realloc["expected_arrival_time"]

    dep_hour, dep_min = map(int, dep_time.split(":"))
    arr_hour, arr_min = map(int, arr_time.split(":"))

    dep_total_mins = dep_hour * 60 + dep_min
    arr_total_mins = arr_hour * 60 + arr_min

    # Transit time must be accounted for
    assert arr_total_mins > dep_total_mins
    # Arrival must be at or before 22:00 (event end) so buses are waiting when crowd exits
    assert arr_total_mins <= 22 * 60


def test_source_service_tradeoff_reported(optimizer, predictor):
    """The system must report how the source stop service is impacted."""
    scenario = get_default_scenario()
    demand = predictor.predict_demand(
        festival_info=scenario["festival"],
        weather_info=scenario["festival"]["weather_forecast"],
        stops=scenario["stops"],
        intervals=scenario["intervals"],
        baseline_matrix=scenario["baseline_demand_matrix"]
    )

    result = optimizer.optimize_reallocation(scenario, demand)
    realloc = result["reallocations"][0]

    assert "source_impact" in realloc
    source_impact = realloc["source_impact"]
    assert "remaining_buses" in source_impact
    assert "service_retained_pct" in source_impact
    assert "headway_change" in source_impact


def test_unmet_demand_warning_displayed(optimizer, predictor):
    """When crowd of 40,000 exceeds fixed fleet capacity, unmet demand must be warned."""
    scenario = get_default_scenario()
    demand = predictor.predict_demand(
        festival_info=scenario["festival"],
        weather_info=scenario["festival"]["weather_forecast"],
        stops=scenario["stops"],
        intervals=scenario["intervals"],
        baseline_matrix=scenario["baseline_demand_matrix"]
    )

    result = optimizer.optimize_reallocation(scenario, demand)
    warnings = result["warnings"]

    # There should be a warning acknowledging that 15 buses cannot clear 40,000 in 2h
    has_unmet_warning = any("UNMET DEMAND" in w for w in warnings)
    assert has_unmet_warning, "Expected unmet demand warning when fixed fleet is overloaded"
