import { useState, useEffect } from 'react'
import { idxToLabel, parseMonthInput } from './utils.js'

const MIN_IDX = 0
const MAX_IDX = 323

export default function TimelineBar({ monthIdx, setMonthIdx, playing, setPlaying, onChatToggle, chatOpen }) {
  const [inputVal, setInputVal] = useState(idxToLabel(monthIdx))
  const [inputErr, setInputErr] = useState(false)

  useEffect(() => {
    if (!inputErr) setInputVal(idxToLabel(monthIdx))
  }, [monthIdx, inputErr])

  const handleInput = (val) => {
    setInputVal(val)
    const idx = parseMonthInput(val)
    if (idx !== null) {
      setInputErr(false)
      setPlaying(false)
      setMonthIdx(idx)
    } else {
      setInputErr(val.length > 0)
    }
  }

  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 280, right: 0,
      height: 54,
      background: 'rgba(8,10,18,0.97)',
      backdropFilter: 'blur(20px)',
      borderTop: '1px solid rgba(255,255,255,0.07)',
      display: 'flex', alignItems: 'center',
      padding: '0 20px', gap: 14,
      fontFamily: 'system-ui, -apple-system, sans-serif',
      zIndex: 1000,
    }}>

      {/* Play / Pause */}
      <button
        onClick={() => setPlaying(p => !p)}
        title={playing ? 'Pause' : 'Play timeline'}
        style={{
          width: 30, height: 30, borderRadius: 7, flexShrink: 0,
          background: playing ? 'rgba(239,68,68,0.25)' : 'rgba(255,255,255,0.06)',
          border: `1px solid ${playing ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.1)'}`,
          color: playing ? '#fca5a5' : '#64748b',
          cursor: 'pointer', fontSize: 11,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {playing ? '⏸' : '▶'}
      </button>

      {/* Date input */}
      <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 0 }}>
        <input
          value={inputVal}
          onChange={e => handleInput(e.target.value)}
          onBlur={() => { if (inputErr) { setInputErr(false); setInputVal(idxToLabel(monthIdx)) } }}
          placeholder="MM/YYYY"
          style={{
            width: 78, padding: '4px 8px',
            background: inputErr ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.05)',
            border: `1px solid ${inputErr ? 'rgba(239,68,68,0.45)' : 'rgba(255,255,255,0.1)'}`,
            borderRadius: 6,
            color: inputErr ? '#fca5a5' : '#e2e8f0',
            fontSize: 13, fontWeight: 600,
            outline: 'none', fontFamily: 'inherit',
            textAlign: 'center',
          }}
        />
      </div>

      {/* Slider section */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 10, color: '#1e293b', whiteSpace: 'nowrap', flexShrink: 0 }}>
          Jan 2000
        </span>
        <input
          type="range"
          min={MIN_IDX}
          max={MAX_IDX}
          value={monthIdx}
          onChange={e => {
            setPlaying(false)
            setInputErr(false)
            setMonthIdx(Number(e.target.value))
          }}
          style={{ flex: 1, accentColor: '#ef4444', cursor: 'pointer', height: 4 }}
        />
        <span style={{ fontSize: 10, color: '#1e293b', whiteSpace: 'nowrap', flexShrink: 0 }}>
          Dec 2026
        </span>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 22, background: 'rgba(255,255,255,0.07)', flexShrink: 0 }} />

      {/* Ask AI button */}
      <button
        onClick={onChatToggle}
        style={{
          height: 30, padding: '0 14px', borderRadius: 7, flexShrink: 0,
          background: chatOpen ? 'rgba(239,68,68,0.25)' : 'rgba(255,255,255,0.06)',
          border: `1px solid ${chatOpen ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.1)'}`,
          color: chatOpen ? '#fca5a5' : '#64748b',
          fontSize: 12, fontWeight: 600,
          cursor: 'pointer', fontFamily: 'inherit',
          display: 'flex', alignItems: 'center', gap: 6,
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{ fontSize: 13 }}>💬</span>
        {chatOpen ? 'Close' : 'Ask AI'}
      </button>
    </div>
  )
}
