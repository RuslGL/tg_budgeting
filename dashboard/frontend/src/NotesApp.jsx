import { useState, useEffect } from 'react'

function getApiBase() {
  const parts = window.location.pathname.split('/')
  return `/n/${parts[2]}/api`
}

const API_BASE = getApiBase()

const CATEGORY_COLORS = [
  '#E8649A',
  '#6C63FF',
  '#00C9B1',
  '#F5A623',
  '#4FC3F7',
  '#EF5350',
  '#AB47BC',
  '#66BB6A',
]

const DARK = {
  bodyBg: '#1C1B2E',
  bg: 'linear-gradient(135deg, #1C1B2E 0%, #16213E 60%, #1a1a2e 100%)',
  card: 'rgba(255,255,255,0.04)',
  cardHover: 'rgba(255,255,255,0.07)',
  cardBorder: 'rgba(255,255,255,0.07)',
  title: '#ffffff',
  noteText: 'rgba(255,255,255,0.85)',
  meta: 'rgba(255,255,255,0.35)',
  dot: 'rgba(255,255,255,0.2)',
  pillBorder: 'rgba(255,255,255,0.15)',
  pillText: 'rgba(255,255,255,0.5)',
  inputBg: 'rgba(255,255,255,0.06)',
  inputBorder: 'rgba(255,255,255,0.12)',
  inputColor: '#fff',
  sep: 'rgba(255,255,255,0.15)',
  resetColor: 'rgba(255,255,255,0.3)',
  empty: 'rgba(255,255,255,0.2)',
  deleteColor: 'rgba(255,255,255,0.2)',
  toggleTrack: 'rgba(255,255,255,0.1)',
  toggleKnob: '#ffffff',
  toggleIcon: '☀️',
}

const LIGHT = {
  bodyBg: '#F0F2F8',
  bg: '#F0F2F8',
  card: '#ffffff',
  cardHover: '#f8fafc',
  cardBorder: 'rgba(0,0,0,0.07)',
  title: '#0f172a',
  noteText: '#1e293b',
  meta: '#94a3b8',
  dot: '#e2e8f0',
  pillBorder: '#e2e8f0',
  pillText: '#64748b',
  inputBg: '#ffffff',
  inputBorder: '#e2e8f0',
  inputColor: '#0f172a',
  sep: '#e2e8f0',
  resetColor: '#94a3b8',
  empty: '#94a3b8',
  deleteColor: '#cbd5e1',
  toggleTrack: '#e2e8f0',
  toggleKnob: '#ffffff',
  toggleIcon: '🌙',
}

function getCategoryColor(categories, type) {
  const idx = categories.indexOf(type)
  return CATEGORY_COLORS[(idx >= 0 ? idx : 0) % CATEGORY_COLORS.length]
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const [y, m, d] = dateStr.split('-')
  return `${d}.${m}.${y}`
}

function TrashIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}

function ThemeToggle({ dark, onToggle }) {
  return (
    <button
      onClick={onToggle}
      title={dark ? 'Светлая тема' : 'Тёмная тема'}
      style={{
        position: 'relative',
        width: 52,
        height: 26,
        borderRadius: 13,
        background: dark ? '#2d2b4e' : '#dde3f0',
        border: `1px solid ${dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'}`,
        cursor: 'pointer',
        padding: 0,
        flexShrink: 0,
        transition: 'background 0.3s, border-color 0.3s',
      }}
    >
      <span style={{
        position: 'absolute',
        top: 3,
        left: dark ? 26 : 3,
        width: 18,
        height: 18,
        borderRadius: '50%',
        background: dark ? '#7c6fff' : '#f6c443',
        boxShadow: dark ? '0 0 6px rgba(124,111,255,0.5)' : '0 0 6px rgba(246,196,67,0.5)',
        transition: 'left 0.3s, background 0.3s, box-shadow 0.3s',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 10,
      }}>
        {dark ? '🌙' : '☀️'}
      </span>
    </button>
  )
}

function NoteCard({ note, categories, onDelete, t }) {
  const color = getCategoryColor(categories, note.type)
  const isToday = note.date === today()
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? t.cardHover : t.card,
        border: `1px solid ${t.cardBorder}`,
        borderLeft: `3px solid ${color}`,
        borderRadius: 12,
        padding: '14px 16px',
        marginBottom: 8,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: 12,
        transition: 'background 0.15s',
        boxShadow: t === LIGHT ? '0 1px 4px rgba(0,0,0,0.06)' : 'none',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{
            fontSize: 11,
            fontWeight: 600,
            color: color,
            textTransform: 'uppercase',
            letterSpacing: '0.6px',
          }}>{note.type}</span>
          <span style={{ color: t.dot, fontSize: 11 }}>·</span>
          <span style={{ fontSize: 11, color: t.meta }}>
            {isToday ? 'Сегодня' : formatDate(note.date)}
          </span>
        </div>
        <div style={{
          fontSize: 14,
          color: t.noteText,
          lineHeight: 1.55,
          whiteSpace: 'pre-wrap',
        }}>{note.text}</div>
      </div>
      <button
        onClick={() => onDelete(note.id)}
        style={{
          flexShrink: 0,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: hovered ? '#E8649A' : t.deleteColor,
          padding: '2px 4px',
          borderRadius: 6,
          lineHeight: 1,
          transition: 'color 0.15s',
        }}
        title="Удалить"
      >
        <TrashIcon />
      </button>
    </div>
  )
}

export default function NotesApp() {
  const [notes, setNotes] = useState([])
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('notes-theme')
    return saved !== null ? saved === 'dark' : true
  })

  const t = dark ? DARK : LIGHT

  useEffect(() => {
    document.body.style.background = t.bodyBg
    document.body.style.margin = '0'
  }, [dark])

  useEffect(() => {
    localStorage.setItem('notes-theme', dark ? 'dark' : 'light')
  }, [dark])

  useEffect(() => {
    fetch(`${API_BASE}/categories`)
      .then(r => r.json())
      .then(setCategories)
  }, [])

  useEffect(() => {
    function fetchNotes() {
      const params = new URLSearchParams()
      if (selectedCategory) params.set('category', selectedCategory)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      fetch(`${API_BASE}/notes?${params}`)
        .then(r => r.json())
        .then(setNotes)
    }
    fetchNotes()
    const interval = setInterval(fetchNotes, 10000)
    return () => clearInterval(interval)
  }, [selectedCategory, dateFrom, dateTo])

  function handleDelete(id) {
    setNotes(prev => prev.filter(n => n.id !== id))
    fetch(`${API_BASE}/note/${id}`, { method: 'DELETE' }).catch(console.error)
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: t.bg,
      color: t.title,
      fontFamily: "'Inter', system-ui, sans-serif",
      padding: '32px 24px',
      maxWidth: 760,
      margin: '0 auto',
      boxSizing: 'border-box',
      transition: 'background 0.25s, color 0.25s',
    }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 20,
        }}>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: '0.5px', color: t.title }}>
            Заметки
          </div>
          <ThemeToggle dark={dark} onToggle={() => setDark(d => !d)} />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <button
            onClick={() => setSelectedCategory(null)}
            style={{
              padding: '6px 16px',
              borderRadius: 20,
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              border: `1.5px solid ${!selectedCategory ? '#94a3b8' : t.pillBorder}`,
              background: !selectedCategory ? 'rgba(148,163,184,0.15)' : 'transparent',
              color: !selectedCategory ? (dark ? '#cbd5e1' : '#475569') : t.pillText,
              transition: 'all 0.15s',
            }}
          >
            Все
          </button>

          {categories.map((cat, i) => {
            const color = CATEGORY_COLORS[i % CATEGORY_COLORS.length]
            const active = selectedCategory === cat
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(active ? null : cat)}
                style={{
                  padding: '6px 16px',
                  borderRadius: 20,
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: 'pointer',
                  border: `1.5px solid ${active ? color : t.pillBorder}`,
                  background: active ? `${color}22` : 'transparent',
                  color: active ? color : t.pillText,
                  transition: 'all 0.15s',
                }}
              >
                {cat}
              </button>
            )
          })}

          <span style={{ color: t.sep, margin: '0 4px' }}>|</span>

          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            style={{
              background: t.inputBg,
              border: `1.5px solid ${t.inputBorder}`,
              borderRadius: 8,
              padding: '5px 10px',
              fontSize: 13,
              color: dateFrom ? t.inputColor : t.meta,
              outline: 'none',
              cursor: 'pointer',
              colorScheme: dark ? 'dark' : 'light',
            }}
          />
          <span style={{ color: t.meta, fontSize: 13 }}>—</span>
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            style={{
              background: t.inputBg,
              border: `1.5px solid ${t.inputBorder}`,
              borderRadius: 8,
              padding: '5px 10px',
              fontSize: 13,
              color: dateTo ? t.inputColor : t.meta,
              outline: 'none',
              cursor: 'pointer',
              colorScheme: dark ? 'dark' : 'light',
            }}
          />
          {(dateFrom || dateTo) && (
            <button
              onClick={() => { setDateFrom(''); setDateTo('') }}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: t.resetColor,
                fontSize: 13,
                padding: '5px 8px',
              }}
            >
              сбросить
            </button>
          )}
        </div>
      </div>

      {notes.length === 0 ? (
        <div style={{
          textAlign: 'center',
          color: t.empty,
          fontSize: 14,
          padding: '80px 0',
        }}>
          Нет заметок
        </div>
      ) : (
        notes.map(note => (
          <NoteCard
            key={note.id}
            note={note}
            categories={categories}
            onDelete={handleDelete}
            t={t}
          />
        ))
      )}
    </div>
  )
}
