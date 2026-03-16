import { useState, useCallback } from 'react'
import DeckGL from '@deck.gl/react'
import { Map } from 'react-map-gl/maplibre'
import { ScatterplotLayer, TextLayer, IconLayer } from '@deck.gl/layers'
import { HexagonLayer } from '@deck.gl/aggregation-layers'
import 'maplibre-gl/dist/maplibre-gl.css'

const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const INITIAL_VIEW = {
  latitude: 27.7172,
  longitude: 85.3240,
  zoom: 11,
  pitch: 0,
  bearing: 0,
  minZoom: 9,
  maxZoom: 16,
}

function getAQIColor(aqi) {
  if (!aqi || aqi <= 0) return [100, 100, 100, 160]
  if (aqi <= 50) return [0, 228, 0, 220]
  if (aqi <= 100) return [255, 255, 0, 220]
  if (aqi <= 150) return [255, 126, 0, 220]
  if (aqi <= 200) return [255, 0, 0, 220]
  if (aqi <= 300) return [143, 63, 151, 220]
  return [126, 0, 35, 220]
}

function getRiskColor(risk) {
  if (risk > 75) return [189, 0, 38]
  if (risk > 50) return [240, 59, 32]
  if (risk > 25) return [253, 141, 60]
  return [254, 204, 92]
}

const SOURCE_LABELS = {
  brick_kiln: '🏭 Brick kiln',
  traffic_corridor: '🚗 Traffic',
  construction_dust: '🏗 Construction',
  garbage_burning: '🔥 Garbage burning',
  industrial_mixed: '⚙️ Industrial',
  unknown: '📍 Unknown',
}

const SOURCE_BREAKDOWN = {
  brick_kiln: { 'Kiln emissions': 35, 'Biomass burning': 25, 'Vehicle exhaust': 20, Other: 20 },
  traffic_corridor: { 'Vehicle exhaust': 55, 'Dust resuspension': 25, Other: 20 },
  construction_dust: { 'Construction dust': 60, 'Vehicle exhaust': 20, Other: 20 },
  garbage_burning: { 'Open burning': 50, 'Biomass burning': 30, 'Vehicle exhaust': 15, Other: 5 },
  industrial_mixed: { Industrial: 45, 'Vehicle exhaust': 30, Other: 25 },
  unknown: { 'Unknown sources': 100 },
}

function buildMapStyle(styleUrl) {
  const selectedStyle = styleUrl || BASEMAP
  const isRasterTileTemplate =
    selectedStyle.includes('{z}') &&
    selectedStyle.includes('{x}') &&
    selectedStyle.includes('{y}')

  if (!isRasterTileTemplate) {
    return selectedStyle
  }

  return {
    version: 8,
    sources: {
      'raster-tiles': {
        type: 'raster',
        tiles: [selectedStyle],
        tileSize: 256,
      },
    },
    layers: [
      {
        id: 'raster-tiles-layer',
        type: 'raster',
        source: 'raster-tiles',
        minzoom: 0,
        maxzoom: 22,
      },
    ],
  }
}

export default function DeckMap({
  stations = [],
  zones = [],
  onZoneClick,
  basemapUrl = BASEMAP,
  layerVisibility = { stations: true, zones: true, zoneLabels: true, uploaded: true },
  aqiThreshold = 0,
  uploadedData = null,
}) {
  const [is3D, setIs3D] = useState(false)
  const [viewState, setViewState] = useState(INITIAL_VIEW)

  const handleViewStateChange = useCallback(({ viewState: nextViewState }) => {
    setViewState(nextViewState)
  }, [])

  // Kept intentionally to match requested imports and allow future icon overlays.
  void IconLayer

  const showStations = layerVisibility?.stations ?? true
  const showZones = layerVisibility?.zones ?? true
  const showZoneLabels = layerVisibility?.zoneLabels ?? true
  const showUploaded = layerVisibility?.uploaded ?? true

  const filteredStations = stations
    .filter((station) => station.lat && station.lon)
    .filter((station) => Number(station.aqi ?? 0) >= Number(aqiThreshold ?? 0))

  const filteredZones = zones.filter((zone) => zone.center_lat && zone.center_lon)

  const stationLayer = new ScatterplotLayer({
    id: 'aq-stations',
    data: filteredStations,
    getPosition: (station) => [parseFloat(station.lon), parseFloat(station.lat)],
    getRadius: (station) => Math.max(120, (station.pm25 || 20) * 6),
    getFillColor: (station) => getAQIColor(station.aqi),
    getLineColor: [255, 255, 255, 50],
    lineWidthMinPixels: 1,
    stroked: true,
    filled: true,
    radiusMinPixels: 4,
    radiusMaxPixels: 22,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 60],
  })

  const zoneLayer = new ScatterplotLayer({
    id: 'zone-circles',
    data: filteredZones,
    getPosition: (zone) => [parseFloat(zone.center_lon), parseFloat(zone.center_lat)],
    getRadius: (zone) => 300 + (zone.risk_score || 0) * 5,
    getFillColor: (zone) => [...getRiskColor(zone.risk_score || 0), 100],
    getLineColor: (zone) => [...getRiskColor(zone.risk_score || 0), 200],
    lineWidthMinPixels: 2,
    stroked: true,
    filled: true,
    radiusMinPixels: 18,
    radiusMaxPixels: 60,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 40],
    onClick: (info) => info.object && onZoneClick && onZoneClick(info.object),
  })

  const zoneHexLayer = new HexagonLayer({
    id: 'zone-hex',
    data: filteredZones,
    getPosition: (zone) => [parseFloat(zone.center_lon), parseFloat(zone.center_lat)],
    getElevationWeight: (zone) => zone.risk_score || 0,
    getColorWeight: (zone) => zone.risk_score || 0,
    elevationScale: is3D ? 12 : 0,
    extruded: is3D,
    radius: 500,
    coverage: 0.88,
    colorRange: [
      [254, 235, 226, 160],
      [251, 180, 185, 180],
      [247, 104, 161, 200],
      [197, 27, 138, 210],
      [122, 1, 119, 220],
    ],
    pickable: false,
    opacity: is3D ? 0.6 : 0,
  })

  const zoneLabelLayer = new TextLayer({
    id: 'zone-labels',
    data: filteredZones,
    getPosition: (zone) => [parseFloat(zone.center_lon), parseFloat(zone.center_lat)],
    getText: (zone) => SOURCE_LABELS[zone.source_type] || '📍 Zone',
    getSize: 11,
    getColor: [255, 255, 255, 220],
    getTextAnchor: 'middle',
    getAlignmentBaseline: 'center',
    fontFamily: 'monospace',
    getPixelOffset: [0, -32],
  })

  const uploadedLayer = uploadedData?.points?.length
    ? new ScatterplotLayer({
        id: 'uploaded-data',
        data: uploadedData.points,
        getPosition: (point) => [Number(point.lon), Number(point.lat)],
        getRadius: 180,
        radiusMinPixels: 4,
        radiusMaxPixels: 20,
        filled: true,
        stroked: true,
        lineWidthMinPixels: 1,
        getFillColor: [168, 85, 247, 190],
        getLineColor: [230, 200, 255, 210],
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 70],
      })
    : null

  const layers = [
    showZones ? zoneHexLayer : null,
    showZones ? zoneLayer : null,
    showStations ? stationLayer : null,
    showZoneLabels ? zoneLabelLayer : null,
    showUploaded ? uploadedLayer : null,
  ].filter(Boolean)

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute',
          top: 10,
          left: 10,
          zIndex: 20,
          display: 'flex',
          gap: 8,
          pointerEvents: 'all',
        }}
      >
        <button
          onClick={() => {
            setIs3D((prev) => !prev)
            setViewState((prev) => ({
              ...prev,
              pitch: !is3D ? 45 : 0,
              bearing: !is3D ? -20 : 0,
              transitionDuration: 600,
            }))
          }}
          style={{
            background: is3D ? '#ff6b35' : 'rgba(20,20,35,0.85)',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 6,
            padding: '6px 12px',
            fontSize: 12,
            cursor: 'pointer',
            fontFamily: 'monospace',
            fontWeight: 500,
            backdropFilter: 'blur(4px)',
          }}
        >
          {is3D ? '3D ON' : '2D'}
        </button>

        <button
          onClick={() => setViewState({ ...INITIAL_VIEW, transitionDuration: 800 })}
          style={{
            background: 'rgba(20,20,35,0.85)',
            color: '#aaa',
            border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: 6,
            padding: '6px 10px',
            fontSize: 12,
            cursor: 'pointer',
            fontFamily: 'monospace',
            backdropFilter: 'blur(4px)',
          }}
        >
          ⌂ Reset
        </button>
      </div>

      <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}>
        <DeckGL
          viewState={viewState}
          onViewStateChange={handleViewStateChange}
          controller={{ dragRotate: true, touchRotate: true, inertia: true }}
          layers={layers}
          getTooltip={({ object, layer }) => {
            if (!object) return null

            if (layer?.id === 'aq-stations') {
              return {
                html: `
                  <div style="font-weight:700;margin-bottom:4px;">${object.name || 'Station'}</div>
                  <div>AQI ${object.aqi || 'N/A'}</div>
                  <div>PM2.5 &nbsp;${object.pm25 ? object.pm25.toFixed(1) : 'N/A'} µg/m³</div>
                  <div>PM10 &nbsp;&nbsp;${object.pm10 ? object.pm10.toFixed(1) : 'N/A'} µg/m³</div>
                  <div>NO₂ &nbsp;&nbsp;&nbsp;${object.no2 ? object.no2.toFixed(1) : 'N/A'} µg/m³</div>
                  <div>Source: ${object.source || 'unknown'}</div>
                `,
                style: {
                  background: '#13131f',
                  color: '#e0e0e0',
                  border: '1px solid #2a2a3f',
                  borderRadius: '8px',
                  padding: '10px 12px',
                },
              }
            }

            if (layer?.id === 'zone-circles') {
              const breakdown = SOURCE_BREAKDOWN[object.source_type] || SOURCE_BREAKDOWN.unknown
              const breakdownHtml = Object.entries(breakdown)
                .map(([key, value]) => `<div style=\"display:flex;justify-content:space-between;gap:12px;\"><span>${key}</span><strong>${value}%</strong></div>`)
                .join('')
              return {
                html: `
                  <div style="font-weight:700;margin-bottom:6px;">${SOURCE_LABELS[object.source_type] || '📍 Zone'}</div>
                  <div>Risk score &nbsp;${(object.risk_score || 0).toFixed(0)}/100</div>
                  <div>Avg PM2.5 &nbsp;${(object.avg_pm25 || 0).toFixed(1)} µg/m³</div>
                  <div>Avg AQI &nbsp;&nbsp;&nbsp;${(object.avg_aqi || 0).toFixed(0)}</div>
                  <div>Confidence ${((object.confidence || 0) * 100).toFixed(0)}%</div>
                  <div style="margin-top:8px;font-weight:700;color:#f5c16c;">CAUSE BREAKDOWN</div>
                  <div style="margin-top:4px;display:flex;flex-direction:column;gap:2px;">${breakdownHtml}</div>
                  <div style="margin-top:8px;color:#b8c4d6;">Click for full analysis</div>
                `,
                style: {
                  background: '#13131f',
                  color: '#e0e0e0',
                  border: '1px solid #2a2a3f',
                  borderRadius: '8px',
                  padding: '10px 12px',
                },
              }
            }

            if (layer?.id === 'uploaded-data') {
              return {
                html: `
                  <div style="font-weight:700;margin-bottom:4px;">Uploaded point</div>
                  <div>Source file: ${uploadedData?.filename || 'uploaded data'}</div>
                  <div>Lat: ${Number(object.lat).toFixed(5)}</div>
                  <div>Lon: ${Number(object.lon).toFixed(5)}</div>
                `,
                style: {
                  background: '#13131f',
                  color: '#e0e0e0',
                  border: '1px solid #2a2a3f',
                  borderRadius: '8px',
                  padding: '10px 12px',
                },
              }
            }
            return null
          }}
        >
          <Map mapStyle={buildMapStyle(basemapUrl)} />
        </DeckGL>
      </div>
    </div>
  )
}
