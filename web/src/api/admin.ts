import { get, getToken, post, put } from './client'

/** Карточка предприятия (как в листе «Админ» 7.1). */
export interface CompanyData {
  full_name: string | null
  short_name: string | null
  legal_address: string | null
  postal_address: string | null
  phone: string | null
  email: string | null
  inn_kpp: string | null
  ogrn: string | null
  director: string | null
  bank: string | null
  bik: string | null
  account: string | null
  corr_account: string | null
}

export interface AdminUser {
  id: number
  username: string
  full_name: string | null
  role: 'admin' | 'user'
  active: boolean
}

export interface AuditRow {
  id: number
  ts: string
  user_id: number | null
  username: string | null
  action: string
  entity: string
  entity_id: string | null
  changes: string | null
}

export interface AuditPage {
  rows: AuditRow[]
  total: number
}

export interface AuditParams {
  user_id?: number
  action?: string
  date_from?: string
  date_to?: string
  q?: string
  page?: number
  size?: number
}

function toQs(params: object): string {
  const qs = new URLSearchParams()
  Object.entries(params as Record<string, unknown>).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  })
  return qs.toString()
}

export const getCompany = () => get<CompanyData | null>('/api/company')
export const saveCompany = (data: Partial<CompanyData>) => put<CompanyData>('/api/company', data)

export const listAdminUsers = () => get<AdminUser[]>('/api/admin/users')
export const createAdminUser = (body: {
  username: string
  password: string
  full_name?: string
  role: 'admin' | 'user'
}) => post<AdminUser>('/api/admin/users', body)
export const updateAdminUser = (id: number, body: {
  full_name?: string
  role?: 'admin' | 'user'
  active?: boolean
  password?: string
}) => put<AdminUser>(`/api/admin/users/${id}`, body)

export interface Setting {
  key: string
  value: string
}

export const listSettings = () => get<Setting[]>('/api/admin/settings')
export const saveSetting = (key: string, value: string) => put<Setting>('/api/admin/settings', { key, value })

export const fetchAudit = (params: AuditParams) => {
  const qs = toQs(params)
  return get<AuditPage>(`/api/admin/audit${qs ? `?${qs}` : ''}`)
}

/** Скачать резервную копию базы (Blob). */
export async function downloadBackup(): Promise<void> {
  const token = getToken()
  const res = await fetch('/api/admin/backup', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`Ошибка копирования (${res.status})`)
  const blob = await res.blob()
  const dispo = res.headers.get('content-disposition') ?? ''
  const m = dispo.match(/filename\*=utf-8''([^;]+)/i)
  const fname = m ? decodeURIComponent(m[1]) : 'склад_резервная_копия.db'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fname
  a.click()
  URL.revokeObjectURL(url)
}

// ---------- Миграция 7.1 ----------

export interface MigrateSkippedRow {
  row: number
  reason: string
}

export interface MigrateSection {
  name: string
  total: number
  created: number
  kept: number
  updated: number
  imported: number
  documents: number
  fields: number
  skipped_rows: MigrateSkippedRow[]
}

export interface MigrateReport {
  ok: boolean
  sections: MigrateSection[]
  created: {
    categories: string[]
    units: string[]
    partners: string[]
    items: string[]
    users: { username: string; password: string }[]
  }
  documents: { total: number; by_type: Record<string, number> }
  stock_check: {
    checked: number
    mismatches: { item: string; expected: number; imported: number; diff: number }[]
  }
  warnings: string[]
}

/** Импортировать файл 7.1 (.xlsm/.xlsx). Возвращает отчёт о переносе. */
export async function importMigrate(file: File): Promise<MigrateReport> {
  const token = getToken()
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/admin/migrate/import', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    let detail: unknown = null
    try { detail = (await res.json()).detail } catch { /* не JSON */ }
    throw new Error(typeof detail === 'string' ? detail : `Импорт не выполнен (${res.status})`)
  }
  return res.json()
}

/** Скачать текущие данные в формате листов 7.1. */
export async function downloadMigrateExport(): Promise<void> {
  const token = getToken()
  const res = await fetch('/api/admin/migrate/export', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`Ошибка экспорта (${res.status})`)
  const blob = await res.blob()
  const dispo = res.headers.get('content-disposition') ?? ''
  const m = dispo.match(/filename\*=utf-8''([^;]+)/i)
  const fname = m ? decodeURIComponent(m[1]) : 'Склад ПРО 7.1.xlsx'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fname
  a.click()
  URL.revokeObjectURL(url)
}

/** Восстановить базу из файла (перезагружает приложение после успеха). */
export async function restoreBackup(file: File): Promise<void> {
  const token = getToken()
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/admin/restore', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    let detail: unknown = null
    try { detail = (await res.json()).detail } catch { /* не JSON */ }
    throw new Error(typeof detail === 'string' ? detail : `Ошибка восстановления (${res.status})`)
  }
  window.location.href = '/'
}
