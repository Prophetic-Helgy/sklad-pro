import { get, post, setToken } from './client'

export interface User {
  id: number
  username: string
  full_name: string | null
  role: 'admin' | 'user'
  active: boolean
}

export async function login(username: string, password: string): Promise<void> {
  const data = await post<{ access_token: string }>('/api/auth/login', { username, password })
  setToken(data.access_token)
}

export async function me(): Promise<User> {
  return get<User>('/api/auth/me')
}

export function logout() {
  setToken(null)
}

/** Активные пользователи (для поля «Отпустил»). */
export const listUsers = () => get<User[]>('/api/auth/users')
