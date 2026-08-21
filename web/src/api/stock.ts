import { get } from './client'

export interface StockRow {
  item_id: number
  item_name: string
  sku: string
  unit_name: string | null
  warehouse_id: number
  warehouse_name: string
  qty: number
  reserved_qty: number
  cost_price: number
  sum_cost: number
  min_qty: number
  below_min: boolean
}

export const listStock = (params: { warehouse_id?: number; q?: string; below_min_only?: boolean; page?: number; size?: number }) =>
  get<{ rows: StockRow[]; total: number }>('/api/stock?' + new URLSearchParams({
    ...(params.warehouse_id ? { warehouse_id: String(params.warehouse_id) } : {}),
    ...(params.q ? { q: params.q } : {}),
    ...(params.below_min_only ? { below_min_only: 'true' } : {}),
    page: String(params.page ?? 1),
    size: String(params.size ?? 50),
  }))
