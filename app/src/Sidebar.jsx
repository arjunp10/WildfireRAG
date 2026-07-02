import { useState, useEffect } from 'react'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function Label({ children }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 700, letterSpacing: 1.2, textTransform: 'uppercase',
      color: '#334155', marginBottom: 8,
    }}>
      {children}
    </div>
  )
}

function StatCard({ value, label, color }) {
  return (
    <div style={{
      flex: 1, padding: '8px 10px',
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 8,
    }}>
      <div style={{ fontSize: 20, fontWeight: 700, color, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: '#334155', marginTop: 3 }}>{label}</div>
    </div>
  )
}

function LegendRow({ color, shape, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#475569' }}>
      <div style={{
        width: shape === 'rect' ? 14 : 8,
        height: 8,
        borderRadius: shape === 'dot' ? '50%' : 2,
        background: shape === 'dot' ? color : 'transparent',
        border: shape === 'rect' ? `1px solid ${color}` : 'none',
        flexShrink: 0,
        opacity: shape === 'rect' ? 0.75 : 1,
      }} />
      <span>{label}</span>
    </div>
  )
}

const WEATHER_VARS = [
  { val: 'fosberg_index',  label: 'Fosberg Index' },
  { val: 'temp_f',         label: 'Temperature' },
  { val: 'humidity_pct',   label: 'Humidity' },
  { val: 'wind_speed_mph', label: 'Wind Speed' },
]

export default function Sidebar({ confidenceFilter, setConfidenceFilter, weatherOn, setWeatherOn, weatherVar, setWeatherVar, riskOn, setRiskOn }) {
  const [stats, setStats] = useState(null)
  const [articles, setArticles] = useState([])
  const [newsLoading, setNewsLoading] = useState(true)

  useEffect(() => {
    fetch('http://localhost:8000/stats').then(r => r.json()).then(setStats).catch(() => {})
    fetch('http://localhost:8000/news')
      .then(r => r.json())
      .then(setArticles)
      .catch(() => {})
      .finally(() => setNewsLoading(false))
  }, [])

  const FILTERS = [
    { val: 'all', label: 'All' },
    { val: 'h',   label: 'High' },
    { val: 'n',   label: 'Nominal' },
  ]

  return (
    <div style={{
      position: 'fixed', left: 0, top: 0,
      width: 280, height: '100vh',
      background: 'rgba(8,10,18,0.97)',
      backdropFilter: 'blur(20px)',
      borderRight: '1px solid rgba(255,255,255,0.07)',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      color: '#e2e8f0',
      zIndex: 1000,
      userSelect: 'none',
    }}>

      {/* Branding */}
      <div style={{ padding: '20px 20px 18px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 9,
            background: 'linear-gradient(135deg, #ef4444 0%, #f97316 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, flexShrink: 0,
            boxShadow: '0 2px 8px rgba(239,68,68,0.35)',
          }}>🔥</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: -0.3, lineHeight: 1 }}>
              FireRAG
            </div>
            <div style={{ fontSize: 10, color: '#334155', marginTop: 2, letterSpacing: 0.2 }}>
              Wildfire Intelligence
            </div>
          </div>
        </div>
      </div>

      {/* Live stats */}
      {stats && stats.total_fires > 0 && (
        <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
          <Label>Live Status</Label>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <StatCard value={stats.total_fires.toLocaleString()} label="Active detections" color="#ef4444" />
            <StatCard value={stats.high_confidence.toLocaleString()} label="High confidence" color="#f97316" />
          </div>
          {stats.last_date && (
            <div style={{ fontSize: 11, color: '#334155' }}>
              Last updated: <span style={{ color: '#475569' }}>{stats.last_date}</span>
            </div>
          )}
        </div>
      )}

      {/* Confidence filter */}
      <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <Label>Filter Active Fires</Label>
        <div style={{ display: 'flex', gap: 5 }}>
          {FILTERS.map(({ val, label }) => {
            const active = confidenceFilter === val
            return (
              <button
                key={val}
                onClick={() => setConfidenceFilter(val)}
                style={{
                  flex: 1, padding: '6px 0', borderRadius: 7,
                  fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  border: `1px solid ${active ? 'rgba(239,68,68,0.45)' : 'rgba(255,255,255,0.07)'}`,
                  background: active ? 'rgba(239,68,68,0.18)' : 'rgba(255,255,255,0.04)',
                  color: active ? '#fca5a5' : '#475569',
                  transition: 'all 0.15s',
                }}
              >
                {label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Risk forecast overlay */}
      <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div>
            <Label>Risk Forecast</Label>
          </div>
          <button
            onClick={() => setRiskOn(v => !v)}
            style={{
              padding: '3px 10px', borderRadius: 5, fontSize: 10, fontWeight: 700,
              cursor: 'pointer', marginTop: -8,
              border: `1px solid ${riskOn ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.07)'}`,
              background: riskOn ? 'rgba(239,68,68,0.18)' : 'rgba(255,255,255,0.04)',
              color: riskOn ? '#fca5a5' : '#475569',
              transition: 'all 0.15s',
            }}
          >
            {riskOn ? 'ON' : 'OFF'}
          </button>
        </div>
        <div style={{ fontSize: 10, color: '#334155', lineHeight: 1.5 }}>
          Where fires are most likely this month — based on current fire weather + 26 years of ignition history.
        </div>
        {riskOn && (
          <div style={{ marginTop: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 3, marginBottom: 3 }}>
              {['#22c55e','#84cc16','#eab308','#f97316','#ef4444','#b91c1c'].map((c, i) => (
                <div key={i} style={{ flex: 1, height: 5, borderRadius: 2, background: c, opacity: 0.85 }} />
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 9, color: '#334155' }}>Low</span>
              <span style={{ fontSize: 9, color: '#334155' }}>High</span>
            </div>
          </div>
        )}
      </div>

      {/* Weather heatmap controls */}
      <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <Label>Weather Heatmap</Label>
          <button
            onClick={() => setWeatherOn(v => !v)}
            style={{
              padding: '3px 10px', borderRadius: 5, fontSize: 10, fontWeight: 700,
              cursor: 'pointer', marginTop: -8,
              border: `1px solid ${weatherOn ? 'rgba(99,102,241,0.5)' : 'rgba(255,255,255,0.07)'}`,
              background: weatherOn ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
              color: weatherOn ? '#a5b4fc' : '#475569',
              transition: 'all 0.15s',
            }}
          >
            {weatherOn ? 'ON' : 'OFF'}
          </button>
        </div>
        {weatherOn && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {WEATHER_VARS.map(({ val, label }) => {
              const active = weatherVar === val
              return (
                <button
                  key={val}
                  onClick={() => setWeatherVar(val)}
                  style={{
                    padding: '5px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                    cursor: 'pointer', textAlign: 'left',
                    border: `1px solid ${active ? 'rgba(99,102,241,0.45)' : 'rgba(255,255,255,0.06)'}`,
                    background: active ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.03)',
                    color: active ? '#c7d2fe' : '#475569',
                    transition: 'all 0.15s',
                    display: 'flex', alignItems: 'center', gap: 7,
                  }}
                >
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                    background: active ? '#818cf8' : '#1e293b',
                  }} />
                  {label}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* News feed */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '14px 20px 6px', flexShrink: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Label>Live News</Label>
          {articles.length > 0 && (
            <span style={{ fontSize: 10, color: '#1e293b', marginTop: -8 }}>{articles.length} articles</span>
          )}
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
          {newsLoading && [0,1,2,3].map(i => (
            <div key={i} style={{ padding: '10px 12px', marginBottom: 2 }}>
              <div style={{ height: 9, width: '38%', background: 'rgba(255,255,255,0.05)', borderRadius: 3, marginBottom: 8 }} />
              <div style={{ height: 12, background: 'rgba(255,255,255,0.05)', borderRadius: 3, marginBottom: 4 }} />
              <div style={{ height: 12, width: '65%', background: 'rgba(255,255,255,0.05)', borderRadius: 3 }} />
            </div>
          ))}

          {!newsLoading && articles.length === 0 && (
            <div style={{ padding: '20px 12px', color: '#1e293b', fontSize: 12, textAlign: 'center' }}>
              No articles yet.
            </div>
          )}

          {articles.map((a, i) => (
            <div
              key={i}
              onClick={() => /^https?:\/\//.test(a.url) && window.open(a.url, '_blank', 'noopener,noreferrer')}
              style={{
                padding: '9px 12px', borderRadius: 8, cursor: 'pointer',
                marginBottom: 1, transition: 'background 0.12s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <div style={{ display: 'flex', gap: 6, marginBottom: 4, alignItems: 'center' }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, color: '#334155',
                  background: 'rgba(255,255,255,0.05)',
                  borderRadius: 3, padding: '2px 5px',
                  textTransform: 'uppercase', letterSpacing: 0.4,
                  whiteSpace: 'nowrap', maxWidth: 100,
                  overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {a.source || 'Unknown'}
                </span>
                <span style={{ fontSize: 10, color: '#1e293b' }}>{timeAgo(a.published_at)}</span>
              </div>
              <div style={{
                fontSize: 12, fontWeight: 600, lineHeight: 1.45, color: '#94a3b8',
                overflow: 'hidden', display: '-webkit-box',
                WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
              }}>
                {a.title}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div style={{
        padding: '12px 20px 16px',
        borderTop: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', flexDirection: 'column', gap: 5, flexShrink: 0,
      }}>
        <Label>Legend</Label>
        <LegendRow color="#22c55e" shape="dot" label="Active — low risk" />
        <LegendRow color="#eab308" shape="dot" label="Active — medium risk" />
        <LegendRow color="#ef4444" shape="dot" label="Active — high risk" />
        <LegendRow color="#f97316" shape="dot" label="Confirmed (historical)" />
        <LegendRow color="#f97316" shape="rect" label="Perimeter ≥ 50k acres" />
      </div>
    </div>
  )
}
