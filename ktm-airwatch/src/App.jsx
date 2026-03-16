import React, { useState, useEffect, useCallback, useRef } from 'react'
import TopBar from './components/TopBar'
import SourceZonePanel from './components/SourceZonePanel'
import DeckMap from './components/DeckMap'
import MapControls from './components/MapControls'
import ZoneExplanation from './components/ZoneExplanation'

const API_BASE = 'http://localhost:8000/api'
const REFRESH_INTERVAL = 15 * 60 * 1000 // 15 minutes
const TOAST_TTL_MS = 8 * 1000
const FETCH_TIMEOUT_MS = 15000
const DEFAULT_BASEMAP_URL = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

async function fetchWithTimeout(url, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, { signal: controller.signal })
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`)
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: error?.message || 'Unexpected UI error',
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-runtime-error">
          <h2>KTM AirWatch UI Error</h2>
          <p>{this.state.message}</p>
          <p>Try a hard refresh. Data services are still running.</p>
        </div>
      )
    }
    return this.props.children
  }
}

function Dashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [selectedZone, setSelectedZone] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [explanationOpen, setExplanationOpen] = useState(false)
  const [health, setHealth] = useState(null)
  const [nextRefreshAt, setNextRefreshAt] = useState(null)
  const [countdownSeconds, setCountdownSeconds] = useState(0)
  const [toasts, setToasts] = useState([])
  const [basemapUrl, setBasemapUrl] = useState(DEFAULT_BASEMAP_URL)
  const [layerVisibility, setLayerVisibility] = useState({
    stations: true,
    zones: true,
    zoneLabels: true,
    uploaded: true,
  })
  const [aqiThreshold, setAqiThreshold] = useState(0)
  const [uploadedData, setUploadedData] = useState(null)
  const autoRefreshRef = useRef(null)
  const recentCriticalRef = useRef(new Map())

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
  }, [])

  const pushToast = useCallback((message) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    setToasts((prev) => [...prev, { id, message }])
    setTimeout(() => {
      dismissToast(id)
    }, TOAST_TTL_MS)
  }, [dismissToast])

  const fetchDashboard = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true)
    try {
      const [dashboardRes, healthRes] = await Promise.all([
        fetchWithTimeout(`${API_BASE}/dashboard`),
        fetchWithTimeout(`${API_BASE}/health`),
      ])

      if (!dashboardRes.ok) throw new Error(`HTTP ${dashboardRes.status}`)
      const data = await dashboardRes.json()
      setDashboard(data)
      setLastUpdate(new Date())
      setError(null)

      if (healthRes.ok) {
        const healthData = await healthRes.json()
        setHealth(healthData)
      }

      const criticalAlerts = (data.alerts ?? []).filter((alert) => alert?.severity === 'critical')
      const now = Date.now()
      criticalAlerts.forEach((alert) => {
        const key = String(alert.message ?? '')
        if (!key) return
        const lastShown = recentCriticalRef.current.get(key) || 0
        if (now - lastShown > TOAST_TTL_MS) {
          pushToast(key)
          recentCriticalRef.current.set(key, now)
        }
      })

      // Auto-select top zone on first load
      setSelectedZone((prev) => {
        if (prev) return prev
        if (data.zones && data.zones.length > 0) return data.zones[0]
        return prev
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [pushToast])

  const fetchForecast = useCallback(async (stationId) => {
    if (!stationId) return
    try {
      const res = await fetchWithTimeout(`${API_BASE}/forecast/${stationId}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setForecast(data)
    } catch (e) {
      console.warn('Forecast fetch failed:', e.message)
    }
  }, [])

  const scheduleNextRefresh = useCallback(() => {
    if (autoRefreshRef.current) {
      clearTimeout(autoRefreshRef.current)
    }
    const nextTs = Date.now() + REFRESH_INTERVAL
    setNextRefreshAt(nextTs)
    autoRefreshRef.current = setTimeout(async () => {
      await fetchDashboard(false)
      scheduleNextRefresh()
    }, REFRESH_INTERVAL)
  }, [fetchDashboard])

  useEffect(() => {
    fetchDashboard(false)
    scheduleNextRefresh()
    return () => {
      if (autoRefreshRef.current) clearTimeout(autoRefreshRef.current)
    }
  }, [fetchDashboard, scheduleNextRefresh])

  useEffect(() => {
    if (!nextRefreshAt) return undefined
    const tick = () => {
      const left = Math.max(0, Math.ceil((nextRefreshAt - Date.now()) / 1000))
      setCountdownSeconds(left)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [nextRefreshAt])

  useEffect(() => {
    if (selectedZone && selectedZone.station_ids && selectedZone.station_ids.length > 0) {
      fetchForecast(selectedZone.station_ids[0])
    } else if (dashboard?.forecast_summary) {
      setForecast(dashboard.forecast_summary)
    }
  }, [selectedZone, dashboard, fetchForecast])

  useEffect(() => {
    if (selectedZone) {
      setExplanationOpen(true)
    }
  }, [selectedZone])

  const handleZoneSelect = useCallback((zone) => {
    setSelectedZone(zone)
  }, [])

  const handleRefresh = useCallback(async () => {
    await fetchDashboard(true)
    scheduleNextRefresh()
  }, [fetchDashboard, scheduleNextRefresh])

  const handleCloseExplanation = useCallback(() => {
    setExplanationOpen(false)
  }, [])

  const handleLayerVisibilityChange = useCallback((partial) => {
    setLayerVisibility((prev) => ({ ...prev, ...partial }))
  }, [])

  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner" />
        <span>Connecting to KTM AirWatch...</span>
      </div>
    )
  }

  if (error && !dashboard) {
    return (
      <div className="app-error">
        <div className="error-icon">⚠</div>
        <h2>Backend Unreachable</h2>
        <p>Could not connect to <code>{API_BASE}</code></p>
        <p className="error-detail">{error}</p>
        <button onClick={() => fetchDashboard()}>Retry</button>
      </div>
    )
  }

  const weather = dashboard?.weather ?? {}
  const stations = dashboard?.stations ?? []
  const zones = dashboard?.zones ?? []
  const alerts = dashboard?.alerts ?? []
  const cityAqi = dashboard?.city_aqi_avg ?? null
  const sourceCounts = stations.reduce((acc, station) => {
    const source = station?.source
    if (source === 'openaq') acc.openaq += 1
    if (source === 'waqi') acc.waqi += 1
    if (source === 'owm') acc.owm += 1
    return acc
  }, { openaq: 0, waqi: 0, owm: 0 })

  const apiStatus = {
    openaq: health?.data_sources?.openaq ?? false,
    waqi: health?.data_sources?.waqi ?? false,
    owm: health?.data_sources?.owm ?? false,
    sourceCounts,
    stationCount: stations.length,
    modelLoaded: health?.model_loaded ?? false,
    modelRmse: health?.model_rmse ?? null,
    lastPredictionAt: forecast?.timestamp ?? dashboard?.timestamp ?? null,
    trainingInfo: 'Trained on 180 days synthetic + live data',
  }

  return (
    <div className="app-root">
      <div className="app-header">
        <TopBar
          cityAqi={cityAqi}
          weather={weather}
          lastUpdate={lastUpdate}
          onRefresh={handleRefresh}
          refreshing={refreshing}
          error={error}
          countdownSeconds={countdownSeconds}
        />
      </div>
      <div className="app-body">
        <div className="left-rail">
          <SourceZonePanel
            zones={zones}
            stations={stations}
            alerts={alerts}
            apiStatus={apiStatus}
            forecast={forecast}
            selectedZone={selectedZone}
            onZoneSelect={handleZoneSelect}
            lastUpdate={lastUpdate}
          />
          <MapControls
            basemapUrl={basemapUrl}
            onBasemapChange={setBasemapUrl}
            layerVisibility={layerVisibility}
            onLayerVisibilityChange={handleLayerVisibilityChange}
            aqiThreshold={aqiThreshold}
            onAqiThresholdChange={setAqiThreshold}
            uploadedData={uploadedData}
            onUploadedDataChange={setUploadedData}
          />
        </div>
        <div className="map-container" style={{ position: 'relative', flex: 1, overflow: 'hidden' }}>
          <DeckMap
            stations={stations}
            zones={zones}
            onZoneClick={handleZoneSelect}
            basemapUrl={basemapUrl}
            layerVisibility={layerVisibility}
            aqiThreshold={aqiThreshold}
            uploadedData={uploadedData}
          />
        </div>
      </div>
      <ZoneExplanation
        zone={selectedZone}
        weather={weather}
        isOpen={explanationOpen}
        onClose={handleCloseExplanation}
      />

      <div className="toast-stack" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <div key={toast.id} className="critical-toast">
            <div className="critical-toast-title">Critical Alert</div>
            <div className="critical-toast-msg">{toast.message}</div>
            <button
              className="critical-toast-close"
              onClick={() => dismissToast(toast.id)}
              aria-label="Dismiss alert"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AppErrorBoundary>
      <Dashboard />
    </AppErrorBoundary>
  )
}

