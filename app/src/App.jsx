import { useState, useEffect, useRef } from 'react'
import GlobeMap from './GlobeMap.jsx'
import Sidebar from './Sidebar.jsx'
import TimelineBar from './TimelineBar.jsx'
import ChatBox from './ChatBox.jsx'

const MIN_IDX = 0
const MAX_IDX = 323

const token = import.meta.env.VITE_MAPBOX_TOKEN

export default function App() {
  const [monthIdx, setMonthIdx] = useState(240)
  const [playing, setPlaying] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const playRef = useRef(false)

  // Present layers
  const [firmsOn, setFirmsOn] = useState(true)
  const [confidenceFilter, setConfidenceFilter] = useState('all')
  const [weatherOn, setWeatherOn] = useState(false)
  const [weatherVar, setWeatherVar] = useState('fosberg_index')

  // Forecast layer
  const [riskOn, setRiskOn] = useState(false)

  // Present overlay
  const [spreadOn, setSpreadOn] = useState(false)

  // Historical layers
  const [historicalDotsOn, setHistoricalDotsOn] = useState(true)
  const [perimeterOn, setPerimeterOn] = useState(true)

  useEffect(() => {
    playRef.current = playing
    if (!playing) return
    const tick = () => {
      if (!playRef.current) return
      setMonthIdx(i => (i >= MAX_IDX ? MIN_IDX : i + 1))
      setTimeout(tick, 150)
    }
    const t = setTimeout(tick, 150)
    return () => clearTimeout(t)
  }, [playing])

  if (!token) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', fontFamily: 'system-ui', color: '#ef4444', fontSize: 15,
        background: '#080a12',
      }}>
        Missing VITE_MAPBOX_TOKEN — add it to app/.env
      </div>
    )
  }

  return (
    <>
      <GlobeMap
        mapboxToken={token}
        monthIdx={monthIdx}
        confidenceFilter={confidenceFilter}
        firmsOn={firmsOn}
        weatherOn={weatherOn}
        weatherVar={weatherVar}
        riskOn={riskOn}
        spreadOn={spreadOn}
        historicalDotsOn={historicalDotsOn}
        perimeterOn={perimeterOn}
      />
      <Sidebar
        firmsOn={firmsOn}
        setFirmsOn={setFirmsOn}
        confidenceFilter={confidenceFilter}
        setConfidenceFilter={setConfidenceFilter}
        weatherOn={weatherOn}
        setWeatherOn={setWeatherOn}
        weatherVar={weatherVar}
        setWeatherVar={setWeatherVar}
        riskOn={riskOn}
        setRiskOn={setRiskOn}
        spreadOn={spreadOn}
        setSpreadOn={setSpreadOn}
        historicalDotsOn={historicalDotsOn}
        setHistoricalDotsOn={setHistoricalDotsOn}
        perimeterOn={perimeterOn}
        setPerimeterOn={setPerimeterOn}
      />
      <TimelineBar
        monthIdx={monthIdx}
        setMonthIdx={setMonthIdx}
        playing={playing}
        setPlaying={setPlaying}
        chatOpen={chatOpen}
        onChatToggle={() => setChatOpen(o => !o)}
      />
      {chatOpen && <ChatBox onClose={() => setChatOpen(false)} />}
    </>
  )
}
