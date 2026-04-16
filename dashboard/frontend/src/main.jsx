import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import CaloriesApp from './CaloriesApp.jsx'
import NotesApp from './NotesApp.jsx'

const path = window.location.pathname
const isNotes = path.startsWith('/n/')
const isCalories = path.startsWith('/cal/')

const favicon = document.querySelector("link[rel='icon']")
if (favicon) {
  if (isNotes) { favicon.href = '/favicon-notes.svg'; favicon.type = 'image/svg+xml' }
  else if (isCalories) { favicon.href = '/favicon-calories.svg'; favicon.type = 'image/svg+xml' }
  else { favicon.href = '/favicon-budget.svg'; favicon.type = 'image/svg+xml' }
}
document.title = isNotes ? 'Заметки' : isCalories ? 'Калории' : 'Бюджет'

let component = <App />
if (isNotes) component = <NotesApp />
else if (isCalories) component = <CaloriesApp />

ReactDOM.createRoot(document.getElementById('root')).render(component)
