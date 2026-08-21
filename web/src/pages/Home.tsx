import { Button, Col, Row, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { User } from '../api/auth'

interface Props {
  user: User
}

/**
 * Главная страница — главное меню (разметка 1-в-1 как в Excel 7.1).
 */
const MENU: { label: string; path: string; adminOnly?: boolean }[] = [
  { label: 'Номенклатура', path: '/items' },
  { label: 'Склад', path: '/stock' },
  { label: 'Поставщики', path: '/partners' },
  { label: 'Справочники', path: '/refs' },
  { label: 'Приход', path: '/docs/in' },
  { label: 'Реестр прихода', path: '/registry/in' },
  { label: 'Отчет по приходу', path: '/reports/in' },
  { label: 'Расход', path: '/docs/out' },
  { label: 'Реестр расхода', path: '/registry/out' },
  { label: 'Отчет по расходу', path: '/reports/out' },
  { label: 'Списание', path: '/docs/writeoff' },
  { label: 'Реестр списания', path: '/registry/writeoff' },
  { label: 'Отчет по списанию', path: '/reports/writeoff' },
  { label: 'Перемещение', path: '/docs/transfer' },
  { label: 'Реестр перемещений', path: '/registry/transfer' },
  { label: 'Инвентаризация', path: '/docs/inventory' },
  { label: 'Админ', path: '/admin', adminOnly: true },
  { label: 'Архивы', path: '/archives' },
]

export default function Home({ user }: Props) {
  const navigate = useNavigate()
  const items = MENU.filter((m) => !m.adminOnly || user.role === 'admin')

  return (
    <div>
      <Typography.Title level={3} style={{ textAlign: 'center', marginBottom: 32 }}>
        Главное меню
      </Typography.Title>
      <Row gutter={[16, 16]} justify="center">
        {items.map((m) => (
          <Col key={m.path} xs={12} sm={8} md={6} lg={4}>
            <Button
              block
              size="large"
              onClick={() => navigate(m.path)}
              style={{ height: 64, fontSize: 15 }}
            >
              {m.label}
            </Button>
          </Col>
        ))}
      </Row>
    </div>
  )
}
