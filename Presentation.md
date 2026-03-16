# KTM AirWatch — Project Presentation

---

## ⚡ The Pitch

> **Every breath in Kathmandu Valley costs you a fraction of your life. We built the system that tells you exactly why — and gives authorities the tools to do something about it.**

Fourteen million people live and work in the Kathmandu Valley. They share an air quality crisis that has no real-time, intelligent command center — no tool that connects live sensor data, satellite fire intelligence, meteorology, machine learning forecasting, and AI-generated policy recommendations into a single operational view.

**KTM AirWatch is that command center.**

It is not another dashboard that shows a colored circle and says "Unhealthy." It is a full-stack pollution intelligence platform that identifies *where* pollution is coming from, *what is causing it*, *how bad it will get in the next 48 hours*, and *what city authorities should do about it today* — all powered by real data and Azure OpenAI reasoning.

We are not solving a theoretical problem. Kathmandu consistently ranks among the most polluted capitals in Asia. PM2.5 levels regularly exceed WHO guidelines by 10–20× during the dry season. The health, economic, and quality-of-life costs are staggering and preventable. Yet the tools available to city operators today are static, slow, and siloed.

**KTM AirWatch changes that — and it is already running.**

---

## 1. Problem Statement

### 1.1 The Air Quality Crisis in Kathmandu Valley

Kathmandu Valley is geographically a closed bowl, ringed by hills that trap cold air during winter inversions. This natural topography, combined with rapid and largely unplanned urbanization, has created one of South Asia's most persistent air quality emergencies.

**The numbers are alarming:**
- Kathmandu's annual average PM2.5 routinely exceeds **50–80 µg/m³** — WHO's safe annual limit is **5 µg/m³**
- During dry season (Oct–May), peak PM2.5 days regularly exceed **200 µg/m³** — classified as **Hazardous**
- Nepal loses an estimated **$3–5 billion USD annually** in health costs, productivity loss, and premature mortality attributable to outdoor air pollution
- Respiratory disease is the **#1 cause of outpatient hospital visits** in Kathmandu-area hospitals
- An estimated **35,000+ premature deaths per year** in Nepal are linked to air pollution (WHO, 2023)

### 1.2 Why Existing Solutions Fail

| Current Tool | What It Lacks |
|---|---|
| IQAir / AirVisual apps | No source attribution, no enforcement guidance, consumer-only |
| Government MOFE portal | Manual updates, no real-time API, no forecasting |
| Static AQI readings | No "why" — just a number |
| Academic studies | Months to years of lag, archived rather than actionable |

**The core problem**: Pollution data exists in fragments across sensors, weather APIs, satellite systems, and academic databases. Nobody has connected them into a unified operational intelligence system that city authorities can act on *today*.

### 1.3 Specific Pain Points This Project Solves

1. **Source blindness** — Authorities don't know whether today's crisis is brick kilns, traffic, garbage burning, or forest fires. They can't enforce what they can't identify.
2. **No forecast capability** — There is no system warning neighborhoods 24–48 hours ahead so schools can cancel outdoor activities or hospitals can prepare for respiratory admissions.
3. **Satellite data is unused** — NASA FIRMS fire detection is publicly available but no operational system in Kathmandu integrates it.
4. **AI is absent** — No system generates language-based, actionable police/enforcement briefs from the aggregated data.

---

## 2. What KTM AirWatch Is

KTM AirWatch is a **real-time pollution intelligence platform** for Kathmandu Valley. It aggregates multi-source sensor data, applies machine learning inference, integrates satellite intelligence, and delivers an interactive 3D command dashboard with AI-written analysis — accessible from any browser.

### 2.1 What It Does

```
Real-time Data Ingestion
         ↓
Multi-source Normalization & Deduplication
         ↓
Spatial Zone Clustering & Source Attribution
         ↓
LSTM 48-Hour PM2.5 Forecast
         ↓
AI Reasoning Engine (Azure OpenAI GPT-4o)
         ↓
Interactive 3D Command Dashboard
```

**Live capabilities at launch:**

| Capability | Description |
|---|---|
| **Live AQI map** | 46+ station readings plotted in real time on 3D interactive map |
| **Source zone identification** | Spatial clustering assigns pollution to brick kilns, traffic corridors, construction zones, garbage burning, industrial mixed |
| **Risk scoring** | Each zone scored 0–100 based on PM2.5 intensity, AQI, confidence, and fire proximity |
| **48-hour LSTM forecast** | PyTorch model predicts PM2.5 trajectory per station |
| **NASA FIRMS fire integration** | Satellite fire detections override zone attribution when hotspots found ≤1 km |
| **AI city-wide analysis** | GPT-4o generates: situation summary, primary threat, immediate actions, 24h prediction, water-tanker deployment priority, risk level |
| **AI zone deep-dive** | Per-zone GPT-4o analysis: cause analysis, recommended enforcement action, estimated impact, enforcement priority score (1–10), suggested tanker routes |
| **Elevation terrain model** | Valley terrain integrated to identify pollution-trap zones |
| **Open-Meteo AQI forecast** | 72-hour air quality trajectory overlay |
| **Traffic road overlay** | Major road corridors from OpenStreetMap via Overpass API |

---

## 3. How It Is Built — Tech Stack

### 3.1 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (Free / Open)               │
│  OpenAQ v3 · WAQI · OpenWeatherMap · Open-Meteo            │
│  NASA FIRMS (VIIRS satellite fire) · OpenStreetMap Overpass │
└─────────────┬───────────────────────────────────────────────┘
              │ HTTP fetch every 15 min
┌─────────────▼───────────────────────────────────────────────┐
│               PYTHON BACKEND (FastAPI)                      │
│  data_pipeline.py — normalize, deduplicate, cluster zones   │
│  lstm_model.py   — PyTorch LSTM 48h PM2.5 forecasting       │
│  main.py         — REST API + Azure OpenAI integration      │
│  FreeDataSources — elevation, fire, traffic, open-meteo     │
└─────────────┬───────────────────────────────────────────────┘
              │ JSON REST API (:8000)
┌─────────────▼───────────────────────────────────────────────┐
│            REACT FRONTEND (Vite + Deck.gl)                  │
│  DeckMap.jsx      — 3D interactive map (ScatterplotLayer,   │
│                     HexagonLayer, TextLayer)                 │
│  SourceZonePanel  — Zone rankings, alerts, forecasts        │
│  MapControls      — Basemap, layer toggles, AQI filter,     │
│                     data upload (CSV/GeoJSON)               │
│  ForecastChart    — 48h PM2.5 chart per station             │
│  TopBar           — City AQI indicator + last update        │
└─────────────────────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│             AZURE OPENAI (GPT-4o)                           │
│  /api/ai-analysis     — City-wide intelligence brief        │
│  /api/ai-zone-analysis/{id} — Zone enforcement deep-dive    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Backend Stack

| Component | Technology | Role |
|---|---|---|
| API Framework | **FastAPI** (Python) | High-performance async REST API |
| ML Model | **PyTorch LSTM** | 48-hour PM2.5 time-series forecast |
| Data Layer | **Custom DataAggregator** | Fetch, normalize, deduplicate, cluster |
| Zone Attribution | **Pollutant-signature scoring** | Heuristic source-type classification |
| AI Reasoning | **Azure OpenAI GPT-4o** | Natural language operational analysis |
| Satellite | **NASA FIRMS API (VIIRS)** | Active fire detection, proximity attribution |
| Meteorology | **Open-Meteo API** | Free 72h weather + AQI forecast |
| Terrain | **Open-Meteo Elevation** | Valley topography + pollution-trap zones |
| Road Data | **Overpass API (OSM)** | Major road/traffic corridor geometry |
| Caching | **In-memory (15 min TTL)** | Reduces API load and improves latency |

### 3.3 Frontend Stack

| Component | Technology | Role |
|---|---|---|
| Framework | **React 18 + Vite** | Fast, modern UI bundling |
| 3D Map | **Deck.gl + MapLibre GL** | GPU-accelerated 3D geospatial rendering |
| Chart | **Custom React chart** | PM2.5 48h forecast visualization |
| File Upload | **PapaParse** | In-browser CSV/GeoJSON parsing for custom data overlay |
| Basemaps | **CARTO (dark/light), ESRI Satellite, OpenTopoMap** | 4 switchable basemap providers |

### 3.4 Data Sources (All Currently Free / Open)

| Source | API | Data |
|---|---|---|
| OpenAQ v3 | REST + API key | Ground PM2.5, PM10, NO2, CO, O3 — 40+ stations |
| WAQI | REST + token | Government + community AQI, supplemental pollutants |
| OpenWeatherMap | REST + key | Current weather, current AQI, short forecast |
| Open-Meteo | Free REST | 72h weather forecast + hourly AQI forecast |
| NASA FIRMS (VIIRS) | Free REST | Near-real-time satellite fire/thermal anomaly detection |
| OpenStreetMap Overpass | Free REST | Major road network geometry |

---

## 4. Why This Project Is Viable Today

### 4.1 The Timing Could Not Be Better

**Climate accountability is accelerating.** The Paris Agreement, COP28 commitments, and Nepal's own NDC pledges demand measurable air quality improvements. Cities need the technological infrastructure to report, monitor, and *act*. KTM AirWatch is that infrastructure.

**AI is now accessible.** Three years ago, deploying a GPT-4-class reasoning engine into an operational city platform would require millions in cloud infrastructure. Today, Azure OpenAI provides pay-per-token pricing that makes real-time AI-generated enforcement briefs affordable at scale.

**Remote sensing is now free and real-time.** NASA FIRMS VIIRS fire detection data — previously available only to researchers — is now accessible via a free API. This is transformative for a city where garbage burning and agricultural fires are major PM2.5 contributors.

**Machine learning forecasting is proven.** Time-series forecasting for urban air quality is well-validated in published literature. The LSTM architecture used here is production-grade and runs on commodity hardware.

### 4.2 Urgency Drivers

1. **Post-pandemic urbanization surge** — Kathmandu's population is growing at ~4% annually, accelerating pollution producing activities
2. **Brick kiln season triggers annual crisis** — October–May cycle creates predictable but unmanaged PM2.5 spikes
3. **Climate finance opportunity** — ADB, World Bank, GEF, and bilateral donors have active funding windows for urban resilience infrastructure in South Asia
4. **Nepal's digital governance push** — The Federal Government of Nepal has signaled digital infrastructure as a national priority under Nepal Digital 2030

### 4.3 Competitive Moat

- **No comparable real-time platform exists** for Kathmandu — the market is effectively uncontested
- **Multi-source fusion** from 6+ APIs with proprietary deduplication gives better station coverage than any single source
- **Source attribution** (knowing *what* causes pollution, not just *how bad* it is) is rare even globally and nonexistent locally
- **AI-generated enforcement briefs** are novel — no government air quality platform in South Asia produces GPT-quality action recommendations

---

## 5. Target Audience

### 5.1 Primary Users

#### 🏛️ Government & Regulatory Bodies
- **Kathmandu Metropolitan City (KMC)** — Environment Department needs real-time monitoring and enforcement tools
- **Department of Environment (Nepal)** — Requires scientifically credible data for policy and reporting
- **Ministry of Forests and Environment (MOFE)** — National air quality program compliance monitoring

*Value delivered: Operational dashboard, automated alerts, AI enforcement briefs, weekly/monthly trend reports*

#### 🚒 Emergency Response & Enforcement
- **Metropolitan Police** — Know which zones to prioritize for garbage burning enforcement
- **Emergency Management Division** — 48h PM2.5 forecasts to pre-position response capacity

*Value delivered: Zone-level enforcement priority scores (1–10), tanker route suggestions, AI zone deep-dive briefs*

### 5.2 Secondary Users

#### 🏥 Healthcare & Public Health
- **Nepal Health Research Council** — Exposure data for epidemiological research
- **Hospital systems** — Predict respiratory admission surges using 48h forecast
- **WHO Nepal / UNICEF** — Reporting and advocacy data

#### 🏫 Schools & Institutions
- **School administrations** — Forecast-based outdoor activity decisions
- **Universities** — Research data access API

#### 📱 General Public & Media
- **Citizens** — Know their neighborhood's current and forecast AQI
- **Journalists** — Data-driven pollution reporting
- **NGOs** — Advocacy and accountability campaigns

#### 💼 Private Sector
- **Real estate developers** — Air quality as a property factor
- **Tourism sector** — Haze forecast for trekking and tourism planning
- **Construction firms** — Dust contribution monitoring and compliance

---

## 6. Startup Pathway — How to Turn This Into a Business

### 6.1 Business Model Tiers

```
TIER 1 — FREE PUBLIC LAYER
  Open AQI map + basic station data + public alerts
  → Builds trust, brand, user base, and press coverage
  → Functions as community infrastructure

TIER 2 — GOVERNMENT SaaS (B2G)  ← Primary Revenue
  Full dashboard + AI analysis + alerts + data export
  + White-label option for MOFE/KMC
  Target: $15,000–$50,000/year per government contract
  → 3–5 city contracts = $75K–$250K ARR

TIER 3 — API & Data Licensing (B2B)
  Clean, fused Kathmandu air quality data via REST API
  for researchers, media, NGOs, health systems
  Target: $500–$5,000/month per organization

TIER 4 — ENTERPRISE INTELLIGENCE (B2B)
  Custom AI reports, integration into ERP/Hospital systems
  Custom alerts, historical data, bespoke zone modeling
  Target: $10,000–$100,000 per engagement

TIER 5 — GEOGRAPHIC EXPANSION
  Platform-as-a-Service for other polluted South Asian cities:
  Pokhara, Dhaka, Lahore, Colombo, Delhi NCR satellite cities
  License the platform stack to local operators
```

### 6.2 Go-to-Market Strategy

**Phase 0 — Proof of Value (Now, 0–3 months)**
- Deploy publicly at a branded URL (e.g., ktmairwatch.com)
- Generate media coverage through data-driven air quality reports
- Brief KMC Environment Department with a live demo
- Apply to ADB's Urban Climate Change Resilience Trust Fund (UCCRTF)

**Phase 1 — Government Anchor Contract (3–12 months)**
- Secure first paid contract with KMC or MOFE for ₨1.5–3M/year
- This becomes the referenceable case study for all future sales
- Integrate with Nepal EPA's monitoring network for data sharing agreement

**Phase 2 — Regional Expansion (12–30 months)**
- Partner with IQAir, PurpleAir, or Clarity Movement for low-cost sensor hardware deployment
- Expand to Pokhara, Biratnagar, and Birgunj
- License platform model to Bangladesh and Pakistan urban authorities

**Phase 3 — Platform Play (30–48 months)**
- Open sensor SDK for municipal and community sensor deployment
- Satellite integration (Sentinel-5P NO2, MODIS AOD)
- Climate credit linkage — pollution reduction verified by satellite → carbon market participation

### 6.3 Funding Landscape

| Source | Type | Fit |
|---|---|---|
| **ADB Urban Climate Fund** | Grant/Concessional Loan | High — urban resilience in South Asia |
| **World Bank ESMAP** | Grant | High — air quality monitoring is listed priority |
| **USAID Clean Air Catalyst** | Grant | High — South Asia focus, technology solutions |
| **GEF Small Grants Programme** | Grant (≤$50K) | Medium — local implementation |
| **YCombinator** | Equity | Medium — climate tech vertical |
| **Draper Richards Kaplan** | Impact equity | High — social enterprise with measurable impact |
| **Nepal Government / ICT Ministry** | Procurement | High — Digital Nepal framework |

### 6.4 Team Requirements to Scale

| Role | Priority |
|---|---|
| Full-Stack Engineer (Python + React) | Core |
| GIS / Remote Sensing Analyst | Core |
| Government Relations Lead | Core |
| Data Scientist (Air Quality domain) | High |
| Field Operations (sensor deployment) | Medium |
| Business Development (South Asia) | High |

---

## 7. Impact Metrics & Accountability

Investors and government bodies need to see measurable outcomes. KTM AirWatch is designed to produce the following measurable results:

| Metric | Baseline | 2-Year Target |
|---|---|---|
| Enforcement actions supported per month | 0 (no tool exists) | 50+ zone-specific briefs/month |
| Garbage burning incidents caught via fire attribution | 0 | 200+/year |
| Schools receiving forecast-based activity alerts | 0 | 500+ schools |
| Reduction in "surprise" pollution spikes (>200 AQI) with <6h public warning | ~0% | >80% forecast-covered |
| Government users on dashboard | 0 | 40+ |
| API calls / data consumers | 0 | 10+ organizations |

---

## 8. Technical Differentiators (Deeper Cut)

### 8.1 Multi-Source Data Fusion

Most air quality apps consume a single data feed. KTM AirWatch fuses **6 independent data sources**, applies geospatial deduplication within 500m radius, selects the highest-confidence reading per station cluster, and normalizes all measurements to standard units before serving downstream.

This means: **more coverage, less noise, and higher confidence readings** than any single-source app.

### 8.2 Heuristic Source Attribution

The system uses pollutant combination fingerprinting to classify zones:
- **Brick kiln**: High PM2.5 + High PM10 + moderate CO → classic solid fuel combustion signature
- **Traffic corridor**: High NO2 + High CO + moderate PM2.5 → internal combustion exhaust
- **Construction dust**: High PM10 + moderate PM2.5 + low NO2 → mechanical dust, no combustion
- **Garbage burning**: High CO + moderate PM2.5 + low NO2 → smoldering organic waste
- **Industrial mixed**: High PM2.5 + High NO2 + moderate SO2 → industrial combustion + chemical

When NASA FIRMS detects an active fire within 1 km of a zone, attribution overrides to `biomass_burning` or `garbage_burning` and risk score is boosted — **satellite intelligence informing ground attribution in real time**.

### 8.3 LSTM Forecasting Architecture

The forecasting model uses:
- **Input**: 24-timestep sequences, 15 features per timestep (PM2.5, PM10, NO2, CO, O3, temp, humidity, wind speed, wind direction sin/cos, hour sin/cos, day-of-week, weekend flag, month)
- **Architecture**: 2-layer stacked LSTM, hidden size 128, dropout 0.2
- **Output**: 5-pollutant prediction (PM2.5, PM10, NO2, CO, O3) at +1h, +6h, +12h, +24h, +48h horizons
- **Runtime**: Backfills history with synthetic timeline when < 24 observations are available for a new station

### 8.4 Azure OpenAI Reasoning Engine

The AI layer does what no dashboard visualization can — it **synthesizes all the data into language** that non-technical officials can immediately act on:

- **City-wide analysis**: situation summary, primary threat, 3 immediate actions, 24h prediction, water tanker deployment priority, risk level + confidence
- **Zone deep-dive**: cause analysis, enforcement recommendation, estimated PM reduction from action, priority score, suggested tanker routes, monitoring recommendations

This closes the gap between *data* and *decision*.

---

## 9. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Government adoption slow | Medium | Start with free public tier + NGO partnerships to build legitimacy before B2G sales |
| Sensor data quality gaps | High | Multi-source fusion + confidence scoring masks individual sensor failures |
| API key costs at scale | Low | All data sources are currently free or low-cost; OpenAQ/WAQI have generous free tiers |
| AI hallucinations in enforcement briefs | Medium | Prompts constrained to JSON structure; temperature=0.3; recommendations always cite source data |
| LSTM forecast accuracy | Medium | Model trained on synthetic patterns; accuracy improves with historical data accumulation; displayed as "guidance, not guarantee" |
| Competition from global platforms | Low | IQAir/BreezoMeter have no Kathmandu-specific source attribution or Nepali government integrations |

---

## 10. Demo Script (Pitch Day Walkthrough)

> *Presenter walks through the live running app*

**Step 1 — Open the dashboard**
"This is Kathmandu, live, right now. Every circle is a real air quality sensor. The color tells you how bad the air is. We're pulling from OpenAQ, WAQI, and OpenWeatherMap simultaneously, fused and deduplicated."

**Step 2 — Show the zone panel**
"These 14 zones are our source attribution. This isn't just 'pollution is bad here.' It's telling us *what's causing it*. Zone 3 is a brick kiln fingerprint — high PM2.5, high PM10, moderate CO. Zone 7 is a traffic corridor. Zone 11 just got flagged as garbage burning because NASA's fire satellite detected a thermal anomaly 800 meters away, 90 minutes ago."

**Step 3 — Toggle 3D mode**
"In 3D mode you can literally see where pollution is piling up — the hexagonal columns show concentration density across the valley. This is where temperature inversions are trapping cold air… and pollution."

**Step 4 — Open the AI Analysis**
"This is where it gets powerful. I'm calling our AI engine right now — it's consuming all 14 zones, current weather, fire hotspot count, wind data. In five seconds it tells us: *Critical situation. Primary threat: brick kiln corridor in Bhaktapur contributing elevated PM2.5 in low-wind conditions. Immediate action: Deploy water tanker suppression on Ring Road East sector and issue school activity advisory for Bhaktapur district.* 

That took me five seconds. Without this system, a government analyst would need half a day — if they had the data at all."

**Step 5 — Zone deep-dive**
"I click Zone 3. AI gives me a complete enforcement brief — enforcement priority 8/10, suggested vehicle route for water tanker deployment, estimated 15% PM2.5 reduction if action is taken. This is what the police environment unit gets on their tablet every morning."

**Step 6 — 48h forecast**
"Finally — the forecast. Click any station. Our LSTM model predicts PM2.5 for the next 48 hours. It's already flagging that Station 12 — near Patan Durbar Square — is heading for a spike in the 6–12 hour window. Schools in that zone can be notified *now*, before children are exposed."

---

## 11. Vision Statement

> **KTM AirWatch is the beginning of an intelligent environmental nervous system for South Asian cities.**

The same architecture — multi-source data fusion, machine learning forecasting, satellite fire intelligence, AI-generated operational analysis — scales directly to every city with a pollution problem and a governance gap. That is most of South Asia.

We are not building a product. We are building infrastructure for climate accountability.

The air does not wait. Neither should we.

---

## 12. Quick Facts Summary Card

| Item | Detail |
|---|---|
| **Project Name** | KTM AirWatch |
| **Stage** | Working prototype — fully functional live demo |
| **Core Team** | Full-stack development complete; seeking domain experts and growth |
| **Data Sources** | 6 (OpenAQ, WAQI, OWM, Open-Meteo, NASA FIRMS, OpenStreetMap) |
| **Station Coverage** | 46+ unique stations across Kathmandu Valley |
| **Forecast Horizon** | 48 hours, 5 pollutants |
| **AI Engine** | Azure OpenAI GPT-4o |
| **Deployment** | Linux server, single `./run_app.sh` command |
| **License** | Proprietary (open to licensing discussions) |
| **Primary Market** | Kathmandu Metropolitan City + Nepal government |
| **TAM (South Asia)** | $2.3B urban air quality monitoring market (2025, GrandViewResearch) |
| **Revenue Model** | B2G SaaS + API licensing + enterprise AI reports |
| **Ask** | Pilot contract with KMC / Seed funding for 12-month scale |

---

*Presentation prepared for KTM AirWatch · March 2026*
*Contact: [Your Name] · [Your Email] · [Your LinkedIn]*
