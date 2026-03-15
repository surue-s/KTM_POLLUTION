# KTM AirWatch

KTM AirWatch is a full-stack air-quality monitoring dashboard for Kathmandu Valley. It aggregates **real station and weather data** from OpenAQ v3, WAQI, and OpenWeatherMap, identifies likely local pollution source zones, and serves the result through a FastAPI backend with a React + Kepler.gl frontend. The frontend displays live station points, source-zone rankings, alerts, model status, and zone-level reasoning.

The system also includes an LSTM forecasting model for PM2.5. This forecast is **modeled output** (not an official agency forecast): the model was trained on synthetic Kathmandu-like seasonal/diurnal patterns and then conditioned with live station/weather snapshots at inference time. Source attribution is also heuristic (chemical-signature pattern scoring), so it should be treated as operational guidance rather than definitive source apportionment.

## Data Sources

- **OpenAQ v3**: real-time ground sensor observations for pollutants and station metadata.
- **WAQI**: government + community station network (AQI and, where available, pollutant fields).
- **OpenWeatherMap**: current weather + current air pollution + short-range air pollution forecast feeds.
- **LSTM model**: trained on synthetic Kathmandu pollution patterns + live feature snapshots for runtime predictions.

## Source Attribution Method

KTM AirWatch uses pollutant-combination scoring to estimate likely source types per clustered zone. Each zone gets confidence scores across these signatures:

- **brick_kiln**: high PM2.5 + high PM10 + moderate CO
- **traffic_corridor**: high NO2 + high CO + moderate PM2.5
- **construction_dust**: high PM10 + moderate PM2.5 + low NO2
- **garbage_burning**: high CO + moderate PM2.5 + low NO2
- **industrial_mixed**: high PM2.5 + high NO2 + moderate SO2

Zones are built by spatial clustering and ranked with a risk score derived from PM2.5/AQI intensity, station count, and attribution confidence.

## Run Locally

### Backend

```bash
pip install -r requirements.txt
python main.py
```

Backend runs on `http://localhost:8000`.

### Frontend

```bash
cd ktm-airwatch
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` (or next free Vite port).

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Service health, source status, model loaded flag, model RMSE estimate, last update |
| `/api/stations` | GET | Normalized station list and station count |
| `/api/source-zones` | GET | Clustered/attributed source zones sorted by risk |
| `/api/forecast/{station_id}` | GET | LSTM PM2.5 forecast for +1h/+6h/+12h/+24h/+48h |
| `/api/dashboard` | GET | Aggregated dashboard payload (stations, zones, weather, alerts, forecast summary) |

## Known Limitations

- Satellite data is **not yet integrated**.
- LSTM is currently trained on synthetic historical patterns; adding real long-range Kathmandu historical datasets (for example IQAir-like historical streams, if licensed/available) would likely improve accuracy and calibration.
- WAQI detailed pollutant fields may be limited by token tier for some stations.
- OpenAQ rate limiting can reduce pollutant completeness for some refresh cycles.
