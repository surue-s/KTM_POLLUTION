import { Database, Radio, Cloud } from 'lucide-react'

const SOURCES = [
  {
    key: 'openaq',
    label: 'OpenAQ',
    desc: 'Ground sensors',
    icon: Database,
  },
  {
    key: 'waqi',
    label: 'WAQI',
    desc: 'AQI network',
    icon: Radio,
  },
  {
    key: 'owm',
    label: 'OpenWeather',
    desc: 'Meteorology',
    icon: Cloud,
  },
]

function StatusDot({ active }) {
  return (
    <span
      className={`api-dot ${active ? 'api-dot--active' : 'api-dot--inactive'}`}
      title={active ? 'Online' : 'Offline'}
    />
  )
}

export default function ApiMonitor({ apiStatus, lastUpdate }) {
  const fmtTime = (d) => {
    if (!d) return 'Never'
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
  }

  const predictionTs = apiStatus?.lastPredictionAt ? new Date(apiStatus.lastPredictionAt) : null
  const modelActive = Boolean(
    apiStatus?.modelLoaded &&
    predictionTs &&
    Number.isFinite(predictionTs.getTime()) &&
    (Date.now() - predictionTs.getTime()) < (30 * 60 * 1000)
  )

  const rmse = Number(apiStatus?.modelRmse)
  const rmseText = Number.isFinite(rmse) ? rmse.toFixed(4) : 'N/A'

  return (
    <div className="api-monitor">
      <div className="panel-section-title">Data Sources</div>
      <div className="api-sources">
        {SOURCES.map(({ key, label, desc, icon: Icon }) => {
          const online = apiStatus?.[key] ?? false
          const sourceCount = apiStatus?.sourceCounts?.[key] ?? 0
          return (
            <div key={key} className={`api-row ${online ? '' : 'api-row--offline'}`}>
              <Icon size={13} className="api-icon" />
              <div className="api-info">
                <span className="api-name">{label}</span>
                <span className="api-desc">{desc}</span>
              </div>
              <span className="api-source-count">{sourceCount}</span>
              <StatusDot active={online} />
            </div>
          )
        })}
      </div>

      <div className="model-status-row">
        <div className="model-state">
          <span className={`api-dot ${modelActive ? 'api-dot--active' : 'api-dot--inactive'}`} />
          <span>Model: {modelActive ? 'Active' : 'Idle'}</span>
        </div>
        <span className="model-rmse">RMSE {rmseText}</span>
      </div>
      <div className="model-training-note">
        {apiStatus?.trainingInfo ?? 'Trained on synthetic + live data'}
      </div>

      <div className="api-footer">
        <span className="api-count">
          <span className="api-count-num">{apiStatus?.stationCount ?? 0}</span>
          &nbsp;stations active
        </span>
        <span className="api-last">
          {fmtTime(lastUpdate)}
        </span>
      </div>
    </div>
  )
}
