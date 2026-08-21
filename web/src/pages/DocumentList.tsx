import { useCallback, useEffect, useState } from 'react'
import { Button, Input, Space, Table, Tag } from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { listDocs, type Doc, type DocType } from '../api/documents'

const TITLES: Record<DocType, { title: string; newLabel: string }> = {
  in: { title: 'Приход', newLabel: 'Новый приход' },
  out: { title: 'Расход', newLabel: 'Новый расход' },
  writeoff: { title: 'Списание', newLabel: 'Новое списание' },
  transfer: { title: 'Перемещение', newLabel: 'Новое перемещение' },
  inventory: { title: 'Инвентаризация', newLabel: 'Новая инвентаризация' },
}

const STATUS_TAG: Record<Doc['status'], { color: string; label: string }> = {
  draft: { color: 'default', label: 'Черновик' },
  posted: { color: 'green', label: 'Проведён' },
  cancelled: { color: 'red', label: 'Отменён' },
}

/** Список документов выбранного типа (в 7.1 — листы «Приход», «Расход», «Списание»). */
export default function DocumentList() {
  const { type = 'in' } = useParams() as { type: DocType }
  const cfg = TITLES[type] ?? TITLES.in
  const navigate = useNavigate()

  const [docs, setDocs] = useState<Doc[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    setBusy(true)
    try {
      const res = await listDocs({ type, q, page })
      setDocs(res.documents)
      setTotal(res.total)
    } finally {
      setBusy(false)
    }
  }, [type, q, page])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const sum = (d: Doc) => d.items.reduce((s, li) => s + (li.qty * (li.price ?? 0)), 0)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>{cfg.title}</h2>
        <Space>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="Номер, накладная, контрагент…"
            style={{ width: 280 }}
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1) }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate(`/docs/${type}/new`)}>
            {cfg.newLabel}
          </Button>
        </Space>
      </div>

      <Table
        rowKey="id"
        size="middle"
        loading={busy}
        dataSource={docs}
        onRow={(d) => ({ onClick: () => navigate(`/docs/${type}/${d.id}`), style: { cursor: 'pointer' } })}
        pagination={{
          current: page,
          pageSize: 50,
          total,
          showTotal: (t) => `Всего: ${t}`,
          onChange: (p) => setPage(p),
        }}
        columns={[
          {
            title: 'Номер', dataIndex: 'number', width: 150,
            render: (v: string | null) => (v ? v : <Tag>Черновик</Tag>),
          },
          { title: 'Дата', dataIndex: 'date', width: 110 },
          { title: 'Контрагент', dataIndex: 'partner_name', ellipsis: true, render: (v) => v ?? '—' },
          { title: 'Накладная', dataIndex: 'doc_ref', width: 130, render: (v) => v ?? '—' },
          {
            title: 'Сумма, руб.', key: 'sum', width: 130, align: 'right',
            render: (_v, d) => (sum(d) ? sum(d).toLocaleString('ru-RU') : '—'),
          },
          {
            title: 'Статус', dataIndex: 'status', width: 110,
            render: (v: Doc['status']) => <Tag color={STATUS_TAG[v].color}>{STATUS_TAG[v].label}</Tag>,
          },
        ]}
      />
    </div>
  )
}
