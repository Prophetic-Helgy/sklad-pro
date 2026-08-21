import { del, get, post, put } from './client'

// ---------- Типы ----------
export interface Unit { id: number; name: string }
export interface Category { id: number; name: string; parent_id: number | null }
export interface Warehouse { id: number; name: string; active: boolean }

export interface Item {
  id: number
  name: string
  sku: string
  barcode: string | null
  unit_id: number
  category_id: number | null
  min_qty: number
  cost_price: number
  sale_price: number
  default_partner_id: number | null
  notes: string | null
  active: boolean
  unit_name?: string | null
  category_name?: string | null
  default_partner_name?: string | null
}

export interface Partner {
  id: number
  kind: 'supplier' | 'customer' | 'both'
  full_name: string
  short_name: string | null
  legal_address: string | null
  postal_address: string | null
  phone: string | null
  email: string | null
  inn: string | null
  ogrn: string | null
  notes: string | null
  active: boolean
}

// ---------- Ед. изм ----------
export const listUnits = () => get<Unit[]>('/api/units')
export const createUnit = (d: { name: string }) => post<Unit>('/api/units', d)
export const updateUnit = (id: number, d: { name: string }) => put<Unit>(`/api/units/${id}`, d)
export const deleteUnit = (id: number) => del<void>(`/api/units/${id}`)

// ---------- Категории ----------
export const listCategories = () => get<Category[]>('/api/categories')
export const createCategory = (d: { name: string; parent_id: number | null }) => post<Category>('/api/categories', d)
export const updateCategory = (id: number, d: { name: string; parent_id: number | null }) =>
  put<Category>(`/api/categories/${id}`, d)
export const deleteCategory = (id: number) => del<void>(`/api/categories/${id}`)

// ---------- Товары ----------
export const listItems = (params: { q?: string; category_id?: number; page?: number; include_inactive?: boolean }) =>
  get<{ items: Item[]; total: number }>('/api/items?' + new URLSearchParams({
    ...(params.q ? { q: params.q } : {}),
    ...(params.category_id ? { category_id: String(params.category_id) } : {}),
    ...(params.include_inactive ? { include_inactive: 'true' } : {}),
    page: String(params.page ?? 1),
  }))
export const listItemsBrief = (q?: string) =>
  get<Item[]>('/api/items/brief?' + new URLSearchParams({ ...(q ? { q } : {}), limit: '20' }))
export const createItem = (d: Partial<Item>) => post<Item>('/api/items', d)
export const updateItem = (id: number, d: Partial<Item>) => put<Item>(`/api/items/${id}`, d)
export const deleteItem = (id: number) => del<void>(`/api/items/${id}`)
export const deactivateItem = (id: number) => post<Item>(`/api/items/${id}/deactivate`)

// ---------- Контрагенты ----------
export const listPartners = (q?: string, kind?: 'supplier' | 'customer' | 'both') =>
  get<Partner[]>('/api/partners?' + new URLSearchParams({
    ...(q ? { q } : {}),
    ...(kind ? { kind } : {}),
  }))
export const createPartner = (d: Partial<Partner>) => post<Partner>('/api/partners', d)
export const updatePartner = (id: number, d: Partial<Partner>) => put<Partner>(`/api/partners/${id}`, d)
export const deletePartner = (id: number) => del<void>(`/api/partners/${id}`)

// ---------- Склады ----------
export const listWarehouses = () => get<Warehouse[]>('/api/warehouses')
export const createWarehouse = (d: { name: string; active: boolean }) => post<Warehouse>('/api/warehouses', d)
export const updateWarehouse = (id: number, d: { name: string; active: boolean }) =>
  put<Warehouse>(`/api/warehouses/${id}`, d)
export const deleteWarehouse = (id: number) => del<void>(`/api/warehouses/${id}`)
