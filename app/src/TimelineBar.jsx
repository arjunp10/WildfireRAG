import { useState, useEffect } from 'react'
import { idxToLabel, parseMonthInput } from './utils.js'

const MIN_IDX = 0
const MAX_IDX = 323

const C = {
  bg:      '#f6f8fa',
  border:  '#d0d7de',
  text1:   '#1f2328',
  text2:   '#636c76',
  text3:   '#6e7781',
  fire:    '#bc4c00',
}

const font = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'

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

  const btn = (active, danger) => ({
    height: 28, borderRadius: 6, cursor: 'pointer', fontFamily: font,
    fontSize: 12, fontWeight: 500,
    border: `1px solid ${danger && active ? '#fca5a5' : C.border}`,
    background: danger && active ? '#fff5f5' : active ? '#ffffff' : '#ffffff',
    color: danger && active ? '#d1242f' : C.text2,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'all 0.1s',
    padding: '0 10px',
  })

  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 260, right: 0,
      height: 48,
      background: C.bg,
      borderTop: `1px solid ${C.border}`,
      display: 'flex', alignItems: 'center',
      padding: '0 16px', gap: 10,
      fontFamily: font,
      zIndex: 1000,
    }}>

      {/* Play / Pause */}
      <button
        onClick={() => setPlaying(p => !p)}
        title={playing ? 'Pause' : 'Play timeline'}
        style={{ ...btn(playing, true), width: 28, padding: 0, flexShrink: 0 }}
      >
        {playing ? '⏸' : '▶'}
      </button>

      {/* Date input */}
      <input
        value={inputVal}
        onChange={e => handleInput(e.target.value)}
        onBlur={() => { if (inputErr) { setInputErr(false); setInputVal(idxToLabel(monthIdx)) } }}
        placeholder="MM/YYYY"
        style={{
          width: 72, height: 28, padding: '0 8px',
          background: inputErr ? '#fff5f5' : '#ffffff',
          border: `1px solid ${inputErr ? '#fca5a5' : C.border}`,
          borderRadius: 6, flexShrink: 0,
          color: inputErr ? '#d1242f' : C.text1,
          fontSize: 12, fontWeight: 500,
          outline: 'none', fontFamily: font,
          textAlign: 'center',
        }}
      />

      {/* Slider */}
      <span style={{ fontSize: 11, color: C.text3, whiteSpace: 'nowrap', flexShrink: 0 }}>Jan 2000</span>
      <input
        type="range" min={MIN_IDX} max={MAX_IDX} value={monthIdx}
        onChange={e => { setPlaying(false); setInputErr(false); setMonthIdx(Number(e.target.value)) }}
        style={{ flex: 1, accentColor: C.fire, cursor: 'pointer', height: 4 }}
      />
      <span style={{ fontSize: 11, color: C.text3, whiteSpace: 'nowrap', flexShrink: 0 }}>Dec 2026</span>

      {/* Divider */}
      <div style={{ width: 1, height: 18, background: C.border, flexShrink: 0 }} />

      {/* Ask AI */}
      <button onClick={onChatToggle} style={{ ...btn(chatOpen, false), flexShrink: 0, whiteSpace: 'nowrap' }}>
        Ask AI
      </button>
    </div>
  )
}
