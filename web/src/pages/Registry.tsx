import { useCallback, useEffect, useState } from 'react'
import { DatePicker, Input, Select, Space, Table, type GetProps, type TableProps } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { listRegistry, type JournalRow } from '../api/registry'
import { listPartners, type Partner } from '../api/references'
import type { DocType } from '../api/documents'

const TITLES: Record<string, { title: string; partnerLabel?: string }> = {
  in: { title: 'Реестр прихода', partnerLabel: 'Поставщик' },
  out: { title: 'Реестр расхода', partnerLabel: 'Покупатель' },
  writeoff: { title: 'Реестр списания', partnerLabel: 'Поставщик' },
  transfer: { title: 'Реестр перемещений' },
}

type RangeValue = GetProps<typeof DatePicker.RangePicker>['value']

/** Реестр — построчный журнал проведённых документов (в 7.1 — листы Reestr*). */
export default function Registry() {
  const { type = 'in' } = useParams()
  const cfg = TITLES[type] ?? TITLES.in
  const navigate = useNavigate()

  const [rows, setRows] = useState<JournalRow[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [partnerId, setPartnerId] = useState<number | undefined>(undefined)
  const [range, setRange] = useState<RangeValue>(null)
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState(false)
  const [partners, setPartners] = useState<Partner[]>([])

  useEffect(() => {
    if (cfg.partnerLabel) listPartners(undefined, undefined).then(setPartners).catch(() => undefined)
  }, [type]) // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(async () => {
    setBusy(true)
    try {
      const res = await listRegistry(type as DocType, {
        q,
        partner_id: partnerId,
        date_from: range?.[0]?.format('YYYY-MM-DD'),
        date_to: range?.[1]?.format('YYYY-MM-DD'),
        page,
      })
      setRows(res.rows)
      setTotal(res.total)
    } finally {
      setBusy(false)
    }
  }, [type, q, partnerId, range, page])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const sumQty = rows.reduce((s, r) => s + r.qty, 0)

  const cols: NonNullable<TableProps<JournalRow>['columns']> = [
    { title: 'Дата', dataIndex: 'date', width: 110 },
    {
      title: 'Номер', dataIndex: 'doc_number', width: 150,
      render: (v: string | null) => v ?? '—',
    },
    { title: 'Наименование', dataIndex: 'item_name', ellipsis: true },
    { title: 'Артикул', dataIndex: 'sku', width: 110 },
    { title: 'Категория', dataIndex: 'category_name', width: 120, render: (v: string | null) => v ?? '—' },
    {
      title: 'Кол-во', dataIndex: 'qty', width: 100, align: 'right',
    },
    { title: 'Ед. изм.', dataIndex: 'unit_name', width: 80 },
    ...(type === 'transfer' ? [
      {
        title: 'Перемещение', key: 'wh', width: 220,
        render: (_v: unknown, r: JournalRow) => `${r.warehouse_from_name ?? '—'} → ${r.warehouse_to_name ?? '—'}`,
      },
    ] : [
      { title: 'Склад', dataIndex: 'warehouse_name', width: 130, render: (v: string | null) => v ?? '—' },
    ]),
    ...(cfg.partnerLabel ? [
      { title: cfg.partnerLabel, dataIndex: 'partner_name', ellipsis: true, render: (v: string | null) => v ?? '—' },
    ] : []),
    ...(type === 'out' ? [
      { title: 'Отпустил', dataIndex: 'out_by_name', width: 140, render: (v: string | null) => v ?? '—' },
      { title: 'Получил', dataIndex: 'received_by', width: 140, render: (v: string | null) => v ?? '—' },
    ] : []),
    ...(type === 'writeoff' ? [
      { title: 'Причина списания', dataIndex: 'reason', ellipsis: true, render: (v: string | null) => v ?? '—' },
    ] : []),
    { title: 'Накладная', dataIndex: 'doc_ref', width: 120, render: (v: string | null) => v ?? '—' },
    { title: 'Комментарий', dataIndex: 'note', ellipsis: true, render: (v: string | null) => v ?? '—' },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>{cfg.title}</h2>
        <Space wrap>
          <DatePicker.RangePicker
            value={range}
            onChange={(v) => { setRange(v); setPage(1) }}
          />
          {cfg.partnerLabel && (
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder={cfg.partnerLabel}
              style={{ width: 200 }}
              value={partnerId}
              onChange={(v) => { setPartnerId(v); setPage(1) }}
              options={partners.map((p) => ({ value: p.id, label: p.full_name }))}
            />
          )}
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="Наименование, артикул, номер, накладная…"
            style={{ width: 280 }}
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1) }}
          />
        </Space>
      </div>

      <Table
        rowKey={(r) => `${r.doc_id}-${r.item_id}`}
        size="middle"
        loading={busy}
        dataSource={rows}
        onRow={(r) => ({ onClick: () => navigate(`/docs/${type}/${r.doc_id}`), style: { cursor: 'pointer' } })}
        pagination={{
          current: page,
          pageSize: 50,
          total,
          showTotal: (t) => `Всего строк: ${t}`,
          onChange: (p) => setPage(p),
        }}
        scroll={{ x: 'max-content' }}
        columns={cols}
        summary={() => (
          <Table.Summary fixed>
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={5} align="right">
                Итого по странице (кол-во):
              </Table.Summary.Cell>
              <Table.Summary.Cell index={5}>
                <b>{sumQty.toLocaleString('ru-RU')}</b>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={6} colSpan={10} />
            </Table.Summary.Row>
          </Table.Summary>
        )}
      />
    </div>
  )
}
