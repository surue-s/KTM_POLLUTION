from datetime import datetime, timezone, timedelta
from collections import defaultdict
import math

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from data_pipeline import DataAggregator
from lstm_model import KTMAirLSTM, predict_next_48h, WINDOW


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
        zones = aggregator.identify_source_zones(stations)
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
        zones = sorted(aggregator.identify_source_zones(stations), key=lambda z: z.get("risk_score", 0), reverse=True)
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
