import { serve } from '@hono/node-server'
import { Hono } from 'hono'
import { pinoLogger, type Env as PinoEnv } from 'hono-pino'
import pino from 'pino'

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
])

const PROXY_CONTROL_HEADERS = new Set([
  'forwarded',
  'host',
  'x-forwarded-for',
  'x-forwarded-host',
  'x-forwarded-proto',
  'x-proxy-token',
  'x-real-ip',
  'x-target-url',
])

type ProxyLogMetadata = {
  target?: {
    host: string
    path: string
    protocol: string
  }
  request?: {
    contentType: string | null
    contentLength: string | null
    body?: Record<string, unknown>
  }
  upstream?: {
    status: number
    contentType: string | null
    contentLength: string | null
  }
}

type AppEnv = PinoEnv & {
  Variables: {
    proxyLog?: ProxyLogMetadata
  }
}

const port = Number.parseInt(process.env.PORT ?? '8787', 10)
const proxyToken = process.env.API_PROXY_TOKEN ?? ''
const logLevel = process.env.LOG_LEVEL ?? 'info'

const app = new Hono<AppEnv>()

app.use(pinoLogger({
  pino: pino({
    level: logLevel,
    base: null,
    redact: {
      paths: [
        'req.headers.authorization',
        'req.headers.cookie',
        'req.headers.x-api-key',
        'req.headers.x-proxy-token',
        'req.headers.ollama-api-key',
      ],
      remove: true,
    },
  }),
  http: {
    reqId: () => crypto.randomUUID(),
    onReqBindings: (c) => ({
      req: {
        method: c.req.method,
        path: c.req.path,
        contentType: c.req.header('Content-Type') ?? null,
        contentLength: c.req.header('Content-Length') ?? null,
      },
    }),
    onResBindings: (c) => {
      const proxy = c.get('proxyLog')
      return {
        res: {
          status: c.res.status,
        },
        proxy,
      }
    },
    onResLevel: (c) => {
      if (c.res.status >= 500) return 'error'
      if (c.res.status >= 400) return 'warn'
      return 'info'
    },
    onResMessage: () => 'proxy request completed',
  },
}))

function jsonError(message: string, status: number): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

function parseTarget(rawTarget: string | null): URL | null {
  if (!rawTarget) {
    return null
  }

  try {
    const target = new URL(rawTarget)
    if (target.protocol !== 'https:' && target.protocol !== 'http:') {
      return null
    }

    return target
  } catch {
    return null
  }
}

function buildUpstreamHeaders(headers: Headers): Headers {
  const upstreamHeaders = new Headers()

  for (const [name, value] of headers.entries()) {
    const lowerName = name.toLowerCase()
    if (HOP_BY_HOP_HEADERS.has(lowerName)) {
      continue
    }

    if (PROXY_CONTROL_HEADERS.has(lowerName)) {
      continue
    }

    upstreamHeaders.set(name, value)
  }

  // Force identity encoding: Node's fetch transparently decompresses
  // gzip/br upstream bodies, so passing the original Content-Encoding header
  // through would make clients decompress an already-plain body (Z_DATA_ERROR).
  upstreamHeaders.set('accept-encoding', 'identity')

  return upstreamHeaders
}

function buildResponseHeaders(headers: Headers): Headers {
  const responseHeaders = new Headers()

  for (const [name, value] of headers.entries()) {
    const lowerName = name.toLowerCase()
    if (HOP_BY_HOP_HEADERS.has(lowerName)) {
      continue
    }

    // The body has already been decompressed by the upstream fetch.
    if (lowerName === 'content-encoding' || lowerName === 'content-length') {
      continue
    }

    responseHeaders.set(name, value)
  }

  return responseHeaders
}

async function readBodyMetadata(request: Request): Promise<Record<string, unknown> | undefined> {
  const contentType = request.headers.get('Content-Type') ?? ''
  if (!contentType.toLowerCase().includes('application/json')) {
    return undefined
  }

  try {
    const body = await request.clone().json() as Record<string, unknown>
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      return { kind: 'json-non-object' }
    }

    return {
      kind: 'json',
      model: typeof body.model === 'string' ? body.model : undefined,
      stream: typeof body.stream === 'boolean' ? body.stream : undefined,
      messageCount: Array.isArray(body.messages) ? body.messages.length : undefined,
      inputCount: Array.isArray(body.input) ? body.input.length : undefined,
      hasTools: Array.isArray(body.tools) ? body.tools.length > 0 : undefined,
      hasStreamOptions: Boolean(body.stream_options),
    }
  } catch (error) {
    return {
      kind: 'json-unreadable',
      error: error instanceof Error ? error.message : 'unknown',
    }
  }
}

app.options('/', () => new Response(null, {
  status: 204,
}))

app.get('/healthz', (c) => c.json({
  ok: true,
}))

app.all('/', async (c) => {
  const requestLog: ProxyLogMetadata['request'] = {
    contentType: c.req.header('Content-Type') ?? null,
    contentLength: c.req.header('Content-Length') ?? null,
  }

  if (!proxyToken) {
    return jsonError('API proxy token is not configured', 500)
  }

  if (c.req.header('X-Proxy-Token') !== proxyToken) {
    return jsonError('Invalid proxy token', 401)
  }

  const target = parseTarget(c.req.header('X-Target-URL') ?? null)
  if (!target) {
    return jsonError('Target URL is invalid', 400)
  }

  const method = c.req.method.toUpperCase()
  if (method !== 'GET' && method !== 'POST') {
    return jsonError('Method is not allowed', 405)
  }

  requestLog.body = method === 'GET' ? undefined : await readBodyMetadata(c.req.raw)

  c.set('proxyLog', {
    target: {
      host: target.host,
      path: target.pathname,
      protocol: target.protocol,
    },
    request: requestLog,
  })

  const upstreamResponse = await fetch(target, {
    method,
    headers: buildUpstreamHeaders(c.req.raw.headers),
    body: method === 'GET' ? undefined : c.req.raw.body,
    duplex: method === 'GET' ? undefined : 'half',
  } as RequestInit & { duplex?: 'half' })

  c.set('proxyLog', {
    target: {
      host: target.host,
      path: target.pathname,
      protocol: target.protocol,
    },
    request: requestLog,
    upstream: {
      status: upstreamResponse.status,
      contentType: upstreamResponse.headers.get('Content-Type'),
      contentLength: upstreamResponse.headers.get('Content-Length'),
    },
  })

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: buildResponseHeaders(upstreamResponse.headers),
  })
})

serve({
  fetch: app.fetch,
  port,
}, (info) => {
  console.log(`api-proxy listening on http://0.0.0.0:${info.port}`)
})
