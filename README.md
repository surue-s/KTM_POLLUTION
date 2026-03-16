# KTM AirWatch

KTM AirWatch is a full-stack, real-time air-quality intelligence system for Kathmandu Valley.
It aggregates multiple sensor/weather/satellite feeds, identifies likely pollution source zones,
provides 48-hour PM2.5 forecasts, and now includes an Azure OpenAI reasoning layer for city-wide
and zone-specific operational analysis.

---

## What’s New in This Version

- Frontend migrated to **React + Deck.gl + MapLibre** (interactive 2D/3D map)
- Added **MapControls** panel:
	- basemap switcher (Dark, Light, Satellite, Topo)
	- CSV/GeoJSON upload overlay
	- layer visibility toggles
	- AQI threshold filter
- Improved UI layout (top bar + panel stacking + smoother panel behavior)
- Added **free no-key enrichment sources**:
	- Open-Meteo weather + AQI forecast
	- NASA FIRMS fire hotspots
	- Overpass traffic roads
	- Open-Meteo elevation grid
- Added Azure OpenAI reasoning endpoints:
	- `/api/ai-analysis`
	- `/api/ai-zone-analysis/{zone_id}`
- Added `run_app.sh` and `stop_app.sh` for one-command local lifecycle control
- Added `.env` support for Azure settings via `run_app.sh`

---

## Architecture Overview

### Backend

- **Framework**: FastAPI (`main.py`)
- **Data Pipeline**: `data_pipeline.py` (`DataAggregator` + `FreeDataSources`)
- **Forecast Model**: PyTorch LSTM (`lstm_model.py`, model file `ktm_lstm.pt`)
- **Cache**: in-memory payload cache with 15-minute TTL
- **AI Reasoning**: Azure OpenAI (`openai` SDK, `AzureOpenAI` client)

### Frontend

- **Framework**: React + Vite (`ktm-airwatch`)
- **Map stack**: Deck.gl + MapLibre
- **Key components**:
	- `DeckMap.jsx`
	- `SourceZonePanel.jsx`
	- `MapControls.jsx`
	- `TopBar.jsx`
	- `ZoneExplanation.jsx`

---

## Data Sources

### Core Operational Feeds

- **OpenAQ v3**: live station observations + metadata
- **WAQI**: valley AQI/station data
- **OpenWeatherMap**: weather + air-quality context

### Free Enrichment Feeds

- **Open-Meteo Forecast API**: weather forecast signals
- **Open-Meteo Air API**: hourly AQI forecast additions
- **NASA FIRMS (VIIRS)**: active fire detections in/near valley
- **Overpass API (OpenStreetMap)**: major road network (traffic proxy)
- **Open-Meteo Elevation API**: valley elevation grid and trap-zone context

---

## Source Attribution & Risk Logic

KTM AirWatch clusters nearby stations into zones, computes pollutant signatures, and classifies likely source type:

- `brick_kiln`: high PM2.5 + PM10 + moderate CO
- `traffic_corridor`: high NO2 + CO + moderate PM2.5
- `construction_dust`: high PM10 + moderate PM2.5 + low NO2
- `garbage_burning`: high CO + moderate PM2.5 + low NO2
- `industrial_mixed`: high PM2.5 + high NO2 + moderate SO2

Zones are ranked by `risk_score` using pollutant intensity, AQI, station count, and confidence.

### Fire-Hotspot Override

If NASA FIRMS detects a hotspot close to a zone centroid, attribution can be elevated/overridden to burning-related labels (e.g., biomass/garbage) and risk is adjusted.

---

## Forecasting Model

- Model: LSTM (`KTMAirLSTM`)
- Horizons: `+1h`, `+6h`, `+12h`, `+24h`, `+48h`
- Endpoint: `/api/forecast/{station_id}`
- Notes:
	- Uses cached station + weather feature points
	- Backfills sequences when station history is short
	- Forecasts are guidance (not regulatory/official forecasts)

---

## AI Reasoning Engine (Azure OpenAI)

Two reasoning endpoints are available:

1. `GET /api/ai-analysis`
	 - City-wide analysis JSON
	 - Uses zones, weather, fire hotspots, and dashboard context

2. `GET /api/ai-zone-analysis/{zone_id}`
	 - Zone deep-dive JSON
	 - Uses selected zone + nearby stations + nearby fires + weather

Expected outputs include situation summary, primary cause/threat, recommended actions, risk level/priority, and operational suggestions.

---

## Environment Configuration

Project root `.env` is supported (loaded by `run_app.sh`).

Example keys:

```env
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_RESOURCE=
AZURE_OPENAI_DEPLOYMENT=gpt-4o

OPENAQ_KEY=
WAQI_TOKEN=
OWM_KEY=

BACKEND_PORT=8000
FRONTEND_PORT=5173
```

> `.env` is ignored by git via `.gitignore`.

---

## Local Run

### One-command start/stop (recommended)

```bash
./run_app.sh
```

```bash
./stop_app.sh
```

### Manual run

Backend:

```bash
pip install -r requirements.txt
python main.py
```

Frontend:

```bash
cd ktm-airwatch
npm install
npm run dev
```

Default URLs:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Service health, source availability, model status/RMSE |
| `/api/stations` | GET | Normalized station list |
| `/api/source-zones` | GET | Clustered and attributed zones sorted by risk |
| `/api/forecast/{station_id}` | GET | LSTM station forecast (+1h/+6h/+12h/+24h/+48h) |
| `/api/dashboard` | GET | Unified payload for frontend (zones, stations, alerts, weather, enrichment data) |
| `/api/ai-analysis` | GET | Azure OpenAI city-wide reasoning JSON |
| `/api/ai-zone-analysis/{zone_id}` | GET | Azure OpenAI zone-level reasoning JSON |

---

## Frontend UX Features

- 2D/3D view toggle
- Zone tooltip with source breakdown
- Top pollution zones + live alert badges
- API source monitor + model status
- Forecast panel with trend indicators
- Upload custom points from CSV/GeoJSON
- Layer toggles and AQI threshold filtering
- Multiple basemap styles

---

## Current Limitations

- Some upstream APIs may intermittently rate-limit or timeout.
- LSTM model currently relies on synthetic pattern training with live conditioning.
- Source attribution is heuristic, intended for operational guidance.
- Azure AI endpoints require valid Azure OpenAI credentials.

---

## Future Improvements

- Move all pipeline/API credentials fully to environment variables
- Persist historical station time-series in a DB
- Add retry/backoff + source health degradation scoring
- Add richer offline fallback behavior for AI endpoint failures
- Expand forecasting calibration with long-range Kathmandu historical datasets
