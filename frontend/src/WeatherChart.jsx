// Mini-graphique : pluie journalière (barres) + température air / sol (lignes)
// J-14 … J+3, fenêtre principale J-7 … J-1 surlignée.
export default function WeatherChart({ days, today }) {
  if (!days?.length) return null
  const W = 300, H = 130, top = 10, bottom = 22, left = 26, right = 26
  const ih = H - top - bottom
  const n = days.length
  const bw = (W - left - right) / n
  const iToday = days.findIndex((d) => d.date === today)
  const maxRain = Math.max(10, ...days.map((d) => d.rain || 0))
  const temps = days.flatMap((d) => [d.tmean, d.soil_t]).filter((v) => v != null)
  const tMin = Math.min(0, Math.floor(Math.min(...temps) / 5) * 5)
  const tMax = Math.max(20, Math.ceil(Math.max(...temps) / 5) * 5)
  const x = (i) => left + i * bw + bw / 2
  const yRain = (v) => top + ih - (v / maxRain) * ih
  const yT = (v) => top + ih - ((v - tMin) / (tMax - tMin)) * ih
  const line = (key) => days.map((d, i) => (d[key] == null ? null : `${x(i)},${yT(d[key])}`))
    .filter(Boolean).join(' ')

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img"
         aria-label="Pluie et température sur 14 jours et 3 jours de prévision">
      {iToday >= 7 && (
        <rect x={left + (iToday - 7) * bw} y={top} width={7 * bw} height={ih} className="chart-window" />
      )}
      {iToday >= 0 && (
        <rect x={left + iToday * bw} y={top} width={(n - iToday) * bw} height={ih} className="chart-forecast" />
      )}
      {days.map((d, i) => (
        <rect key={d.date} x={left + i * bw + 1} width={Math.max(1, bw - 2)}
              y={yRain(d.rain || 0)} height={top + ih - yRain(d.rain || 0)}
              className={i >= iToday && iToday >= 0 ? 'bar bar-fc' : 'bar'}>
          <title>{`${d.date} : ${d.rain ?? '–'} mm, air ${d.tmean ?? '–'} °C, sol ${d.soil_t ?? '–'} °C`}</title>
        </rect>
      ))}
      <polyline points={line('tmean')} className="line-air" />
      <polyline points={line('soil_t')} className="line-soil" />
      <line x1={left} x2={W - right} y1={top + ih} y2={top + ih} className="axis" />
      <text x={left - 4} y={top + 4} className="tick" textAnchor="end">{Math.round(maxRain)}</text>
      <text x={left - 4} y={top + ih} className="tick" textAnchor="end">0</text>
      <text x={left - 4} y={H - 4} className="tick" textAnchor="end">mm</text>
      <text x={W - right + 4} y={top + 4} className="tick">{tMax}°</text>
      <text x={W - right + 4} y={top + ih} className="tick">{tMin}°</text>
      {[0, 7, iToday, n - 1].filter((i) => i >= 0).map((i) => (
        <text key={i} x={x(i)} y={H - 6} className="tick" textAnchor="middle">
          {i === iToday ? 'auj.' : i < iToday ? `J-${iToday - i}` : `J+${i - iToday}`}
        </text>
      ))}
    </svg>
  )
}
