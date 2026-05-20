import * as Sentry from '@sentry/cloudflare'

type DeviceType = 'mobile' | 'desktop' | 'tablet'
type TrafficSource = 'paid_search' | 'social' | 'direct' | 'organic' | 'unknown'

type Segments = {
  device_types?: DeviceType[]
  traffic_sources?: TrafficSource[]
}

type Variant = {
  id: string
  name: string
  destination_url: string
  hyros_tag?: string | null
  weight: number
  is_control: boolean
  metadata?: {
    multivariate?: boolean
    multivariate_values?: Record<string, string>
  }
}

type ExperimentConfig = {
  id: string
  name: string
  entry_slug: string
  entry_url: string
  status: 'active' | 'paused'
  traffic_pct: number
  segments?: Segments
  variants: Variant[]
}

type ImpressionEvent = {
  experiment_id: string
  variant_id: string
  device_type: DeviceType
  traffic_source: TrafficSource
  country: string | null
  ts: string
}

interface Env {
  EXPERIMENTS_KV: KVNamespace
  IMPRESSIONS_QUEUE?: Queue<ImpressionEvent>
  BACKEND_BASE_URL: string
  INGEST_API_KEY: string
  ASSIGNMENT_TTL_SECONDS?: string
  ALLOW_DIRECT_INGEST_FALLBACK?: string
  SENTRY_DSN?: string
  SENTRY_ENVIRONMENT?: string
  SENTRY_TRACES_SAMPLE_RATE?: string
}

const DEFAULT_ASSIGNMENT_TTL = 60 * 60 * 24 * 30
const TRACKING_PARAM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid', 'msclkid']

const handler: ExportedHandler<Env, ImpressionEvent> = {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      const url = new URL(request.url)

      if (url.pathname === '/debug-sentry') {
        const expected = `Bearer ${env.INGEST_API_KEY}`
        const authorization = request.headers.get('authorization')
        if (authorization !== expected) {
          return new Response('Invalid ingest API key', { status: 401 })
        }
        throw new Error('Temporary Worker Sentry verification error')
      }

      const slug = extractSlug(url.pathname)

      if (!slug) {
        return new Response('Missing experiment slug.', { status: 404 })
      }

      const config = await env.EXPERIMENTS_KV.get<ExperimentConfig>(`experiment:${slug}`, 'json')

      if (!config) {
        return new Response(`Experiment "${slug}" was not found in KV.`, { status: 404 })
      }

      if (config.status !== 'active') {
        return redirect(config.entry_url)
      }

      const deviceType = detectDeviceType(request.headers.get('user-agent') || '')
      const trafficSource = detectTrafficSource(request)

      if (!passesSegmentation(config.segments, deviceType, trafficSource)) {
        return redirect(config.entry_url)
      }

      if (Math.random() * 100 > config.traffic_pct) {
        return redirect(config.entry_url)
      }

      const visitorId = readCookie(request.headers.get('cookie'), 'lgg_uid') || crypto.randomUUID()
      const assignmentKey = `assignment:${visitorId}:${config.id}`
      const assignedVariantId = await env.EXPERIMENTS_KV.get(assignmentKey)
      const assignedVariant = config.variants.find((variant) => variant.id === assignedVariantId)
      const variant = assignedVariant ?? selectVariant(config.variants)

      try {
        await env.EXPERIMENTS_KV.put(assignmentKey, variant.id, {
          expirationTtl: Number(env.ASSIGNMENT_TTL_SECONDS || DEFAULT_ASSIGNMENT_TTL),
        })
      } catch (error) {
        console.warn('KV assignment write failed; continuing redirect.', error)
      }

      const destination = buildDestinationUrl(
        variant.destination_url,
        url,
        config.id,
        variant.id,
        variant.metadata?.multivariate_values,
        variant.hyros_tag,
      )
      const country = typeof request.cf?.country === 'string' ? request.cf.country : null

      const impressionEvent = {
        experiment_id: config.id,
        variant_id: variant.id,
        device_type: deviceType,
        traffic_source: trafficSource,
        country,
        ts: new Date().toISOString(),
      }

      try {
        if (env.IMPRESSIONS_QUEUE) {
          await env.IMPRESSIONS_QUEUE.send(impressionEvent)
        } else if (env.ALLOW_DIRECT_INGEST_FALLBACK === 'true') {
          await ingestDirect(env, impressionEvent)
        } else {
          console.warn('Impression delivery skipped because no queue binding or direct-ingest fallback is enabled.')
        }
      } catch (error) {
        // Remote preview mode does not currently support Queues reliably.
        console.warn('Impression delivery failed; continuing redirect.', error)
      }

      return new Response(null, {
        status: 302,
        headers: {
          Location: destination,
          'Set-Cookie': `lgg_uid=${visitorId}; Path=/; Max-Age=${env.ASSIGNMENT_TTL_SECONDS || DEFAULT_ASSIGNMENT_TTL}; HttpOnly; Secure; SameSite=Lax`,
        },
      })
    } catch (error) {
      Sentry.withScope((scope) => {
        scope.setTag('worker.phase', 'fetch')
        scope.setExtra('request_url', request.url)
        Sentry.captureException(error)
      })
      const detail = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
      return new Response(`Worker execution failed: ${detail}`, { status: 500 })
    }
  },

  async queue(batch: MessageBatch<ImpressionEvent>, env: Env): Promise<void> {
    const events = batch.messages.map((message) => message.body)
    const response = await fetch(`${env.BACKEND_BASE_URL}/ingest/impressions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${env.INGEST_API_KEY}`,
      },
      body: JSON.stringify({ events }),
    })

    if (!response.ok) {
      throw new Error(`Impression ingest failed with ${response.status}`)
    }

    batch.ackAll()
  },
}

export default Sentry.withSentry<Env, ImpressionEvent>(
  (env: Env) => {
    if (!env.SENTRY_DSN) {
      return undefined
    }

    return {
      dsn: env.SENTRY_DSN,
      environment: env.SENTRY_ENVIRONMENT || 'production',
      tracesSampleRate: Number(env.SENTRY_TRACES_SAMPLE_RATE || '0'),
    }
  },
  handler,
)

async function ingestDirect(env: Env, event: ImpressionEvent) {
  const response = await fetch(`${env.BACKEND_BASE_URL}/ingest/impressions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${env.INGEST_API_KEY}`,
    },
    body: JSON.stringify({ events: [event] }),
  })

  if (!response.ok) {
    throw new Error(`Direct impression ingest failed with ${response.status}`)
  }
}

function extractSlug(pathname: string) {
  return pathname.replace(/^\/+/, '').split('/')[0] || ''
}

function detectDeviceType(userAgent: string): DeviceType {
  const ua = userAgent.toLowerCase()
  if (/ipad|tablet/.test(ua)) return 'tablet'
  if (/mobi|iphone|android/.test(ua)) return 'mobile'
  return 'desktop'
}

function detectTrafficSource(request: Request): TrafficSource {
  const url = new URL(request.url)
  const medium = url.searchParams.get('utm_medium')?.toLowerCase()
  const source = url.searchParams.get('utm_source')?.toLowerCase()
  const referer = request.headers.get('referer')?.toLowerCase() || ''
  const hasPaidClickId = Boolean(url.searchParams.get('gclid') || url.searchParams.get('msclkid'))

  if (medium === 'cpc' || medium === 'ppc' || source === 'googleads' || hasPaidClickId) {
    return 'paid_search'
  }

  if (isSocialReferer(referer) || ['facebook', 'instagram', 'tiktok', 'linkedin', 'x'].includes(source || '')) {
    return 'social'
  }

  if (!referer) {
    return 'direct'
  }

  if (isSearchEngine(referer)) {
    return 'organic'
  }

  return 'unknown'
}

function isSearchEngine(referer: string) {
  return /(google\.[a-z.]+\/search|bing\.com|yahoo\.com|duckduckgo\.com)/.test(referer)
}

function isSocialReferer(referer: string) {
  return /(facebook\.com|instagram\.com|tiktok\.com|linkedin\.com|x\.com|l\.facebook\.com)/.test(referer)
}

function passesSegmentation(segments: Segments | undefined, deviceType: DeviceType, trafficSource: TrafficSource) {
  if (!segments) return true

  if (segments.device_types && segments.device_types.length > 0 && !segments.device_types.includes(deviceType)) {
    return false
  }

  if (
    segments.traffic_sources &&
    segments.traffic_sources.length > 0 &&
    !segments.traffic_sources.includes(trafficSource)
  ) {
    return false
  }

  return true
}

function selectVariant(variants: Variant[]) {
  const random = Math.floor(Math.random() * 100)
  let cursor = 0

  for (const variant of variants) {
    cursor += variant.weight
    if (random < cursor) {
      return variant
    }
  }

  return variants[0]
}

function buildDestinationUrl(
  destinationUrl: string,
  entryUrl: URL,
  experimentId: string,
  variantId: string,
  multivariateValues?: Record<string, string>,
  hyrosTag?: string | null,
) {
  const destination = new URL(destinationUrl)

  TRACKING_PARAM_KEYS.forEach((key) => {
    const incomingValue = entryUrl.searchParams.get(key)
    if (incomingValue) {
      destination.searchParams.set(key, incomingValue)
    }
  })

  entryUrl.searchParams.forEach((value, key) => {
    if (key.startsWith('utm_') && value) {
      destination.searchParams.set(key, value)
    }
  })

  if (hyrosTag) {
    destination.searchParams.set('test_tag', hyrosTag)
  }

  destination.searchParams.set('exp_id', experimentId)
  destination.searchParams.set('variant_id', variantId)
  if (multivariateValues) {
    Object.entries(multivariateValues).forEach(([key, value]) => {
      destination.searchParams.set(`mv_${key}`, value)
    })
  }

  return destination.toString()
}

function redirect(destination: string) {
  return Response.redirect(destination, 302)
}

function readCookie(cookieHeader: string | null, name: string) {
  if (!cookieHeader) return null
  const cookie = cookieHeader
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))

  return cookie ? cookie.slice(name.length + 1) : null
}
