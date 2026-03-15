"""
KTM AirWatch – LSTM Air Quality Forecast Model
───────────────────────────────────────────────
PyTorch LSTM that predicts Kathmandu PM2.5 at:
  +1h, +6h, +12h, +24h, +48h

Input features (15 per timestep):
  pm25, pm10, no2, co, o3,
  temperature, humidity, wind_speed,
  wind_direction_sin, wind_direction_cos,
  hour_sin, hour_cos,
  day_of_week, is_weekend, month

Architecture:
  LSTM(15 → hidden=128, layers=2, dropout=0.2)
  → Linear(128, 64) → ReLU → Linear(64, 5)

Dependencies: torch, numpy, math, random, datetime, json
"""

import json
import math
import random
import datetime

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# ── Constants ─────────────────────────────────────────────────────────────────

FEATURE_NAMES = [
    "pm25", "pm10", "no2", "co", "o3",
    "temperature", "humidity", "wind_speed",
    "wind_direction_sin", "wind_direction_cos",
    "hour_sin", "hour_cos",
    "day_of_week", "is_weekend", "month",
]

N_FEATURES  = len(FEATURE_NAMES)   # 15
WINDOW      = 24                   # look-back window in hours
HORIZONS    = [1, 6, 12, 24, 48]  # forecast horizons in hours
N_OUTPUTS   = len(HORIZONS)        # 5

HIDDEN_SIZE = 128
NUM_LAYERS  = 2
DROPOUT     = 0.2


# ── 1. Model ──────────────────────────────────────────────────────────────────

class KTMAirLSTM(nn.Module):
    """
    2-layer LSTM followed by a 2-layer MLP head.

    Input  : (batch, seq=24, features=15)
    Output : (batch, 5)  — normalised PM2.5 at +1h, +6h, +12h, +24h, +48h
    """

    def __init__(
        self,
        input_size:  int   = N_FEATURES,
        hidden_size: int   = HIDDEN_SIZE,
        num_layers:  int   = NUM_LAYERS,
        dropout:     float = DROPOUT,
        output_size: int   = N_OUTPUTS,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size  = input_size,
            hidden_size = hidden_size,
            num_layers  = num_layers,
            dropout     = dropout if num_layers > 1 else 0.0,
            batch_first = True,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Linear(64, output_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq, features)
        lstm_out, _ = self.lstm(x)       # (batch, seq, hidden)
        last        = lstm_out[:, -1, :] # take final hidden state (batch, hidden)
        return self.head(last)           # (batch, 5)


# ── 2. Dataset ────────────────────────────────────────────────────────────────

class AQIDataset(Dataset):
    """
    Sliding-window dataset built from a list of hourly reading dicts.

    Each dict must contain the keys listed in FEATURE_NAMES.
    Missing values are forward/backward-filled then zero-filled.

    Normalisation: min/max computed on this split.
    A `normalizer` dict {min: [...], max: [...]} is attached to the
    instance after __init__ and must be passed to predict_next_48h().

    Targets are PM2.5 values at HORIZONS hours ahead of each window end:
      window covers [i, i+WINDOW);  targets[k] = pm25[i + WINDOW + HORIZONS[k] - 1]

    Windows whose furthest target falls outside the array are dropped.
    """

    def __init__(
        self,
        data_list:  list,
        window:     int  = WINDOW,
        horizons:   list = None,
        normalizer: dict = None,
    ):
        super().__init__()
        self.window   = window
        self.horizons = horizons or HORIZONS
        self.max_h    = max(self.horizons)

        # ── Build raw feature matrix ───────────────────────────────────────────
        raw = self._extract_features(data_list)   # (T, 15)  float32

        # ── Compute or apply normalizer ────────────────────────────────────────
        if normalizer is None:
            feat_min = raw.min(axis=0)
            feat_max = raw.max(axis=0)
            rng      = feat_max - feat_min
            rng[rng == 0] = 1.0
            normalizer = {
                "min": feat_min.tolist(),
                "max": feat_max.tolist(),
            }
        else:
            feat_min = np.array(normalizer["min"], dtype=np.float32)
            feat_max = np.array(normalizer["max"], dtype=np.float32)
            rng      = feat_max - feat_min
            rng[rng == 0] = 1.0

        self.normalizer = normalizer
        normed      = (raw - feat_min) / rng       # (T, 15)  in [0, 1]
        pm25_normed = normed[:, 0]                  # (T,)  pm25 column

        # ── Build sliding windows ──────────────────────────────────────────────
        T = len(normed)
        self.X: list = []
        self.y: list = []

        for i in range(T - window - self.max_h + 1):
            x_win   = normed[i : i + window]                        # (24, 15)
            targets = [
                pm25_normed[i + window + h - 1]
                for h in self.horizons
            ]
            self.X.append(torch.tensor(x_win,    dtype=torch.float32))
            self.y.append(torch.tensor(targets,  dtype=torch.float32))

    # ── Feature extraction ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_features(data_list: list) -> np.ndarray:
        """
        Convert list-of-dicts → float32 array (T, 15).
        Missing keys → NaN → forward-fill → back-fill → 0.
        """
        rows = []
        for d in data_list:
            rows.append([float(d.get(k, float("nan"))) for k in FEATURE_NAMES])
        arr = np.array(rows, dtype=np.float32)

        # Per-column fill
        for col in range(arr.shape[1]):
            col_data = arr[:, col]
            mask     = np.isnan(col_data)
            if not mask.any():
                continue
            # Forward fill
            last = 0.0
            for t in range(len(col_data)):
                if not mask[t]:
                    last = col_data[t]
                else:
                    col_data[t] = last
            # Back fill any remaining leading NaNs
            last = 0.0
            for t in range(len(col_data) - 1, -1, -1):
                if not np.isnan(col_data[t]):
                    last = col_data[t]
                else:
                    col_data[t] = last
            arr[:, col] = col_data

        return np.nan_to_num(arr, nan=0.0)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


# ── 3. Training ───────────────────────────────────────────────────────────────

def train_model(
    data_list:  list,
    epochs:     int   = 50,
    batch_size: int   = 64,
    lr:         float = 1e-3,
    device:     str   = None,
) -> tuple:
    """
    Train KTMAirLSTM on data_list.

    Parameters
    ----------
    data_list  : list of hourly reading dicts
    epochs     : number of training epochs
    batch_size : mini-batch size
    lr         : Adam learning rate
    device     : 'cpu' or 'cuda' (auto-detected if None)

    Returns
    -------
    (model, normalizer, history)
      model      : trained KTMAirLSTM (on CPU)
      normalizer : dict {min: [...], max: [...]} for 15 features
      history    : list of per-epoch average MSE loss
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"\n── Training KTMAirLSTM ({'GPU' if device == 'cuda' else 'CPU'}) ──────────────────")

    dataset    = AQIDataset(data_list)
    normalizer = dataset.normalizer
    loader     = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)

    model     = KTMAirLSTM().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.5)

    print(f"  Dataset   : {len(dataset)} windows  |  {len(loader)} batches/epoch")
    print(f"  Parameters: {sum(p.numel() for p in model.parameters()):,}")

    history: list = []
    model.train()

    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        n_batches  = 0

        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item()
            n_batches  += 1

        avg_loss = epoch_loss / max(n_batches, 1)
        history.append(avg_loss)
        scheduler.step()

        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:>3}/{epochs}  loss={avg_loss:.6f}  "
                  f"lr={scheduler.get_last_lr()[0]:.2e}")

    print(f"  Training complete. Final loss: {history[-1]:.6f}\n")
    model = model.cpu()
    return model, normalizer, history


# ── 4. Prediction ─────────────────────────────────────────────────────────────

def predict_next_48h(
    model:           "KTMAirLSTM",
    recent_readings: list,
    normalizer:      dict,
) -> dict:
    """
    Forecast PM2.5 for the next +1h, +6h, +12h, +24h, +48h.

    Parameters
    ----------
    model           : trained KTMAirLSTM
    recent_readings : list of ≥24 hourly reading dicts with FEATURE_NAMES keys
    normalizer      : dict returned by train_model

    Returns
    -------
    dict: {1: float, 6: float, 12: float, 24: float, 48: float}  (µg/m³)
    """
    if len(recent_readings) < WINDOW:
        raise ValueError(
            f"predict_next_48h needs at least {WINDOW} readings; "
            f"got {len(recent_readings)}"
        )

    window_data = recent_readings[-WINDOW:]

    feat_min = np.array(normalizer["min"], dtype=np.float32)
    feat_max = np.array(normalizer["max"], dtype=np.float32)
    rng      = feat_max - feat_min
    rng[rng == 0] = 1.0

    raw  = AQIDataset._extract_features(window_data)    # (24, 15)
    norm = (raw - feat_min) / rng                        # (24, 15)
    x    = torch.tensor(norm, dtype=torch.float32).unsqueeze(0)  # (1, 24, 15)

    model.eval()
    with torch.no_grad():
        pred_norm = model(x).squeeze(0).numpy()         # (5,)

    # Denormalise pm25 (index 0)
    pm25_min = float(feat_min[0])
    pm25_rng = float(rng[0])
    pred_ugm3 = pred_norm * pm25_rng + pm25_min
    pred_ugm3 = np.clip(pred_ugm3, 0.0, None)

    return {h: round(float(v), 2) for h, v in zip(HORIZONS, pred_ugm3)}


# ── 5. Synthetic training data ────────────────────────────────────────────────

def generate_synthetic_training_data(n_days: int = 180) -> list:
    """
    Generate n_days × 24 hourly synthetic Kathmandu readings with
    realistic seasonal, diurnal and meteorological patterns.

    Seasonal PM2.5 base (Kathmandu climate):
      Winter  Nov–Feb : 150–250 µg/m³  (stagnant air, biomass burning)
      Spring  Mar–May :  80–140 µg/m³  (pre-monsoon dust)
      Monsoon Jun–Sep :  30–60  µg/m³  (wet scavenging)
      Autumn  Oct     :  60–100 µg/m³  (transition)

    Diurnal cycle:
      Morning rush 07–09 h : +50–80 µg/m³ Gaussian peak
      Evening rush 17–20 h : +40–70 µg/m³ Gaussian peak
      Pre-dawn trough ~03 h: base × 0.5 suppression

    Meteorological corrections:
      Humidity > 70 % → PM2.5 × 0.55–1.0  (wet scavenging)
      Wind    > 3 m/s → PM2.5 × 0.65–1.0  (dispersion)
    """
    random.seed(42)
    np.random.seed(42)

    records: list = []
    start = datetime.datetime(2025, 1, 1, 0, 0, 0)

    for day_offset in range(n_days):
        dt_day = start + datetime.timedelta(days=day_offset)
        month  = dt_day.month

        # ── Seasonal base values ───────────────────────────────────────────────
        if month in (11, 12, 1, 2):             # Winter
            pm25_base     = random.uniform(150, 250)
            temp_base     = random.uniform(5,   15)
            hum_base      = random.uniform(55,  70)
        elif month in (3, 4, 5):                # Spring / pre-monsoon
            pm25_base     = random.uniform(80,  140)
            temp_base     = random.uniform(18,  28)
            hum_base      = random.uniform(35,  55)
        elif month in (6, 7, 8, 9):             # Monsoon
            pm25_base     = random.uniform(30,  60)
            temp_base     = random.uniform(22,  30)
            hum_base      = random.uniform(75,  95)
        else:                                   # Autumn Oct
            pm25_base     = random.uniform(60,  100)
            temp_base     = random.uniform(15,  22)
            hum_base      = random.uniform(50,  65)

        # Day-to-day meteorology
        wind_day_base = random.uniform(0.5, 4.5)
        wind_dir_deg  = random.uniform(0, 360)

        for hour in range(24):
            dt = dt_day + datetime.timedelta(hours=hour)

            # Temperature: diurnal sinusoid, peak ~14:00
            temp = (
                temp_base
                + 5.0 * math.sin(math.pi * (hour - 6) / 12)
                + random.gauss(0, 1.5)
            )

            # Humidity: inverse of temp cycle
            humidity = (
                hum_base
                - 10.0 * math.sin(math.pi * (hour - 6) / 12)
                + random.gauss(0, 4.0)
            )
            humidity = max(10.0, min(99.0, humidity))

            # Wind: afternoon peak due to convection
            wind_speed = (
                wind_day_base
                * (1 + 0.4 * math.sin(math.pi * (hour - 12) / 12))
                + random.gauss(0, 0.3)
            )
            wind_speed = max(0.1, wind_speed)

            # Wind direction drifts slowly
            wind_dir_deg = (wind_dir_deg + random.gauss(0, 10)) % 360
            wind_sin     = math.sin(math.radians(wind_dir_deg))
            wind_cos     = math.cos(math.radians(wind_dir_deg))

            # ── PM2.5 diurnal model ────────────────────────────────────────────
            morning_peak = math.exp(-0.5 * ((hour - 8.0) / 1.2) ** 2) * 70.0
            evening_peak = math.exp(-0.5 * ((hour - 18.5) / 1.8) ** 2) * 55.0
            night_trough = -pm25_base * 0.4 * math.exp(-0.5 * ((hour - 3.0) / 2.0) ** 2)

            pm25 = pm25_base + morning_peak + evening_peak + night_trough

            # Meteorological suppression
            if humidity > 70:
                wet_factor = 0.55 + 0.45 * (1 - (humidity - 70) / 30)
                pm25 *= wet_factor
            if wind_speed > 3.0:
                wind_factor = 0.65 + 0.35 * max(0.0, 1 - (wind_speed - 3.0) / 3.0)
                pm25 *= wind_factor

            pm25 = max(5.0, pm25 + random.gauss(0, pm25 * 0.12))

            # PM10 ~ 1.5-2× PM2.5 (Kathmandu: dust + coarse particles)
            pm10 = pm25 * random.uniform(1.5, 2.0) + random.gauss(0, 5)
            pm10 = max(pm25 + 1.0, pm10)

            # NO2: traffic-correlated, peaks with rush hours
            no2 = (
                15.0
                + 20.0 * math.exp(-0.5 * ((hour - 8.0) / 1.5) ** 2)
                + 15.0 * math.exp(-0.5 * ((hour - 18.0) / 2.0) ** 2)
                + random.gauss(0, 3.0)
            )
            no2 = max(1.0, no2)

            # CO: traffic + garbage burning (evening peaks)
            co = (
                300.0
                + 300.0 * math.exp(-0.5 * ((hour - 8.0)  / 1.5) ** 2)
                + 250.0 * math.exp(-0.5 * ((hour - 18.0) / 2.0) ** 2)
                + random.gauss(0, 30.0)
            )
            co = max(100.0, co)

            # O3: photochemical, peaks early afternoon
            o3 = (
                15.0
                + 45.0 * math.exp(-0.5 * ((hour - 13.0) / 3.0) ** 2)
                + random.gauss(0, 5.0)
            )
            o3 = max(1.0, o3)

            # Cyclic time encodings
            hour_sin    = math.sin(2 * math.pi * hour / 24)
            hour_cos    = math.cos(2 * math.pi * hour / 24)
            day_of_week = dt.weekday()          # 0=Mon … 6=Sun
            is_weekend  = 1 if day_of_week >= 5 else 0

            records.append({
                "timestamp":          dt.isoformat(),
                "pm25":               round(pm25,       2),
                "pm10":               round(pm10,       2),
                "no2":                round(no2,        2),
                "co":                 round(co,         2),
                "o3":                 round(o3,         2),
                "temperature":        round(temp,       2),
                "humidity":           round(humidity,   2),
                "wind_speed":         round(wind_speed, 3),
                "wind_direction_sin": round(wind_sin,   4),
                "wind_direction_cos": round(wind_cos,   4),
                "hour_sin":           round(hour_sin,   4),
                "hour_cos":           round(hour_cos,   4),
                "day_of_week":        day_of_week,
                "is_weekend":         is_weekend,
                "month":              month,
            })

    print(f"Generated {len(records):,} synthetic hourly records "
          f"({n_days} days, start={start.date()})")
    return records


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sep(char: str = "─", width: int = 62) -> None:
    print(char * width)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print("╔════════════════════════════════════════════════════════════╗")
    print("║    KTM AirWatch – LSTM Air Quality Forecast                ║")
    print("╚════════════════════════════════════════════════════════════╝")

    # ── Step 1: synthetic data ─────────────────────────────────────────────────
    _sep()
    print("Step 1 – Generating synthetic training data (180 days) …")
    data = generate_synthetic_training_data(n_days=180)

    pm25_all  = [d["pm25"] for d in data]
    print(f"  PM2.5 – min:{min(pm25_all):.1f}  max:{max(pm25_all):.1f}  "
          f"mean:{sum(pm25_all)/len(pm25_all):.1f}  µg/m³")

    # Seasonal sanity check
    seasons = {
        "Winter (Jan)": [d["pm25"] for d in data if d["month"] == 1],
        "Spring (Apr)": [d["pm25"] for d in data if d["month"] == 4],
        "Monsoon(Jul)": [d["pm25"] for d in data if d["month"] == 7],
    }
    for label, vals in seasons.items():
        if vals:
            print(f"  {label}: mean={sum(vals)/len(vals):.1f}  "
                  f"min={min(vals):.1f}  max={max(vals):.1f}  µg/m³")

    # ── Step 2: train ──────────────────────────────────────────────────────────
    _sep()
    print("Step 2 – Training model …")
    model, normalizer, history = train_model(data, epochs=50)

    # Loss summary
    _sep()
    print("Training loss summary:")
    for ep in [1, 10, 20, 30, 40, 50]:
        print(f"  Epoch {ep:>3} : {history[ep - 1]:.6f}")
    pct_drop = (history[0] - history[-1]) / history[0] * 100 if history[0] > 0 else 0.0
    print(f"  Total loss reduction: {pct_drop:.1f}%")

    # ── Step 3: test prediction ────────────────────────────────────────────────
    _sep()
    print("Step 3 – Test prediction  (last 24 h of training data) …")
    recent_24h = data[-WINDOW:]
    forecast   = predict_next_48h(model, recent_24h, normalizer)

    # Ground-truth values at each horizon (if available in training data)
    actual: dict = {}
    last_idx = len(data) - 1
    for h in HORIZONS:
        idx = last_idx - WINDOW + h
        if 0 <= idx < len(data):
            actual[h] = data[idx]["pm25"]

    _sep()
    print(f"  {'Horizon':<10}  {'Predicted (µg/m³)':>17}  {'Actual (µg/m³)':>15}  "
          f"{'Error':>8}")
    _sep("─")
    for h in HORIZONS:
        pred = forecast[h]
        act  = actual.get(h)
        err  = f"{abs(pred - act):.2f}" if act is not None else "–"
        act_s = f"{act:.2f}" if act is not None else "–"
        print(f"  +{h:<9}  {pred:>17.2f}  {act_s:>15}  {err:>8}")
    _sep()

    # ── Step 4: save model ─────────────────────────────────────────────────────
    save_path = "ktm_lstm.pt"
    torch.save({
        "model_state_dict":      model.state_dict(),
        "normalizer":            normalizer,
        "horizons":              HORIZONS,
        "feature_names":         FEATURE_NAMES,
        "n_features":            N_FEATURES,
        "hidden_size":           HIDDEN_SIZE,
        "num_layers":            NUM_LAYERS,
        "dropout":               DROPOUT,
        "window":                WINDOW,
        "training_loss_history": history,
        "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, save_path)
    print(f"  ✓ Model checkpoint saved  → {save_path}")

    # ── Step 5: save forecast snapshot ────────────────────────────────────────
    snap = {
        "model_path":       save_path,
        "input_window_end": recent_24h[-1].get("timestamp"),
        "input_pm25_last":  recent_24h[-1]["pm25"],
        "forecast_ugm3":    {f"+{h}h": forecast[h] for h in HORIZONS},
        "training_epochs":  50,
        "final_loss":       round(history[-1], 6),
        "generated_at":     datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    snap_path = "ktm_lstm_forecast.json"
    with open(snap_path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2)
    print(f"  ✓ Forecast snapshot saved → {snap_path}")

    _sep("═")
    print(f"  Model parameters : {sum(p.numel() for p in model.parameters()):,}")
    print(f"  Training windows : {len(AQIDataset(data))}")
    print(f"  Forecast at +1h  : {forecast[1]:.2f} µg/m³")
    print(f"  Forecast at +48h : {forecast[48]:.2f} µg/m³")
    _sep("═")


if __name__ == "__main__":
    main()
