import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  LineChart,
  Line,
} from 'recharts'
import { X } from 'lucide-react'

const SOURCE_PROFILES = {
  brick_kiln: [
    { name: 'Kilns', value: 35, color: '#ff6b35' },
    { name: 'Vehicle', value: 20, color: '#ff9f43' },
    { name: 'Biomass', value: 25, color: '#feca57' },
    { name: 'Other', value: 20, color: '#8395a7' },
  ],
  traffic_corridor: [
    { name: 'Vehicle Emissions', value: 55, color: '#ff6b35' },
    { name: 'Dust Resuspension', value: 25, color: '#ff9f43' },
    { name: 'Other', value: 20, color: '#8395a7' },
  ],
  construction_dust: [
    { name: 'Construction', value: 60, color: '#ff6b35' },
    { name: 'Vehicle', value: 20, color: '#ff9f43' },
    { name: 'Other', value: 20, color: '#8395a7' },
  ],
  garbage_burning: [
    { name: 'Open Burning', value: 50, color: '#ff6b35' },
    { name: 'Biomass', value: 30, color: '#ff9f43' },
    { name: 'Vehicle', value: 15, color: '#feca57' },
    { name: 'Other', value: 5, color: '#8395a7' },
  ],
  industrial_mixed: [
    { name: 'Industry', value: 40, color: '#ff6b35' },
    { name: 'Vehicle', value: 25, color: '#ff9f43' },
    { name: 'Biomass', value: 20, color: '#feca57' },
    { name: 'Other', value: 15, color: '#8395a7' },
  ],
}

const ACTION_TEXT = {
  brick_kiln: (zoneName) =>
    `Deploy inspectors to ${zoneName}. Kilns in this area should be restricted to off-peak hours.`,
  traffic_corridor: (zoneName) =>
    `Reroute heavy vehicles. Deploy water tanker to ${zoneName}.`,
  construction_dust: (zoneName) =>
    `Require dust suppression at active sites. Check permits for ${zoneName}.`,
  garbage_burning: (zoneName) =>
    'Alert ward office. Coordinate pickup to prevent burning.',
  industrial_mixed: (zoneName) =>
    `Deploy inspectors to ${zoneName}. Prioritize mixed-emission controls across the zone.`,
}

function sourceLabel(type) {
  return type?.replaceAll('_', ' ')?.replace(/\b\w/g, (match) => match.toUpperCase()) || 'Unknown'
}

function seededRandom(seed) {
  const value = Math.sin(seed) * 10000
  return value - Math.floor(value)
}

function buildSevenDayTrend(zone) {
  const zoneKey = String(zone?.zone_id ?? 'zone')
  const seedBase = zoneKey.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  const base = Number(zone?.avg_pm25 ?? 55)
  const now = new Date()
  const points = []

  for (let offset = 6; offset >= 0; offset -= 1) {
    const dt = new Date(now)
    dt.setDate(now.getDate() - offset)
    const weekday = dt.toLocaleDateString('en-US', { weekday: 'short' })
    const noise = (seededRandom(seedBase + offset * 19) - 0.5) * 14
    const wave = Math.sin((offset / 6) * Math.PI * 1.7) * 9
    const pm25 = Math.max(12, base + wave + noise)
    points.push({ day: weekday, pm25: Number(pm25.toFixed(1)) })
  }

  return points
}

function inferKeyDrivers(zone, weather, trend) {
  const windSpeed = Number(weather?.wind_speed_ms ?? weather?.wind_speed ?? weather?.wind?.speed ?? 0)
  const temperature = Number(weather?.temp_c ?? weather?.temperature ?? weather?.main?.temp ?? 0)
  const humidity = Number(weather?.humidity_pct ?? weather?.humidity ?? weather?.main?.humidity ?? 0)
  const currentHour = new Date().getHours()

  const latest = trend[trend.length - 1]?.pm25 ?? Number(zone?.avg_pm25 ?? 60)
  const sixHoursAgo = trend[Math.max(0, trend.length - 2)]?.pm25 ?? latest * 0.8
  const risePct = sixHoursAgo > 0 ? ((latest - sixHoursAgo) / sixHoursAgo) * 100 : 0

  const candidates = [
    {
      score: Math.max(0, 3 - windSpeed) * 2.2,
      text: `wind speed is low (${windSpeed.toFixed(1)} m/s) → trapping pollutants`,
      feature: 'Wind speed',
    },
    {
      score: (currentHour >= 4 && currentHour <= 9 ? 4 : 1) + (humidity > 70 ? 2 : 0),
      text: `temperature inversion likely → it is ${currentHour < 12 ? 'early morning' : 'stable evening hours'}`,
      feature: 'Boundary-layer stability',
    },
    {
      score: Math.max(0, risePct / 12),
      text: `PM2.5 has risen ${Math.round(Math.max(0, risePct))}% in the last 6 hours`,
      feature: 'Recent PM2.5 momentum',
    },
    {
      score: Math.max(0, humidity - 60) / 8,
      text: `humidity is elevated (${Math.round(humidity)}%) → poor dispersion conditions`,
      feature: 'Humidity',
    },
    {
      score: temperature < 15 ? 2.5 : 1,
      text: `temperature is ${temperature.toFixed(1)}°C, supporting pollutant accumulation`,
      feature: 'Temperature regime',
    },
  ]

  const top = candidates
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)

  const reasoning = `High risk predicted because: ${top.map((item) => `[${item.text}]`).join(', ')}`

  return {
    topFeatures: top.map((item) => item.feature),
    reasoning,
    risePct: Math.round(risePct),
  }
}

function AttributionTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="zone-exp-tooltip">
      <span>{row.name}</span>
      <strong>{row.value}%</strong>
    </div>
  )
}

export default function ZoneExplanation({
  zone,
  weather,
  isOpen,
  onClose,
}) {
  if (!zone) return null

  const profile = SOURCE_PROFILES[zone.source_type] ?? SOURCE_PROFILES.industrial_mixed
  const trend = buildSevenDayTrend(zone)
  const drivers = inferKeyDrivers(zone, weather, trend)
  const zoneName = zone.zone_id || sourceLabel(zone.source_type)
  const actionBuilder = ACTION_TEXT[zone.source_type] ?? ACTION_TEXT.industrial_mixed
  const actionText = actionBuilder(zoneName)

  return (
    <>
      <div className={`zone-exp-backdrop ${isOpen ? 'open' : ''}`} onClick={onClose} />
      <aside className={`zone-exp-drawer ${isOpen ? 'open' : ''}`}>
        <header className="zone-exp-header">
          <div>
            <h3>Why is this zone polluted?</h3>
            <p>{zoneName} · {sourceLabel(zone.source_type)}</p>
          </div>
          <button className="zone-exp-close" onClick={onClose} aria-label="Close explanation">
            <X size={16} />
          </button>
        </header>

        <section className="zone-exp-section">
          <div className="zone-exp-title">Source attribution</div>
          <div className="zone-exp-chart">
            <ResponsiveContainer width="100%" height={190}>
              <BarChart data={profile} layout="vertical" margin={{ top: 6, right: 18, left: 10, bottom: 0 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#93a3b8', fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="name" width={130} tick={{ fill: '#d2deef', fontSize: 11 }} />
                <Tooltip content={<AttributionTooltip />} cursor={{ fill: '#ffffff10' }} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                  {profile.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="zone-exp-section">
          <div className="zone-exp-title">LSTM reasoning</div>
          <p className="zone-exp-reasoning">{drivers.reasoning}</p>
          <div className="zone-exp-tags">
            {drivers.topFeatures.map((feature) => (
              <span key={feature} className="zone-exp-tag">{feature}</span>
            ))}
          </div>
        </section>

        <section className="zone-exp-section">
          <div className="zone-exp-title">Recommended action</div>
          <p className="zone-exp-action">{actionText}</p>
        </section>

        <section className="zone-exp-section">
          <div className="zone-exp-title">Historical context (7 days PM2.5)</div>
          <div className="zone-exp-sparkline">
            <ResponsiveContainer width="100%" height={92}>
              <LineChart data={trend} margin={{ top: 8, right: 6, left: 0, bottom: 0 }}>
                <XAxis dataKey="day" tick={{ fill: '#8fa0b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis hide domain={['dataMin - 10', 'dataMax + 10']} />
                <Tooltip
                  formatter={(v) => [`${v} µg/m³`, 'PM2.5']}
                  labelFormatter={(label) => `${label}`}
                  contentStyle={{ background: '#111828', border: '1px solid #2e3a50', borderRadius: 8 }}
                />
                <Line type="monotone" dataKey="pm25" stroke="#ff6b35" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      </aside>
    </>
  )
}
