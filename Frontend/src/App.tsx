import { startTransition, useCallback, useEffect, useState } from 'react'
import './App.css'

type ExperimentStatus = 'active' | 'paused'
type DeviceType = 'mobile' | 'desktop' | 'tablet'
type TrafficSource = 'paid_search' | 'social' | 'direct' | 'organic' | 'unknown'

type Segments = {
  device_types: DeviceType[]
  traffic_sources: TrafficSource[]
}

type Variant = {
  id?: string
  name: string
  destination_url: string
  hyros_tag: string
  weight: number
  is_control: boolean
}

type Experiment = {
  id?: string
  name: string
  entry_slug: string
  entry_url: string
  status: ExperimentStatus
  traffic_pct: number
  segments: Segments
  variants: Variant[]
}

type StatsSummary = {
  experiment_id: string
  totals: Array<{
    variant_id: string
    variant_name: string
    is_control: boolean
    count: number
  }>
  by_device_type: Array<{ dimension: string; count: number }>
  by_traffic_source: Array<{ dimension: string; count: number }>
  generated_at: string
}

type DailyCount = {
  day: string
  variant_id: string
  variant_name: string
  count: number
}

const STORAGE_KEYS = {
  apiBaseUrl: 'traffic-splitting-api-base-url',
  apiKey: 'traffic-splitting-api-key',
}

const deviceOptions: DeviceType[] = ['mobile', 'desktop', 'tablet']
const sourceOptions: TrafficSource[] = ['paid_search', 'social', 'direct', 'organic', 'unknown']

const defaultDateRange = () => {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 13)
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  }
}

const blankExperiment = (): Experiment => ({
  name: 'New traffic split',
  entry_slug: 'new-entry-slug',
  entry_url: 'https://example.com/home',
  status: 'paused',
  traffic_pct: 100,
  segments: { device_types: [], traffic_sources: [] },
  variants: [
    {
      name: 'Control',
      destination_url: 'https://example.com/home',
      hyros_tag: 'control',
      weight: 50,
      is_control: true,
    },
    {
      name: 'Variant A',
      destination_url: 'https://example.com/home-alt',
      hyros_tag: 'variant-a',
      weight: 50,
      is_control: false,
    },
  ],
})

function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(
    localStorage.getItem(STORAGE_KEYS.apiBaseUrl) || import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  )
  const [apiKey, setApiKey] = useState(
    localStorage.getItem(STORAGE_KEYS.apiKey) || import.meta.env.VITE_API_KEY || 'dev-admin-key',
  )
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState<Experiment>(blankExperiment())
  const [isCreating, setIsCreating] = useState(true)
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [dailyCounts, setDailyCounts] = useState<DailyCount[]>([])
  const [dateRange, setDateRange] = useState(defaultDateRange())
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isTogglingStatus, setIsTogglingStatus] = useState(false)
  const [isRefreshingStats, setIsRefreshingStats] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.apiBaseUrl, apiBaseUrl)
  }, [apiBaseUrl])

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.apiKey, apiKey)
  }, [apiKey])

  const apiRequest = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
        ...(init?.headers || {}),
      },
    })

    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `Request failed with status ${response.status}`)
    }

    if (response.status === 204) {
      return undefined as T
    }

    return response.json() as Promise<T>
  }, [apiBaseUrl, apiKey])

  const loadStats = useCallback(async (experimentId: string) => {
    setIsRefreshingStats(true)
    try {
      const [summary, daily] = await Promise.all([
        apiRequest<StatsSummary>(`/experiments/${experimentId}/stats`),
        apiRequest<DailyCount[]>(
          `/experiments/${experimentId}/stats/daily?start_date=${dateRange.start}&end_date=${dateRange.end}`,
        ),
      ])
      setStats(summary)
      setDailyCounts(daily)
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setIsRefreshingStats(false)
    }
  }, [apiRequest, dateRange.end, dateRange.start])

  const loadExperiments = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const nextExperiments = await apiRequest<Experiment[]>('/experiments')
      setExperiments(nextExperiments)

      if (nextExperiments.length === 0) {
        setIsCreating(true)
        setSelectedId(null)
        setDraft(blankExperiment())
        setStats(null)
        setDailyCounts([])
        return
      }

      const preferred = selectedId
        ? nextExperiments.find((experiment) => experiment.id === selectedId)
        : nextExperiments[0]

      if (preferred?.id) {
        startTransition(() => {
          setSelectedId(preferred.id!)
          setIsCreating(false)
          setDraft(preferred)
        })
        await loadStats(preferred.id)
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setIsLoading(false)
    }
  }, [apiRequest, loadStats, selectedId])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadExperiments()
    }, 0)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [loadExperiments])

  async function selectExperiment(experiment: Experiment) {
    if (!experiment.id) return
    setError(null)
    setIsCreating(false)
    setSelectedId(experiment.id)
    setDraft(structuredClone(experiment))
    await loadStats(experiment.id)
  }

  function updateExperiment<K extends keyof Experiment>(field: K, value: Experiment[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  function toggleSegment<K extends keyof Segments>(field: K, value: Segments[K][number]) {
    setDraft((current) => {
      const existing = current.segments[field]
      const nextValues = existing.includes(value as never)
        ? existing.filter((item) => item !== value)
        : [...existing, value]

      return {
        ...current,
        segments: {
          ...current.segments,
          [field]: nextValues,
        },
      }
    })
  }

  function updateVariant(index: number, field: keyof Variant, value: string | number | boolean) {
    setDraft((current) => {
      const variants = current.variants.map((variant, variantIndex) => {
        if (variantIndex !== index) return variant
        return { ...variant, [field]: value }
      })
      return { ...current, variants }
    })
  }

  function addVariant() {
    setDraft((current) => {
      const nextVariants = rebalanceWeights([
        ...current.variants,
        {
          name: `Variant ${String.fromCharCode(65 + current.variants.length)}`,
          destination_url: current.entry_url,
          hyros_tag: `variant-${current.variants.length + 1}`,
          weight: 0,
          is_control: false,
        },
      ])
      return { ...current, variants: nextVariants }
    })
  }

  function removeVariant(index: number) {
    setDraft((current) => {
      const nextVariants = current.variants.filter((_, variantIndex) => variantIndex !== index)
      return { ...current, variants: rebalanceWeights(nextVariants) }
    })
  }

  function createNewExperiment() {
    setError(null)
    setSelectedId(null)
    setIsCreating(true)
    setDraft(blankExperiment())
    setStats(null)
    setDailyCounts([])
  }

  async function saveExperiment() {
    setIsSaving(true)
    setError(null)
    try {
      const payload = {
        ...draft,
        traffic_pct: Number(draft.traffic_pct),
        variants: draft.variants.map((variant) => ({
          ...variant,
          weight: Number(variant.weight),
          hyros_tag: variant.hyros_tag || null,
        })),
      }

      const saved = isCreating || !draft.id
        ? await apiRequest<Experiment>('/experiments', {
            method: 'POST',
            body: JSON.stringify(payload),
          })
        : await apiRequest<Experiment>(`/experiments/${draft.id}`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
          })

      setDraft(saved)
      setSelectedId(saved.id || null)
      setIsCreating(false)
      await loadExperiments()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setIsSaving(false)
    }
  }

  async function toggleStatus() {
    if (!draft.id) return
    setIsTogglingStatus(true)
    setError(null)
    try {
      const next = await apiRequest<Experiment>(`/experiments/${draft.id}/toggle`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setDraft(next)
      await loadExperiments()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setIsTogglingStatus(false)
    }
  }

  async function deleteCurrentExperiment() {
    if (!draft.id || !window.confirm(`Delete ${draft.name}?`)) return
    setError(null)
    try {
      await apiRequest<void>(`/experiments/${draft.id}`, { method: 'DELETE' })
      createNewExperiment()
      await loadExperiments()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    }
  }

  const totalWeight = draft.variants.reduce((sum, variant) => sum + Number(variant.weight || 0), 0)
  const totalImpressions = stats?.totals.reduce((sum, item) => sum + item.count, 0) ?? 0
  const groupedDailyCounts = groupDailyCounts(dailyCounts)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <p className="eyebrow">LGG Internal</p>
          <h1>Traffic Splitting Control Room</h1>
          <p className="lede">FastAPI admin, Cloudflare edge router, and reporting in one internal tool.</p>
        </div>

        <section className="sidebar__section">
          <label>
            API base URL
            <input value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} />
          </label>
          <label>
            Admin API key
            <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" />
          </label>
          <button className="button button--ghost" type="button" onClick={() => void loadExperiments()}>
            {isLoading ? 'Refreshing...' : 'Refresh experiments'}
          </button>
        </section>

        <section className="sidebar__section sidebar__section--stretch">
          <div className="section-heading">
            <h2>Experiments</h2>
            <button className="button button--primary" type="button" onClick={createNewExperiment}>
              New
            </button>
          </div>

          <div className="experiment-list">
            {experiments.map((experiment) => (
              <button
                key={experiment.id}
                type="button"
                className={`experiment-card ${selectedId === experiment.id ? 'experiment-card--active' : ''}`}
                onClick={() => void selectExperiment(experiment)}
              >
                <div>
                  <strong>{experiment.name}</strong>
                  <span>{experiment.entry_slug}</span>
                </div>
                <span className={`status-pill status-pill--${experiment.status}`}>{experiment.status}</span>
              </button>
            ))}

            {experiments.length === 0 && !isLoading ? (
              <div className="empty-state">
                <p>No experiments yet.</p>
                <span>Create one from the editor.</span>
              </div>
            ) : null}
          </div>
        </section>
      </aside>

      <main className="main-panel">
        <header className="hero-panel">
          <div>
            <p className="eyebrow">Entry router</p>
            <h2>{isCreating ? 'Create experiment' : draft.name}</h2>
            <p>
              Manage entry slugs, traffic gates, segmentation rules, variant routing, and dashboard reads from the
              same surface.
            </p>
          </div>
          <div className="hero-panel__meta">
            <div>
              <span>Total weight</span>
              <strong>{totalWeight}%</strong>
            </div>
            <div>
              <span>Total impressions</span>
              <strong>{totalImpressions.toLocaleString()}</strong>
            </div>
          </div>
        </header>

        {error ? <div className="banner banner--error">{error}</div> : null}

        <section className="grid">
          <article className="panel">
            <div className="section-heading">
              <h3>Experiment settings</h3>
              <span>{isLoading ? 'Loading...' : isSaving ? 'Saving...' : 'Ready'}</span>
            </div>

            <div className="form-grid">
              <label>
                Name
                <input value={draft.name} onChange={(event) => updateExperiment('name', event.target.value)} />
              </label>
              <label>
                Entry slug
                <input
                  value={draft.entry_slug}
                  onChange={(event) => updateExperiment('entry_slug', event.target.value.toLowerCase())}
                />
              </label>
              <label className="form-grid__wide">
                Entry URL
                <input value={draft.entry_url} onChange={(event) => updateExperiment('entry_url', event.target.value)} />
              </label>
              <label>
                Status
                <select
                  value={draft.status}
                  onChange={(event) => updateExperiment('status', event.target.value as ExperimentStatus)}
                >
                  <option value="paused">paused</option>
                  <option value="active">active</option>
                </select>
              </label>
              <label>
                Traffic %
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={draft.traffic_pct}
                  onChange={(event) => updateExperiment('traffic_pct', Number(event.target.value))}
                />
              </label>
            </div>

            <div className="segmentation">
              <div>
                <h4>Device segments</h4>
                <div className="chip-row">
                  {deviceOptions.map((device) => (
                    <button
                      key={device}
                      type="button"
                      className={`chip ${draft.segments.device_types.includes(device) ? 'chip--active' : ''}`}
                      onClick={() => toggleSegment('device_types', device)}
                    >
                      {device}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <h4>Traffic source segments</h4>
                <div className="chip-row">
                  {sourceOptions.map((source) => (
                    <button
                      key={source}
                      type="button"
                      className={`chip ${draft.segments.traffic_sources.includes(source) ? 'chip--active' : ''}`}
                      onClick={() => toggleSegment('traffic_sources', source)}
                    >
                      {humanizeLabel(source)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </article>

          <article className="panel">
            <div className="section-heading">
              <h3>Variants</h3>
              <div className="inline-actions">
                <span className={totalWeight === 100 ? 'metric metric--ok' : 'metric metric--warn'}>
                  {totalWeight === 100 ? 'Weights valid' : 'Weights must sum to 100'}
                </span>
                <button className="button button--ghost" type="button" onClick={addVariant}>
                  Add variant
                </button>
              </div>
            </div>

            <div className="variant-stack">
              {draft.variants.map((variant, index) => (
                <div className="variant-card" key={variant.id || `${variant.name}-${index}`}>
                  <div className="variant-card__header">
                    <h4>{variant.name}</h4>
                    {draft.variants.length > 1 ? (
                      <button className="text-button" type="button" onClick={() => removeVariant(index)}>
                        Remove
                      </button>
                    ) : null}
                  </div>

                  <div className="form-grid">
                    <label>
                      Variant name
                      <input value={variant.name} onChange={(event) => updateVariant(index, 'name', event.target.value)} />
                    </label>
                    <label>
                      Weight
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={variant.weight}
                        onChange={(event) => updateVariant(index, 'weight', Number(event.target.value))}
                      />
                    </label>
                    <label className="form-grid__wide">
                      Destination URL
                      <input
                        value={variant.destination_url}
                        onChange={(event) => updateVariant(index, 'destination_url', event.target.value)}
                      />
                    </label>
                    <label>
                      Hyros tag
                      <input
                        value={variant.hyros_tag}
                        onChange={(event) => updateVariant(index, 'hyros_tag', event.target.value)}
                      />
                    </label>
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={variant.is_control}
                        onChange={() => {
                          setDraft((current) => ({
                            ...current,
                            variants: current.variants.map((item, itemIndex) => ({
                              ...item,
                              is_control: itemIndex === index,
                            })),
                          }))
                        }}
                      />
                      Control variant
                    </label>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel-actions">
              <button className="button button--primary" type="button" onClick={() => void saveExperiment()} disabled={isSaving || isTogglingStatus}>
                {isSaving ? (isCreating ? 'Creating...' : 'Saving...') : (isCreating ? 'Create experiment' : 'Save changes')}
              </button>
              {draft.id ? (
                <button className="button button--ghost" type="button" onClick={() => void toggleStatus()} disabled={isSaving || isTogglingStatus}>
                  {isTogglingStatus ? (draft.status === 'active' ? 'Pausing...' : 'Activating...') : (draft.status === 'active' ? 'Pause experiment' : 'Activate experiment')}
                </button>
              ) : null}
              {draft.id ? (
                <button className="button button--danger" type="button" onClick={() => void deleteCurrentExperiment()}>
                  Delete
                </button>
              ) : null}
            </div>
          </article>
        </section>

        <section className="panel panel--full">
          <div className="section-heading">
            <div>
              <h3>Reporting</h3>
              <p>Launch metrics from PostgreSQL with Redis cache in front of the heaviest queries.</p>
            </div>
            <div className="inline-actions">
              <label className="date-field">
                Start
                <input
                  type="date"
                  value={dateRange.start}
                  onChange={(event) => setDateRange((current) => ({ ...current, start: event.target.value }))}
                />
              </label>
              <label className="date-field">
                End
                <input
                  type="date"
                  value={dateRange.end}
                  onChange={(event) => setDateRange((current) => ({ ...current, end: event.target.value }))}
                />
              </label>
              <button
                className="button button--ghost"
                type="button"
                onClick={() => {
                  if (draft.id) void loadStats(draft.id)
                }}
                disabled={!draft.id || isRefreshingStats}
              >
                {isRefreshingStats ? 'Refreshing...' : 'Refresh reporting'}
              </button>
            </div>
          </div>

          {!draft.id ? (
            <div className="empty-state">
              <p>Reporting unlocks once the experiment has been created.</p>
              <span>Create the experiment first, then the API can start serving summary and daily stats.</span>
            </div>
          ) : (
            <>
              <div className="stats-grid">
                <div className="stat-card">
                  <span>Total impressions</span>
                  <strong>{totalImpressions.toLocaleString()}</strong>
                  <small>{stats ? `Generated ${new Date(stats.generated_at).toLocaleString()}` : 'No data yet'}</small>
                </div>
                <div className="stat-card">
                  <span>Device mix</span>
                  <strong>{stats?.by_device_type.length || 0} segments</strong>
                  <small>{stats?.by_device_type.map((item) => `${item.dimension}: ${item.count}`).join(' · ') || 'No data yet'}</small>
                </div>
                <div className="stat-card">
                  <span>Source mix</span>
                  <strong>{stats?.by_traffic_source.length || 0} segments</strong>
                  <small>{stats?.by_traffic_source.map((item) => `${humanizeLabel(item.dimension)}: ${item.count}`).join(' · ') || 'No data yet'}</small>
                </div>
              </div>

              <div className="reporting-grid">
                <div className="report-panel">
                  <h4>Variant totals</h4>
                  <div className="totals-list">
                    {stats?.totals.map((item) => {
                      const share = totalImpressions === 0 ? 0 : (item.count / totalImpressions) * 100
                      return (
                        <div key={item.variant_id} className="bar-row">
                          <div className="bar-row__labels">
                            <span>{item.variant_name}</span>
                            <span>{item.count.toLocaleString()}</span>
                          </div>
                          <div className="bar">
                            <div className="bar__fill" style={{ width: `${share}%` }} />
                          </div>
                        </div>
                      )
                    }) || <span className="muted">No data yet.</span>}
                  </div>
                </div>

                <div className="report-panel">
                  <h4>Daily traffic</h4>
                  <div className="timeline">
                    {groupedDailyCounts.length === 0 ? (
                      <span className="muted">No daily impressions in the selected range.</span>
                    ) : (
                      groupedDailyCounts.map((bucket) => (
                        <div key={bucket.day} className="timeline__row">
                          <strong>{bucket.day}</strong>
                          <div>
                            {bucket.items.map((item) => (
                              <span key={`${bucket.day}-${item.variant_id}`} className="timeline__badge">
                                {item.variant_name}: {item.count}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  )
}

function rebalanceWeights(variants: Variant[]) {
  if (variants.length === 0) return variants
  const baseWeight = Math.floor(100 / variants.length)
  let remainder = 100 - baseWeight * variants.length

  return variants.map((variant) => {
    const weight = baseWeight + (remainder > 0 ? 1 : 0)
    remainder = Math.max(0, remainder - 1)
    return { ...variant, weight }
  })
}

function groupDailyCounts(dailyCounts: DailyCount[]) {
  const grouped = new Map<string, DailyCount[]>()

  dailyCounts.forEach((item) => {
    const bucket = grouped.get(item.day) || []
    bucket.push(item)
    grouped.set(item.day, bucket)
  })

  return Array.from(grouped.entries()).map(([day, items]) => ({ day, items }))
}

function humanizeLabel(value: string) {
  return value.replaceAll('_', ' ')
}

function getErrorMessage(value: unknown) {
  if (value instanceof Error) return value.message
  return 'Something went wrong while talking to the API.'
}

export default App
