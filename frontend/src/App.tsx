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
  is_operational?: boolean | null
  lifts_open?: number | null
  lifts_total?: number | null
  trails_open?: number | null
  trails_total?: number | null
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

type View = 'top-picks' | 'all-resorts'
type StateFilter = 'all' | 'NH' | 'VT' | 'ME'

const resolveApiUrl = () => {
  const configured = import.meta.env.VITE_API_URL?.trim()
  if (configured && configured.length > 0) {
    if (configured.startsWith('http')) {
      return configured.replace(/\/$/, '')
    }
    if (typeof window !== 'undefined') {
      const origin = window.location.origin.replace(/\/$/, '')
      const relativePath = configured.replace(/^\/+/, '')
      return `${origin}/${relativePath}`
    }
    return configured
  }

  if (typeof window === 'undefined') {
    return 'http://localhost:8000'
  }

  const origin = window.location.origin
  const isLocal = /localhost|127\.0\.0\.1/.test(origin)
  return (isLocal ? 'http://localhost:8000' : origin).replace(/\/$/, '')
}

const API_URL = resolveApiUrl()

const formatNumber = (value?: number | null, suffix = '') =>
  value === undefined || value === null ? '—' : `${value.toFixed(1)}${suffix}`

const formatDate = (value?: string | null) => {
  if (!value) return 'Not yet refreshed'
  return new Date(value).toLocaleString()
}

const formatCount = (open?: number | null, total?: number | null) => {
  if (open === undefined || open === null) return '—'
  if (total === undefined || total === null) return `${open}`
  return `${open}/${total}`
}

const resolveStatus = (flag?: boolean | null) => {
  if (flag === true) {
    return { label: 'Open', badge: 'bg-emerald-500/20 text-emerald-50', description: 'Reported open by the resort' }
  }
  if (flag === false) {
    return { label: 'Closed', badge: 'bg-rose-500/20 text-rose-50', description: 'Reported closed by the resort' }
  }
  return { label: 'Unknown', badge: 'bg-amber-500/20 text-amber-50', description: 'No official status reported yet' }
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


const ResortCard = ({ resort }: { resort: Ranking }) => {
  const status = resolveStatus(resort.conditions.is_operational)
  const isClosed = resort.conditions.is_operational === false
  const rationaleItems = resort.rationale.split(';').map((item) => item.trim()).filter(Boolean)

  return (
    <article
      className={`rounded-2xl bg-white/10 p-5 text-white shadow-card backdrop-blur transition hover:-translate-y-1 hover:bg-white/15 ${
        isClosed ? 'border border-rose-400/70' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-blue-200">{resort.state}</p>
          <h4 className="text-xl font-semibold text-white">{resort.name}</h4>
          <p className="text-sm text-slate-100">{resort.conditions.precip_type ?? 'Clear skies'}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-blue-200">Score</p>
          <p className="text-3xl font-black text-white">{resort.score.toFixed(0)}</p>
          <p className="text-xs font-semibold text-blue-100">
            {resort.powder ? 'Powder bonus' : resort.icy ? 'Watch for ice' : isClosed ? 'Closed today' : 'Balanced'}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
        <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 ${status.badge}`} title={status.description}>
          {status.label}
        </span>
        {resort.conditions.trails_open !== undefined && resort.conditions.trails_open !== null && (
          <MetricBadge
            label="Trails"
            value={formatCount(resort.conditions.trails_open, resort.conditions.trails_total)}
            accent="bg-purple-500/20 text-purple-50"
          />
        )}
        {resort.conditions.lifts_open !== undefined && resort.conditions.lifts_open !== null && (
          <MetricBadge
            label="Lifts"
            value={formatCount(resort.conditions.lifts_open, resort.conditions.lifts_total)}
            accent="bg-indigo-500/20 text-indigo-50"
          />
        )}
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

      <ul className="mt-4 space-y-1 text-sm leading-relaxed text-slate-100">
        {rationaleItems.map((item) => (
          <li key={item} className="flex items-start gap-2">
            <span className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-blue-500" />
            <span className="flex-1">{item}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-blue-100">Last updated {formatDate(resort.conditions.timestamp)}</p>
    </article>
  )
}

const ViewToggle = ({ view, onViewChange }: { view: View; onViewChange: (v: View) => void }) => (
  <div className="flex rounded-xl bg-white/10 p-1 backdrop-blur">
    <button
      onClick={() => onViewChange('top-picks')}
      className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
        view === 'top-picks'
          ? 'bg-blue-600 text-white shadow-card'
          : 'text-white/70 hover:text-white hover:bg-white/10'
      }`}
    >
      Top Picks
    </button>
    <button
      onClick={() => onViewChange('all-resorts')}
      className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
        view === 'all-resorts'
          ? 'bg-blue-600 text-white shadow-card'
          : 'text-white/70 hover:text-white hover:bg-white/10'
      }`}
    >
      All Resorts
    </button>
  </div>
)

const StateFilterButtons = ({ filter, onFilterChange }: { filter: StateFilter; onFilterChange: (f: StateFilter) => void }) => (
  <div className="flex flex-wrap gap-2">
    {(['all', 'NH', 'VT', 'ME'] as StateFilter[]).map((state) => (
      <button
        key={state}
        onClick={() => onFilterChange(state)}
        className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
          filter === state
            ? 'bg-blue-600 text-white'
            : 'bg-white/15 text-white/70 hover:text-white hover:bg-white/25'
        }`}
      >
        {state === 'all' ? 'All States' : state}
      </button>
    ))}
  </div>
)

function App() {
  const [rankings, setRankings] = useState<Ranking[]>([])
  const [summary, setSummary] = useState('Fetching resort intel...')
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [view, setView] = useState<View>('top-picks')
  const [stateFilter, setStateFilter] = useState<StateFilter>('all')
  // Force dark mode always
  useEffect(() => {
    document.documentElement.classList.add('dark')
  }, [])

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

  const filteredResorts = useMemo(() => {
    if (stateFilter === 'all') return rankings
    return rankings.filter((r) => r.state === stateFilter)
  }, [rankings, stateFilter])

  const groupedByState = useMemo(() => {
    const groups: Record<string, Ranking[]> = { NH: [], VT: [], ME: [] }
    filteredResorts.forEach((resort) => {
      if (groups[resort.state]) {
        groups[resort.state].push(resort)
      }
    })
    return groups
  }, [filteredResorts])

  return (
    <div className="min-h-screen bg-mountain-hero bg-cover bg-center text-white">
      <div className="min-h-screen bg-slate-900/60 px-6 py-8 backdrop-blur">
        <header className="mx-auto flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-blue-200">Snow Day</p>
            <h1 className="text-3xl font-bold text-white drop-shadow-none sm:text-4xl">
              Pick today's best ride
            </h1>
            <p className="text-sm text-slate-200">Live resort conditions with AI highlights.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <ViewToggle view={view} onViewChange={setView} />
          </div>
        </header>

        <main className="mx-auto mt-10 flex max-w-6xl flex-col gap-8">
          {/* Summary Section - Always visible */}
          <section className="rounded-2xl bg-white/10 p-6 text-white shadow-card backdrop-blur md:flex md:items-center md:justify-between">
            <div className="md:max-w-3xl">
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-blue-200">Why today?</p>
              <h2 className="text-2xl font-semibold text-white">{loading ? 'Loading picks...' : "Today's call"}</h2>
              <p className="mt-3 whitespace-pre-line text-base leading-relaxed text-slate-100">{summary}</p>
              <div className="mt-4 flex flex-wrap gap-3 text-xs text-blue-100">
                <span className="rounded-full bg-white/15 px-3 py-1 font-semibold">
                  Updated {formatDate(updatedAt)}
                </span>
                <span className="rounded-full bg-white/15 px-3 py-1 font-semibold">
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
              <p className="text-xs text-blue-100">Pulls fresh conditions from all resorts.</p>
            </div>
          </section>

          {/* Top Picks View */}
          {view === 'top-picks' && (
            <section>
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-blue-200">Top resorts</p>
                  <h3 className="text-xl font-semibold text-white">Powder-ready picks</h3>
                </div>
                <div className="text-sm text-blue-100">Sorted by Snow Day score</div>
              </div>
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {topResorts.map((resort) => (
                  <ResortCard key={resort.resort_id} resort={resort} />
                ))}
                {!loading && topResorts.length === 0 && (
                  <div className="rounded-2xl bg-white/10 p-6 text-center text-sm text-blue-100 shadow-card">
                    No resort data yet. Kick off a refresh to pull the latest conditions.
                  </div>
                )}
              </div>
            </section>
          )}

          {/* All Resorts View */}
          {view === 'all-resorts' && (
            <section>
              <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-blue-200">All resorts</p>
                  <h3 className="text-xl font-semibold text-white">
                    {stateFilter === 'all' ? 'Every mountain at a glance' : `${stateFilter} Mountains`}
                  </h3>
                </div>
                <StateFilterButtons filter={stateFilter} onFilterChange={setStateFilter} />
              </div>

              {stateFilter === 'all' ? (
                // Grouped by state view
                <div className="space-y-8">
                  {(['NH', 'VT', 'ME'] as const).map((state) => {
                    const stateResorts = groupedByState[state]
                    if (stateResorts.length === 0) return null
                    return (
                      <div key={state}>
                        <div className="mb-4 flex items-center gap-3">
                          <h4 className="text-lg font-bold text-white">
                            {state === 'NH' && '🏔️ New Hampshire'}
                            {state === 'VT' && '🌲 Vermont'}
                            {state === 'ME' && '🦞 Maine'}
                          </h4>
                          <span className="rounded-full bg-white/15 px-2 py-0.5 text-xs font-semibold text-white/70">
                            {stateResorts.length} {stateResorts.length === 1 ? 'resort' : 'resorts'}
                          </span>
                        </div>
                        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                          {stateResorts.map((resort) => (
                            <ResortCard key={resort.resort_id} resort={resort} />
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                // Filtered single state view
                <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                  {filteredResorts.map((resort) => (
                    <ResortCard key={resort.resort_id} resort={resort} />
                  ))}
                  {filteredResorts.length === 0 && (
                    <div className="rounded-2xl bg-white/10 p-6 text-center text-sm text-blue-100 shadow-card">
                      No resorts found for {stateFilter}.
                    </div>
                  )}
                </div>
              )}

              {!loading && rankings.length === 0 && (
                <div className="rounded-2xl bg-white/10 p-6 text-center text-sm text-blue-100 shadow-card">
                  No resort data yet. Kick off a refresh to pull the latest conditions.
                </div>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
