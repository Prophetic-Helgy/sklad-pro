import { useEffect, useState, type ReactNode } from 'react'
import {
  App as AntApp, AutoComplete, Button, Card, Col, DatePicker, InputNumber, Popconfirm,
  Row, Select, Space, Spin, Table, Tag,
} from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { useNavigate, useParams } from 'react-router-dom'
import { cancelDoc, createDoc, getDoc, postDoc, updateDoc } from '../api/documents'
import { listItemsBrief, listWarehouses, type Item, type Warehouse } from '../api/references'
import { listStock } from '../api/stock'

/** Строка инвентаризации: книга (расчётный остаток) vs факт. */
interface InvLine {
  key: number
  itemId: number | null
  itemName: string
  unitName: string
  bookQty: number
  countedQty: number | null
}

let lineKey = 1
const emptyLine = (): InvLine => ({ key: lineKey++, itemId: null, itemName: '', unitName: '', bookQty: 0, countedQty: null })

/** Форма инвентаризации: выбор склада, подсчёт фактических остатков, проведение с корректировкой. */
export default function InventoryForm() {
  const { id } = useParams()
  const docId = id ? Number(id) : null
  const navigate = useNavigate()
  const { message } = AntApp.useApp()

  const [loading, setLoading] = useState(!!docId)
  const [savedId, setSavedId] = useState<number | null>(docId)
  const [status, setStatus] = useState<string | null>(null)
  const [number, setNumber] = useState<string | null>(null)

  const [date, setDate] = useState<Dayjs>(dayjs())
  const [whId, setWhId] = useState<number | undefined>(undefined)
  const [lines, setLines] = useState<InvLine[]>([emptyLine()])
  const [saving, setSaving] = useState(false)

  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [brief, setBrief] = useState<Item[]>([])
  const [bookMap, setBookMap] = useState<Record<number, number>>({})

  useEffect(() => {
    listWarehouses().then(setWarehouses).catch(() => undefined)
    listItemsBrief(undefined).then(setBrief).catch(() => undefined)
  }, [])

  // Книжные остатки по выбранному складу
  useEffect(() => {
    if (!whId) {
      setBookMap({})
      return
    }
    listStock({ warehouse_id: whId, size: 500 })
      .then((r) => setBookMap(Object.fromEntries(r.rows.map((s) => [s.item_id, s.qty]))))
      .catch(() => undefined)
  }, [whId])

  // Загрузка существующего документа
  useEffect(() => {
    if (!docId) return
    getDoc(docId)
      .then((d) => {
        setStatus(d.status)
        setNumber(d.number)
        setDate(dayjs(d.date))
        setWhId(d.warehouse_id ?? undefined)
        if (d.results.length) {
          setLines(d.results.map((r) => ({
            key: lineKey++,
            itemId: r.item_id,
            itemName: r.item_name ?? '',
            unitName: r.unit_name ?? '',
            bookQty: r.diff_qty != null ? r.counted_qty - r.diff_qty : 0,
            countedQty: r.counted_qty,
          })))
        } else {
          setLines([emptyLine()])
        }
      })
      .finally(() => setLoading(false))
  }, [docId])

  const editable = !status || status === 'draft'

  function patchLine(key: number, patch: Partial<InvLine>) {
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  }

  function pickItem(key: number, item: Item) {
    patchLine(key, {
      itemId: item.id,
      itemName: item.name,
      unitName: item.unit_name ?? '',
      bookQty: bookMap[item.id] ?? 0,
    })
  }

  function buildPayload() {
    if (!whId) {
      message.error('Выберите склад')
      return null
    }
    const valid = lines.filter((l) => l.itemId !== null)
    if (!valid.length) {
      message.error('Добавьте хотя бы одну строку с товаром')
      return null
    }
    return {
      type: 'inventory' as const,
      date: date.format('YYYY-MM-DD'),
      warehouse_id: whId,
      results: valid.map((l) => ({ item_id: l.itemId as number, counted_qty: l.countedQty ?? 0 })),
    }
  }

  async function saveDraft(): Promise<number | null> {
    const payload = buildPayload()
    if (!payload) return null
    setSaving(true)
    try {
      const d = savedId ? await updateDoc(savedId, payload) : await createDoc(payload)
      setSavedId(d.id)
      return d.id
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка сохранения')
      return null
    } finally {
      setSaving(false)
    }
  }

  async function onPost() {
    const nid = await saveDraft()
    if (!nid) return
    setSaving(true)
    try {
      const d = await postDoc(nid)
      message.success(`Инвентаризация ${d.number} проведена, расхождения исправлены`)
      navigate('/docs/inventory')
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка проведения')
    } finally {
      setSaving(false)
    }
  }

  async function onCancel() {
    if (!savedId) return
    setSaving(true)
    try {
      const d = await cancelDoc(savedId)
      setStatus(d.status)
      message.success(`Документ ${d.number} отменён`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка отмены')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>
          Инвентаризация
          {number && <Tag color="blue" style={{ marginLeft: 8 }}>{number}</Tag>}
          {status === 'draft' && <Tag style={{ marginLeft: 8 }}>Черновик</Tag>}
          {status === 'posted' && <Tag color="green" style={{ marginLeft: 8 }}>Проведён</Tag>}
          {status === 'cancelled' && <Tag color="red" style={{ marginLeft: 8 }}>Отменён</Tag>}
        </h2>
        {editable ? (
          <Space>
            <Button onClick={() => navigate('/docs/inventory')}>Назад к списку</Button>
            <Button onClick={() => void saveDraft()} loading={saving}>Сохранить черновик</Button>
            <Button type="primary" onClick={() => void onPost()} loading={saving}>Записать (провести)</Button>
          </Space>
        ) : (
          <Space>
            <Button onClick={() => navigate('/docs/inventory')}>Назад к списку</Button>
            <Button onClick={() => window.open(`/print/inventory/${savedId}`, '_blank')}>Печать</Button>
            {status === 'posted' && (
              <Popconfirm title="Отменить инвентаризацию? Корректировки остатков будут отменены." onConfirm={() => void onCancel()}>
                <Button danger loading={saving}>Отменить</Button>
              </Popconfirm>
            )}
          </Space>
        )}
      </div>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 8]}>
          <Col xs={24} sm={8} md={4}>
            <Field label="Дата">
              <DatePicker style={{ width: '100%' }} value={date} onChange={(d) => d && setDate(d)} disabled={!editable} />
            </Field>
          </Col>
          <Col xs={24} sm={8} md={6}>
            <Field label="Склад *">
              <Select
                allowClear
                style={{ width: '100%' }}
                placeholder="Выберите склад"
                value={whId}
                onChange={(v) => setWhId(v)}
                disabled={!editable}
                options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
              />
            </Field>
          </Col>
        </Row>
      </Card>

      <Table
        rowKey="key"
        size="middle"
        dataSource={lines}
        pagination={false}
        scroll={{ x: 'max-content' }}
        columns={[
          {
            title: 'Наименование', key: 'item', width: 320,
            render: (_v, l: InvLine) => (
              <AutoComplete
                style={{ width: '100%' }}
                value={l.itemName}
                placeholder="Наименование или артикул"
                disabled={!editable}
                options={brief
                  .filter((b) => b.id !== l.itemId)
                  .map((b) => ({ value: b.name, label: `${b.name} (${b.sku})` }))}
                onSelect={(value: string) => {
                  const b = brief.find((x) => x.name === value)
                  if (b) pickItem(l.key, b)
                }}
                onChange={(v: string) => {
                  if (l.itemId !== null) patchLine(l.key, { itemId: null, unitName: '', itemName: v, bookQty: 0 })
                  else patchLine(l.key, { itemName: v })
                }}
              />
            ),
          },
          {
            title: 'Кол-во (нач), шт.', key: 'book', width: 150, align: 'right',
            render: (_v, l: InvLine) => (
              <InputNumber
                style={{ width: '100%' }}
                value={l.bookQty}
                onChange={(v) => patchLine(l.key, { bookQty: v ?? 0 })}
                disabled={!editable}
              />
            ),
          },
          {
            title: 'Остаток (факт)', key: 'counted', width: 150,
            render: (_v, l: InvLine) => (
              <InputNumber
                style={{ width: '100%' }} min={0} step="any"
                value={l.countedQty}
                onChange={(v) => patchLine(l.key, { countedQty: v ?? null })}
                disabled={!editable}
              />
            ),
          },
          {
            title: 'Расхождение', key: 'diff', width: 130, align: 'right',
            render: (_v, l: InvLine) => {
              if (l.countedQty == null) return '—'
              const diff = l.countedQty - l.bookQty
              if (diff === 0) return <Tag>0</Tag>
              return (
                <Tag color={diff > 0 ? 'green' : 'red'}>
                  {diff > 0 ? '+' : ''}{diff.toLocaleString('ru-RU')}
                </Tag>
              )
            },
          },
          ...(editable ? [
            {
              title: '', key: 'del', width: 40,
              render: (_v: unknown, l: InvLine) => (
                <Button type="text" danger icon={<DeleteOutlined />} onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))} />
              ),
            },
          ] : []),
        ]}
      />

      {editable && (
        <Button
          icon={<PlusOutlined />}
          style={{ marginTop: 12 }}
          onClick={() => setLines((ls) => [...ls, emptyLine()])}
        >
          Добавить строку
        </Button>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: '#8a90a6', marginBottom: 2 }}>{label}</div>
      {children}
    </div>
  )
}
