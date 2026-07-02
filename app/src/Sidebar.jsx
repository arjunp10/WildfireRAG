import { useState, useEffect } from 'react'

// GitHub design tokens
const C = {
  bg:        '#ffffff',
  bgSubtle:  '#f6f8fa',
  bgHover:   '#f3f4f6',
  border:    '#d0d7de',
  borderMuted: '#d8dee4',
  text1:     '#1f2328',
  text2:     '#636c76',
  text3:     '#6e7781',
  fire:      '#bc4c00',   // GitHub "severe" — perfect for fire
  fireSubtle:'#fff1e5',
  blue:      '#0969da',
  blueSubtle:'#ddf4ff',
  amber:     '#9a6700',
  amberSubtle:'#fdf7e5',
}


function Divider() {
  return <div style={{ height: 1, background: C.border }} />
}

function SectionHeader({ children }) {
  return (
    <div style={{
      fontSize: 12, fontWeight: 600, color: C.text2,
      marginBottom: 8,
    }}>
      {children}
    </div>
  )
}

// GitHub-style pill toggle
function Toggle({ active, onToggle, color }) {
  const bg = active ? (color || C.fire) : C.border
  return (
    <button
      onClick={onToggle}
      aria-checked={active}
      role="switch"
      style={{
        position: 'relative', width: 28, height: 16,
        borderRadius: 8, border: 'none', padding: 0,
        background: bg, cursor: 'pointer', flexShrink: 0,
        transition: 'background 0.15s',
      }}
    >
      <div style={{
        position: 'absolute',
        top: 2, left: active ? 12 : 2,
        width: 12, height: 12, borderRadius: '50%',
        background: '#ffffff',
        boxShadow: '0 1px 2px rgba(31,35,40,0.2)',
        transition: 'left 0.15s',
      }} />
    </button>
  )
}

// One layer row: label + toggle, optional children when active
function LayerRow({ label, active, onToggle, color, children }) {
  return (
    <div>
      <div
        style={{
          display: 'flex', alignItems: 'center',
          justifyContent: 'space-between',
          padding: '5px 0', borderRadius: 6,
        }}
      >
        <span style={{
          fontSize: 13, color: active ? C.text1 : C.text3,
          fontWeight: active ? 500 : 400,
          transition: 'color 0.12s',
        }}>
          {label}
        </span>
        <Toggle active={active} onToggle={onToggle} color={color} />
      </div>
      {active && children && (
        <div style={{ paddingBottom: 6 }}>{children}</div>
      )}
    </div>
  )
}

// Small segmented button group (confidence filter)
function SegGroup({ options, value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 0, marginTop: 4 }}>
      {options.map(({ val, label }, i) => {
        const sel = value === val
        return (
          <button
            key={val}
            onClick={() => onChange(val)}
            style={{
              flex: 1, padding: '3px 0', fontSize: 11,
              fontWeight: sel ? 600 : 400,
              cursor: 'pointer', lineHeight: '20px',
              background: sel ? C.text1 : C.bg,
              color: sel ? '#ffffff' : C.text2,
              border: `1px solid ${C.border}`,
              borderLeft: i > 0 ? 'none' : `1px solid ${C.border}`,
              borderRadius: i === 0 ? '6px 0 0 6px' : i === options.length - 1 ? '0 6px 6px 0' : '0',
              transition: 'all 0.1s',
            }}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

// Small radio-style option rows (weather variables)
function RadioList({ options, value, onChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', marginTop: 4 }}>
      {options.map(({ val, label }) => {
        const sel = value === val
        return (
          <button
            key={val}
            onClick={() => onChange(val)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '4px 6px', borderRadius: 6,
              border: 'none', background: sel ? C.bgSubtle : 'transparent',
              cursor: 'pointer', textAlign: 'left', fontSize: 12,
              color: sel ? C.text1 : C.text2,
              fontWeight: sel ? 500 : 400,
            }}
          >
            <div style={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              border: sel ? `2.5px solid ${C.blue}` : `1.5px solid ${C.border}`,
              background: sel ? C.blue : 'transparent',
              transition: 'all 0.1s',
            }} />
            {label}
          </button>
        )
      })}
    </div>
  )
}

// Tiny color ramp
function Ramp({ stops }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', gap: 1, borderRadius: 3, overflow: 'hidden' }}>
        {stops.map((c, i) => (
          <div key={i} style={{ flex: 1, height: 4, background: c }} />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
        <span style={{ fontSize: 10, color: C.text3 }}>Low</span>
        <span style={{ fontSize: 10, color: C.text3 }}>High</span>
      </div>
    </div>
  )
}

const CONFIDENCE_OPTS = [
  { val: 'all', label: 'All' },
  { val: 'h',   label: 'High' },
  { val: 'n',   label: 'Nominal' },
]

const WEATHER_VARS = [
  { val: 'fosberg_index',  label: 'Fosberg FWI' },
  { val: 'temp_f',         label: 'Temperature' },
  { val: 'humidity_pct',   label: 'Humidity' },
  { val: 'wind_speed_mph', label: 'Wind Speed' },
]

export default function Sidebar({
  firmsOn, setFirmsOn,
  confidenceFilter, setConfidenceFilter,
  weatherOn, setWeatherOn, weatherVar, setWeatherVar,
  spreadOn, setSpreadOn,
  riskOn, setRiskOn,
  historicalDotsOn, setHistoricalDotsOn,
  perimeterOn, setPerimeterOn,
}) {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetch('http://localhost:8000/stats').then(r => r.json()).then(setStats).catch(() => {})
  }, [])

  const font = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'

  return (
    <div style={{
      position: 'fixed', left: 0, top: 0,
      width: 260, height: '100vh',
      background: C.bg,
      borderRight: `1px solid ${C.border}`,
      display: 'flex', flexDirection: 'column',
      fontFamily: font,
      color: C.text1,
      zIndex: 1000,
      userSelect: 'none',
    }}>

      {/* Branding */}
      <div style={{ padding: '16px 16px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18, lineHeight: 1 }}>🔥</span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: C.text1, lineHeight: 1.2 }}>
              FireRAG
            </div>
            <div style={{ fontSize: 11, color: C.text3, marginTop: 1 }}>
              Wildfire Intelligence
            </div>
          </div>
        </div>
      </div>

      <Divider />

      {/* Stats */}
      {stats && stats.total_fires > 0 && (
        <>
          <div style={{ padding: '10px 16px' }}>
            <div style={{ fontSize: 12, color: C.text2 }}>
              <span style={{ fontWeight: 600, color: C.fire }}>
                {stats.total_fires.toLocaleString()}
              </span>
              {' '}active detections
              {stats.last_date && (
                <span style={{ color: C.text3 }}> · {stats.last_date}</span>
              )}
            </div>
            {stats.high_confidence > 0 && (
              <div style={{ fontSize: 11, color: C.text3, marginTop: 2 }}>
                {stats.high_confidence.toLocaleString()} high-confidence
              </div>
            )}
          </div>
          <Divider />
        </>
      )}

      {/* Scrollable layer controls + news */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>

        {/* Present */}
        <div style={{ padding: '12px 16px' }}>
          <SectionHeader>Present</SectionHeader>

          <LayerRow label="Active Fires" active={firmsOn} onToggle={() => setFirmsOn(v => !v)} color={C.fire}>
            <SegGroup options={CONFIDENCE_OPTS} value={confidenceFilter} onChange={setConfidenceFilter} />
          </LayerRow>

          <LayerRow label="Weather Conditions" active={weatherOn} onToggle={() => setWeatherOn(v => !v)} color={C.blue}>
            <RadioList options={WEATHER_VARS} value={weatherVar} onChange={setWeatherVar} />
            <Ramp stops={['#60a5fa','#a3e635','#fbbf24','#f97316','#dc2626']} />
          </LayerRow>

          <LayerRow label="Spread Zones" active={spreadOn} onToggle={() => setSpreadOn(v => !v)} color="#cf222e">
            <p style={{ fontSize: 11, color: C.text3, margin: '4px 0 0', lineHeight: 1.5 }}>
              24h spread projection for active clusters.
            </p>
          </LayerRow>
        </div>

        <Divider />

        {/* Forecast */}
        <div style={{ padding: '12px 16px' }}>
          <SectionHeader>7-Day Forecast</SectionHeader>
          <LayerRow label="Risk Index" active={riskOn} onToggle={() => setRiskOn(v => !v)} color={C.amber}>
            <Ramp stops={['#22c55e','#84cc16','#eab308','#f97316','#ef4444','#b91c1c']} />
            <p style={{ fontSize: 11, color: C.text3, margin: '6px 0 0', lineHeight: 1.5 }}>
              Peak 7-day FWI × 26-year ignition history.
            </p>
          </LayerRow>
        </div>

        <Divider />

        {/* Historical */}
        <div style={{ padding: '12px 16px' }}>
          <SectionHeader>Historical · 2000–2026</SectionHeader>
          <LayerRow label="Fire Locations" active={historicalDotsOn} onToggle={() => setHistoricalDotsOn(v => !v)} color={C.fire} />
          <LayerRow label="Perimeters" active={perimeterOn} onToggle={() => setPerimeterOn(v => !v)} color={C.fire} />
        </div>

        <div style={{ height: 16 }} />

      </div>
    </div>
  )
}
