import React, { useCallback, useEffect, useState } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell,
  ComposedChart, Line,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const SECRET = window.location.pathname.split('/')[2] || ''
const BASE = `/cal/${SECRET}/api`

const TODAY_ISO = new Date().toISOString().slice(0, 10)

// Sberbank-inspired palette
const C = {
  green:     '#21A038',  // Sberbank primary
  greenDim:  '#1A7F2C',
  greenBright:'#2DB84B',
  blue:      '#1E90FF',
  amber:     '#FFB300',
  coral:     '#FF5252',
  red:       '#F44336',
}

function addDays(iso, n) {
  const d = new Date(iso)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

function formatDateFull(iso) {
  if (!iso) return ''
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function formatDateShort(iso) {
  if (!iso) return ''
  const [, m, d] = iso.split('-')
  return `${d}.${m}`
}

function fillWeightGaps(weightData, days) {
  if (!weightData.length) return []
  const map = {}
  for (const { date, weight } of weightData) map[date] = weight
  const end = TODAY_ISO
  const start = addDays(end, -(days - 1))
  const result = []
  let lastWeight = null
  for (const { date, weight } of weightData) {
    if (date < start) lastWeight = weight
  }
  let cur = start
  while (cur <= end) {
    if (map[cur] !== undefined) {
      lastWeight = map[cur]
      result.push({ date: cur, weight: lastWeight, actual: true })
    } else if (lastWeight !== null) {
      result.push({ date: cur, weight: lastWeight, actual: false })
    }
    cur = addDays(cur, 1)
  }
  return result
}

function useDark() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('cal_theme')
    return saved !== null ? saved === 'dark' : true
  })
  const toggle = () => setDark(d => {
    localStorage.setItem('cal_theme', !d ? 'dark' : 'light')
    return !d
  })
  return [dark, toggle]
}

function getTheme(dark) {
  return dark
    ? {
        bg:         '#111111',
        bgGrad:     '#111111',
        card:       '#1C1C1E',
        cardAlt:    '#242426',
        surface:    'rgba(255,255,255,0.05)',
        border:     'rgba(255,255,255,0.1)',
        text:       '#F0F0F0',
        sub:        '#888888',
        muted:      'rgba(255,255,255,0.08)',
        divider:    'rgba(255,255,255,0.07)',
        tooltip:    '#1C1C1E',
      }
    : {
        bg:         '#F2F8F3',
        bgGrad:     '#F2F8F3',
        card:       '#FFFFFF',
        cardAlt:    '#F7FBF7',
        surface:    'rgba(33,160,56,0.06)',
        border:     'rgba(33,160,56,0.2)',
        text:       '#132016',
        sub:        '#557A5E',
        muted:      'rgba(0,0,0,0.06)',
        divider:    'rgba(0,0,0,0.07)',
        tooltip:    '#FFFFFF',
      }
}

async function fetchJson(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(r.status)
  return r.json()
}

function MacroTile({ label, consumed, limit, color, unit = 'г', isCalories = false, t }) {
  const pct = limit > 0 ? Math.min(100, Math.round(consumed / limit * 100)) : 0
  const remaining = Math.max(0, limit - consumed)
  const over = consumed > limit
  return (
    <div style={{
      background: t.card,
      borderRadius: 16,
      padding: '14px 16px',
      flex: 1,
      minWidth: 0,
      border: `1px solid ${t.border}`,
    }}>
      <div style={{ fontSize: 11, color: t.sub, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color, lineHeight: 1 }}>
        {consumed}
        <span style={{ fontSize: 22, fontWeight: 400, color: t.sub, marginLeft: 2 }}>/{limit}</span>
      </div>
      {isCalories && (
        <div style={{ fontSize: 11, color: over ? C.coral : t.sub, marginTop: 3 }}>
          {over ? `+${consumed - limit} сверх` : `${remaining} до лим.`}
        </div>
      )}
      <div style={{ marginTop: 10, height: 5, borderRadius: 3, background: t.muted, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', borderRadius: 3,
          background: over ? C.coral : color,
          transition: 'width 0.4s ease',
        }} />
      </div>
      <div style={{ fontSize: 10, color: t.sub, marginTop: 4 }}>{pct}%</div>
    </div>
  )
}

function groupMealsByTime(meals) {
  const groups = []
  let current = null
  for (const meal of meals) {
    if (!current) {
      current = { time: meal.time, items: [meal] }
    } else {
      const [h1, m1] = current.time.split(':').map(Number)
      const [h2, m2] = meal.time.split(':').map(Number)
      const diff = (h2 * 60 + m2) - (h1 * 60 + m1)
      if (diff <= 30) {
        current.items.push(meal)
      } else {
        groups.push(current)
        current = { time: meal.time, items: [meal] }
      }
    }
  }
  if (current) groups.push(current)
  return groups
}

function MealGroup({ group, idx, t }) {
  const totalCal   = group.items.reduce((s, i) => s + i.calories, 0)
  const totalProt  = group.items.reduce((s, i) => s + i.protein, 0)
  const totalFat   = group.items.reduce((s, i) => s + i.fat, 0)
  const totalCarbs = group.items.reduce((s, i) => s + i.carbs, 0)
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '6px 0', marginBottom: 6,
      }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: t.sub, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          Приём {idx} · {group.time}
        </span>
        <span style={{ fontSize: 12, color: C.green, fontWeight: 700 }}>
          {Math.round(totalCal)} ккал · Б:{totalProt.toFixed(1)} Ж:{totalFat.toFixed(1)} У:{totalCarbs.toFixed(1)}
        </span>
      </div>
      {group.items.map((item, i) => (
        <div key={i} style={{
          background: t.card,
          border: `1px solid ${t.border}`,
          borderRadius: 12, padding: '10px 14px',
          marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: t.text }}>{item.food_name}</div>
            <div style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>Б:{item.protein} Ж:{item.fat} У:{item.carbs}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: C.green }}>{Math.round(item.calories)} к</div>
            <div style={{ fontSize: 12, color: t.sub }}>{item.grams} г</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function StatsPanel({ t, history, profile, calLimit }) {
  const rawWeight = history?.weight || []
  const weightData = fillWeightGaps(rawWeight, 30)
  const calData = history?.calories || []
  const goalWeight = parseFloat(profile.goal_weight || '0')
  const tdee = parseInt(profile.tdee || '0')
  const proteinLimit = parseInt(profile.protein_limit || '140')
  const fatLimit = parseInt(profile.fat_limit || '78')
  const carbsLimit = parseInt(profile.carbs_limit || '220')

  return (
    <div>
      {/* Limits */}
      <div style={{ background: t.card, border: `1px solid ${t.border}`, borderRadius: 16, padding: '16px', marginBottom: 14 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: t.sub, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 }}>Нормы БЖУ</div>
        {[
          { label: 'Калории',   value: calLimit,     unit: 'ккал', color: C.green },
          { label: 'Белки',     value: proteinLimit, unit: 'г',    color: C.blue  },
          { label: 'Жиры',      value: fatLimit,     unit: 'г',    color: C.amber },
          { label: 'Углеводы',  value: carbsLimit,   unit: 'г',    color: C.coral },
        ].map(({ label, value, unit, color }) => (
          <div key={label} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '8px 0', borderBottom: `1px solid ${t.divider}`,
          }}>
            <span style={{ fontSize: 14, color: t.sub }}>{label}</span>
            <span style={{ fontSize: 16, fontWeight: 700, color }}>{value} <span style={{ fontWeight: 400, fontSize: 12 }}>{unit}</span></span>
          </div>
        ))}
        {goalWeight > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
            <span style={{ fontSize: 14, color: t.sub }}>Цель по весу</span>
            <span style={{ fontSize: 16, fontWeight: 700, color: C.green }}>{goalWeight} кг</span>
          </div>
        )}
      </div>

      {/* Weight chart */}
      {weightData.length > 0 && (() => {
        const actualWeights = weightData.filter(w => w.actual).map(w => w.weight)
        const minW = Math.min(...actualWeights)
        const maxW = Math.max(...actualWeights)
        const spread = Math.max(maxW - minW, 1)
        const pad = Math.max(1, spread * 0.6)
        const yMin = parseFloat((minW - pad).toFixed(1))
        const yMax = parseFloat((maxW + pad * 0.5).toFixed(1))
        const latestActual = [...weightData].reverse().find(w => w.actual)?.weight ?? null
        const toGoal = goalWeight > 0 && latestActual ? (latestActual - goalWeight).toFixed(1) : null

        // Indices of actual weigh-ins for labelling first / middle / last
        const _actIdx = weightData.map((w, i) => w.actual ? i : -1).filter(i => i >= 0)
        const labelledIndices = new Set(
          _actIdx.length <= 3
            ? _actIdx
            : [_actIdx[0], _actIdx[Math.floor((_actIdx.length - 1) / 2)], _actIdx[_actIdx.length - 1]]
        )

        // Linear trend over actual points
        const pts = weightData.map((w, i) => ({ i, w: w.weight, actual: w.actual }))
        const n = pts.length
        const sumI = pts.reduce((s, p) => s + p.i, 0)
        const sumW = pts.reduce((s, p) => s + p.w, 0)
        const sumIW = pts.reduce((s, p) => s + p.i * p.w, 0)
        const sumI2 = pts.reduce((s, p) => s + p.i * p.i, 0)
        const slope = (n * sumIW - sumI * sumW) / (n * sumI2 - sumI * sumI)
        const intercept = (sumW - slope * sumI) / n
        const chartData = weightData.map((w, i) => ({
          ...w,
          trend: parseFloat((intercept + slope * i).toFixed(2)),
        }))

        return (
        <div style={{ background: t.card, border: `1px solid ${t.border}`, borderRadius: 16, padding: '16px 8px', marginBottom: 14 }}>
          <div style={{ paddingLeft: 8, paddingRight: 8, marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: t.sub, textTransform: 'uppercase', letterSpacing: 1 }}>Динамика веса — 30 дней</div>
              {goalWeight > 0 && (
                <div style={{ fontSize: 12, color: C.green }}>цель {goalWeight} кг</div>
              )}
            </div>
            {toGoal !== null && (
              <div style={{ fontSize: 13, color: parseFloat(toGoal) > 0 ? C.coral : C.green, marginTop: 4, fontWeight: 600 }}>
                {parseFloat(toGoal) > 0 ? `до цели ${toGoal} кг` : `цель достигнута (−${Math.abs(parseFloat(toGoal))} кг)`}
              </div>
            )}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 28, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="weightGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={C.coral} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={C.coral} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={t.divider} vertical={false} />
              <XAxis dataKey="date" tickFormatter={formatDateShort} tick={{ fill: t.sub, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[yMin, yMax]} tick={{ fill: t.sub, fontSize: 11 }} width={38} axisLine={false} tickLine={false} tickFormatter={v => v.toFixed(1)} />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null
                  const entry = payload[0]?.payload
                  const isActual = entry?.actual !== false
                  return (
                    <div style={{ background: t.tooltip, border: `1px solid ${t.border}`, borderRadius: 10, padding: '10px 14px' }}>
                      <div style={{ fontSize: 11, color: t.sub, marginBottom: 4 }}>{formatDateFull(label)}</div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: C.coral }}>{entry?.weight} кг</div>
                      {!isActual && <div style={{ fontSize: 11, color: t.sub, marginTop: 2 }}>нет замера — перенос</div>}
                      {goalWeight > 0 && isActual && (
                        <div style={{ fontSize: 11, color: t.sub, marginTop: 2 }}>
                          до цели: {(entry.weight - goalWeight).toFixed(1)} кг
                        </div>
                      )}
                    </div>
                  )
                }}
              />
              {goalWeight > 0 && (
                <ReferenceLine y={goalWeight} stroke={C.green} strokeDasharray="5 3" strokeWidth={1.5}
                  label={{ value: `${goalWeight}`, fill: C.green, fontSize: 11, position: 'insideTopRight' }} />
              )}
              <Area type="monotone" dataKey="weight" stroke={C.coral} strokeWidth={2}
                fill="url(#weightGrad)" dot={(props) => {
                  const { cx, cy, payload, index } = props
                  if (!payload.actual) return null
                  const labelled = labelledIndices.has(index)
                  return (
                    <g key={cx}>
                      <circle cx={cx} cy={cy} r={labelled ? 4 : 3} fill={C.coral} stroke="none" />
                      {labelled && (
                        <text x={cx} y={cy - 10} textAnchor="middle" fontSize={11} fontWeight={700} fill={C.coral}>
                          {payload.weight}
                        </text>
                      )}
                    </g>
                  )
                }}
                activeDot={{ r: 5, fill: C.coral }}
              />
              <Line type="monotone" dataKey="trend" stroke={C.amber} strokeWidth={1.5}
                strokeDasharray="4 3" dot={false} activeDot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        )
      })()}

      {/* Calorie chart */}
      {calData.length > 0 && (
        <div style={{ background: t.card, border: `1px solid ${t.border}`, borderRadius: 16, padding: '16px 8px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: t.sub, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1, paddingLeft: 8 }}>Калории по дням — 30 дней</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={calData}>
              <defs>
                <linearGradient id="calGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={C.green} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={C.green} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={t.divider} />
              <XAxis dataKey="date" tickFormatter={formatDateShort} tick={{ fill: t.sub, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: t.sub, fontSize: 11 }} width={42} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(v) => [`${v} ккал`, 'Калории']}
                labelFormatter={formatDateShort}
                contentStyle={{ background: t.tooltip, border: `1px solid ${t.border}`, borderRadius: 10, color: t.text }}
              />
              <ReferenceLine y={calLimit} stroke={C.greenDim} strokeDasharray="4 4" strokeWidth={1.5}
                label={{ value: 'Лимит', fill: C.green, fontSize: 11 }} />
              {tdee > 0 && (
                <ReferenceLine y={tdee} stroke={C.amber} strokeDasharray="4 4" strokeWidth={1.5}
                  label={{ value: 'TDEE', fill: C.amber, fontSize: 11 }} />
              )}
              <Area type="monotone" dataKey="calories" stroke={C.green} strokeWidth={2.5} fill="url(#calGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export default function CaloriesApp() {
  const [dark, toggleDark] = useDark()
  const [selectedDate, setSelectedDate] = useState(TODAY_ISO)
  const [todayData, setTodayData] = useState(null)
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showStats, setShowStats] = useState(false)

  const t = getTheme(dark)
  const isToday = selectedDate === TODAY_ISO

  const loadDay = useCallback(async (date) => {
    try {
      const data = await fetchJson(`${BASE}/today?date=${date}`)
      setTodayData(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const h = await fetchJson(`${BASE}/history?days=30`)
      setHistory(h)
    } catch (e) {
      console.error(e)
    }
  }, [])

  useEffect(() => {
    loadDay(selectedDate)
    loadHistory()
  }, [selectedDate, loadDay, loadHistory])

  useEffect(() => {
    if (!isToday) return
    const id = setInterval(() => {
      loadDay(selectedDate)
      loadHistory()
    }, 30000)
    return () => clearInterval(id)
  }, [isToday, selectedDate, loadDay, loadHistory])

  // Reload when tab becomes visible again (e.g. after switching from Telegram)
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        loadDay(selectedDate)
        loadHistory()
      }
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [selectedDate, loadDay, loadHistory])

  const goBack    = () => setSelectedDate(d => addDays(d, -1))
  const goForward = () => { if (!isToday) setSelectedDate(d => addDays(d, 1)) }
  const goToday   = () => setSelectedDate(TODAY_ISO)

  if (loading) {
    return (
      <div style={{ background: t.bgGrad, minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: t.text }}>
        Загрузка...
      </div>
    )
  }

  const profile      = todayData?.profile || {}
  const macros       = todayData?.macros  || {}
  const meals        = todayData?.meals   || []
  const calLimit     = parseInt(profile.cal_limit     || '2000')
  const proteinLimit = parseInt(profile.protein_limit || '140')
  const fatLimit     = parseInt(profile.fat_limit     || '78')
  const carbsLimit   = parseInt(profile.carbs_limit   || '220')

  const mealGroups   = groupMealsByTime(meals)
  const weightData   = history?.weight || []
  const latestWeight = weightData.length > 0 ? weightData[weightData.length - 1].weight : null

  return (
    <div style={{ background: t.bgGrad, minHeight: '100vh', color: t.text, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      <div style={{ maxWidth: 520, margin: '0 auto', padding: '0 0 48px' }}>

        {/* Header */}
        <div style={{ padding: '28px 16px 12px', position: 'relative', textAlign: 'center' }}>

          {/* Theme toggle */}
          <button onClick={toggleDark} style={{
            position: 'absolute', right: 16, top: 28,
            background: t.card, border: `1px solid ${t.border}`,
            borderRadius: 20, padding: '6px 14px',
            cursor: 'pointer', color: t.text, fontSize: 15,
          }}>
            {dark ? '☀' : '☾'}
          </button>

          {/* Title */}
          <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: 2, color: C.green, textTransform: 'uppercase' }}>
            Калькулятор питания
          </div>

          {/* Date nav */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0, marginTop: 10 }}>
            <button onClick={goBack} style={{
              background: 'none', border: 'none', cursor: 'pointer', color: t.text,
              fontSize: 24, padding: '0 12px', opacity: 0.6, lineHeight: 1,
            }}>‹</button>
            <div style={{ minWidth: 200, textAlign: 'center' }}>
              <div style={{ fontSize: 17, fontWeight: 700, color: isToday ? C.green : t.text }}>
                {isToday ? 'Сегодня' : formatDateFull(selectedDate)}
              </div>
              <div style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>{selectedDate}</div>
            </div>
            <button onClick={goForward} style={{
              background: 'none', border: 'none', cursor: 'pointer', color: t.text,
              fontSize: 24, padding: '0 12px', opacity: isToday ? 0.15 : 0.6, lineHeight: 1,
            }} disabled={isToday}>›</button>
          </div>

          {!isToday && (
            <button onClick={goToday} style={{
              marginTop: 8, background: 'none', border: `1px solid ${C.green}`,
              borderRadius: 12, padding: '4px 14px', color: C.green, fontSize: 12,
              cursor: 'pointer', fontWeight: 600,
            }}>
              Вернуться к сегодня
            </button>
          )}

          {/* Weight */}
          {latestWeight && (
            <div style={{ marginTop: 14 }}>
              <span style={{ fontSize: 13, color: t.sub }}>Вес: </span>
              <span style={{ fontSize: 26, fontWeight: 800, color: C.green }}>{latestWeight} кг</span>
            </div>
          )}
        </div>

        {/* Macro tiles */}
        <div style={{ padding: '0 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 20 }}>
          <MacroTile label="Калории"  consumed={macros.calories || 0} limit={calLimit}     color={C.green} isCalories t={t} />
          <MacroTile label="Белки"    consumed={macros.protein  || 0} limit={proteinLimit} color={C.blue}  t={t} />
          <MacroTile label="Жиры"     consumed={macros.fat      || 0} limit={fatLimit}     color={C.amber} t={t} />
          <MacroTile label="Углеводы" consumed={macros.carbs    || 0} limit={carbsLimit}   color={C.coral} t={t} />
        </div>

        {/* Stats toggle */}
        <div style={{ padding: '0 16px', marginBottom: 16 }}>
          <button onClick={() => setShowStats(s => !s)} style={{
            width: '100%', padding: '14px 18px',
            background: showStats ? t.surface : t.card,
            border: `1px solid ${showStats ? C.green : t.border}`,
            borderRadius: 14, cursor: 'pointer',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            color: showStats ? C.green : t.text, fontSize: 14, fontWeight: 700,
            transition: 'all 0.2s',
          }}>
            <span>Нормы и статистика</span>
            <span style={{ fontSize: 16, color: showStats ? C.green : t.sub }}>{showStats ? '▲' : '▼'}</span>
          </button>
        </div>

        {showStats && (
          <div style={{ padding: '0 16px', marginBottom: 16 }}>
            <StatsPanel t={t} history={history} profile={profile} calLimit={calLimit} />
          </div>
        )}

        {/* Meals */}
        <div style={{ padding: '0 16px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 14, color: t.sub, textTransform: 'uppercase', letterSpacing: 1 }}>
            {isToday ? 'Сегодняшние приёмы' : 'Приёмы пищи'}
          </div>
          {mealGroups.length === 0
            ? <div style={{ color: t.sub, fontSize: 14, textAlign: 'center', paddingTop: 24 }}>Приёмов пищи нет</div>
            : mealGroups.map((g, i) => <MealGroup key={i} group={g} idx={i + 1} t={t} />)
          }
        </div>

      </div>
    </div>
  )
}
