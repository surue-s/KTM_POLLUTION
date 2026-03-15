import ForecastChart from './ForecastChart'
import ApiMonitor from './ApiMonitor'

const SOURCE_ICONS = {
  brick_kiln: '🏭',
  traffic_corridor: '🚗',
  construction_dust: '🏗',
  garbage_burning: '🔥',
  industrial_mixed: '🏭',
}

const SOURCE_LABELS = {
  brick_kiln: 'Brick Kiln',
  traffic_corridor: 'Traffic',
  construction_dust: 'Construction',
  garbage_burning: 'Waste Burning',
  industrial_mixed: 'Industrial',
}

function riskMeta(score) {
  if (score > 75) return { color: '#ff4444', bg: '#ff444415', label: 'Critical' }
  if (score > 50) return { color: '#ff6b35', bg: '#ff6b3515', label: 'High' }
  if (score > 25) return { color: '#ffcc00', bg: '#ffcc0015', label: 'Moderate' }
  return { color: '#00cc66', bg: '#00cc6615', label: 'Low' }
}

function AlertBadge({ severity }) {
  const colors = {
    critical: { bg: '#ff444420', border: '#ff4444', text: '#ff6666' },
    warning:  { bg: '#ff6b3520', border: '#ff6b35', text: '#ff9060' },
    info:     { bg: '#4fc3f720', border: '#4fc3f7', text: '#7dd3fc' },
  }
  const c = colors[severity] ?? colors.info
  return (
    <span
      className="alert-badge"
      style={{ background: c.bg, borderColor: c.border, color: c.text }}
    >
      {severity}
    </span>
  )
}

export default function SourceZonePanel({
  zones,
  stations,
  alerts,
  apiStatus,
  forecast,
  selectedZone,
  onZoneSelect,
  lastUpdate,
}) {
  const stationById = new Map((stations ?? []).map((station) => [String(station.id), station]))

  const dataQuality = (timestamp) => {
    if (!timestamp) return { label: 'Stale', cls: 'dq-stale' }
    const ts = new Date(timestamp)
    if (!Number.isFinite(ts.getTime())) return { label: 'Stale', cls: 'dq-stale' }
    const ageHours = (Date.now() - ts.getTime()) / (1000 * 60 * 60)
    if (ageHours <= 3) return { label: 'Live', cls: 'dq-live' }
    if (ageHours <= 24) return { label: 'Stale', cls: 'dq-stale' }
    return { label: 'Offline', cls: 'dq-offline' }
  }

  const handleZoneClick = (zone) => {
    onZoneSelect(zone)
  }

  const sortedZones = [...(zones ?? [])].sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))

  return (
    <aside className="side-panel">
      {/* ── Pollution Sources ── */}
      <div className="panel-section">
        <div className="panel-section-title">
          Top Pollution Sources
          <span className="panel-badge">{zones?.length ?? 0}</span>
        </div>
        <div className="zone-list">
          {sortedZones.slice(0, 12).map((zone, idx) => {
            const risk = riskMeta(zone.risk_score ?? 0)
            const isSelected = selectedZone?.zone_id === zone.zone_id
            const icon = SOURCE_ICONS[zone.source_type] ?? '📍'
            const label = SOURCE_LABELS[zone.source_type] ?? zone.source_type ?? 'Unknown'
            const pm25 = zone.avg_pm25 != null ? zone.avg_pm25.toFixed(1) : '—'
            const score = Math.round(zone.risk_score ?? 0)
            const primaryStationId = zone.station_ids?.[0] != null ? String(zone.station_ids[0]) : null
            const primaryStation = primaryStationId ? stationById.get(primaryStationId) : null
            const quality = dataQuality(primaryStation?.timestamp ?? lastUpdate)

            return (
              <button
                key={zone.zone_id ?? idx}
                className={`zone-row ${isSelected ? 'zone-row--selected' : ''}`}
                style={{ '--risk-color': risk.color, '--risk-bg': risk.bg }}
                onClick={() => handleZoneClick(zone)}
              >
                <div className="zone-rank">#{idx + 1}</div>
                <div className="zone-icon">{icon}</div>
                <div className="zone-info">
                  <div className="zone-type">{label}</div>
                  <div className="zone-name">{zone.zone_id ?? `Zone ${idx + 1}`}</div>
                  <span className={`dq-badge ${quality.cls}`}>{quality.label}</span>
                  <div className="zone-bar-wrap">
                    <div
                      className="zone-bar"
                      style={{ width: `${Math.min(score, 100)}%`, background: risk.color }}
                    />
                  </div>
                </div>
                <div className="zone-stats">
                  <span className="zone-score" style={{ color: risk.color }}>{score}</span>
                  <span className="zone-pm25">{pm25}</span>
                  <span className="zone-pm25-unit">µg/m³</span>
                </div>
              </button>
            )
          })}
          {sortedZones.length === 0 && (
            <div className="panel-empty">No zone data</div>
          )}
        </div>
      </div>

      {/* ── Alerts ── */}
      {alerts && alerts.length > 0 && (
        <div className="panel-section panel-section--alerts">
          <div className="panel-section-title">
            Active Alerts
            <span className="panel-badge panel-badge--alert">{alerts.length}</span>
          </div>
          <div className="alert-list">
            {alerts.map((alert, idx) => (
              <div key={idx} className="alert-row">
                <AlertBadge severity={alert.severity ?? 'info'} />
                <span className="alert-msg">{alert.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── API Monitor ── */}
      <div className="panel-section">
        <ApiMonitor apiStatus={apiStatus} lastUpdate={lastUpdate} />
      </div>

      {/* ── LSTM Forecast ── */}
      <div className="panel-section panel-section--forecast">
        <ForecastChart
          forecast={forecast}
          stationId={selectedZone?.station_ids?.[0]}
        />
      </div>
    </aside>
  )
}
