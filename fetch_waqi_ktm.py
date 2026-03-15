"""
WAQI API – Kathmandu Valley Air Quality
────────────────────────────────────────
1. Fetches all stations within the Kathmandu valley bounding box via
   GET /map/bounds/
2. For each station fetches full data via GET /feed/@{uid}/
3. Prints a summary table + per-station detail
4. Saves all raw results to waqi_ktm.json
"""

import json
import time
import requests

TOKEN   = "a47034f13924a350ec41fb89a9310a1dc7a5d1c8"
# latlng order: lat1,lng1,lat2,lng2  (SW corner → NE corner)
BOUNDS  = "27.6,85.2,27.8,85.5"
BOUNDS_URL = f"https://api.waqi.info/map/bounds/?token={TOKEN}&latlng={BOUNDS}"
FEED_URL   = "https://api.waqi.info/feed/@{uid}/?token={token}"


# ── helpers ──────────────────────────────────────────────────────────────────

def get_bounds() -> list:
    """Return list of station dicts from the bounds endpoint."""
    resp = requests.get(BOUNDS_URL, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "ok":
        raise RuntimeError(f"Bounds API error: {body}")
    return body["data"]


def get_feed(uid: int | str) -> tuple[dict, str]:
    """
    Return (feed_data_dict, source_note) for a station uid.
    source_note is 'feed' on success, or an error string on failure.
    """
    url  = FEED_URL.format(uid=uid, token=TOKEN)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") == "ok":
        return body["data"], "feed"
    # Common failure: trial tokens are restricted to /map/bounds only
    reason = body.get("data", body.get("status", "unknown error"))
    return {}, f"feed unavailable ({reason})"


def iaqi_val(feed: dict, key: str) -> str:
    """Extract a value from the iaqi block, return '–' when absent."""
    try:
        v = feed["iaqi"][key]["v"]
        return f"{v:.1f}" if isinstance(v, float) else str(v)
    except (KeyError, TypeError):
        return "–"


def sep(char: str = "─", width: int = 90) -> None:
    print(char * width)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Bounds query ──────────────────────────────────────────────────────────
    print("Fetching stations in Kathmandu valley bounding box …")
    stations = get_bounds()
    print(f"  {len(stations)} station(s) found.\n")

    # 2. Full feed for every station ───────────────────────────────────────────
    feeds: dict = {}      # uid → feed dict (may be empty if restricted)
    feed_notes: dict = {} # uid → source note string
    feed_failures = 0
    for st in stations:
        uid = st.get("uid")
        print(f"  Fetching feed for uid={uid}  ({st.get('station', {}).get('name', '?')}) …")
        feeds[uid], feed_notes[uid] = get_feed(uid)
        if feeds[uid] == {}:
            feed_failures += 1
        time.sleep(0.1)          # be polite to the free-tier API

    if feed_failures:
        print(f"\n  NOTE: {feed_failures}/{len(stations)} station feed(s) could not be fetched.")
        print("  Individual feed access (/feed/@uid/) may require an upgraded WAQI token.")
        print("  Falling back to bounds-level data (AQI, coords, timestamp) where available.\n")

    # 3. Print summary table ───────────────────────────────────────────────────
    print()
    sep("═")
    print(f"  {'Station':<40} {'AQI':>5}  {'PM2.5':>6}  {'PM10':>6}  "
          f"{'NO2':>6}  {'CO':>6}  {'Lat':>9}  {'Lng':>10}  Timestamp")
    sep()

    for st in stations:
        uid  = st.get("uid")
        feed = feeds.get(uid) or {}

        # Name: prefer feed city name, fall back to bounds station name
        name = (feed.get("city") or {}).get("name") or st.get("station", {}).get("name") or f"uid={uid}"

        # AQI: prefer feed (int), fall back to bounds (string)
        if feed:
            aqi = str(feed.get("aqi", "–"))
            if aqi == "-":
                aqi = "–"
        else:
            aqi = str(st.get("aqi", "–"))

        pm25 = iaqi_val(feed, "pm25")
        pm10 = iaqi_val(feed, "pm10")
        no2  = iaqi_val(feed, "no2")
        co   = iaqi_val(feed, "co")

        # Coords: prefer feed geo, fall back to bounds lat/lon
        geo  = (feed.get("city") or {}).get("geo")
        if geo:
            lat = f"{geo[0]:.5f}"
            lng = f"{geo[1]:.5f}"
        else:
            lat = f"{st['lat']:.5f}" if st.get("lat") is not None else "–"
            lng = f"{st['lon']:.5f}" if st.get("lon") is not None else "–"

        # Timestamp: prefer feed, fall back to bounds station time
        ts = (feed.get("time") or {}).get("s") or st.get("station", {}).get("time") or "–"

        name_disp = (name[:37] + "…") if len(name) > 38 else name
        print(f"  {name_disp:<40} {aqi:>5}  {pm25:>6}  {pm10:>6}  "
              f"{no2:>6}  {co:>6}  {lat:>9}  {lng:>10}  {ts}")

    sep()

    # 4. Per-station detail ────────────────────────────────────────────────────
    print()
    for st in stations:
        uid  = st.get("uid")
        feed = feeds.get(uid)
        note = feed_notes.get(uid, "")

        name = (feed.get("city") or {}).get("name") if feed else None
        name = name or st.get("station", {}).get("name") or f"uid={uid}"

        sep("─")
        print(f"  {name}  (uid={uid})")
        sep("─")

        if not feed:
            # Bounds-level data only
            print(f"  Feed status : {note}")
            print(f"  AQI         : {st.get('aqi', '–')}")
            print(f"  Coordinates : {st.get('lat')}, {st.get('lon')}")
            print(f"  Timestamp   : {st.get('station', {}).get('time', '–')}")
            print()
            continue

        print(f"  AQI        : {feed.get('aqi', '–')}")
        print(f"  Dominant   : {feed.get('dominentpol', '–')}")

        ts_info = feed.get("time") or {}
        print(f"  Timestamp  : {ts_info.get('s', '–')}  (tz: {ts_info.get('tz', '–')})")

        geo = (feed.get("city") or {}).get("geo")
        if geo:
            print(f"  Coordinates: {geo[0]}, {geo[1]}")

        iaqi = feed.get("iaqi") or {}
        if iaqi:
            print(f"  {'Pollutant':<16} Value")
            print(f"  {'─'*16} ─────")
            for key, obj in iaqi.items():
                v = obj.get("v", "–")
                v_fmt = f"{v:.2f}" if isinstance(v, float) else str(v)
                print(f"  {key:<16} {v_fmt}")

        attribs = feed.get("attributions") or []
        if attribs:
            print(f"  Source(s)  : {', '.join(a.get('name', '') for a in attribs)}")
        print()

    # 5. Save raw JSON ─────────────────────────────────────────────────────────
    output = {
        "bounds_results": stations,
        "feeds_by_uid":   feeds,
        "feed_notes":     {str(k): v for k, v in feed_notes.items()},
    }
    out_file = "waqi_ktm.json"
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    sep("═")
    print(f"  Raw JSON saved → {out_file}")
    sep("═")


if __name__ == "__main__":
    main()
