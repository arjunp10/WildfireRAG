import GlobeMap from './GlobeMap.jsx'
import ChatBox from './ChatBox.jsx'
import NewsPanel from './NewsPanel.jsx'
import StatsBar from './StatsBar.jsx'

const token = import.meta.env.VITE_MAPBOX_TOKEN

export default function App() {
  if (!token) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', fontFamily: 'system-ui', color: '#ef4444',
        fontSize: '16px',
      }}>
        Missing VITE_MAPBOX_TOKEN — add it to app/.env
      </div>
    )
  }
  return (
    <>
      <GlobeMap mapboxToken={token} />
      <StatsBar />
      <NewsPanel />
      <ChatBox />
    </>
  )
}
