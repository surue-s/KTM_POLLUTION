const AQI_BANDS = [
  { max: 50,  label: 'Good',           color: '#00e400', bg: '#00e40022' },
  { max: 100, label: 'Moderate',       color: '#ffff00', bg: '#ffff0022' },
  { max: 150, label: 'Unhealthy (SG)', color: '#ff7e00', bg: '#ff7e0022' },
  { max: 200, label: 'Unhealthy',      color: '#ff0000', bg: '#ff000022' },
  { max: 300, label: 'Very Unhealthy', color: '#8f3f97', bg: '#8f3f9722' },
  { max: Infinity, label: 'Hazardous', color: '#7e0023', bg: '#7e002322' },
]

export function aqiMeta(aqi) {
  return AQI_BANDS.find((band) => (aqi ?? 0) < band.max) ?? AQI_BANDS.at(-1)
}
