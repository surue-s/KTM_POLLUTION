"""
OpenAQ v3 API – Kathmandu Valley Air Quality
Fetches locations within the Kathmandu valley bounding box,
prints PM2.5/PM10 readings, polls the first 3 location /latest
endpoints, and saves raw JSON to ktm_locations.json.

OpenAQ v3 data-model notes
──────────────────────────
• GET /locations  – each location includes a `sensors` list with full
  parameter metadata (id, name, units) but NO live reading values.
• GET /locations/{id}/latest – returns per-sensor readings
  (sensorsId + value + datetime) but NO parameter names; names must be
  joined back from the sensors list in the /locations response.
"""

import json
import requests

API_KEY = "20cf4573b8d2de683113a783f36c8d4e38b5a0b7e016df46c5356e96c317ff10"
BASE_URL = "https://api.openaq.org/v3"

HEADERS = {
    "X-API-Key": API_KEY,
    "Accept": "application/json",
}

# ── Kathmandu valley bounding box: minLon,minLat,maxLon,maxLat ──────────────
BBOX = "85.2,27.6,85.5,27.8"
LIMIT = 50


def get_locations() -> dict:
    """Fetch locations within the Kathmandu bounding box."""
    url = f"{BASE_URL}/locations"
    params = {
        "bbox": BBOX,
        "limit": LIMIT,
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_latest(location_id: int) -> dict:
    """Fetch the latest sensor readings for a given location id."""
    url = f"{BASE_URL}/locations/{location_id}/latest"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_sensor_map(sensors: list) -> dict:
    """
    Return a dict mapping sensor_id → {name, units, displayName}
    built from the `sensors` list inside a /locations result.
    """
    mapping: dict = {}
    for s in sensors:
        sid   = s.get("id")
        param = s.get("parameter", {})
        if sid is not None and isinstance(param, dict):
            mapping[sid] = {
                "name":        param.get("name", "unknown"),
                "units":       param.get("units", ""),
                "displayName": param.get("displayName", param.get("name", "unknown")),
            }
    return mapping


def find_pm_value(sensor_map: dict, readings: list, param_name: str) -> str:
    """
    Given a sensor-id→param mapping and a list of /latest readings,
    return the formatted value string for `param_name`, or '–'.
    """
    for reading in readings:
        info = sensor_map.get(reading.get("sensorsId"), {})
        if info.get("name", "").lower() == param_name.lower():
            value = reading.get("value")
            if value is not None:
                v_fmt = f"{value:.2f}" if isinstance(value, float) else str(value)
                return f"{v_fmt} {info.get('units', '')}".strip()
    return "–"


def print_separator(char: str = "─", width: int = 74) -> None:
    print(char * width)


def main() -> None:
    # ── 1. Fetch all locations ───────────────────────────────────────────────
    print("Fetching locations …")
    location_data = get_locations()

    results = location_data.get("results", [])
    meta    = location_data.get("meta", {})
    print(f"  Found {len(results)} location(s)  "
          f"(total reported by API: {meta.get('found', 'unknown')})\n")

    # Build sensor-ID → parameter-info maps for every location so we can
    # join them with /latest readings (which only carry sensorsId, not names).
    loc_sensor_maps: dict = {}
    for loc in results:
        lid = loc.get("id")
        loc_sensor_maps[lid] = build_sensor_map(loc.get("sensors", []))

    # ── 3. /latest for the first 3 locations (fetch before table so we can
    #        show PM2.5 / PM10 values inline) ─────────────────────────────────
    first_three    = results[:3]
    latest_payloads: dict = {}

    print("Fetching /latest for first 3 locations …\n")
    for loc in first_three:
        loc_id = loc.get("id")
        try:
            latest_payloads[loc_id] = get_latest(loc_id)
        except requests.HTTPError as exc:
            print(f"  WARNING: /latest failed for id={loc_id}: {exc}")
            latest_payloads[loc_id] = {}

    # ── 2. Print all locations with PM2.5 / PM10 ────────────────────────────
    print_separator("═")
    print(f"{'ID':<10} {'Name':<36} {'Lat':>10} {'Lon':>11}  {'PM2.5':<18} PM10")
    print_separator()

    for loc in results:
        loc_id = loc.get("id", "?")
        name   = loc.get("name") or loc.get("locality") or "N/A"
        coords = loc.get("coordinates") or {}
        lat    = coords.get("latitude",  "N/A")
        lon    = coords.get("longitude", "N/A")

        if loc_id in latest_payloads:
            # We have live data – join sensor map with /latest readings
            sensor_map = loc_sensor_maps.get(loc_id, {})
            readings   = latest_payloads[loc_id].get("results", [])
            pm25 = find_pm_value(sensor_map, readings, "pm25")
            pm10 = find_pm_value(sensor_map, readings, "pm10")
        else:
            # No live data yet – indicate whether a PM sensor exists at all
            smap = loc_sensor_maps.get(loc_id, {})
            pm25 = "(has sensor)" if any(v["name"].lower() == "pm25" for v in smap.values()) else "–"
            pm10 = "(has sensor)" if any(v["name"].lower() == "pm10" for v in smap.values()) else "–"

        name_disp = (name[:33] + "…") if len(name) > 34 else name
        print(f"{str(loc_id):<10} {name_disp:<36} {str(lat):>10} {str(lon):>11}  "
              f"{pm25:<18} {pm10}")

    print_separator()

    # ── Print /latest detail for the first 3 locations ───────────────────────
    print()
    for loc in first_three:
        loc_id = loc.get("id")
        name   = loc.get("name") or loc.get("locality") or f"id={loc_id}"
        latest = latest_payloads.get(loc_id, {})

        print_separator("─")
        print(f"  Location : {name}  (id={loc_id})")
        print_separator("─")

        readings   = latest.get("results", [])
        sensor_map = loc_sensor_maps.get(loc_id, {})

        if not readings:
            print("  No sensor readings returned.")
        else:
            print(f"  {'Parameter':<20} {'Display':<14} {'Value':>14}  {'Unit':<10}  Timestamp (local)")
            print(f"  {'─'*20} {'─'*14} {'─'*14}  {'─'*10}  {'─'*24}")
            for reading in readings:
                sensor_id = reading.get("sensorsId")
                info      = sensor_map.get(sensor_id, {})
                p_name    = info.get("name",        f"sensor#{sensor_id}")
                p_display = info.get("displayName", p_name)
                p_units   = info.get("units",       "")
                value     = reading.get("value", "N/A")
                v_fmt     = f"{value:.2f}" if isinstance(value, float) else str(value)
                ts_local  = (reading.get("datetime") or {}).get("local", "N/A")
                print(f"  {p_name:<20} {p_display:<14} {v_fmt:>14}  {p_units:<10}  {ts_local}")
        print()

    # ── 4. Save raw JSON ─────────────────────────────────────────────────────
    output = {
        "locations": location_data,
        "latest_by_location_id": latest_payloads,
    }

    output_file = "ktm_locations.json"
    with open(output_file, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    print_separator("═")
    print(f"Raw JSON saved to: {output_file}")
    print_separator("═")


if __name__ == "__main__":
    main()
