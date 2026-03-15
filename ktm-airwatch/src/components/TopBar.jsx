import { Wind, Thermometer, Droplets, RefreshCw, AlertCircle } from 'lucide-react'
import { aqiMeta } from '../utils/aqi'

const WIND_DIRS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                   'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']

function windDir(deg) {
  if (deg == null) return '—'
  return WIND_DIRS[Math.round(deg / 22.5) % 16]
}

function windArrow(deg) {
  if (deg == null) return null
  return (
    <svg
      viewBox="0 0 24 24"
      width={14}
      height={14}
      style={{ transform: `rotate(${deg}deg)`, flexShrink: 0 }}
    >
      <path d="M12 2 L6 20 L12 16 L18 20 Z" fill="currentColor" />
    </svg>
  )
}

export default function TopBar({ cityAqi, weather, lastUpdate, onRefresh, refreshing, error, countdownSeconds }) {
  const meta = aqiMeta(cityAqi)
  const temp = weather?.temp_c ?? weather?.temperature ?? weather?.main?.temp ?? null
  const humidity = weather?.humidity_pct ?? weather?.humidity ?? weather?.main?.humidity ?? null
  const windSpeed = weather?.wind_speed_ms ?? weather?.wind_speed ?? weather?.wind?.speed ?? null
  const windDeg = weather?.wind_deg ?? weather?.wind_direction ?? weather?.wind?.deg ?? null
  const desc = weather?.condition ?? weather?.description ?? weather?.weather?.[0]?.description ?? ''

  const fmtTime = (d) => {
    if (!d) return '—'
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
  }

  const fmtCountdown = (secondsTotal) => {
    const total = Math.max(0, Number(secondsTotal || 0))
    const minutes = Math.floor(total / 60)
    const seconds = total % 60
    return `${minutes}:${String(seconds).padStart(2, '0')}`
  }

  return (
    <header className="topbar">
      {/* Logo */}
      <div className="topbar-logo">
        <span className="logo-icon">◉</span>
        <span className="logo-text">KTM AirWatch</span>
        <span className="logo-sub">Kathmandu</span>
      </div>

      {/* AQI badge */}
      <div className="topbar-aqi" style={{ '--aqi-color': meta.color, '--aqi-bg': meta.bg }}>
        <div className="aqi-number">{cityAqi != null ? Math.round(cityAqi) : '—'}</div>
        <div className="aqi-meta">
          <span className="aqi-unit">AQI</span>
          <span className="aqi-label">{cityAqi != null ? meta.label : 'No data'}</span>
        </div>
      </div>

      {/* Weather strip */}
      <div className="topbar-weather">
        {temp != null && (
          <div className="wx-item">
            <Thermometer size={13} />
            <span>{Math.round(temp)}°C</span>
          </div>
        )}
        {humidity != null && (
          <div className="wx-item">
            <Droplets size={13} />
            <span>{Math.round(humidity)}%</span>
          </div>
        )}
        {windSpeed != null && (
          <div className="wx-item">
            <Wind size={13} />
            <span>{windSpeed.toFixed(1)} m/s</span>
            {windArrow(windDeg)}
            <span className="wx-dir">{windDir(windDeg)}</span>
          </div>
        )}
        {desc && (
          <div className="wx-item wx-desc">
            <span>{desc}</span>
          </div>
        )}
      </div>

      <div className="topbar-spacer" />

      {/* Status */}
      <div className="topbar-status">
        {error && (
          <div className="status-error">
            <AlertCircle size={13} />
            <span>Stale data</span>
          </div>
        )}
        <div className="live-dot-wrap">
          <span className="live-dot" />
          <span className="live-text">Live</span>
        </div>
        <span className="last-update">
          {lastUpdate ? `Updated ${fmtTime(lastUpdate)}` : 'Loading…'}
        </span>
        <span className="next-update">Next update in {fmtCountdown(countdownSeconds)}</span>
      </div>

      {/* Refresh */}
      <button
        className={`refresh-btn ${refreshing ? 'spinning' : ''}`}
        onClick={onRefresh}
        disabled={refreshing}
        title="Refresh data"
      >
        <RefreshCw size={15} />
      </button>
    </header>
  )
}
