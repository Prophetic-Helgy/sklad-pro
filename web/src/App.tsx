import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { App as AntApp, Button, Layout, Spin, Typography } from 'antd'
import { me, logout, type User } from './api/auth'
import { getToken } from './api/client'
import Login from './pages/Login'
import Home from './pages/Home'
import Items from './pages/Items'
import Partners from './pages/Partners'
import References from './pages/References'
import Stock from './pages/Stock'
import DocumentList from './pages/DocumentList'
import DocumentForm from './pages/DocumentForm'
import InventoryForm from './pages/InventoryForm'
import Registry from './pages/Registry'
import Reports from './pages/Reports'
import Admin from './pages/Admin'
import Archives from './pages/Archives'
import PrintDoc from './pages/PrintDoc'

/** Форма движения: инвентаризация — отдельная, остальные типы — общая. */
function DocRoute() {
  const { type } = useParams() as { type: string }
  if (type === 'inventory') return <InventoryForm />
  return <DocumentForm />
}

/** Каркас приложения: авторизация + общий Layout. */
export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="Загрузка…" />
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login onLogin={setUser} />} />
        <Route
          path="/print/:type/:id"
          element={
            user ? (
              <AntApp>
                <PrintDoc />
              </AntApp>
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
        <Route
          path="/*"
          element={
            user ? (
              <AntApp>
              <Layout style={{ minHeight: '100vh' }}>
                <Layout.Header className="app-header" style={{ padding: 0 }}>
                  <span className="app-title">Склад ПРО</span>
                  <span>
                    {user.full_name || user.username}
                    {user.role === 'admin' && ' (администратор)'}
                    <Button
                      size="small"
                      style={{ marginLeft: 12 }}
                      onClick={() => {
                        logout()
                        setUser(null)
                        window.location.href = '/login'
                      }}
                    >
                      Выйти
                    </Button>
                  </span>
                </Layout.Header>
                <Layout.Content className="app-content">
                  <Routes>
                    <Route path="/" element={<Home user={user} />} />
                    <Route path="/items" element={<Items />} />
                    <Route path="/partners" element={<Partners />} />
                    <Route path="/refs" element={<References />} />
                    <Route path="/stock" element={<Stock />} />
                    <Route path="/docs/:type" element={<DocumentList />} />
                    <Route path="/docs/:type/new" element={<DocRoute />} />
                    <Route path="/docs/:type/:id" element={<DocRoute />} />
                    <Route path="/registry/:type" element={<Registry />} />
                    <Route path="/reports" element={<Reports />} />
                    <Route path="/reports/:preset" element={<Reports />} />
                    <Route path="/admin" element={<Admin />} />
                    <Route path="/archives" element={<Archives />} />
                    <Route
                      path="*"
                      element={
                        <Typography.Text type="secondary">Раздел в разработке</Typography.Text>
                      }
                    />
                  </Routes>
                </Layout.Content>
              </Layout>
              </AntApp>
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
