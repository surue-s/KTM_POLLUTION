import { useMemo, useRef, useState } from 'react'
import Papa from 'papaparse'

const MAP_STYLES = [
  { id: 'dark', label: 'Dark', url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json' },
  { id: 'light', label: 'Light', url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json' },
  { id: 'satellite', label: 'Satellite', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}' },
  { id: 'topo', label: 'Topo', url: 'https://tile.opentopomap.org/{z}/{x}/{y}.png' },
]

const SECTION_TITLES = {
  style: 'Map Style Switcher',
  upload: 'Data File Upload',
  layers: 'Layer Visibility',
  filter: 'AQI Filter',
  language: 'Map Language',
}

const SECTION_ORDER = ['style', 'upload', 'layers', 'filter', 'language']

const LAT_KEYS = ['lat', 'latitude', 'y']
const LON_KEYS = ['lng', 'lon', 'longitude', 'x']

function detectCoordinateKeys(firstRow) {
  if (!firstRow || typeof firstRow !== 'object') return { latKey: null, lonKey: null }
  const keyMap = Object.keys(firstRow).reduce((acc, key) => {
    acc[key.toLowerCase().trim()] = key
    return acc
  }, {})

  const latLookup = LAT_KEYS.find((candidate) => keyMap[candidate])
  const lonLookup = LON_KEYS.find((candidate) => keyMap[candidate])

  return {
    latKey: latLookup ? keyMap[latLookup] : null,
    lonKey: lonLookup ? keyMap[lonLookup] : null,
  }
}

function isFiniteNumber(value) {
  return Number.isFinite(Number(value))
}

function parseCsvPoints(text) {
  const result = Papa.parse(text, {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: false,
  })

  if (result.errors?.length) {
    throw new Error(result.errors[0]?.message || 'Could not parse CSV')
  }

  const rows = result.data || []
  const { latKey, lonKey } = detectCoordinateKeys(rows[0])
  if (!latKey || !lonKey) {
    throw new Error('CSV must include latitude/longitude columns (lat/latitude + lon/lng/longitude/x/y)')
  }

  return rows
    .filter((row) => isFiniteNumber(row?.[latKey]) && isFiniteNumber(row?.[lonKey]))
    .map((row, index) => ({
      id: `csv-${index}`,
      lat: Number(row[latKey]),
      lon: Number(row[lonKey]),
      ...row,
    }))
}

function parseGeoJsonPoints(text) {
  let parsed
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error('Invalid GeoJSON file')
  }

  const features = Array.isArray(parsed?.features) ? parsed.features : []
  const points = features
    .filter((feature) => feature?.geometry?.type === 'Point')
    .map((feature, index) => {
      const coords = feature?.geometry?.coordinates || []
      return {
        id: `geojson-${index}`,
        lon: Number(coords[0]),
        lat: Number(coords[1]),
        ...(feature?.properties || {}),
      }
    })
    .filter((point) => isFiniteNumber(point.lat) && isFiniteNumber(point.lon))

  return points
}

export default function MapControls({
  basemapUrl,
  onBasemapChange,
  layerVisibility,
  onLayerVisibilityChange,
  aqiThreshold,
  onAqiThresholdChange,
  uploadedData,
  onUploadedDataChange,
}) {
  const fileInputRef = useRef(null)
  const [expanded, setExpanded] = useState({
    style: true,
    upload: false,
    layers: false,
    filter: false,
    language: false,
  })
  const [uploadError, setUploadError] = useState('')

  const activeStyleId = useMemo(() => {
    const selected = MAP_STYLES.find((style) => style.url === basemapUrl)
    return selected?.id ?? 'dark'
  }, [basemapUrl])

  const toggleSection = (sectionKey) => {
    setExpanded((prev) => ({ ...prev, [sectionKey]: !prev[sectionKey] }))
  }

  const handleFile = async (file) => {
    if (!file) return
    const name = file.name || 'uploaded-file'
    const extension = name.toLowerCase().split('.').pop()
    setUploadError('')

    try {
      const text = await file.text()
      let points = []

      if (extension === 'csv') {
        points = parseCsvPoints(text)
      } else if (extension === 'geojson' || extension === 'json') {
        points = parseGeoJsonPoints(text)
      } else {
        throw new Error('Only .csv and .geojson files are supported')
      }

      if (!points.length) {
        throw new Error('No valid points found in uploaded file')
      }

      onUploadedDataChange({
        filename: name,
        points,
      })
    } catch (error) {
      onUploadedDataChange(null)
      setUploadError(error?.message || 'Upload failed')
    }
  }

  const handleDrop = async (event) => {
    event.preventDefault()
    const file = event.dataTransfer?.files?.[0]
    await handleFile(file)
  }

  return (
    <div style={{ marginTop: 12, padding: '0 8px 10px' }}>
      <div style={{ color: '#dbe8f8', fontSize: 12, fontWeight: 700, marginBottom: 8 }}>
        Map Controls
      </div>

      {SECTION_ORDER.map((sectionKey) => (
        <div key={sectionKey} style={{ border: '1px solid #2a3448', borderRadius: 8, marginBottom: 8, overflow: 'hidden' }}>
          <button
            onClick={() => toggleSection(sectionKey)}
            style={{
              width: '100%',
              textAlign: 'left',
              background: '#131b2d',
              color: '#d8e4f7',
              border: 'none',
              padding: '8px 10px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>{SECTION_TITLES[sectionKey]}</span>
            <span>{expanded[sectionKey] ? '▾' : '▸'}</span>
          </button>

          {expanded[sectionKey] && (
            <div style={{ background: '#101728', padding: 10 }}>
              {sectionKey === 'style' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {MAP_STYLES.map((style) => (
                    <button
                      key={style.id}
                      onClick={() => onBasemapChange(style.url)}
                      style={{
                        padding: '7px 8px',
                        borderRadius: 6,
                        border: `1px solid ${activeStyleId === style.id ? '#ff6b35' : '#2b3a52'}`,
                        background: activeStyleId === style.id ? '#2b1d18' : '#161f31',
                        color: '#d5e1f1',
                        fontSize: 12,
                        cursor: 'pointer',
                      }}
                    >
                      {style.label}
                    </button>
                  ))}
                </div>
              )}

              {sectionKey === 'upload' && (
                <div>
                  <div
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    style={{
                      border: '1px dashed #3b4d68',
                      borderRadius: 8,
                      padding: 12,
                      textAlign: 'center',
                      color: '#9db2cc',
                      fontSize: 12,
                      cursor: 'pointer',
                      background: '#121b2c',
                    }}
                  >
                    Drag & drop .csv/.geojson<br />
                    or click to upload
                  </div>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.geojson,application/geo+json,application/json"
                    style={{ display: 'none' }}
                    onChange={async (event) => {
                      const file = event.target.files?.[0]
                      await handleFile(file)
                      event.target.value = ''
                    }}
                  />

                  {uploadedData && (
                    <div style={{ marginTop: 10, fontSize: 12, color: '#d3deee' }}>
                      <div>File: {uploadedData.filename}</div>
                      <div>Points: {uploadedData.points?.length ?? 0}</div>
                      <button
                        onClick={() => onUploadedDataChange(null)}
                        style={{
                          marginTop: 8,
                          border: '1px solid #5d2d36',
                          background: '#2b171b',
                          color: '#f0b2bc',
                          borderRadius: 6,
                          padding: '5px 8px',
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  )}

                  {uploadError && (
                    <div style={{ marginTop: 8, color: '#ff8a8a', fontSize: 12 }}>
                      {uploadError}
                    </div>
                  )}
                </div>
              )}

              {sectionKey === 'layers' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12, color: '#d5e1f1' }}>
                  <label><input type="checkbox" checked={layerVisibility.stations} onChange={(e) => onLayerVisibilityChange({ stations: e.target.checked })} /> AQ Stations</label>
                  <label><input type="checkbox" checked={layerVisibility.zones} onChange={(e) => onLayerVisibilityChange({ zones: e.target.checked })} /> Pollution Zones</label>
                  <label><input type="checkbox" checked={layerVisibility.zoneLabels} onChange={(e) => onLayerVisibilityChange({ zoneLabels: e.target.checked })} /> Zone Labels</label>
                  <label><input type="checkbox" checked={layerVisibility.uploaded} onChange={(e) => onLayerVisibilityChange({ uploaded: e.target.checked })} disabled={!uploadedData} /> Uploaded Data</label>
                </div>
              )}

              {sectionKey === 'filter' && (
                <div style={{ color: '#d5e1f1', fontSize: 12 }}>
                  <div style={{ marginBottom: 6 }}>Show stations with AQI above: {aqiThreshold}</div>
                  <input
                    type="range"
                    min={0}
                    max={300}
                    step={1}
                    value={aqiThreshold}
                    onChange={(e) => onAqiThresholdChange(Number(e.target.value) || 0)}
                    style={{ width: '100%' }}
                  />
                </div>
              )}

              {sectionKey === 'language' && (
                <div style={{ color: '#9fb4ce', fontSize: 12 }}>
                  Labels: English (CARTO default)
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
