import { useEffect, useState, type ReactNode } from 'react'
import {
  App as AntApp, AutoComplete, Button, Card, Col, DatePicker, Input,
  InputNumber, Popconfirm, Row, Select, Space, Spin, Table, Tag,
} from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { useNavigate, useParams } from 'react-router-dom'
import {
  cancelDoc, createDoc, getDoc, listDocs, postDoc, updateDoc,
  type Doc, type DocPayload, type DocType,
} from '../api/documents'
import {
  listItemsBrief, listPartners, listWarehouses,
  type Item, type Partner, type Warehouse,
} from '../api/references'
import { listUsers, type User } from '../api/auth'

/** Настройки отображения по типам документов. */
const CFG: Record<string, {
  title: string
  partnerKind?: 'supplier' | 'customer'
  price?: 'cost' | 'sale'
  outBy?: boolean
  reason?: boolean
}> = {
  in: { title: 'Приход', partnerKind: 'supplier', price: 'cost' },
  out: { title: 'Расход', partnerKind: 'customer', price: 'sale', outBy: true },
  writeoff: { title: 'Списание', price: 'cost', reason: true },
  transfer: { title: 'Перемещение' },
}

interface Line {
  key: number
  itemId: number | null
  itemName: string
  unitName: string
  qty: number | null
  price: number | null
  whFrom: number | null
  whTo: number | null
}

let lineKey = 1
const emptyLine = (): Line => ({ key: lineKey++, itemId: null, itemName: '', unitName: '', qty: null, price: null, whFrom: null, whTo: null })

/** Форма движения: черновик → «Записать» (проведение). Поля шапки — как в 7.1. */
export default function DocumentForm() {
  const { type = 'in', id } = useParams()
  const cfg = CFG[type] ?? CFG.in
  const docId = id ? Number(id) : null
  const navigate = useNavigate()
  const { message } = AntApp.useApp()

  const [loading, setLoading] = useState(!!docId)
  const [savedId, setSavedId] = useState<number | null>(docId)
  const [status, setStatus] = useState<Doc['status'] | null>(null)
  const [number, setNumber] = useState<string | null>(null)

  // Шапка
  const [date, setDate] = useState<Dayjs>(dayjs())
  const [partnerId, setPartnerId] = useState<number | undefined>(undefined)
  const [docRef, setDocRef] = useState('')
  const [receivedBy, setReceivedBy] = useState('')
  const [outById, setOutById] = useState<number | undefined>(undefined)
  const [reason, setReason] = useState('')
  const [whId, setWhId] = useState<number | undefined>(undefined)
  const [sourceId, setSourceId] = useState<number | undefined>(undefined)

  // Строки
  const [lines, setLines] = useState<Line[]>([emptyLine()])
  const [brief, setBrief] = useState<Item[]>([])
  const [saving, setSaving] = useState(false)

  // Справочные данные для селектов
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [partners, setPartners] = useState<Partner[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [sourceDocs, setSourceDocs] = useState<Doc[]>([])

  useEffect(() => {
    listWarehouses().then(setWarehouses).catch(() => undefined)
    listPartners(undefined, cfg.partnerKind).then(setPartners).catch(() => undefined)
    if (cfg.outBy) listUsers().then(setUsers).catch(() => undefined)
    // Для «на основании»: последние проведённые документы
    if (!docId) listDocs({ page: 1 }).then((r) => setSourceDocs(r.documents.filter((d) => d.status === 'posted').slice(0, 30))).catch(() => undefined)
  }, [type]) // eslint-disable-line react-hooks/exhaustive-deps

  // Номенклатура для выбора в строках
  useEffect(() => {
    listItemsBrief(undefined).then(setBrief).catch(() => undefined)
  }, [])

  // Загрузка существующего документа
  useEffect(() => {
    if (!docId) return
    getDoc(docId)
      .then((d) => {
        setStatus(d.status)
        setNumber(d.number)
        setDate(dayjs(d.date))
        setPartnerId(d.partner_id ?? undefined)
        setDocRef(d.doc_ref ?? '')
        setReceivedBy(d.received_by ?? '')
        setOutById(d.out_by_id ?? undefined)
        setReason(d.reason ?? '')
        setWhId(d.warehouse_id ?? undefined)
        setLines(
          d.items.length
            ? d.items.map((li) => ({
              key: lineKey++,
              itemId: li.item_id,
              itemName: li.item_name ?? '',
              unitName: li.unit_name ?? '',
              qty: li.qty,
              price: li.price ?? null,
              whFrom: li.warehouse_from_id ?? null,
              whTo: li.warehouse_to_id ?? null,
            }))
            : [emptyLine()],
        )
      })
      .finally(() => setLoading(false))
  }, [docId])

  const editable = !status || status === 'draft'

  function patchLine(key: number, patch: Partial<Line>) {
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  }

  function pickItem(key: number, item: Item) {
    patchLine(key, {
      itemId: item.id,
      itemName: item.name,
      unitName: item.unit_name ?? '',
      price: null, // цену всегда подтверждает пользователь
    })
  }

  /** «На основании»: копирование строк из проведённого документа. */
  async function onSourceChange(sid: number) {
    setSourceId(sid)
    try {
      const src = await getDoc(sid)
      if (src.items.length) {
        setLines(src.items.map((li) => ({
          key: lineKey++,
          itemId: li.item_id,
          itemName: li.item_name ?? '',
          unitName: li.unit_name ?? '',
          qty: li.qty,
          price: li.price ?? null,
          whFrom: li.warehouse_from_id ?? null,
          whTo: li.warehouse_to_id ?? null,
        })))
      }
      setPartnerId(src.partner_id ?? undefined)
      setDocRef(src.doc_ref ?? '')
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Не удалось загрузить документ-основание')
    }
  }

  function buildPayload(): DocPayload | null {
    const valid = lines.filter((l) => l.itemId !== null)
    if (!valid.length) {
      message.error('Добавьте хотя бы одну строку с товаром')
      return null
    }
    for (const l of valid) {
      if (!l.qty || l.qty <= 0) {
        message.error(`Строка «${l.itemName || 'без товара'}»: количество должно быть больше 0`)
        return null
      }
      if (type === 'transfer' && (!l.whFrom || !l.whTo)) {
        message.error(`Строка «${l.itemName}»: укажите склады «откуда» и «куда»`)
        return null
      }
    }
    return {
      type: type as DocType,
      date: date.format('YYYY-MM-DD'),
      partner_id: partnerId ?? null,
      doc_ref: docRef || null,
      received_by: receivedBy || null,
      out_by_id: outById ?? null,
      reason: reason || null,
      warehouse_id: whId ?? null,
      source_doc_id: sourceId ?? null,
      items: valid.map((l) => ({
        item_id: l.itemId as number,
        warehouse_from_id: l.whFrom ?? null,
        warehouse_to_id: l.whTo ?? null,
        qty: l.qty as number,
        price: cfg.price ? (l.price ?? null) : null,
      })),
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

  async function onSaveDraft() {
    const nid = await saveDraft()
    if (nid) {
      message.success('Черновик сохранён')
      navigate(`/docs/${type}/${nid}`)
    }
  }

  async function onPost() {
    const nid = await saveDraft()
    if (!nid) return
    setSaving(true)
    try {
      const d = await postDoc(nid)
      message.success(`Документ ${d.number} проведён`)
      navigate(`/docs/${type}`)
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

  const totalSum = lines.reduce((s, l) => s + ((l.qty ?? 0) * (l.price ?? 0)), 0)

  const whSelect = (value: number | null, onChange: (v: number | null) => void, placeholder: string) => (
    <Select
      allowClear
      style={{ width: '100%' }}
      placeholder={placeholder}
      value={value ?? undefined}
      onChange={(v) => onChange(v ?? null)}
      disabled={!editable}
      options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
    />
  )

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>
          {cfg.title}
          {number && <Tag color="blue" style={{ marginLeft: 8 }}>{number}</Tag>}
          {status === 'draft' && <Tag style={{ marginLeft: 8 }}>Черновик</Tag>}
          {status === 'posted' && <Tag color="green" style={{ marginLeft: 8 }}>Проведён</Tag>}
          {status === 'cancelled' && <Tag color="red" style={{ marginLeft: 8 }}>Отменён</Tag>}
        </h2>
        {editable ? (
          <Space>
            <Button onClick={() => navigate(`/docs/${type}`)}>Назад к списку</Button>
            <Button onClick={() => void onSaveDraft()} loading={saving}>Сохранить черновик</Button>
            <Button type="primary" onClick={() => void onPost()} loading={saving}>Записать (провести)</Button>
          </Space>
        ) : (
          <Space>
            <Button onClick={() => navigate(`/docs/${type}`)}>Назад к списку</Button>
            <Button onClick={() => window.open(`/print/${type}/${savedId}`, '_blank')}>Печать</Button>
            {status === 'posted' && (
              <Popconfirm title="Отменить документ? Остатки будут возвращены." onConfirm={() => void onCancel()}>
                <Button danger loading={saving}>Отменить</Button>
              </Popconfirm>
            )}
          </Space>
        )}
      </div>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 8]}>
          <Col xs={24} sm={6} md={4}>
            <Field label="Дата">
              <DatePicker style={{ width: '100%' }} value={date} onChange={(d) => d && setDate(d)} disabled={!editable} />
            </Field>
          </Col>
          {cfg.partnerKind && (
            <Col xs={24} sm={12} md={6}>
              <Field label={cfg.partnerKind === 'supplier' ? 'Поставщик' : 'Покупатель'}>
                <Select
                  allowClear showSearch optionFilterProp="label"
                  style={{ width: '100%' }}
                  placeholder="Выберите"
                  value={partnerId}
                  onChange={(v) => setPartnerId(v)}
                  disabled={!editable}
                  options={partners.map((p) => ({ value: p.id, label: p.full_name }))}
                />
              </Field>
            </Col>
          )}
          <Col xs={24} sm={6} md={4}>
            <Field label="Накладная (№)">
              <Input value={docRef} onChange={(e) => setDocRef(e.target.value)} disabled={!editable} placeholder="№ накладной" />
            </Field>
          </Col>
          {cfg.outBy && (
            <Col xs={24} sm={6} md={4}>
              <Field label="Отпустил">
                <Select
                  allowClear style={{ width: '100%' }}
                  placeholder="Сотрудник"
                  value={outById}
                  onChange={(v) => setOutById(v)}
                  disabled={!editable}
                  options={users.map((u) => ({ value: u.id, label: u.full_name || u.username }))}
                />
              </Field>
            </Col>
          )}
          {cfg.reason && (
            <Col xs={24} sm={8} md={5}>
              <Field label="Причина списания">
                <Input value={reason} onChange={(e) => setReason(e.target.value)} disabled={!editable} placeholder="Например: брак" />
              </Field>
            </Col>
          )}
          {type !== 'transfer' && (
            <Col xs={24} sm={6} md={4}>
              <Field label="Склад">
                {whSelect(whId ?? null, (v) => setWhId(v ?? undefined), 'Склад (по умолчанию)')}
              </Field>
            </Col>
          )}
          {type === 'in' && (
            <Col xs={24} sm={8} md={5}>
              <Field label="Получил">
                <Input value={receivedBy} onChange={(e) => setReceivedBy(e.target.value)} disabled={!editable} placeholder="ФИО получателя" />
              </Field>
            </Col>
          )}
          {!docId && sourceDocs.length > 0 && (
            <Col xs={24} sm={10} md={6}>
              <Field label="Создан на основании">
                <Select
                  allowClear
                  placeholder="Из проведённого документа"
                  value={sourceId}
                  onChange={(v) => v && void onSourceChange(v)}
                  options={sourceDocs.map((d) => ({
                    value: d.id,
                    label: `${d.number} — ${CFG[d.type]?.title ?? d.type}`,
                  }))}
                />
              </Field>
            </Col>
          )}
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
            title: 'Наименование', key: 'item', width: 300,
            render: (_v, l: Line) => (
              <AutoComplete
                style={{ width: '100%' }}
                value={l.itemName}
                placeholder="Наименование или артикул"
                disabled={!editable}
                options={brief
                  .filter((b) => b.id !== l.itemId)
                  .map((b) => ({ value: b.name, label: `${b.name} (${b.sku}) — ${b.unit_name ?? ''}` }))}
                onSelect={(value: string) => {
                  const b = brief.find((x) => x.name === value)
                  if (b) pickItem(l.key, b)
                }}
                onChange={(v: string) => {
                  // Сброс товара при ручном изменении текста
                  if (l.itemId !== null) patchLine(l.key, { itemId: null, unitName: '', itemName: v })
                  else patchLine(l.key, { itemName: v })
                }}
              />
            ),
          },
          {
            title: 'Кол-во', key: 'qty', width: 120,
            render: (_v, l: Line) => (
              <InputNumber
                style={{ width: '100%' }} min={0} step="any"
                value={l.qty}
                onChange={(v) => patchLine(l.key, { qty: v ?? null })}
                disabled={!editable}
              />
            ),
          },
          ...(type === 'transfer' ? [
            {
              title: 'Склад от', key: 'whFrom', width: 160,
              render: (_v: unknown, l: Line) => whSelect(l.whFrom, (v) => patchLine(l.key, { whFrom: v }), 'откуда'),
            },
            {
              title: 'Склад к', key: 'whTo', width: 160,
              render: (_v: unknown, l: Line) => whSelect(l.whTo, (v) => patchLine(l.key, { whTo: v }), 'куда'),
            },
          ] : []),
          ...(cfg.price ? [
            {
              title: 'Цена, руб.', key: 'price', width: 130,
              render: (_v: unknown, l: Line) => (
                <InputNumber
                  style={{ width: '100%' }} min={0} step="any"
                  value={l.price}
                  onChange={(v) => patchLine(l.key, { price: v ?? null })}
                  disabled={!editable}
                />
              ),
            },
            {
              title: 'Сумма, руб.', key: 'sum', width: 130, align: 'right' as const,
              render: (_v: unknown, l: Line) =>
                (l.qty && l.price ? (l.qty * l.price).toLocaleString('ru-RU') : '—'),
            },
          ] : []),
          ...(editable ? [
            {
              title: '', key: 'del', width: 40,
              render: (_v: unknown, l: Line) => (
                <Button type="text" danger icon={<DeleteOutlined />} onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))} />
              ),
            },
          ] : []),
        ]}
        summary={cfg.price ? () => (
          <Table.Summary fixed>
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={3} align="right">
                Итого:
              </Table.Summary.Cell>
              <Table.Summary.Cell index={1}>
                <b>{totalSum.toLocaleString('ru-RU')}</b>
              </Table.Summary.Cell>
              {editable && <Table.Summary.Cell index={2} />}
            </Table.Summary.Row>
          </Table.Summary>
        ) : undefined}
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
