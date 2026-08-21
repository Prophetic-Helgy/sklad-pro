import { get } from './client'
import type { DocType } from './documents'

/** Строка реестра: построчный журнал проведённых документов (в 7.1 — Reestr*). */
export interface JournalRow {
  doc_id: number
  doc_number: string | null
  date: string
  item_id: number
  item_name: string
  sku: string
  category_name: string | null
  qty: number
  unit_name: string | null
  partner_name: string | null
  doc_ref: string | null
  out_by_name: string | null
  received_by: string | null
  reason: string | null
  warehouse_name: string | null
  warehouse_from_name: string | null
  warehouse_to_name: string | null
  note: string | null
}

export const listRegistry = (
  type: DocType,
  params: { date_from?: string; date_to?: string; partner_id?: number; q?: string; page?: number } = {},
) =>
  get<{ rows: JournalRow[]; total: number }>(`/api/registry/${type}?` + new URLSearchParams({
    ...(params.date_from ? { date_from: params.date_from } : {}),
    ...(params.date_to ? { date_to: params.date_to } : {}),
    ...(params.partner_id ? { partner_id: String(params.partner_id) } : {}),
    ...(params.q ? { q: params.q } : {}),
    page: String(params.page ?? 1),
  }))
