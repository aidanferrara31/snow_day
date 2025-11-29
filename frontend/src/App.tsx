import { useEffect, useMemo, useState } from 'react'

type Condition = {
  resort_id: string
  name: string
  state: string
  timestamp: string
  wind_speed?: number | null
  wind_chill?: number | null
  temp_min?: number | null
  temp_max?: number | null
  snowfall_12h?: number | null
  snowfall_24h?: number | null
  snowfall_7d?: number | null
  base_depth?: number | null
  precip_type?: string | null
}

type Ranking = {
  resort_id: string
  name: string
  state: string
  score: number
  rationale: string
  powder: boolean
  icy: boolean
  conditions: Condition
}

type RankingsResponse = {
  updated_at: string | null
  rankings: Ranking[]
  summary: string
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const formatNumber = (value?: number | null, suffix = '') =>
  value === undefined || value === null ? '—' : `${value.toFixed(1)}${suffix}`

const formatDate = (value?: string | null) => {
  if (!value) return 'Not yet refreshed'
  return new Date(value).toLocaleString()
}

const MetricBadge = ({ label, value, accent }: { label: string; value: string; accent?: string }) => (
  <span
    className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
      accent ?? 'bg-white/15 text-white'
    }`}
  >
    {label}: {value}
  </span>
)

const ThemeToggle = ({ theme, onToggle }: { theme: 'light' | 'dark'; onToggle: () => void }) => (
  <button
    onClick={onToggle}
    className="rounded-full bg-white/10 px-4 py-2 text-sm font-semibold text-white shadow-card backdrop-blur hover:bg-white/20"
  >
    {theme === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
  </button>
)

function App() {
  const [rankings, setRankings] = useState<Ranking[]>([])
  const [summary, setSummary] = useState('Fetching resort intel...')
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const stored = localStorage.getItem('snowday-theme') as 'light' | 'dark' | null
    return stored ?? 'dark'
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('snowday-theme', theme)
  }, [theme])

  const fetchRankings = async (path: 'rankings' | 'refresh') => {
    const isRefresh = path === 'refresh'
    isRefresh ? setRefreshing(true) : setLoading(true)
    try {
      const response = await fetch(`${API_URL}/${path}`, {
        method: path === 'refresh' ? 'POST' : 'GET',
      })
      const data: RankingsResponse = await response.json()
      setRankings(data.rankings ?? [])
      setSummary(data.summary ?? '')
      setUpdatedAt(data.updated_at)
    } catch (error) {
      console.error('Failed to load rankings', error)
      setSummary('Unable to reach the Snow Day API right now.')
    } finally {
      isRefresh ? setRefreshing(false) : setLoading(false)
    }
  }

  useEffect(() => {
    fetchRankings('rankings')
  }, [])

  const topResorts = useMemo(() => rankings.slice(0, 3), [rankings])

  return (
    <div className="min-h-screen bg-mountain-hero bg-cover bg-center text-slate-900 dark:text-white">
      <div className="min-h-screen bg-slate-100/70 px-6 py-8 backdrop-blur dark:bg-slate-900/60">
        <header className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-blue-200">Snow Day</p>
            <h1 className="text-3xl font-bold text-white drop-shadow sm:text-4xl dark:drop-shadow-none">
              Pick today\'s best ride
            </h1>
            <p className="text-sm text-slate-700 dark:text-slate-200">Live resort conditions with AI highlights.</p>
          </div>
          <ThemeToggle theme={theme} onToggle={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />
        </header>

        <main className="mx-auto mt-10 flex max-w-6xl flex-col gap-8">
          <section className="rounded-2xl bg-white/90 p-6 text-slate-900 shadow-card backdrop-blur md:flex md:items-center md:justify-between dark:bg-white/10 dark:text-white">
            <div className="md:max-w-3xl">
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-blue-200">Why today?</p>
              <h2 className="text-2xl font-semibold text-slate-900 dark:text-white">{loading ? 'Loading picks...' : 'Today\'s call'}</h2>
              <p className="mt-3 whitespace-pre-line text-base leading-relaxed text-slate-700 dark:text-slate-100">{summary}</p>
              <div className="mt-4 flex flex-wrap gap-3 text-xs text-blue-700 dark:text-blue-100">
                <span className="rounded-full bg-white/60 px-3 py-1 font-semibold dark:bg-white/15">
                  Updated {formatDate(updatedAt)}
                </span>
                <span className="rounded-full bg-white/60 px-3 py-1 font-semibold dark:bg-white/15">
                  {rankings.length} resorts scored
                </span>
              </div>
            </div>
            <div className="mt-6 flex flex-col gap-3 md:mt-0">
              <button
                onClick={() => fetchRankings('refresh')}
                className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-card transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
                disabled={refreshing}
              >
                {refreshing ? 'Refreshing…' : 'Manual refresh'}
              </button>
              <p className="text-xs text-blue-700 dark:text-blue-100">Pulls fresh conditions from all resorts.</p>
            </div>
          </section>

          <section>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-blue-200">Top resorts</p>
                <h3 className="text-xl font-semibold text-slate-900 dark:text-white">Powder-ready picks</h3>
              </div>
              <div className="text-sm text-blue-700 dark:text-blue-100">Sorted by Snow Day score</div>
            </div>
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {topResorts.map((resort) => (
                <article
                  key={resort.resort_id}
                  className="rounded-2xl bg-white/90 p-5 text-slate-900 shadow-card backdrop-blur transition hover:-translate-y-1 hover:bg-white dark:bg-white/10 dark:text-white"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-blue-600 dark:text-blue-200">{resort.state}</p>
                      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">{resort.name}</h4>
                      <p className="text-sm text-slate-700 dark:text-slate-100">{resort.conditions.precip_type ?? 'Clear skies'}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-blue-600 dark:text-blue-200">Score</p>
                      <p className="text-3xl font-black text-slate-900 dark:text-white">{resort.score.toFixed(0)}</p>
                      <p className="text-xs font-semibold text-blue-700 dark:text-blue-100">
                        {resort.powder ? 'Powder bonus' : resort.icy ? 'Watch for ice' : 'Balanced'}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2 text-xs">
                    <MetricBadge label="24h Snow" value={formatNumber(resort.conditions.snowfall_24h, ' in')} accent="bg-blue-500/20 text-blue-100" />
                    <MetricBadge label="Base" value={formatNumber(resort.conditions.base_depth, ' in')} accent="bg-white/15 text-white" />
                    <MetricBadge label="Wind" value={formatNumber(resort.conditions.wind_speed, ' mph')} accent="bg-amber-400/30 text-amber-50" />
                    <MetricBadge
                      label="Temps"
                      value={`${formatNumber(resort.conditions.temp_min, '°')} / ${formatNumber(resort.conditions.temp_max, '°')}`}
                      accent="bg-emerald-400/20 text-emerald-50"
                    />
                  </div>

                  <p className="mt-4 text-sm leading-relaxed text-slate-700 dark:text-slate-100">{resort.rationale}</p>
                  <p className="mt-2 text-xs text-blue-700 dark:text-blue-100">Last updated {formatDate(resort.conditions.timestamp)}</p>
                </article>
              ))}
              {!loading && topResorts.length === 0 && (
                <div className="rounded-2xl bg-white/80 p-6 text-center text-sm text-blue-700 shadow-card dark:bg-white/10 dark:text-blue-100">
                  No resort data yet. Kick off a refresh to pull the latest conditions.
                </div>
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}

export default App
