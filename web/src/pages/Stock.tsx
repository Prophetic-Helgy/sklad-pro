import { useCallback, useEffect, useState } from 'react'
import { Checkbox, Input, Select, Space, Table, Tag } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { listStock, type StockRow } from '../api/stock'
import { listWarehouses, type Warehouse } from '../api/references'

/** Экран «Склад» — текущие остатки по позициям и складам (в 7.1 — расчётные формулы). */
export default function Stock() {
  const [rows, setRows] = useState<StockRow[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [wh, setWh] = useState<number | undefined>(undefined)
  const [belowOnly, setBelowOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState(false)
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])

  useEffect(() => {
    listWarehouses().then(setWarehouses).catch(() => undefined)
  }, [])

  const refresh = useCallback(async () => {
    setBusy(true)
    try {
      const res = await listStock({ q, warehouse_id: wh, below_min_only: belowOnly, page })
      setRows(res.rows)
      setTotal(res.total)
    } finally {
      setBusy(false)
    }
  }, [q, wh, belowOnly, page])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const totalSum = rows.reduce((s, r) => s + r.sum_cost, 0)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>Склад — остатки</h2>
        <Space wrap>
          <Select
            allowClear
            placeholder="Все склады"
            style={{ width: 180 }}
            value={wh}
            onChange={(v) => { setWh(v); setPage(1) }}
            options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
          />
          <Checkbox
            checked={belowOnly}
            onChange={(e) => { setBelowOnly(e.target.checked); setPage(1) }}
          >
            Ниже минимума
          </Checkbox>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="Наименование, артикул, штрих-код…"
            style={{ width: 280 }}
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1) }}
          />
        </Space>
      </div>

      <Table
        rowKey={(r) => `${r.item_id}-${r.warehouse_id}`}
        size="middle"
        loading={busy}
        dataSource={rows}
        pagination={{
          current: page,
          pageSize: 50,
          total,
          showTotal: (t) => `Всего: ${t}`,
          onChange: (p) => setPage(p),
        }}
        scroll={{ x: 'max-content' }}
        columns={[
          { title: 'Артикул', dataIndex: 'sku', width: 110 },
          { title: 'Наименование', dataIndex: 'item_name', ellipsis: true },
          { title: 'Ед. изм.', dataIndex: 'unit_name', width: 90 },
          { title: 'Склад', dataIndex: 'warehouse_name', width: 150 },
          {
            title: 'Остаток', dataIndex: 'qty', width: 110, align: 'right',
            render: (v: number, r) => (
              <span style={{ color: r.below_min ? '#e5484d' : undefined, fontWeight: r.below_min ? 600 : undefined }}>
                {v}
                {r.below_min && <Tag color="red" style={{ marginLeft: 6 }}>ниже мин.</Tag>}
              </span>
            ),
          },
          { title: 'Мин.', dataIndex: 'min_qty', width: 80, align: 'right' },
          { title: 'Резерв', dataIndex: 'reserved_qty', width: 90, align: 'right' },
          { title: 'Себест.', dataIndex: 'cost_price', width: 100, align: 'right' },
          { title: 'Сумма, руб.', dataIndex: 'sum_cost', width: 120, align: 'right' },
        ]}
        summary={() => (
          <Table.Summary fixed>
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={8} align="right">
                Итого по странице:
              </Table.Summary.Cell>
              <Table.Summary.Cell index={1}>
                <b>{totalSum.toLocaleString('ru-RU')}</b>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          </Table.Summary>
        )}
      />
    </div>
  )
}
