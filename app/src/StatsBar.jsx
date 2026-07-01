import { useState, useEffect } from 'react'

export default function StatsBar() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetch('http://localhost:8000/stats')
      .then(r => r.json())
      .then(setStats)
      .catch(() => {})
  }, [])

  if (!stats || stats.total_fires === 0) return null

  return (
    <div style={{
      position: 'fixed', top: 0, left: 300, right: 0,
      height: 36, zIndex: 900,
      background: 'rgba(15,15,25,0.80)',
      backdropFilter: 'blur(8px)',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      display: 'flex', alignItems: 'center',
      gap: 24, paddingLeft: 20, paddingRight: 20,
      fontFamily: 'system-ui', fontSize: 12, color: '#e2e8f0',
    }}>
      <span>
        🔥 <strong style={{ color: '#ef4444' }}>{stats.total_fires.toLocaleString()}</strong> active detections
      </span>
      <span style={{ color: 'rgba(255,255,255,0.3)' }}>|</span>
      <span>
        <strong style={{ color: '#f97316' }}>{stats.high_confidence.toLocaleString()}</strong> high-confidence
      </span>
      {stats.last_date && (
        <>
          <span style={{ color: 'rgba(255,255,255,0.3)' }}>|</span>
          <span style={{ color: '#94a3b8' }}>Last detection: {stats.last_date}</span>
        </>
      )}
    </div>
  )
}
