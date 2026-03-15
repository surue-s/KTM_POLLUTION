import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts'

const WHO_GUIDELINE = 15 // µg/m³ PM2.5 daily mean guideline

function buildChartData(forecast) {
  if (!forecast) return []
  const current = forecast.current_pm25 ?? forecast.forecasts?.current ?? null
  const np = forecast.next_pm25 ?? forecast.forecasts ?? {}
  const points = [
    { hour: 0,  label: 'Now',  pm25: current },
    { hour: 1,  label: '+1h',  pm25: np['1']  ?? np[1]  ?? null },
    { hour: 6,  label: '+6h',  pm25: np['6']  ?? np[6]  ?? null },
    { hour: 12, label: '+12h', pm25: np['12'] ?? np[12] ?? null },
    { hour: 24, label: '+24h', pm25: np['24'] ?? np[24] ?? null },
    { hour: 48, label: '+48h', pm25: np['48'] ?? np[48] ?? null },
  ].filter(p => p.pm25 != null)
    .map(p => ({ ...p, pm25: Math.round(p.pm25 * 10) / 10 }))
  return points
}

function areaColor(pm25) {
  if (pm25 < 15)  return '#00cc66'
  if (pm25 < 35)  return '#ffcc00'
  if (pm25 < 75)  return '#ff7e00'
  if (pm25 < 150) return '#ff4444'
  return '#7e0023'
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const { label, pm25 } = payload[0].payload
  return (
    <div className="forecast-tooltip">
      <span className="tt-label">{label}</span>
      <span className="tt-value">{pm25} µg/m³</span>
    </div>
  )
}

export default function ForecastChart({ forecast, stationId }) {
  const data = buildChartData(forecast)
  if (!data.length) {
    return (
      <div className="forecast-empty">
        <span>No forecast data</span>
        {stationId && <span className="forecast-id">{stationId}</span>}
      </div>
    )
  }

  const maxVal = Math.max(...data.map(d => d.pm25), WHO_GUIDELINE, 50)
  const yMax = Math.ceil(maxVal * 1.15 / 25) * 25 // round up to nearest 25

  const trend = forecast?.trend ?? 'stable'
  const trendColor = trend === 'improving' ? '#00cc66' : trend === 'worsening' ? '#ff4444' : '#a0a0a0'
  const trendArrow = trend === 'improving' ? '↓' : trend === 'worsening' ? '↑' : '→'

  const strokeColor = data.length ? areaColor(data[data.length - 1].pm25) : '#ff6b35'

  return (
    <div className="forecast-chart-wrap">
      <div className="forecast-header">
        <span className="forecast-title">48h PM2.5 Forecast</span>
        <span className="forecast-trend" style={{ color: trendColor }}>
          {trendArrow} {trend}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="pm25Grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={strokeColor} stopOpacity={0.35} />
              <stop offset="95%" stopColor={strokeColor} stopOpacity={0.05} />
            </linearGradient>
          </defs>

          {/* AQI background bands */}
          <ReferenceArea y1={0}   y2={Math.min(15,  yMax)} fill="#00e40008" />
          <ReferenceArea y1={15}  y2={Math.min(35,  yMax)} fill="#ffff0008" />
          <ReferenceArea y1={35}  y2={Math.min(75,  yMax)} fill="#ff7e0008" />
          <ReferenceArea y1={75}  y2={Math.min(150, yMax)} fill="#ff000010" />
          <ReferenceArea y1={150} y2={yMax}                fill="#8f3f9710" />

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#2a2a4a"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: '#666', fontSize: 10, fontFamily: 'var(--mono)' }}
            axisLine={{ stroke: '#2a2a4a' }}
            tickLine={false}
          />
          <YAxis
            domain={[0, yMax]}
            tick={{ fill: '#666', fontSize: 10, fontFamily: 'var(--mono)' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `${v}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            y={WHO_GUIDELINE}
            stroke="#4fc3f7"
            strokeDasharray="4 4"
            strokeWidth={1}
            label={{ value: 'WHO 15', position: 'right', fill: '#4fc3f7', fontSize: 9 }}
          />
          <Area
            type="monotone"
            dataKey="pm25"
            stroke={strokeColor}
            strokeWidth={1.5}
            fill="url(#pm25Grad)"
            dot={{ fill: strokeColor, r: 3, strokeWidth: 0 }}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
