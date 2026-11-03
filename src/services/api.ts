export type User = { id: number; name: string; email: string; role: 'Administrator' | 'Emergency Officer' | 'Viewer' }
export type AreaRecord = { id: number; area_id: string; name: string; latitude: number; longitude: number; population_affected: number; severity: number; injured_people: number; trapped_people: number; emergency_requests: number; accessibility: number; distance_to_resource_center: number; priority_score: number; priority_class: string; status: string }
export type ResourceRecord = { id: number; resource_key: string; name: string; total: number; available: number; allocated: number; deployed: number; remaining: number; unit: string; center_id: number | null; center_name: string | null; status: string }
export type RequestRecord = { id: number; request_id: string; area_id: string; area_name: string; request_type: string; severity: string; people_affected: number; status: string; timestamp: string }
export type AlertRecord = { id: number; alert_id: string; severity: string; title: string; message: string; area_id: string | null; is_read: boolean; timestamp: string }
export type OptimizationRun = { id: number; status: string; fitness: number; generations: number; parameters: Record<string, number>; created_at: string }

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api'
const TOKEN_KEY = 'resqai.access_token'
const USER_KEY = 'resqai.user'

function responseError(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') return fallback
  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (typeof item === 'string') return item
      if (!item || typeof item !== 'object') return String(item)
      const error = item as { loc?: unknown[]; msg?: unknown }
      const location = Array.isArray(error.loc) ? error.loc.filter(part => part !== 'body').join('.') : ''
      const message = typeof error.msg === 'string' ? error.msg : 'Invalid value'
      return location ? `${location}: ${message}` : message
    })
    if (messages.length) return messages.join('; ')
  }
  if (detail && typeof detail === 'object') {
    const error = detail as { message?: unknown; msg?: unknown }
    if (typeof error.message === 'string') return error.message
    if (typeof error.msg === 'string') return error.msg
    try { return JSON.stringify(detail) } catch { return fallback }
  }
  return fallback
}

export function getSessionUser(): User | null {
  try { return JSON.parse(localStorage.getItem(USER_KEY) ?? 'null') as User | null } catch { return null }
}
export function clearSession() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY) }
export async function login(email: string, password: string): Promise<User> {
  const response = await fetch(`${API_BASE}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(responseError(payload, 'Unable to sign in. Check that the Sahaaya API is running.'))
  localStorage.setItem(TOKEN_KEY, payload.access_token)
  localStorage.setItem(USER_KEY, JSON.stringify(payload.user))
  return payload.user as User
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY)
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers: { ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers } })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(responseError(payload, `Request failed (${response.status})`))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
export function downloadCsv(path: string, filename: string) {
  return apiBlob(path).then(blob => { const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url) })
}
async function apiBlob(path: string) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) ?? ''}` } })
  if (!response.ok) throw new Error('The report could not be generated.')
  return response.blob()
}
