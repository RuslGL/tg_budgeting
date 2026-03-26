import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import NotesApp from './NotesApp.jsx'

const isNotes = window.location.pathname.startsWith('/n/')

const favicon = document.querySelector("link[rel='icon']")
if (favicon) {
  favicon.href = isNotes ? '/favicon-notes.svg' : '/favicon-budget.svg'
  favicon.type = 'image/svg+xml'
}
document.title = isNotes ? 'Заметки' : 'Бюджет'

ReactDOM.createRoot(document.getElementById('root')).render(
  isNotes ? <NotesApp /> : <App />
)
