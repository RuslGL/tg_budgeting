import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'

const COLORS = [
  '#3b82f6', '#8b5cf6', '#06b6d4', '#f59e0b', '#10b981',
  '#f43f5e', '#a78bfa', '#34d399', '#fbbf24', '#60a5fa',
  '#e879f9', '#2dd4bf', '#fb923c', '#a3e635', '#818cf8',
]

const MONTHS_RU = [
  'Январь','Февраль','Март','Апрель','Май','Июнь',
  'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь',
]

function getApiBase() {
  const parts = window.location.pathname.split('/')
  return `/d/${parts[2]}/api`
}

const API_BASE = getApiBase()

function fmt(n) {
  return Math.round(n).toLocaleString('ru-RU')
}

const S = {
  app: {
    minHeight: '100vh',
    background: '#0f172a',
    color: '#f1f5f9',
    fontFamily: "'Inter', system-ui, sans-serif",
    padding: '24px 20px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 28,
    flexWrap: 'wrap',
    gap: 12,
  },
  logo: {
    fontSize: 20,
    fontWeight: 700,
    color: '#f1f5f9',
    letterSpacing: '1px',
  },
  select: {
    background: '#3b82f6',
    border: 'none',
    color: '#ffffff',
    fontSize: 14,
    padding: '8px 12px',
    borderRadius: 8,
    cursor: 'pointer',
    outline: 'none',
  },
  chartsRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
  },
  card: {
    background: '#1e293b',
    border: '1px solid #334155',
    borderRadius: 12,
    padding: '20px',
  },
  cardTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.8px',
    marginBottom: 4,
  },
  cardSubtitle: {
    fontSize: 20,
    fontWeight: 700,
    color: '#f1f5f9',
    marginBottom: 16,
    letterSpacing: '-0.3px',
  },
  empty: {
    color: '#475569',
    fontSize: 14,
    textAlign: 'center',
    padding: '40px 0',
  },
}

const CustomTooltip = ({ active, payload, total }) => {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0]
  const pct = total > 0 ? (value / total * 100).toFixed(1) + '%' : null
  return (
    <div style={{
      background: '#0f172a',
      border: '1px solid #334155',
      borderRadius: 8,
      padding: '10px 14px',
      fontSize: 13,
    }}>
      <div style={{ color: '#94a3b8', marginBottom: 4 }}>{name}</div>
      <div style={{ color: '#f1f5f9', fontWeight: 700 }}>{fmt(value)} руб</div>
      {pct && <div style={{ color: '#64748b', marginTop: 2 }}>{pct}</div>}
    </div>
  )
}

const CustomLegend = ({ payload }) => (
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 16px', marginTop: 8, justifyContent: 'center' }}>
    {payload.map((entry, i) => (
      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94a3b8' }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: entry.color, flexShrink: 0 }} />
        {entry.value}
      </div>
    ))}
  </div>
)

function PieCard({ title, subtitle, data, showYearTotals }) {
  const expenses = data.filter(r => r.type !== 'Доход')
  const chartData = expenses.map(r => ({ name: r.category, value: r.total }))

  const yearIncome = showYearTotals ? data.filter(r => r.type === 'Доход').reduce((s, r) => s + r.total, 0) : 0
  const yearExpense = showYearTotals ? expenses.reduce((s, r) => s + r.total, 0) : 0
  const yearBalance = yearIncome - yearExpense

  return (
    <div style={S.card}>
      <div style={S.cardTitle}>{title}</div>
      <div style={S.cardSubtitle}>{subtitle}</div>

      {showYearTotals && data.length > 0 && (
        <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, background: '#0f172a', borderRadius: 8, padding: '10px 14px' }}>
            <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.7px', marginBottom: 4 }}>Доход</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#22c55e' }}>{fmt(yearIncome)}</div>
          </div>
          <div style={{ flex: 1, background: '#0f172a', borderRadius: 8, padding: '10px 14px' }}>
            <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.7px', marginBottom: 4 }}>Расходы</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#f43f5e' }}>{fmt(yearExpense)}</div>
          </div>
          <div style={{ flex: 1, background: '#0f172a', borderRadius: 8, padding: '10px 14px' }}>
            <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.7px', marginBottom: 4 }}>Разница</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: yearBalance >= 0 ? '#22c55e' : '#f43f5e' }}>{fmt(yearBalance)}</div>
          </div>
        </div>
      )}

      {chartData.length === 0 ? (
        <div style={S.empty}>Нет данных</div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="45%"
                outerRadius={100}
                innerRadius={40}
                paddingAngle={2}
                label={({ percent }) => percent >= 0.07 ? `${(percent * 100).toFixed(0)}%` : ''}
                labelLine={false}
              >
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip content={(props) => <CustomTooltip {...props} total={yearExpense} />} />
              <Legend content={<CustomLegend />} />
            </PieChart>
          </ResponsiveContainer>

          <div style={{ marginTop: 16, borderTop: '1px solid #334155', paddingTop: 12 }}>
            {[...chartData].sort((a, b) => b.value - a.value).map((row, i) => (
              <div key={i} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '6px 0',
                borderBottom: '1px solid #1e293b',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS[i % COLORS.length], flexShrink: 0 }} />
                  <span style={{ fontSize: 13, color: '#cbd5e1' }}>{row.name}</span>
                </div>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9' }}>{fmt(row.value)}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

const AUTHOR_COLORS = ['#3b82f6', '#a78bfa', '#f59e0b', '#34d399']

function BarCard({ title, subtitle, data }) {
  // data: [{category, author, total}]
  const authors = [...new Set(data.map(r => r.author))].sort()

  // pivot: [{category, Author1: total, Author2: total, _sum: total}]
  const byCategory = {}
  for (const row of data) {
    if (!byCategory[row.category]) byCategory[row.category] = { category: row.category, _sum: 0 }
    byCategory[row.category][row.author] = row.total
    byCategory[row.category]._sum += row.total
  }
  const chartData = Object.values(byCategory).sort((a, b) => b._sum - a._sum)

  if (chartData.length === 0) return (
    <div style={S.card}>
      <div style={S.cardTitle}>{title}</div>
      <div style={S.cardSubtitle}>{subtitle}</div>
      <div style={S.empty}>Нет данных</div>
    </div>
  )

  return (
    <div style={S.card}>
      <div style={S.cardTitle}>{title}</div>
      <div style={S.cardSubtitle}>{subtitle}</div>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: 8, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" vertical={false} />
          <XAxis
            dataKey="category"
            tick={{ fill: '#64748b', fontSize: 11 }}
            angle={-35}
            textAnchor="end"
            interval={0}
          />
          <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => fmt(v)} width={60} />
          <Tooltip
            cursor={false}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null
              return (
                <div style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, padding: '10px 14px', fontSize: 13 }}>
                  <div style={{ color: '#94a3b8', marginBottom: 6 }}>{label}</div>
                  {payload.map((p, i) => (
                    <div key={i} style={{ color: p.fill, marginBottom: 2 }}>
                      {p.dataKey}: <strong>{fmt(p.value)}</strong>
                    </div>
                  ))}
                </div>
              )
            }}
          />
          <Legend
            wrapperStyle={{ paddingTop: 8, fontSize: 13, color: '#94a3b8' }}
            formatter={v => <span style={{ color: '#94a3b8' }}>{v}</span>}
          />
          {authors.map((author, i) => (
            <Bar key={author} dataKey={author} fill={AUTHOR_COLORS[i % AUTHOR_COLORS.length]} radius={[3, 3, 0, 0]} maxBarSize={32} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function App() {
  const [company, setCompany] = useState('family')
  const [months, setMonths] = useState([])
  const [selectedYear, setSelectedYear] = useState(null)
  const [selectedMonth, setSelectedMonth] = useState(null)
  const [monthData, setMonthData] = useState([])
  const [yearData, setYearData] = useState([])
  const [monthByAuthor, setMonthByAuthor] = useState([])
  const [yearByAuthor, setYearByAuthor] = useState([])

  useEffect(() => {
    fetch(`${API_BASE}/months?company=${company}`)
      .then(r => r.json())
      .then(ms => {
        setMonths(ms)
        if (ms.length > 0) {
          setSelectedYear(ms[0].year)
          setSelectedMonth(ms[0].month)
        } else {
          setSelectedYear(null)
          setSelectedMonth(null)
        }
      })
  }, [company])

  // available years from data
  const years = [...new Set(months.map(m => m.year))].sort((a, b) => b - a)

  // available months for selected year
  const monthsForYear = months
    .filter(m => m.year === selectedYear)
    .map(m => m.month)
    .sort((a, b) => b - a)

  // if selected month not available in new year — pick first available
  useEffect(() => {
    if (!selectedYear || monthsForYear.length === 0) return
    if (!monthsForYear.includes(selectedMonth)) {
      setSelectedMonth(monthsForYear[0])
    }
  }, [selectedYear])

  useEffect(() => {
    if (!selectedYear || !selectedMonth) return
    fetch(`${API_BASE}/month?year=${selectedYear}&month=${selectedMonth}&company=${company}`)
      .then(r => r.json())
      .then(setMonthData)
    fetch(`${API_BASE}/month/by-author?year=${selectedYear}&month=${selectedMonth}&company=${company}`)
      .then(r => r.json())
      .then(setMonthByAuthor)
  }, [selectedYear, selectedMonth, company])

  useEffect(() => {
    if (!selectedYear) return
    fetch(`${API_BASE}/year?year=${selectedYear}&company=${company}`)
      .then(r => r.json())
      .then(setYearData)
    fetch(`${API_BASE}/year/by-author?year=${selectedYear}&company=${company}`)
      .then(r => r.json())
      .then(setYearByAuthor)
  }, [selectedYear, company])

  const monthLabel = selectedYear && selectedMonth
    ? `${MONTHS_RU[selectedMonth - 1]} ${selectedYear}`
    : ''

  return (
    <div style={S.app}>
      <div style={S.header}>
        <select
          style={{ ...S.select, fontSize: 20, fontWeight: 700, letterSpacing: '1px' }}
          value={company}
          onChange={e => setCompany(e.target.value)}
        >
          <option value="family">БЮДЖЕТ СЕМЕЙНЫЙ</option>
          <option value="business">БЮДЖЕТ БИЗНЕС</option>
        </select>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select
            style={S.select}
            value={selectedYear || ''}
            onChange={e => setSelectedYear(Number(e.target.value))}
          >
            {years.map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select
            style={S.select}
            value={selectedMonth || ''}
            onChange={e => setSelectedMonth(Number(e.target.value))}
          >
            {monthsForYear.map(m => (
              <option key={m} value={m}>{MONTHS_RU[m - 1]}</option>
            ))}
          </select>
        </div>
      </div>

      <div style={S.chartsRow}>
        <PieCard
          title="За месяц"
          subtitle={monthLabel}
          data={monthData}
          showYearTotals
        />
        <PieCard
          title="За год"
          subtitle={String(selectedYear || '')}
          data={yearData}
          showYearTotals
        />
      </div>

      <div style={{ ...S.chartsRow, marginTop: 16 }}>
        <BarCard
          title="По пользователям — месяц"
          subtitle={monthLabel}
          data={monthByAuthor}
        />
        <BarCard
          title="По пользователям — год"
          subtitle={String(selectedYear || '')}
          data={yearByAuthor}
        />
      </div>
    </div>
  )
}
