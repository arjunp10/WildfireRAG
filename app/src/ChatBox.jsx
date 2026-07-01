import { useState, useEffect, useRef } from 'react'

const WELCOME = "Ask me about wildfire patterns, history, or current conditions — e.g. 'Why is fire risk high in Northern California?' or 'What were the biggest fires in 2020?'"

export default function ChatBox({ onClose }) {
  const [messages, setMessages] = useState([{ role: 'assistant', content: WELCOME }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const send = async () => {
    const question = input.trim()
    if (!question || loading) return
    setInput('')
    setError(null)
    const next = [...messages, { role: 'user', content: question }]
    setMessages(next)
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, history: messages.slice(-6) }),
      })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      setMessages(m => [...m, { role: 'assistant', content: data.answer }])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', bottom: 62, right: 20,
      width: 360, height: 460,
      background: 'rgba(8,10,18,0.98)',
      backdropFilter: 'blur(20px)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 14,
      boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      fontSize: 13, color: '#e2e8f0',
      zIndex: 1100,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 22, height: 22, borderRadius: 6,
            background: 'linear-gradient(135deg, #ef4444, #f97316)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11,
          }}>🔥</div>
          <span style={{ fontWeight: 600, fontSize: 13 }}>FireRAG Assistant</span>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#334155', fontSize: 18, lineHeight: 1, padding: '2px 4px',
            display: 'flex', alignItems: 'center',
          }}
          title="Close"
        >×</button>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '12px',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            display: 'flex',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            <div style={{
              maxWidth: '85%', padding: '8px 12px',
              background: m.role === 'user'
                ? 'rgba(239,68,68,0.18)'
                : 'rgba(255,255,255,0.05)',
              border: m.role === 'user'
                ? '1px solid rgba(239,68,68,0.25)'
                : '1px solid rgba(255,255,255,0.06)',
              borderRadius: m.role === 'user' ? '12px 12px 3px 12px' : '12px 12px 12px 3px',
              lineHeight: 1.55, whiteSpace: 'pre-wrap',
              color: m.role === 'user' ? '#fecaca' : '#94a3b8',
              fontSize: 12.5,
            }}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{
              padding: '8px 14px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: '12px 12px 12px 3px',
              color: '#334155', letterSpacing: 3, fontSize: 11,
            }}>• • •</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 12px',
        borderTop: '1px solid rgba(255,255,255,0.07)',
        flexShrink: 0,
      }}>
        {error && (
          <div style={{ color: '#ef4444', fontSize: 11, marginBottom: 8, opacity: 0.8 }}>{error}</div>
        )}
        <div style={{ display: 'flex', gap: 8 }}>
          <textarea
            ref={inputRef}
            rows={2}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="Ask about fire patterns..."
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.09)',
              borderRadius: 8, color: '#e2e8f0',
              padding: '7px 10px', resize: 'none',
              fontFamily: 'inherit', fontSize: 12.5, outline: 'none',
              lineHeight: 1.5,
            }}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            style={{
              background: loading || !input.trim() ? 'rgba(239,68,68,0.2)' : '#ef4444',
              color: loading || !input.trim() ? '#7f1d1d' : 'white',
              border: 'none', borderRadius: 8,
              padding: '0 14px',
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              fontWeight: 600, fontSize: 12,
              alignSelf: 'stretch', transition: 'background 0.15s',
              fontFamily: 'inherit',
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
