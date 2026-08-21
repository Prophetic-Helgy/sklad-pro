import { get } from './client'

/** Карточка предприятия (на печатных формах: «От кого» и шапка). */
export interface Company {
  full_name: string | null
  short_name: string | null
  legal_address: string | null
  phone: string | null
  email: string | null
  inn_kpp: string | null
  ogrn: string | null
  director: string | null
}

export const getCompany = () => get<Company | null>('/api/company')
