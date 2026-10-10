"""Weather integration service for FestivalFlow AI using Open-Meteo API.

Features:
- Configurable festival locations (presets + custom latitude/longitude)
- Real-time forecast fetching (temperature, precipitation, rain probability, wind, WMO code)
- In-memory caching (10-minute TTL) with last-known fallback retention
- Honest failure handling (flags live_unavailable without fabricating fake weather)
- Feature extraction converting raw weather into transparent demand modifiers
- Full Open-Meteo attribution and documentation links
"""

import os
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger("festivalflow.weather")

OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


# Open-Meteo WMO Weather Interpretation Codes (WW)
# Source: https://open-meteo.com/en/docs
WMO_WEATHER_CODES: Dict[int, Dict[str, Any]] = {
    0: {"description": "Clear sky", "icon": "☀️", "category": "Clear", "severity": 0},
    1: {"description": "Mainly clear", "icon": "🌤️", "category": "Clear", "severity": 0},
    2: {"description": "Partly cloudy", "icon": "⛅", "category": "Partly Cloudy", "severity": 0},
    3: {"description": "Overcast", "icon": "☁️", "category": "Overcast", "severity": 1},
    45: {"description": "Fog", "icon": "🌫️", "category": "Foggy", "severity": 1},
    48: {"description": "Depositing rime fog", "icon": "🌫️", "category": "Foggy", "severity": 1},
    51: {"description": "Light drizzle", "icon": "🌦️", "category": "Light Rain", "severity": 2},
    53: {"description": "Moderate drizzle", "icon": "🌦️", "category": "Light Rain", "severity": 2},
    55: {"description": "Dense drizzle", "icon": "🌧️", "category": "Light Rain", "severity": 2},
    56: {"description": "Light freezing drizzle", "icon": "🌧️", "category": "Light Rain", "severity": 2},
    57: {"description": "Dense freezing drizzle", "icon": "🌧️", "category": "Light Rain", "severity": 3},
    61: {"description": "Slight rain", "icon": "🌦️", "category": "Light Rain", "severity": 2},
    63: {"description": "Moderate rain", "icon": "🌧️", "category": "Moderate Rain", "severity": 3},
    65: {"description": "Heavy rain", "icon": "🌧️", "category": "Heavy Rain", "severity": 4},
    66: {"description": "Light freezing rain", "icon": "🌧️", "category": "Moderate Rain", "severity": 3},
    67: {"description": "Heavy freezing rain", "icon": "🌧️", "category": "Heavy Rain", "severity": 4},
    71: {"description": "Slight snow fall", "icon": "🌨️", "category": "Snow", "severity": 3},
    73: {"description": "Moderate snow fall", "icon": "🌨️", "category": "Snow", "severity": 3},
    75: {"description": "Heavy snow fall", "icon": "❄️", "category": "Snow", "severity": 4},
    77: {"description": "Snow grains", "icon": "❄️", "category": "Snow", "severity": 2},
    80: {"description": "Slight rain showers", "icon": "🌦️", "category": "Light Rain", "severity": 2},
    81: {"description": "Moderate rain showers", "icon": "🌧️", "category": "Moderate Rain", "severity": 3},
    82: {"description": "Violent rain showers", "icon": "⛈️", "category": "Heavy Rain", "severity": 4},
    85: {"description": "Slight snow showers", "icon": "🌨️", "category": "Snow", "severity": 3},
    86: {"description": "Heavy snow showers", "icon": "❄️", "category": "Snow", "severity": 4},
    95: {"description": "Thunderstorm", "icon": "⛈️", "category": "Thunderstorm", "severity": 4},
    96: {"description": "Thunderstorm with slight hail", "icon": "⛈️", "category": "Thunderstorm", "severity": 5},
    99: {"description": "Thunderstorm with heavy hail", "icon": "⛈️", "category": "Thunderstorm", "severity": 5},
}

PRESET_LOCATIONS: List[Dict[str, Any]] = [
    {
        "id": "cbe_arena",
        "name": "Grand Cultural Arena (Coimbatore, IN)",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "region": "Tamil Nadu, India"
    },
    {
        "id": "chennai_marina",
        "name": "Marina Festival Grounds (Chennai, IN)",
        "latitude": 13.0475,
        "longitude": 80.2824,
        "region": "Tamil Nadu, India"
    },
    {
        "id": "delhi_jln",
        "name": "Jawaharlal Nehru Stadium Arena (Delhi, IN)",
        "latitude": 28.5828,
        "longitude": 77.2344,
        "region": "Delhi, India"
    },
    {
        "id": "mumbai_bkc",
        "name": "BKC Festival Park (Mumbai, IN)",
        "latitude": 19.0662,
        "longitude": 72.8687,
        "region": "Maharashtra, India"
    },
    {
        "id": "glastonbury_uk",
        "name": "Worthy Farm Festival Grounds (Glastonbury, UK)",
        "latitude": 51.1537,
        "longitude": -2.5855,
        "region": "Somerset, United Kingdom"
    },
    {
        "id": "coachella_us",
        "name": "Empire Polo Club Arena (Indio, CA, US)",
        "latitude": 33.6799,
        "longitude": -116.2372,
        "region": "California, United States"
    }
]

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
ATTRIBUTION_TEXT = "Weather data provided by Open-Meteo.com (CC BY 4.0)"
ATTRIBUTION_URL = "https://open-meteo.com/en/docs"
CACHE_TTL_SECONDS = 600  # 10 minutes


class WeatherService:
    """Manages Open-Meteo integration, response caching, fallback retention,
    and translation into operational festival demand features.
    """

    def __init__(self, cache_ttl: int = CACHE_TTL_SECONDS):
        self.cache_ttl = cache_ttl
        # Key: (round(lat, 3), round(lon, 3)) -> (timestamp, data)
        self._cache: Dict[Tuple[float, float], Tuple[float, Dict[str, Any]]] = {}
        # Retained last known weather per coordinate
        self._last_known: Dict[Tuple[float, float], Dict[str, Any]] = {}

    def get_preset_locations(self) -> List[Dict[str, Any]]:
        """Return configurable venue presets."""
        return PRESET_LOCATIONS

    def _cache_key(self, lat: float, lon: float) -> Tuple[float, float]:
        return (round(float(lat), 3), round(float(lon), 3))

    @staticmethod
    def is_api_enabled() -> bool:
        """Check whether external weather API is enabled in environment."""
        return os.environ.get("WEATHER_API_ENABLED", "false").lower() in ["true", "1", "yes"]

    @staticmethod
    def get_provider() -> str:
        """Return configured weather provider ('open-meteo' or 'openweather')."""
        return os.environ.get("WEATHER_PROVIDER", "open-meteo").strip().lower()

    @staticmethod
    def get_openweather_key() -> str:
        """Return configured OpenWeather API key if present."""
        return os.environ.get("OPENWEATHER_API_KEY", "").strip()

    def get_synthetic_baseline(
        self,
        latitude: float,
        longitude: float,
        condition: str = "Clear",
        source_label: str = "synthetic"
    ) -> Dict[str, Any]:
        """Generate an explicitly labelled synthetic or manual baseline weather record."""
        now = time.time()
        category_map = {
            "Clear": ("Clear sky", "☀️", 28.0, 0.0, 5, 0),
            "Light Rain": ("Light rain showers", "🌦️", 23.0, 1.2, 75, 2),
            "Heavy Rain": ("Heavy thunderstorm rain", "⛈️", 20.0, 6.5, 95, 4),
            "Cloudy": ("Overcast clouds", "☁️", 25.0, 0.0, 20, 1),
            "Partly Cloudy": ("Partly cloudy", "⛅", 27.0, 0.0, 10, 0)
        }
        desc, icon, temp, precip, rain_prob, severity = category_map.get(
            condition, category_map["Clear"]
        )
        features = self._derive_features(
            weather_code=0 if condition == "Clear" else (61 if condition == "Light Rain" else 65),
            category=condition,
            temp_c=temp,
            precip_mm=precip,
            rain_prob_pct=rain_prob,
            wind_kmh=12.0
        )
        return {
            "status": "MANUAL_BASELINE" if source_label == "manual" else "SYNTHETIC_PROTOTYPE",
            "is_live": False,
            "live_unavailable": False,
            "source_label": source_label,  # 'live', 'manual', 'synthetic', or 'unknown'
            "is_cached": False,
            "latitude": latitude,
            "longitude": longitude,
            "temperature_celsius": temp,
            "precipitation_probability_pct": rain_prob,
            "precipitation_amount_mm": precip,
            "wind_speed_kmh": 12.0,
            "weather_code": 0,
            "weather_condition": desc,
            "weather_icon": icon,
            "category": condition,
            "forecast_time": time.strftime("%Y-%m-%dT%H:00", time.gmtime(now)),
            "last_updated_timestamp": int(now),
            "last_updated_time_iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now)),
            "attribution": "FestivalFlow AI Baseline Simulator (Configurable manual/synthetic input)",
            "attribution_url": "https://festivalflow.ai",
            "provider": "Manual / Heuristic",
            "features": features
        }

    def fetch_weather(
        self,
        latitude: float,
        longitude: float,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Fetch weather data adhering to environment configuration and transparent source labeling."""
        # If API is disabled by configuration, return clearly labelled synthetic baseline
        if not self.is_api_enabled():
            return self.get_synthetic_baseline(latitude, longitude, condition="Clear", source_label="synthetic")

        key = self._cache_key(latitude, longitude)
        now = time.time()

        # Check in-memory cache
        if not force_refresh and key in self._cache:
            cached_time, cached_data = self._cache[key]
            if now - cached_time < self.cache_ttl:
                res = dict(cached_data)
                res["is_cached"] = True
                res["cache_age_seconds"] = int(now - cached_time)
                return res

        # Check if OpenWeatherMap provider requested and key configured
        provider_pref = self.get_provider()
        ow_key = self.get_openweather_key()
        if provider_pref == "openweather" and ow_key:
            try:
                with httpx.Client(timeout=8.0) as client:
                    ow_resp = client.get(
                        OPENWEATHER_BASE_URL,
                        params={"lat": latitude, "lon": longitude, "appid": ow_key, "units": "metric"}
                    )
                if ow_resp.status_code == 200:
                    ow_json = ow_resp.json()
                    temp_c = float(ow_json.get("main", {}).get("temp", 25.0))
                    w_item = ow_json.get("weather", [{}])[0]
                    main_w = w_item.get("main", "Clear")
                    desc = w_item.get("description", "Clear sky").capitalize()
                    
                    cat = "Clear"
                    icon = "☀️"
                    if "Rain" in main_w or "Drizzle" in main_w:
                        cat = "Heavy Rain" if "heavy" in desc.lower() else "Light Rain"
                        icon = "🌧️"
                    elif "Cloud" in main_w:
                        cat = "Cloudy" if "overcast" in desc.lower() else "Partly Cloudy"
                        icon = "⛅"
                    elif "Thunderstorm" in main_w:
                        cat = "Thunderstorm"
                        icon = "⛈️"

                    precip_mm = float(ow_json.get("rain", {}).get("1h", 0.0))
                    wind_kmh = round(float(ow_json.get("wind", {}).get("speed", 0.0)) * 3.6, 1)
                    rain_prob = 80 if "Rain" in cat else (10 if cat == "Clear" else 30)

                    features = self._derive_features(
                        weather_code=61 if "Rain" in cat else 0,
                        category=cat,
                        temp_c=temp_c,
                        precip_mm=precip_mm,
                        rain_prob_pct=rain_prob,
                        wind_kmh=wind_kmh
                    )

                    result_data = {
                        "status": "LIVE_SUCCESS",
                        "is_live": True,
                        "live_unavailable": False,
                        "source_label": "live",
                        "provider": "OpenWeatherMap",
                        "is_cached": False,
                        "latitude": latitude,
                        "longitude": longitude,
                        "temperature_celsius": temp_c,
                        "precipitation_probability_pct": rain_prob,
                        "precipitation_amount_mm": precip_mm,
                        "wind_speed_kmh": wind_kmh,
                        "weather_code": 61 if "Rain" in cat else 0,
                        "weather_condition": desc,
                        "weather_icon": icon,
                        "category": cat,
                        "forecast_time": time.strftime("%Y-%m-%dT%H:00", time.gmtime(now)),
                        "last_updated_timestamp": int(now),
                        "last_updated_time_iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now)),
                        "attribution": "OpenWeatherMap API",
                        "attribution_url": "https://openweathermap.org",
                        "features": features
                    }
                    self._cache[key] = (now, result_data)
                    self._last_known[key] = result_data
                    return result_data
            except Exception as e:
                logger.warning(f"OpenWeather call failed: {e}. Falling back to Open-Meteo.")

        # Attempt live API call to Open-Meteo
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
            "hourly": "precipitation_probability,precipitation",
            "forecast_days": 1
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(OPEN_METEO_BASE_URL, params=params)

            if response.status_code == 200:
                raw_json = response.json()
                if raw_json.get("error"):
                    raise ValueError(raw_json.get("reason", "Open-Meteo returned error"))

                current = raw_json.get("current", {})
                hourly = raw_json.get("hourly", {})

                weather_code = int(current.get("weather_code", 0))
                wmo_meta = WMO_WEATHER_CODES.get(
                    weather_code,
                    {"description": f"Weather code {weather_code}", "icon": "🌤️", "category": "Clear", "severity": 0}
                )

                # Extract max rain probability over the next few hours
                hourly_probs = hourly.get("precipitation_probability", [])
                max_rain_prob = max(hourly_probs[:6]) if hourly_probs else 0

                temp_c = float(current.get("temperature_2m", 25.0))
                precip_mm = float(current.get("precipitation", 0.0))
                wind_kmh = float(current.get("wind_speed_10m", 0.0))
                forecast_time = current.get("time", "")

                features = self._derive_features(
                    weather_code=weather_code,
                    category=wmo_meta["category"],
                    temp_c=temp_c,
                    precip_mm=precip_mm,
                    rain_prob_pct=max_rain_prob,
                    wind_kmh=wind_kmh
                )

                result_data: Dict[str, Any] = {
                    "status": "LIVE_SUCCESS",
                    "is_live": True,
                    "live_unavailable": False,
                    "source_label": "live",
                    "provider": "Open-Meteo",
                    "is_cached": False,
                    "latitude": latitude,
                    "longitude": longitude,
                    "temperature_celsius": temp_c,
                    "precipitation_probability_pct": max_rain_prob,
                    "precipitation_amount_mm": precip_mm,
                    "wind_speed_kmh": wind_kmh,
                    "weather_code": weather_code,
                    "weather_condition": wmo_meta["description"],
                    "weather_icon": wmo_meta["icon"],
                    "category": wmo_meta["category"],
                    "forecast_time": forecast_time,
                    "last_updated_timestamp": int(now),
                    "last_updated_time_iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now)),
                    "attribution": ATTRIBUTION_TEXT,
                    "attribution_url": ATTRIBUTION_URL,
                    "features": features
                }

                # Save to cache and last known
                self._cache[key] = (now, result_data)
                self._last_known[key] = result_data
                return result_data

            else:
                raise ValueError(f"Open-Meteo HTTP {response.status_code}")

        except Exception as exc:
            # Handle failure: Check if last-known weather exists for this coordinate
            if key in self._last_known:
                fallback_data = dict(self._last_known[key])
                fallback_data["status"] = "RETAINED_FALLBACK"
                fallback_data["is_live"] = False
                fallback_data["live_unavailable"] = False
                fallback_data["is_cached"] = True
                fallback_data["warning"] = f"Open-Meteo API unavailable ({str(exc)}). Retaining last known weather."
                return fallback_data

            # No cache available: honestly return live unavailable without fabricating data
            return {
                "status": "UNAVAILABLE",
                "is_live": False,
                "live_unavailable": True,
                "source_label": "unknown",
                "provider": "Unavailable",
                "is_cached": False,
                "latitude": latitude,
                "longitude": longitude,
                "temperature_celsius": None,
                "precipitation_probability_pct": None,
                "precipitation_amount_mm": None,
                "wind_speed_kmh": None,
                "weather_code": None,
                "weather_condition": "Live weather unavailable",
                "weather_icon": "⚠️",
                "category": "Unknown",
                "forecast_time": None,
                "last_updated_timestamp": int(now),
                "last_updated_time_iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now)),
                "attribution": ATTRIBUTION_TEXT,
                "attribution_url": ATTRIBUTION_URL,
                "error_detail": f"Provider connection failed: {str(exc)}",
                "features": {
                    "surge_multiplier": 1.0,
                    "early_departure_factor": 1.0,
                    "peak_window_shift_mins": 0,
                    "transit_travel_time_multiplier": 1.0,
                    "explanation": "Live weather unavailable. Baseline festival schedule applied without weather modifiers."
                }
            }

    def _derive_features(
        self,
        weather_code: int,
        category: str,
        temp_c: float,
        precip_mm: float,
        rain_prob_pct: int,
        wind_kmh: float
    ) -> Dict[str, Any]:
        """Convert live weather measurements into transparent, explainable demand features.

        Follows domain physics:
        - Rain probability and rain mm compress exit dispersion window
        - Heavy storms accelerate mass evacuation and slow bus transit speeds
        - Dry weather retains standard baseline curve
        """
        wmo = WMO_WEATHER_CODES.get(weather_code, {"severity": 0})
        severity = wmo.get("severity", 0)

        # Baseline: No weather impact
        surge_mult = 1.0
        early_mult = 1.0
        shift_mins = 0
        travel_mult = 1.0
        notes = []

        if severity >= 4 or "Thunderstorm" in category or precip_mm >= 2.5:
            surge_mult = 1.35
            early_mult = 1.60
            shift_mins = -30
            travel_mult = 1.50
            notes.append("Severe rain/storm alert: +35% surge concentration, peak shifted 30 min earlier, bus transit time +50%.")
        elif severity == 3 or "Moderate Rain" in category or precip_mm >= 1.0 or rain_prob_pct >= 70:
            surge_mult = 1.25
            early_mult = 1.40
            shift_mins = -20
            travel_mult = 1.30
            notes.append("Moderate precipitation: +25% peak concentration, peak shifted 20 min earlier, transit delays +30%.")
        elif severity == 2 or "Light Rain" in category or precip_mm > 0.0 or rain_prob_pct >= 40:
            # Proportional adjustment based on rain probability
            prob_factor = (rain_prob_pct / 100.0) * 0.15
            surge_mult = round(1.0 + prob_factor + min(0.10, precip_mm * 0.05), 2)
            early_mult = round(1.0 + (rain_prob_pct / 100.0) * 0.25, 2)
            shift_mins = -15
            travel_mult = 1.20
            notes.append(f"Light precipitation/drizzle ({rain_prob_pct}% rain probability): +{int((surge_mult-1.0)*100)}% surge, peak shifted 15 min earlier.")
        else:
            notes.append("Fair weather conditions: Standard festival exit dispersion curve applies.")

        return {
            "surge_multiplier": surge_mult,
            "early_departure_factor": early_mult,
            "peak_window_shift_mins": shift_mins,
            "transit_travel_time_multiplier": travel_mult,
            "explanation": " ".join(notes)
        }
