"""Demand prediction package for FestivalFlow AI."""
from .interface import DemandPredictorInterface
from .baseline import RuleBasedDemandPredictor, WEATHER_MULTIPLIERS

__all__ = [
    "DemandPredictorInterface",
    "RuleBasedDemandPredictor",
    "WEATHER_MULTIPLIERS"
]
