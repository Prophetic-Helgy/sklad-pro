import { get, getToken } from './client'

/** Метаданные колонки отчёта (сервер строит таблицу по ним). */
export interface ReportColumn {
  key: string
  title: string
  kind?: 'text' | 'number' | 'money' | 'percent' | null
  align?: 'left' | 'right' | null
  width?: number | null
}

/** Страница отчёта. rows — списки значений в порядке columns. */
export interface ReportData {
  title: string
  period: string | null
  columns: ReportColumn[]
  rows: (string | number | null)[][]
  totals: (string | number | null)[] | null
  total: number
}

export type ReportKind = 'balance' | 'movement' | 'turnover' | 'below_min' | 'abc' | 'turnover_speed'

export interface ReportParams {
  date_from?: string
  date_to?: string
  as_of?: string
  warehouse_id?: number
  doc_type?: string
  q?: string
  page?: number
}

function toQs(params: object): string {
  const qs = new URLSearchParams()
  Object.entries(params as Record<string, unknown>).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  })
  return qs.toString()
}

export function fetchReport(kind: ReportKind, params: ReportParams): Promise<ReportData> {
  const qs = toQs(params)
  return get<ReportData>(`/api/reports/${kind}${qs ? `?${qs}` : ''}`)
}

/** Экспорт отчёта в файл (Excel/PDF) с сохранением через браузер. */
export async function downloadReport(kind: ReportKind, fmt: 'excel' | 'pdf', params: ReportParams): Promise<void> {
  const { page: _page, ...rest } = params
  const qs = toQs(rest)
  const token = getToken()
  const res = await fetch(`/api/reports/${kind}/export?fmt=${fmt}${qs ? `&${qs}` : ''}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`Ошибка экспорта (${res.status})`)
  const blob = await res.blob()
  const dispo = res.headers.get('content-disposition') ?? ''
  const m = dispo.match(/filename\*=utf-8''([^;]+)/i)
  const fname = m ? decodeURIComponent(m[1]) : `Отчёт.${fmt === 'excel' ? 'xlsx' : 'pdf'}`
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fname
  a.click()
  URL.revokeObjectURL(url)
}
