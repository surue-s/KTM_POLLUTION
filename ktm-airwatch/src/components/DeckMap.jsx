import DeckGL from '@deck.gl/react'
import { Map } from 'react-map-gl/maplibre'
import { ScatterplotLayer } from '@deck.gl/layers'
import { HexagonLayer } from '@deck.gl/aggregation-layers'
import 'maplibre-gl/dist/maplibre-gl.css'

const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const INITIAL_VIEW = {
  latitude: 27.7172,
  longitude: 85.3240,
  zoom: 11,
  pitch: 40,
  bearing: 0,
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

export default function DeckMap({ stations = [], zones = [], onZoneClick }) {
  const stationLayer = new ScatterplotLayer({
    id: 'aq-stations',
    data: stations.filter((station) => Number.isFinite(station?.lat) && Number.isFinite(station?.lon)),
    getPosition: (station) => [station.lon, station.lat],
    getRadius: (station) => Math.max(150, (station.pm25 || 20) * 10),
    getFillColor: (station) => getAQIColor(station.aqi),
    getLineColor: [255, 255, 255, 60],
    lineWidthMinPixels: 1,
    stroked: true,
    filled: true,
    radiusMinPixels: 5,
    radiusMaxPixels: 30,
    pickable: true,
    opacity: 0.9,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 80],
  })

  const zoneLayer = new HexagonLayer({
    id: 'pollution-zones',
    data: zones.filter((zone) => Number.isFinite(zone?.center_lat) && Number.isFinite(zone?.center_lon)),
    getPosition: (zone) => [zone.center_lon, zone.center_lat],
    getElevationWeight: (zone) => zone.risk_score || 0,
    getColorWeight: (zone) => zone.risk_score || 0,
    elevationScale: 80,
    extruded: true,
    radius: 600,
    coverage: 0.88,
    colorRange: [
      [254, 235, 226, 180],
      [251, 180, 185, 200],
      [247, 104, 161, 210],
      [197, 27, 138, 220],
      [122, 1, 119, 240],
    ],
    pickable: true,
    onClick: (info) => {
      if (info.object && onZoneClick) {
        const nearest = zones.reduce((best, zone) => {
          const [lon, lat] = info.object.position
          const distance = Math.abs(zone.center_lat - lat) + Math.abs(zone.center_lon - lon)
          return distance < best.distance ? { zone, distance } : best
        }, { zone: zones[0], distance: Infinity })
        if (nearest.zone) onZoneClick(nearest.zone)
      }
    },
    opacity: 0.75,
  })

  return (
    <DeckGL
      initialViewState={INITIAL_VIEW}
      controller
      layers={[zoneLayer, stationLayer]}
      getTooltip={({ object, layer }) => {
        if (!object) return null
        if (layer.id === 'aq-stations') {
          return {
            html: `
              <div>
                <strong>${object.name || 'Station'}</strong><br/>
                AQI: ${object.aqi || 'N/A'}<br/>
                PM2.5: ${object.pm25 ? object.pm25.toFixed(1) : 'N/A'} µg/m³<br/>
                PM10: ${object.pm10 ? object.pm10.toFixed(1) : 'N/A'} µg/m³<br/>
                NO₂: ${object.no2 ? object.no2.toFixed(1) : 'N/A'} µg/m³<br/>
                Source: ${object.source || 'unknown'}
              </div>
            `,
            style: {
              backgroundColor: '#1a1a2e',
              color: '#e0e0e0',
              border: '1px solid #333',
              borderRadius: '6px',
              padding: '8px 10px',
            },
          }
        }
        if (layer.id === 'pollution-zones') {
          return {
            html: `
              <div>
                <strong>Pollution cluster</strong><br/>
                Points: ${object.points?.length || 0}<br/>
                Avg risk: ${object.colorValue?.toFixed(0) || 'N/A'}
              </div>
            `,
            style: {
              backgroundColor: '#1a1a2e',
              color: '#e0e0e0',
              border: '1px solid #333',
              borderRadius: '6px',
              padding: '8px 10px',
            },
          }
        }
        return null
      }}
    >
      <Map mapStyle={BASEMAP} />
    </DeckGL>
  )
}
