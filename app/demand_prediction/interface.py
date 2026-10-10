"""Interface definition for FestivalFlow AI demand prediction."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DemandPredictorInterface(ABC):
    """Abstract base class for passenger demand predictors."""

    @abstractmethod
    def predict_demand(
        self,
        festival_info: Dict[str, Any],
        weather_info: Dict[str, Any],
        stops: List[Dict[str, Any]],
        intervals: List[str],
        baseline_matrix: Dict[str, List[int]] = None
    ) -> Dict[str, Any]:
        """Estimate passenger demand for each stop across designated time intervals.

        Returns:
            Dict containing:
                - model_type (str)
                - is_ml_model (bool)
                - intervals (list of str)
                - predictions (dict mapping stop_id to list of predicted passenger counts)
                - explanation (dict of heuristics, weather modifiers, peak window)
        """
        pass
