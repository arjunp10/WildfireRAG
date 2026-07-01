import { useState, useEffect, useCallback } from 'react'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function SkeletonCard() {
  return (
    <div style={{ padding: 12, marginBottom: 4 }}>
      <div style={{ height: 10, background: 'rgba(255,255,255,0.08)', borderRadius: 4, marginBottom: 8, width: '40%' }} />
      <div style={{ height: 13, background: 'rgba(255,255,255,0.08)', borderRadius: 4, marginBottom: 4 }} />
      <div style={{ height: 13, background: 'rgba(255,255,255,0.08)', borderRadius: 4, width: '75%' }} />
    </div>
  )
}

export default function NewsPanel() {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    fetch('http://localhost:8000/news')
      .then(r => {
        if (!r.ok) throw new Error(`Server error ${r.status}`)
        return r.json()
      })
      .then(data => setArticles(data))
      .catch(() => setError('Could not load news.'))
      .finally(() => setLoading(false))
  }, [])

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        style={{
          position: 'fixed', left: 0, top: '50%', transform: 'translateY(-50%)',
          zIndex: 1000,
          background: 'rgba(15,15,25,0.85)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderLeft: 'none',
          borderRadius: '0 8px 8px 0',
          color: '#e2e8f0', cursor: 'pointer',
          padding: '12px 6px',
          writingMode: 'vertical-rl',
          fontSize: 11, fontFamily: 'system-ui', fontWeight: 600,
          letterSpacing: 1,
        }}
      >
        📰 NEWS
      </button>
    )
  }

  return (
    <div style={{
      position: 'fixed', left: 0, top: 0,
      width: 300, height: '100vh',
      background: 'rgba(15,15,25,0.85)',
      backdropFilter: 'blur(12px)',
      borderRight: '1px solid rgba(255,255,255,0.1)',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'system-ui', color: '#e2e8f0',
      zIndex: 1000,
    }}>
      <div style={{
        padding: '16px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontWeight: 600, fontSize: 14,
      }}>
        <span>📰 Live News</span>
        <button
          onClick={() => setCollapsed(true)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#64748b', fontSize: 16, lineHeight: 1, padding: 2,
          }}
          title="Collapse"
        >
          ‹
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        {loading && Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}

        {error && (
          <div style={{ padding: 12, color: '#94a3b8', fontSize: 12 }}>{error}</div>
        )}

        {!loading && !error && articles.length === 0 && (
          <div style={{ padding: 12, color: '#94a3b8', fontSize: 12 }}>
            No articles yet. Run: python3 data/news.py
          </div>
        )}

        {articles.map((article, i) => (
          <div
            key={i}
            onClick={() => {
              if (/^https?:\/\//.test(article.url)) {
                window.open(article.url, '_blank', 'noopener,noreferrer')
              }
            }}
            style={{
              padding: 12, marginBottom: 4, borderRadius: 8,
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div style={{ marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                background: 'rgba(239,68,68,0.2)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 4, padding: '2px 6px',
                fontSize: 10, color: '#fca5a5',
                whiteSpace: 'nowrap', overflow: 'hidden',
                maxWidth: 120, textOverflow: 'ellipsis',
              }}>
                {article.source || 'Unknown'}
              </span>
              <span style={{ fontSize: 10, color: '#64748b' }}>
                {timeAgo(article.published_at)}
              </span>
            </div>
            <div style={{
              fontSize: 13, fontWeight: 600, lineHeight: 1.4,
              overflow: 'hidden', display: '-webkit-box',
              WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            }}>
              {article.title}
            </div>
            {article.description && (
              <div style={{
                fontSize: 11, color: '#94a3b8', marginTop: 4,
                overflow: 'hidden', display: '-webkit-box',
                WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
                lineHeight: 1.5,
              }}>
                {article.description}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
