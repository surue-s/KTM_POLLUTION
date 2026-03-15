"""
OpenWeatherMap API – Kathmandu Weather + Air Pollution
───────────────────────────────────────────────────────
1. Current weather  – /data/2.5/weather
2. Current air pollution   – /data/2.5/air_pollution
3. Air pollution forecast  – /data/2.5/air_pollution/forecast
Saves combined raw JSON to owm_ktm.json.
"""

import json
import requests
from datetime import datetime, timezone

API_KEY = "e3a3fe86d3ba962d14ed95944bc2535d"
LAT, LON = 27.7172, 85.3240

WEATHER_URL   = (
    f"https://api.openweathermap.org/data/2.5/weather"
    f"?q=Kathmandu,NP&appid={API_KEY}&units=metric"
)
POLLUTION_URL = (
    f"https://api.openweathermap.org/data/2.5/air_pollution"
    f"?lat={LAT}&lon={LON}&appid={API_KEY}"
)
FORECAST_URL  = (
    f"https://api.openweathermap.org/data/2.5/air_pollution/forecast"
    f"?lat={LAT}&lon={LON}&appid={API_KEY}"
)

# AQI index labels per OWM docs
AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}

# Cardinal direction from wind degrees
def wind_dir(deg: float | None) -> str:
    if deg is None:
        return "–"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(deg / 22.5) % 16]


def fmt(val, unit: str = "", decimals: int = 1) -> str:
    if val is None:
        return "–"
    v = f"{val:.{decimals}f}" if isinstance(val, float) else str(val)
    return f"{v} {unit}".strip()


def utc_ts(epoch: int | None) -> str:
    if epoch is None:
        return "–"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def sep(char: str = "─", width: int = 70) -> None:
    print(char * width)


# ── fetch ─────────────────────────────────────────────────────────────────────

def fetch(url: str, label: str) -> dict:
    print(f"  Fetching {label} …")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


# ── print helpers ─────────────────────────────────────────────────────────────

def print_weather(w: dict) -> None:
    main  = w.get("main", {})
    wind  = w.get("wind", {})
    cond  = (w.get("weather") or [{}])[0]
    sys_  = w.get("sys", {})
    rain  = w.get("rain", {})
    snow  = w.get("snow", {})

    sep("═")
    print("  CURRENT WEATHER – Kathmandu")
    sep()
    print(f"  Condition      : {cond.get('description', '–').title()}")
    print(f"  Temperature    : {fmt(main.get('temp'), '°C')}  "
          f"(feels like {fmt(main.get('feels_like'), '°C')})")
    print(f"  Min / Max      : {fmt(main.get('temp_min'), '°C')} / "
          f"{fmt(main.get('temp_max'), '°C')}")
    print(f"  Humidity       : {fmt(main.get('humidity'), '%', 0)}")
    print(f"  Pressure       : {fmt(main.get('pressure'), 'hPa', 0)}")
    print(f"  Visibility     : {fmt(w.get('visibility'), 'm', 0)}")
    spd = wind.get("speed")
    gst = wind.get("gust")
    deg = wind.get("deg")
    print(f"  Wind speed     : {fmt(spd, 'm/s')}  "
          f"(gust: {fmt(gst, 'm/s')})")
    print(f"  Wind direction : {fmt(deg, '°', 0)}  ({wind_dir(deg)})")
    clouds = (w.get("clouds") or {}).get("all")
    print(f"  Cloud cover    : {fmt(clouds, '%', 0)}")
    if rain:
        print(f"  Rain (1h/3h)   : {fmt(rain.get('1h'), 'mm')} / "
              f"{fmt(rain.get('3h'), 'mm')}")
    if snow:
        print(f"  Snow (1h/3h)   : {fmt(snow.get('1h'), 'mm')} / "
              f"{fmt(snow.get('3h'), 'mm')}")
    print(f"  Sunrise        : {utc_ts(sys_.get('sunrise'))}")
    print(f"  Sunset         : {utc_ts(sys_.get('sunset'))}")
    print(f"  Timestamp      : {utc_ts(w.get('dt'))}")
    sep()


def print_pollution_entry(comp: dict, aqi: int | None, ts: int | None,
                          label: str = "CURRENT AIR POLLUTION") -> None:
    aqi_label = AQI_LABELS.get(aqi, "–") if aqi else "–"
    sep("═")
    print(f"  {label}")
    sep()
    print(f"  AQI (OWM 1-5)  : {aqi}  ({aqi_label})")
    print(f"  Timestamp      : {utc_ts(ts)}")
    sep("─")
    print(f"  {'Pollutant':<14}  {'Value':>12}  Unit")
    sep("─")
    fields = [
        ("PM2.5",  "pm2_5",  "µg/m³"),
        ("PM10",   "pm10",   "µg/m³"),
        ("NO2",    "no2",    "µg/m³"),
        ("O3",     "o3",     "µg/m³"),
        ("CO",     "co",     "µg/m³"),
        ("SO2",    "so2",    "µg/m³"),
        ("NO",     "no",     "µg/m³"),
        ("NH3",    "nh3",    "µg/m³"),
    ]
    for name, key, unit in fields:
        v = comp.get(key)
        print(f"  {name:<14}  {fmt(v, decimals=2):>12}  {unit}")
    sep()


def print_forecast_summary(forecast: dict) -> None:
    entries = forecast.get("list", [])
    if not entries:
        print("  No forecast data.")
        return

    sep("═")
    print(f"  AIR POLLUTION FORECAST  ({len(entries)} hourly steps)")
    sep()
    print(f"  {'Timestamp (UTC)':<22}  {'AQI':>3}  {'PM2.5':>7}  "
          f"{'PM10':>7}  {'NO2':>7}  {'O3':>7}  {'CO':>9}")
    sep("─")
    for e in entries[:24]:           # first 24 h
        c   = e.get("components", {})
        aqi = (e.get("main") or {}).get("aqi")
        ts  = utc_ts(e.get("dt")).replace(" UTC", "")
        print(f"  {ts:<22}  {str(aqi):>3}  "
              f"{fmt(c.get('pm2_5'), decimals=1):>7}  "
              f"{fmt(c.get('pm10'),  decimals=1):>7}  "
              f"{fmt(c.get('no2'),   decimals=1):>7}  "
              f"{fmt(c.get('o3'),    decimals=1):>7}  "
              f"{fmt(c.get('co'),    decimals=1):>9}")
    if len(entries) > 24:
        print(f"  … ({len(entries) - 24} more steps not shown)")
    sep()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Fetching OpenWeatherMap data for Kathmandu …\n")

    weather  = fetch(WEATHER_URL,   "current weather")
    pollution = fetch(POLLUTION_URL, "current air pollution")
    forecast  = fetch(FORECAST_URL,  "air pollution forecast")

    print()

    # ── print weather ──────────────────────────────────────────────────────────
    print_weather(weather)

    # ── print current pollution ────────────────────────────────────────────────
    curr_list = pollution.get("list", [{}])
    if curr_list:
        e = curr_list[0]
        print_pollution_entry(
            comp  = e.get("components", {}),
            aqi   = (e.get("main") or {}).get("aqi"),
            ts    = e.get("dt"),
            label = "CURRENT AIR POLLUTION – Kathmandu",
        )

    # ── print forecast summary ─────────────────────────────────────────────────
    print_forecast_summary(forecast)

    # ── save ───────────────────────────────────────────────────────────────────
    output = {
        "weather":           weather,
        "air_pollution":     pollution,
        "air_pollution_forecast": forecast,
    }
    out_file = "owm_ktm.json"
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    sep("═")
    print(f"  Raw JSON saved → {out_file}")
    sep("═")


if __name__ == "__main__":
    main()
