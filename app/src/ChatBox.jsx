import { useState, useEffect, useRef } from 'react'

const WELCOME = "Ask me about wildfire patterns, history, or current conditions — e.g. 'Why is fire risk high in Northern California?' or 'What were the biggest fires in 2020?'"

const C = {
  bg:      '#ffffff',
  bgSubtle:'#f6f8fa',
  border:  '#d0d7de',
  text1:   '#1f2328',
  text2:   '#636c76',
  text3:   '#6e7781',
  fire:    '#bc4c00',
  fireSubtle: '#fff1e5',
  fireBorder: '#f6c9a9',
  blue:    '#0969da',
}

const font = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'

export default function ChatBox({ onClose }) {
  const [messages, setMessages] = useState([{ role: 'assistant', content: WELCOME }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])
  useEffect(() => { inputRef.current?.focus() }, [])

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
      position: 'fixed', bottom: 56, right: 16,
      width: 360, height: 460,
      background: C.bg,
      border: `1px solid ${C.border}`,
      borderRadius: 6,
      boxShadow: '0 8px 24px rgba(31,35,40,0.12)',
      display: 'flex', flexDirection: 'column',
      fontFamily: font,
      fontSize: 13, color: C.text1,
      zIndex: 1100,
      overflow: 'hidden',
    }}>

      {/* Header */}
      <div style={{
        padding: '10px 12px',
        borderBottom: `1px solid ${C.border}`,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0, background: C.bgSubtle,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ fontSize: 15 }}>🔥</span>
          <span style={{ fontWeight: 600, fontSize: 13, color: C.text1 }}>FireRAG</span>
          <span style={{
            fontSize: 10, fontWeight: 500, color: C.fire,
            background: C.fireSubtle, border: `1px solid ${C.fireBorder}`,
            borderRadius: 20, padding: '1px 6px',
          }}>AI</span>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: C.text3, fontSize: 16, lineHeight: 1, padding: '2px 6px',
            borderRadius: 4,
          }}
          onMouseEnter={e => e.currentTarget.style.background = C.bgSubtle}
          onMouseLeave={e => e.currentTarget.style.background = 'none'}
        >×</button>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '12px',
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            {m.role === 'assistant' && (
              <div style={{
                width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                background: C.bgSubtle, border: `1px solid ${C.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 10, marginRight: 6, marginTop: 2,
              }}>🔥</div>
            )}
            <div style={{
              maxWidth: '80%', padding: '7px 11px',
              background: m.role === 'user' ? C.bgSubtle : C.bg,
              border: `1px solid ${C.border}`,
              borderRadius: m.role === 'user' ? '12px 12px 3px 12px' : '3px 12px 12px 12px',
              lineHeight: 1.55, whiteSpace: 'pre-wrap',
              color: C.text1, fontSize: 12.5,
            }}>
              {m.content}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
              background: C.bgSubtle, border: `1px solid ${C.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, marginRight: 6,
            }}>🔥</div>
            <div style={{
              padding: '7px 14px', background: C.bg,
              border: `1px solid ${C.border}`,
              borderRadius: '3px 12px 12px 12px',
              color: C.text3, letterSpacing: 3, fontSize: 11,
            }}>···</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '10px 12px', borderTop: `1px solid ${C.border}`, flexShrink: 0 }}>
        {error && (
          <div style={{ color: '#d1242f', fontSize: 11, marginBottom: 6 }}>{error}</div>
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
              flex: 1, background: C.bg,
              border: `1px solid ${C.border}`,
              borderRadius: 6, color: C.text1,
              padding: '7px 10px', resize: 'none',
              fontFamily: font, fontSize: 12.5, outline: 'none',
              lineHeight: 1.5,
            }}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            style={{
              background: loading || !input.trim() ? C.bgSubtle : C.text1,
              color: loading || !input.trim() ? C.text3 : '#ffffff',
              border: `1px solid ${loading || !input.trim() ? C.border : C.text1}`,
              borderRadius: 6, padding: '0 14px',
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              fontWeight: 500, fontSize: 12,
              alignSelf: 'stretch', transition: 'all 0.1s',
              fontFamily: font,
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
