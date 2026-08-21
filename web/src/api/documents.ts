import { del, get, post, put } from './client'

// ---------- Типы ----------
export type DocType = 'in' | 'out' | 'writeoff' | 'transfer' | 'inventory'
export type DocStatus = 'draft' | 'posted' | 'cancelled'

export interface DocItem {
  id?: number
  item_id: number
  item_name?: string
  unit_name?: string | null
  warehouse_from_id?: number | null
  warehouse_from_name?: string | null
  warehouse_to_id?: number | null
  warehouse_to_name?: string | null
  qty: number
  price?: number | null
  note?: string | null
}

export interface InventoryResultRow {
  id?: number
  item_id: number
  item_name?: string
  unit_name?: string | null
  counted_qty: number
  diff_qty?: number | null
}

export interface Doc {
  id: number
  type: DocType
  number: string | null
  date: string
  status: DocStatus
  partner_id?: number | null
  partner_name?: string | null
  doc_ref?: string | null
  out_by_id?: number | null
  out_by_name?: string | null
  received_by?: string | null
  reason?: string | null
  warehouse_id?: number | null
  warehouse_name?: string | null
  source_doc_id?: number | null
  notes?: string | null
  created_at?: string | null
  posted_at?: string | null
  items: DocItem[]
  results: InventoryResultRow[]
}

export interface DocLinePayload {
  item_id: number
  warehouse_from_id?: number | null
  warehouse_to_id?: number | null
  qty: number
  price?: number | null
  note?: string | null
}

export interface DocPayload {
  type: DocType
  date: string
  partner_id?: number | null
  doc_ref?: string | null
  out_by_id?: number | null
  received_by?: string | null
  reason?: string | null
  warehouse_id?: number | null
  source_doc_id?: number | null
  notes?: string | null
  items?: DocLinePayload[]
  results?: { item_id: number; counted_qty: number }[]
}

// ---------- API ----------
export const listDocs = (params: { type?: DocType; status?: DocStatus; q?: string; page?: number }) =>
  get<{ documents: Doc[]; total: number }>('/api/documents?' + new URLSearchParams({
    ...(params.type ? { type: params.type } : {}),
    ...(params.status ? { status: params.status } : {}),
    ...(params.q ? { q: params.q } : {}),
    page: String(params.page ?? 1),
  }))

export const getDoc = (id: number) => get<Doc>(`/api/documents/${id}`)
export const createDoc = (d: DocPayload) => post<Doc>('/api/documents', d)
export const updateDoc = (id: number, d: DocPayload) => put<Doc>(`/api/documents/${id}`, d)
export const deleteDoc = (id: number) => del<void>(`/api/documents/${id}`)
export const postDoc = (id: number) => post<Doc>(`/api/documents/${id}/post`)
export const cancelDoc = (id: number) => post<Doc>(`/api/documents/${id}/cancel`)
