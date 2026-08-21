/**
 * Клиент API «Склад ПРО».
 * В dev-режиме vite проксирует /api на сервер (8700),
 * в production/Electron — тот же origin.
 */

const TOKEN_KEY = 'sklad_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number
  code?: string
  constructor(message: string, status: number, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

/** Универсальный запрос к API с токеном. */
export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const res = await fetch(path, { ...options, headers })
  if (res.status === 401 && !path.startsWith('/api/auth/login')) {
    setToken(null)
    window.location.href = '/login'
    throw new ApiError('Сессия истекла', 401)
  }
  if (!res.ok) {
    let detail: unknown = null
    try { detail = (await res.json()).detail } catch { /* не JSON */ }
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const d = detail as { message: string; code?: string }
      throw new ApiError(d.message, res.status, d.code)
    }
    throw new ApiError(typeof detail === 'string' ? detail : `Ошибка ${res.status}`, res.status)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const get = <T = unknown>(path: string) => api<T>(path)
export const post = <T = unknown>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
export const put = <T = unknown>(path: string, body: unknown) =>
  api<T>(path, { method: 'PUT', body: JSON.stringify(body) })
export const del = <T = unknown>(path: string) => api<T>(path, { method: 'DELETE' })
