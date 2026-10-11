import { API_BASE_URL } from './config'
import { clearTokens, getTokens, setTokens, type Tokens } from './tokens'

export type FieldErrors = Record<string, string[]>

// Normalises DRF error bodies: {"detail": "..."} or {"field": ["..."]}.
export class ApiError extends Error {
  readonly status: number
  readonly detail: string | null
  readonly fieldErrors: FieldErrors
  readonly retryAfterSeconds: number | null

  constructor(status: number, body: unknown) {
    // A bare ValidationError("...") raised in a service arrives as ["..."].
    const list = Array.isArray(body) && typeof body[0] === 'string' ? (body[0] as string) : null
    const record = body && typeof body === 'object' && !list ? (body as Record<string, unknown>) : {}
    const detail = list ?? (typeof record.detail === 'string' ? record.detail : null)
    super(detail ?? `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.fieldErrors = {}
    for (const [key, value] of Object.entries(record)) {
      if (key === 'detail') continue
      if (Array.isArray(value)) this.fieldErrors[key] = value.map(String)
      else if (typeof value === 'string') this.fieldErrors[key] = [value]
    }
    const wait = status === 429 && detail ? /(\d+)\s*seconds?/.exec(detail) : null
    this.retryAfterSeconds = wait ? Number(wait[1]) : null
  }

  get isNetworkError(): boolean {
    return this.status === 0
  }
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  // JSON, or FormData for file uploads (the browser sets the multipart boundary).
  body?: unknown
  auth?: boolean
  // e.g. Idempotency-Key, which the API requires on orders and uploads.
  headers?: Record<string, string>
}

async function send(path: string, method: string, body: unknown, access?: string, extra?: Record<string, string>): Promise<Response> {
  const form = body instanceof FormData
  const headers: Record<string, string> = { Accept: 'application/json', ...extra }
  if (body !== undefined && !form) headers['Content-Type'] = 'application/json'
  if (access) headers.Authorization = `Bearer ${access}`
  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, null)
  }
}

async function parse<T>(response: Response): Promise<T> {
  const text = await response.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }
  if (!response.ok) throw new ApiError(response.status, data)
  return data as T
}

// Access tokens live 15 minutes and refresh tokens rotate on every use
// (SIMPLE_JWT ROTATE_REFRESH_TOKENS), so concurrent 401s must share one refresh.
let pendingRefresh: Promise<Tokens | null> | null = null

function refreshTokens(): Promise<Tokens | null> {
  pendingRefresh ??= (async () => {
    const current = getTokens()
    if (!current) return null
    try {
      const response = await send('/auth/token/refresh/', 'POST', { refresh: current.refresh })
      if (!response.ok) {
        clearTokens()
        return null
      }
      const data = (await response.json()) as { access: string; refresh?: string }
      const next = { access: data.access, refresh: data.refresh ?? current.refresh }
      setTokens(next)
      return next
    } catch {
      return null
    } finally {
      pendingRefresh = null
    }
  })()
  return pendingRefresh
}

export async function request<T>(path: string, { method = 'GET', body, auth = false, headers }: RequestOptions = {}): Promise<T> {
  if (!auth) return parse<T>(await send(path, method, body, undefined, headers))

  const tokens = getTokens()
  if (!tokens) throw new ApiError(401, null)
  let response = await send(path, method, body, tokens.access, headers)
  if (response.status === 401) {
    const fresh = await refreshTokens()
    if (!fresh) throw new ApiError(401, null)
    response = await send(path, method, body, fresh.access, headers)
  }
  return parse<T>(response)
}

// One key per user action, so a retried request is not applied twice.
export function idempotencyKey(): string {
  return crypto.randomUUID()
}
