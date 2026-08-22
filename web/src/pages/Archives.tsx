import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Empty, Input, Select, Space, Table, Tag } from 'antd'
import { ArrowLeftOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'
import { listDocs, type Doc, type DocType } from '../api/documents'

const TYPE_LABELS: Record<DocType, string> = {
  in: 'Приход',
  out: 'Расход',
  writeoff: 'Списание',
  transfer: 'Перемещение',
  inventory: 'Инвентаризация',
}

/** Архивы: отменённые документы (в 7.1 — лист «Архив»). */
export default function Archives() {
  const navigate = useNavigate()
  const [type, setType] = useState<DocType | 'all'>('all')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [docs, setDocs] = useState<Doc[]>([])
  const [total, setTotal] = useState(0)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    setBusy(true)
    try {
      const res = await listDocs({ status: 'cancelled', q, page, ...(type !== 'all' ? { type } : {}) })
      setDocs(res.documents)
      setTotal(res.total)
    } finally {
      setBusy(false)
    }
  }, [type, q, page])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const cols = [
    { title: 'Дата', dataIndex: 'date', width: 110, render: (v: string) => dayjs(v).format('DD.MM.YYYY') },
    { title: 'Номер', dataIndex: 'number', width: 180, render: (v: string | null) => v || '—' },
    {
      title: 'Тип', dataIndex: 'type', width: 130,
      render: (v: DocType) => <Tag color="blue">{TYPE_LABELS[v] ?? v}</Tag>,
    },
    { title: 'Контрагент', dataIndex: 'partner_name', render: (v: string | null) => v || '—' },
    { title: 'Склад', dataIndex: 'warehouse_name', width: 160, render: (v: string | null) => v || '—' },
    { title: 'Причина / примечание', key: 'reason', render: (_v: unknown, d: Doc) => d.reason || d.notes || '—' },
    {
      title: 'Отменён', dataIndex: 'posted_at', width: 150,
      render: (_v: unknown, d: Doc) => (d.posted_at ? dayjs(d.posted_at).format('DD.MM.YYYY HH:mm') : '—'),
    },
  ]

  return (
    <div>
      <h2 style={{ margin: '0 0 16px' }}>Архивы</h2>
      <Card size="small">
        <Space wrap style={{ marginBottom: 12 }}>
          <Select
            style={{ width: 180 }}
            value={type}
            onChange={(v) => { setType(v); setPage(1) }}
            options={[{ value: 'all', label: 'Все типы' }, ...Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label }))]}
          />
          <Button type="text" icon={<ArrowLeftOutlined />} title="Назад в главное меню" onClick={() => navigate('/')} />
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="Номер, накладная, контрагент…"
            style={{ width: 280 }}
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1) }}
          />
        </Space>
        <Table
          rowKey="id"
          size="middle"
          loading={busy}
          columns={cols}
          dataSource={docs}
          locale={{ emptyText: <Empty description="Отменённых документов нет" /> }}
          onRow={(d) => ({ onClick: () => navigate(`/docs/${d.type}/${d.id}`), style: { cursor: 'pointer' } })}
          pagination={{
            current: page,
            pageSize: 50,
            total,
            showTotal: (t) => `Всего в архиве: ${t}`,
            onChange: (p) => setPage(p),
          }}
        />
      </Card>
    </div>
  )
}
