"""OpenRouter AI Integration Service for FestivalFlow AI.

Provides optional backend-only generative explanations of:
- Why the optimizer recommends moving a particular bus.
- Summaries of passenger demand changes for Depot Admins.
- Plain-language explanations of unmet demand and operational constraints.
- Impacts of event delays (Scenario A) and weather shifts (Scenario B).

Architecture Guardrails:
1. OpenRouter NEVER performs numerical demand forecasting or bus allocation.
   Deterministic mathematical models in demand_prediction and bus_optimization handle all calculations.
2. AI explanations strictly translate calculated backend results into human-readable operations briefings.
3. Operates gracefully without an API key (deterministic heuristic explanation fallback).
4. Zero secret exposure: API keys and auth headers are never logged or returned to clients.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("festivalflow.ai_explainer")

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash"


def get_configured_model() -> str:
    """Return the model configured in the environment, or default."""
    return os.environ.get("OPENROUTER_MODEL", "").strip() or DEFAULT_MODEL


def is_openrouter_configured() -> bool:
    """Check if an OpenRouter API key is present in environment."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    return bool(key)


def get_ai_status() -> Dict[str, Any]:
    """Return non-sensitive status of the AI explanation service."""
    configured = is_openrouter_configured()
    model = get_configured_model()
    return {
        "provider": "OpenRouter",
        "configured": configured,
        "model": model,
        "status": "READY" if configured else "FALLBACK_MODE",
        "note": (
            "Live generative explanations enabled via OpenRouter"
            if configured
            else "Operating in deterministic rule-based explanation mode (No OPENROUTER_API_KEY configured)"
        )
    }


def _call_openrouter(system_prompt: str, user_prompt: str, timeout_seconds: float = 8.0) -> Optional[str]:
    """Backend-only HTTP client for OpenRouter chat completions.
    
    Catches timeouts, connection errors, and quotas safely without crashing.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None

    model = get_configured_model()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://festivalflow.ai",
        "X-Title": "FestivalFlow AI Operations Engine"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 400
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(OPENROUTER_ENDPOINT, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "").strip()
            else:
                logger.warning("OpenRouter API returned non-200 code: %d", resp.status_code)
                return None
    except Exception as e:
        logger.warning("OpenRouter request failed gracefully: %s", str(e))
        return None


def explain_recommendation(
    reallocations: List[Dict[str, Any]],
    hub_stop_name: str,
    source_stop_name: str,
    buses_moved: int,
    unmet_demand_after: int,
    peak_demand: int,
    travel_time_mins: int,
    departure_time: str
) -> Dict[str, Any]:
    """Generate plain-language explanation of a proactive bus reallocation plan."""
    # Deterministic baseline explanation
    baseline_explanation = (
        f"The optimizer recommends proactively moving {buses_moved} buses from '{source_stop_name}' to "
        f"'{hub_stop_name}' departing at {departure_time} ({travel_time_mins} min transit). "
        f"This directly addresses the peak surge of {peak_demand:,} passengers exiting the festival arena. "
        f"'{source_stop_name}' retains sufficient minimum service to protect commuter travel. "
        f"{'Remaining unmet demand is ' + str(unmet_demand_after) + ' passengers due to the strictly fixed fleet capacity.' if unmet_demand_after > 0 else 'All anticipated exit demand is accommodated.'}"
    )

    if not is_openrouter_configured():
        return {
            "source": "DETERMINISTIC_BASELINE",
            "model": "RuleBasedExplainer-v1",
            "explanation": baseline_explanation,
            "buses_moved": buses_moved,
            "departure_time": departure_time
        }

    sys_prompt = (
        "You are an expert municipal public transit operations assistant for festival crowd dispersal. "
        "Summarize the calculated bus reallocation recommendation in 2 to 3 concise, professional sentences. "
        "DO NOT invent new numbers or change bus counts. Strictly use the provided data."
    )
    user_prompt = (
        f"Calculated Data:\n"
        f"- Target stop: {hub_stop_name}\n"
        f"- Source stop: {source_stop_name}\n"
        f"- Recommended buses moved: {buses_moved}\n"
        f"- Staging departure time: {departure_time} (Transit time: {travel_time_mins} mins)\n"
        f"- Peak crowd volume: {peak_demand} passengers\n"
        f"- Unmet demand remaining: {unmet_demand_after} passengers\n"
        "Explain the operational logic and staging benefit."
    )

    llm_resp = _call_openrouter(sys_prompt, user_prompt)
    if llm_resp:
        return {
            "source": "OPENROUTER_AI",
            "model": get_configured_model(),
            "explanation": llm_resp,
            "buses_moved": buses_moved,
            "departure_time": departure_time
        }

    return {
        "source": "DETERMINISTIC_FALLBACK",
        "model": "RuleBasedExplainer-v1",
        "explanation": baseline_explanation,
        "buses_moved": buses_moved,
        "departure_time": departure_time
    }


def explain_scenario_change(
    scenario_type: str,
    old_value: str,
    new_value: str,
    demand_change_summary: str,
    recommendation_change_summary: str
) -> Dict[str, Any]:
    """Generate operations summary for live input changes (e.g. event delay or rain)."""
    baseline_summary = (
        f"Operational parameter updated: {scenario_type} shifted from {old_value} to {new_value}. "
        f"Demand Impact: {demand_change_summary}. "
        f"Fleet Recommendation: {recommendation_change_summary}. "
        "Note: In accordance with safety protocol, all reallocations remain advisory pending Depot Admin manual approval."
    )

    if not is_openrouter_configured():
        return {
            "source": "DETERMINISTIC_BASELINE",
            "model": "RuleBasedExplainer-v1",
            "summary": baseline_summary
        }

    sys_prompt = (
        "You are a public transit operations coordinator briefing a Depot Admin during a major festival. "
        "Provide a 2-sentence executive summary of the operational recalculation."
    )
    user_prompt = (
        f"Change details:\n"
        f"- Parameter: {scenario_type}\n"
        f"- Old value: {old_value}\n"
        f"- New value: {new_value}\n"
        f"- Demand impact: {demand_change_summary}\n"
        f"- Fleet impact: {recommendation_change_summary}\n"
    )

    llm_resp = _call_openrouter(sys_prompt, user_prompt)
    if llm_resp:
        return {
            "source": "OPENROUTER_AI",
            "model": get_configured_model(),
            "summary": llm_resp
        }

    return {
        "source": "DETERMINISTIC_FALLBACK",
        "model": "RuleBasedExplainer-v1",
        "summary": baseline_summary
    }
