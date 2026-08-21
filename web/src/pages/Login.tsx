import { useState } from 'react'
import { Alert, Button, Card, Input, Typography } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { login, me, type User } from '../api/auth'

interface Props {
  onLogin: (user: User) => void
}

/** Экран входа (в 7.1 — форма «Авторизация»). */
export default function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit() {
    if (!username || !password) {
      setError('Введите логин и пароль')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await login(username, password)
      const user = await me()
      onLogin(user)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка входа')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <Card className="login-card">
        <Typography.Title level={3} style={{ textAlign: 'center', marginTop: 0 }}>
          Склад ПРО
        </Typography.Title>
        <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', marginBottom: 24 }}>
          Складской учёт
        </Typography.Text>
        {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Input
            size="large"
            prefix={<UserOutlined />}
            placeholder="Логин"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onPressEnter={submit}
          />
          <Input.Password
            size="large"
            prefix={<LockOutlined />}
            placeholder="Пароль"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onPressEnter={submit}
          />
          <Button type="primary" size="large" loading={busy} onClick={submit}>
            Войти
          </Button>
        </div>
      </Card>
    </div>
  )
}
