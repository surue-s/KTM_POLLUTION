from datetime import datetime, timezone, timedelta
from collections import defaultdict
import json as json_lib
import math
import os

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

try:
    from openai import AzureOpenAI
    _OPENAI_IMPORT_OK = True
except ImportError:
    _OPENAI_IMPORT_OK = False

from data_pipeline import DataAggregator, haversine_m
from lstm_model import KTMAirLSTM, predict_next_48h, WINDOW

# ---------------------------------------------------------------------------
# Azure OpenAI configuration
# ---------------------------------------------------------------------------
AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
# Set to your Azure OpenAI resource name (the subdomain in your endpoint URL):
# e.g. https://MY-RESOURCE.openai.azure.com  →  AZURE_RESOURCE = "MY-RESOURCE"
AZURE_RESOURCE = "YOUR_RESOURCE_NAME"           # <-- replace before use
AZURE_DEPLOYMENT = "gpt-4o"                     # change if your deployment differs

try:
    if not _OPENAI_IMPORT_OK:
        raise ImportError("openai package not installed")
    ai_client = AzureOpenAI(
        api_key=AZURE_KEY,
        api_version="2024-02-01",
        azure_endpoint=f"https://{AZURE_RESOURCE}.openai.azure.com/",
    )
    AI_AVAILABLE = True
except Exception as _ai_exc:
    print(f"Azure OpenAI not configured: {_ai_exc}")
    ai_client = None
    AI_AVAILABLE = False


CACHE_TTL_SECONDS = 15 * 60
MODEL_PATH = "ktm_lstm.pt"

app = FastAPI(title="KTM AirWatch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


aggregator = DataAggregator()

cache = {
    "timestamp": None,
    "data": None,
    "last_error": None,
    "source_status": {"openaq": False, "waqi": False, "owm": False},
}

model_bundle = {
    "loaded": False,
    "model": None,
    "normalizer": None,
    "error": None,
    "rmse": None,
}

# in-memory station history for forecast endpoint
# station_id -> list of chronological snapshots
station_history = defaultdict(list)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_cache() -> dict:
    """Return cached data, refreshing if stale or absent."""
    ts = cache["timestamp"]
    stale = ts is None or (datetime.now(timezone.utc) - ts) > timedelta(seconds=CACHE_TTL_SECONDS)
    if stale:
        refresh_data(force=True)
    if cache["data"] is None:
        detail = cache["last_error"] or "Data not available"
        raise HTTPException(status_code=503, detail=detail)
    return cache["data"]


def _to_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _wind_sin_cos(deg):
    if deg is None:
        return 0.0, 1.0
    rad = math.radians(float(deg))
    return math.sin(rad), math.cos(rad)


def _build_feature_point(station: dict, weather: dict, ts: datetime) -> dict:
    wind_deg = _to_float(weather.get("wind_deg"))
    wind_sin, wind_cos = _wind_sin_cos(wind_deg)

    return {
        "pm25": _to_float(station.get("pm25")) or 0.0,
        "pm10": _to_float(station.get("pm10")) or 0.0,
        "no2": _to_float(station.get("no2")) or 0.0,
        "co": _to_float(station.get("co")) or 0.0,
        "o3": _to_float(station.get("o3")) or 0.0,
        "temperature": _to_float(weather.get("temp_c")) or 0.0,
        "humidity": _to_float(weather.get("humidity_pct")) or 0.0,
        "wind_speed": _to_float(weather.get("wind_speed_ms")) or 0.0,
        "wind_direction_sin": wind_sin,
        "wind_direction_cos": wind_cos,
        "hour_sin": math.sin(2 * math.pi * ts.hour / 24.0),
        "hour_cos": math.cos(2 * math.pi * ts.hour / 24.0),
        "day_of_week": ts.weekday(),
        "is_weekend": 1 if ts.weekday() >= 5 else 0,
        "month": ts.month,
    }


def _refresh_station_history(stations: list, weather: dict) -> None:
    ts = datetime.now(timezone.utc)
    for station in stations:
        sid = station.get("id")
        if not sid:
            continue
        point = _build_feature_point(station, weather, ts)
        point["timestamp"] = now_iso()
        station_history[sid].append(point)
        # keep last 240 points (~10 days if fetched hourly; much less in this API)
        if len(station_history[sid]) > 240:
            station_history[sid] = station_history[sid][-240:]


def _build_recent_series(station: dict, weather: dict) -> list:
    """
    Build last 24 timesteps for LSTM input.
    Priority:
      1) actual in-memory history for this station
      2) backfilled synthetic timeline using current values
    """
    sid = station.get("id")
    hist = list(station_history.get(sid, []))

    if len(hist) >= WINDOW:
        return hist[-WINDOW:]

    # Backfill to 24 points using current station+weather snapshot
    needed = WINDOW - len(hist)
    base_time = datetime.now(timezone.utc) - timedelta(hours=needed)
    backfill = []
    for i in range(needed):
        ts = base_time + timedelta(hours=i)
        backfill.append(_build_feature_point(station, weather, ts))

    series = backfill + hist
    return series[-WINDOW:]


def _compute_trend(current_pm25: float, forecast_12h: float) -> str:
    if current_pm25 is None or current_pm25 <= 0:
        return "stable"
    ratio = forecast_12h / current_pm25
    if ratio > 1.1:
        return "rising"
    if ratio < 0.9:
        return "falling"
    return "stable"


def _load_model() -> None:
    try:
        ckpt = torch.load(MODEL_PATH, map_location="cpu")
        model = KTMAirLSTM(
            input_size=ckpt.get("n_features", 15),
            hidden_size=ckpt.get("hidden_size", 128),
            num_layers=ckpt.get("num_layers", 2),
            dropout=ckpt.get("dropout", 0.2),
            output_size=5,
        )
        model.load_state_dict(ckpt["model_state_dict"])
        model.eval()

        model_bundle["loaded"] = True
        model_bundle["model"] = model
        model_bundle["normalizer"] = ckpt.get("normalizer")
        model_bundle["error"] = None
        loss_history = ckpt.get("training_loss_history") or []
        if isinstance(loss_history, list) and len(loss_history) > 0:
            last_mse = float(loss_history[-1])
            model_bundle["rmse"] = math.sqrt(last_mse) if last_mse >= 0 else None
        else:
            model_bundle["rmse"] = None
    except Exception as exc:
        model_bundle["loaded"] = False
        model_bundle["model"] = None
        model_bundle["normalizer"] = None
        model_bundle["error"] = str(exc)
        model_bundle["rmse"] = None


# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------

def build_reasoning_prompt(dashboard_data: dict) -> str:
    """Build a detailed Kathmandu air-quality reasoning prompt from dashboard data."""
    zones = dashboard_data.get("zones", [])[:5]
    weather = dashboard_data.get("weather", {})
    fire_hotspots = dashboard_data.get("fire_hotspots", [])

    zones_text = "\n".join([
        f"- {z.get('zone_id','?')}: type={z.get('source_type','?')}, "
        f"risk={z.get('risk_score',0):.0f}/100, "
        f"PM2.5={z.get('avg_pm25',0):.1f}\u00b5g/m\u00b3, "
        f"AQI={z.get('avg_aqi',0):.0f}, "
        f"confidence={z.get('confidence',0)*100:.0f}%"
        for z in zones
    ])

    fire_text = (
        f"{len(fire_hotspots)} active fire/burn detections in valley"
        if fire_hotspots
        else "No active fire detections"
    )
    wind = weather.get("wind", {})

    return f"""You are an air quality analyst for Kathmandu Valley, Nepal. Analyze this real-time pollution data and provide actionable intelligence for city authorities.

CURRENT CONDITIONS:
- Temperature: {weather.get('temperature', 'N/A')}\u00b0C
- Humidity: {weather.get('humidity', 'N/A')}%
- Wind: {wind.get('speed', 'N/A')} m/s from {wind.get('direction', 'N/A')}
- Conditions: {weather.get('description', 'N/A')}
- Fire detections: {fire_text}

TOP POLLUTION ZONES:
{zones_text}

CONTEXT:
- Kathmandu valley is a bowl surrounded by hills \u2014 inversions trap pollution
- Brick kilns in Bhaktapur corridor are major PM2.5 sources (active Oct-May)
- Morning rush 7-9am and evening rush 5-8pm drive NO2/CO spikes
- Garbage burning happens mostly in peripheral wards at dusk
- Monsoon (Jun-Sep) dramatically reduces pollution via rain washout

Provide a JSON response with exactly this structure:
{{
  "situation_summary": "2-3 sentence plain English summary of current air quality situation",
  "primary_threat": "single biggest pollution source right now and why",
  "immediate_actions": ["action 1 for authorities", "action 2", "action 3"],
  "24h_prediction": "what will happen in next 24 hours based on weather trend",
  "water_tanker_priority": ["ward/area 1 - reason", "ward/area 2 - reason"],
  "risk_level": "LOW|MODERATE|HIGH|CRITICAL",
  "confidence": 0.0
}}
Return ONLY the JSON, no other text."""


def build_zone_reasoning_prompt(
    zone: dict,
    nearby_stations: list,
    weather: dict,
    nearby_fires: list,
) -> str:
    """Build a zone-specific deep-dive prompt."""
    stations_text = "\n".join([
        f"  - {s.get('name','?')}: AQI={s.get('aqi','?')}, "
        f"PM2.5={s.get('pm25','?')}\u00b5g/m\u00b3, "
        f"PM10={s.get('pm10','?')}\u00b5g/m\u00b3, "
        f"NO2={s.get('no2','?')}\u00b5g/m\u00b3"
        for s in nearby_stations
    ]) or "  No nearby stations with data"

    fire_text = (
        f"{len(nearby_fires)} fire/burn detections within 2 km "
        f"(brightest: {max((f.get('brightness',0) for f in nearby_fires), default=0):.0f} K)"
        if nearby_fires
        else "No fire detections within 2 km"
    )
    wind = weather.get("wind", {})

    return f"""You are a field operations analyst for Kathmandu's Air Quality Command Center.
Conduct a deep-dive analysis of this specific pollution zone and return deployment-ready recommendations.

ZONE PROFILE:
- ID: {zone.get('zone_id','?')}
- Type: {zone.get('source_type','?')}
- Risk score: {zone.get('risk_score',0):.0f}/100
- Confidence: {zone.get('confidence',0)*100:.0f}%
- Coordinates: ({zone.get('lat','?')}, {zone.get('lon','?')})
- Average PM2.5: {zone.get('avg_pm25',0):.1f} \u00b5g/m\u00b3
- Average AQI: {zone.get('avg_aqi',0):.0f}
- Station count: {zone.get('station_count',0)}
- Fire hotspot nearby: {zone.get('fire_hotspot_nearby', False)}

NEARBY MONITORING STATIONS (within 2 km):
{stations_text}

METEOROLOGY:
- Temperature: {weather.get('temperature','N/A')}\u00b0C
- Humidity: {weather.get('humidity','N/A')}%
- Wind: {wind.get('speed','N/A')} m/s from {wind.get('direction','N/A')}
- Conditions: {weather.get('description','N/A')}

FIRE INTELLIGENCE (2 km radius):
{fire_text}

Return a JSON object with exactly this structure:
{{
  "cause_analysis": "Detailed explanation of what is causing elevated pollution in this specific zone",
  "recommended_action": "Single most impactful enforcement/mitigation action",
  "estimated_impact": "Expected AQI/PM2.5 reduction if action is taken (quantified estimate)",
  "enforcement_priority": 7,
  "suggested_tanker_routes": [
    "Route 1: from X to Y via Z \u2014 rationale",
    "Route 2: alternative approach"
  ],
  "secondary_actions": ["action a", "action b"],
  "monitoring_recommendation": "What additional monitoring is needed here"
}}
Return ONLY the JSON, no other text."""


def refresh_data(force: bool = False) -> None:
    ts = cache["timestamp"]
    if not force and ts is not None:
        if (datetime.now(timezone.utc) - ts).total_seconds() < CACHE_TTL_SECONDS:
            return

    try:
        payload = aggregator.fetch_all()
        stations = payload.get("stations", [])
        weather = payload.get("weather", {})

        cache["data"] = payload
        cache["timestamp"] = datetime.now(timezone.utc)
        cache["last_error"] = None
        cache["source_status"] = {
            "openaq": payload.get("meta", {}).get("openaq_raw_count", 0) > 0,
            "waqi": payload.get("meta", {}).get("waqi_raw_count", 0) > 0,
            "owm": bool(weather),
        }

        _refresh_station_history(stations, weather)
    except Exception as exc:
        cache["last_error"] = f"Data refresh failed: {exc}"
        # keep previous cache if any


@app.on_event("startup")
def on_startup():
    _load_model()
    refresh_data(force=True)


@app.get("/api/health")
def health():
    # opportunistically refresh if stale
    try:
        refresh_data(force=False)
    except Exception:
        pass

    return {
        "status": "ok" if cache["data"] is not None else "degraded",
        "data_sources": cache["source_status"],
        "model_loaded": bool(model_bundle["loaded"]),
        "model_rmse": model_bundle.get("rmse"),
        "last_update": cache["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ") if cache["timestamp"] else None,
    }


@app.get("/api/stations")
def get_stations():
    try:
        data = _ensure_cache()
        stations = data.get("stations", [])
        return {
            "stations": stations,
            "timestamp": now_iso(),
            "total_count": len(stations),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load stations: {exc}")


@app.get("/api/source-zones")
def get_source_zones():
    try:
        data = _ensure_cache()
        stations = data.get("stations", [])
        fire_hotspots = data.get("fire_hotspots", [])
        zones = aggregator.identify_source_zones(stations, fire_hotspots)
        zones = sorted(zones, key=lambda z: z.get("risk_score", 0), reverse=True)
        return {
            "zones": zones,
            "timestamp": now_iso(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compute source zones: {exc}")


@app.get("/api/forecast/{station_id}")
def get_station_forecast(station_id: str):
    try:
        data = _ensure_cache()
        if not model_bundle["loaded"] or not model_bundle["normalizer"]:
            raise HTTPException(status_code=503, detail=f"Model unavailable: {model_bundle['error']}")

        stations = data.get("stations", [])
        station = next((s for s in stations if s.get("id") == station_id), None)
        if station is None:
            raise HTTPException(status_code=404, detail=f"Station '{station_id}' not found")

        recent_series = _build_recent_series(station, data.get("weather", {}))
        forecasts = predict_next_48h(model_bundle["model"], recent_series, model_bundle["normalizer"])

        current_pm25 = _to_float(station.get("pm25"))
        f12 = forecasts.get(12)
        trend = _compute_trend(current_pm25, f12 if f12 is not None else (current_pm25 or 0.0))

        return {
            "station_id": station_id,
            "forecasts": {
                "1h": forecasts.get(1),
                "6h": forecasts.get(6),
                "12h": forecasts.get(12),
                "24h": forecasts.get(24),
                "48h": forecasts.get(48),
            },
            "current_pm25": current_pm25,
            "trend": trend,
            "timestamp": now_iso(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Forecast failed: {exc}")


@app.get("/api/dashboard")
def get_dashboard():
    try:
        data = _ensure_cache()
        stations = data.get("stations", [])
        weather = data.get("weather", {})
        fire_hotspots = data.get("fire_hotspots", [])
        elevation_data = data.get("elevation_grid", {})
        zones = sorted(
            aggregator.identify_source_zones(stations, fire_hotspots),
            key=lambda z: z.get("risk_score", 0),
            reverse=True,
        )
        top_offenders = zones[:5]

        aqi_values = [float(s["aqi"]) for s in stations if s.get("aqi") is not None]
        city_aqi_avg = round(sum(aqi_values) / len(aqi_values), 2) if aqi_values else None

        alerts = []

        # Zone risk alerts
        for z in zones:
            risk = z.get("risk_score", 0)
            if risk > 75:
                alerts.append({
                    "zone_id": z.get("zone_id"),
                    "message": f"Critical pollution risk in zone {z.get('zone_id')} ({risk:.1f}/100)",
                    "severity": "critical",
                })

        # Forecast acceleration alerts (12h > current * 1.3)
        forecast_alerts = []
        if model_bundle["loaded"] and model_bundle["normalizer"]:
            for station in sorted(stations, key=lambda s: (s.get("pm25") or 0), reverse=True)[:10]:
                current = _to_float(station.get("pm25"))
                if current is None or current <= 0:
                    continue
                series = _build_recent_series(station, weather)
                fc = predict_next_48h(model_bundle["model"], series, model_bundle["normalizer"])
                if fc.get(12) is not None and fc[12] > current * 1.3:
                    forecast_alerts.append({
                        "zone_id": None,
                        "message": f"PM2.5 rising fast at {station.get('name')} (12h forecast {fc[12]:.1f} vs current {current:.1f})",
                        "severity": "warning",
                    })

        alerts.extend(forecast_alerts)

        # Forecast summary using highest-pm25 station (if any)
        forecast_summary = None
        if model_bundle["loaded"] and model_bundle["normalizer"] and stations:
            focus = max(stations, key=lambda s: (s.get("pm25") or 0))
            series = _build_recent_series(focus, weather)
            fc = predict_next_48h(model_bundle["model"], series, model_bundle["normalizer"])
            forecast_summary = {
                "station_id": focus.get("id"),
                "station_name": focus.get("name"),
                "current_pm25": _to_float(focus.get("pm25")),
                "next_pm25": {
                    "1h": fc.get(1),
                    "6h": fc.get(6),
                    "12h": fc.get(12),
                    "24h": fc.get(24),
                    "48h": fc.get(48),
                },
                "trend": _compute_trend(_to_float(focus.get("pm25")), fc.get(12) or 0.0),
            }

        return {
            "stations": stations,
            "zones": zones,
            "weather": weather,
            "open_meteo_weather": data.get("open_meteo_weather", {}),
            "open_meteo_aqi_forecast": data.get("open_meteo_aqi_forecast", []),
            "fire_hotspots": fire_hotspots,
            "traffic_roads": data.get("traffic_roads", []),
            "elevation_data": elevation_data,
            "top_offenders": top_offenders,
            "city_aqi_avg": city_aqi_avg,
            "forecast_summary": forecast_summary,
            "alerts": alerts,
            "timestamp": now_iso(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build dashboard: {exc}")


# ---------------------------------------------------------------------------
# AI analysis endpoints
# ---------------------------------------------------------------------------

@app.get("/api/ai-analysis")
async def get_ai_analysis():
    """City-wide intelligent pollution analysis powered by Azure OpenAI."""
    if not AI_AVAILABLE:
        return {
            "error": "Azure OpenAI not configured — set AZURE_RESOURCE in main.py",
            "fallback": True,
        }
    try:
        dashboard = get_dashboard()  # sync call — reuse existing logic
        prompt = build_reasoning_prompt(dashboard)

        response = ai_client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise air quality analyst. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if model wraps response
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        analysis = json_lib.loads(raw)
        analysis["generated_at"] = datetime.utcnow().isoformat() + "Z"
        analysis["model"] = AZURE_DEPLOYMENT
        return analysis

    except Exception as exc:
        return {
            "error": str(exc),
            "situation_summary": "AI analysis temporarily unavailable.",
            "risk_level": "UNKNOWN",
            "fallback": True,
        }


@app.get("/api/ai-zone-analysis/{zone_id}")
async def get_ai_zone_analysis(zone_id: str):
    """Deep-dive AI analysis for a specific pollution zone."""
    if not AI_AVAILABLE:
        return {
            "error": "Azure OpenAI not configured — set AZURE_RESOURCE in main.py",
            "fallback": True,
        }
    try:
        data = _ensure_cache()
        stations = data.get("stations", [])
        weather = data.get("weather", {})
        fire_hotspots = data.get("fire_hotspots", [])

        zones = aggregator.identify_source_zones(stations, fire_hotspots)
        zone = next((z for z in zones if z.get("zone_id") == zone_id), None)
        if zone is None:
            raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")

        zone_lat = zone.get("lat")
        zone_lon = zone.get("lon")

        # Stations within 2 km of zone centroid
        nearby_stations: list = []
        if zone_lat is not None and zone_lon is not None:
            for s in stations:
                slat, slon = s.get("lat"), s.get("lon")
                if slat is None or slon is None:
                    continue
                if haversine_m(zone_lat, zone_lon, float(slat), float(slon)) <= 2000:
                    nearby_stations.append(s)

        # Fire hotspots within 2 km
        nearby_fires: list = []
        if zone_lat is not None and zone_lon is not None:
            for f in fire_hotspots:
                flat, flon = f.get("lat"), f.get("lon")
                if flat is None or flon is None:
                    continue
                if haversine_m(zone_lat, zone_lon, float(flat), float(flon)) <= 2000:
                    nearby_fires.append(f)

        prompt = build_zone_reasoning_prompt(zone, nearby_stations, weather, nearby_fires)

        response = ai_client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are a field operations analyst. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        analysis = json_lib.loads(raw)
        analysis["zone_id"] = zone_id
        analysis["generated_at"] = datetime.utcnow().isoformat() + "Z"
        analysis["model"] = AZURE_DEPLOYMENT
        analysis["nearby_station_count"] = len(nearby_stations)
        analysis["nearby_fire_count"] = len(nearby_fires)
        return analysis

    except HTTPException:
        raise
    except Exception as exc:
        return {
            "zone_id": zone_id,
            "error": str(exc),
            "cause_analysis": "AI zone analysis temporarily unavailable.",
            "enforcement_priority": 0,
            "fallback": True,
        }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
