import { useCallback, useEffect, useState } from 'react'
import {
  App as AntApp, Button, Input, Modal, Popconfirm, Select, Space, Switch, Table,
  type TableColumnsType,
} from 'antd'
import { ArrowLeftOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

/** Селект с одноразовой (ленивой) загрузкой опций. */
function LazySelect({ load, value, onChange, placeholder }: {
  load: () => Promise<{ value: number | string; label: string }[]>
  value: number | string | undefined
  onChange: (v: number | string | null) => void
  placeholder?: string
}) {
  const [opts, setOpts] = useState<{ value: number | string; label: string }[]>([])
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    let alive = true
    setLoading(true)
    load().then((o) => { if (alive) setOpts(o) }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [load])
  return (
    <Select
      style={{ width: '100%' }}
      value={value}
      onChange={(nv) => onChange(nv ?? null)}
      options={opts}
      loading={loading}
      placeholder={placeholder}
      allowClear
      showSearch
      optionFilterProp="label"
    />
  )
}

/**
 * Универсальная страница справочника: таблица + поиск + модальная форма.
 * Используется для Номенклатуры, Поставщиков, Складов, Ед. изм., Категорий.
 */

export interface FieldDef {
  name: string
  label: string
  type: 'text' | 'number' | 'select' | 'textarea' | 'boolean'
  required?: boolean
  placeholder?: string
  /** Загрузка опций для select (value/label). */
  options?: () => Promise<{ value: number | string; label: string }[]>
  /** Значение по умолчанию для новой записи. */
  defaultValue?: unknown
}

interface CrudPageProps<T extends { id: number }> {
  /** Заголовок (не показывается, например, внутри вкладок). */
  title?: string
  load: (q?: string, page?: number) => Promise<{ rows: T[]; total?: number }>
  create: (data: Record<string, unknown>) => Promise<unknown>
  update?: (id: number, data: Record<string, unknown>) => Promise<unknown>
  remove?: (id: number) => Promise<unknown>
  /** Деактивация вместо удаления (для записей с историей). */
  deactivate?: (row: T) => Promise<unknown>
  columns: TableColumnsType<T>
  fields: FieldDef[]
  searchPlaceholder?: string
  addLabel?: string
}

/** Универсальная страница справочника: таблица + поиск + модальная форма. */
export default function CrudPage<T extends { id: number }>({
  title, load, create, update, remove, deactivate, columns, fields,
  searchPlaceholder, addLabel = 'Добавить',
}: CrudPageProps<T>) {
  const navigate = useNavigate()
  const { message } = AntApp.useApp()
  const [rows, setRows] = useState<T[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState(false)
  const [modal, setModal] = useState<{ open: boolean; row: T | null }>({ open: false, row: null })
  const [formValues, setFormValues] = useState<Record<string, unknown>>({})

  const refresh = useCallback(async (query?: string, pg?: number) => {
    setBusy(true)
    try {
      const res = await load(query, pg)
      setRows(res.rows)
      setTotal(res.total ?? res.rows.length)
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка загрузки')
    } finally {
      setBusy(false)
    }
  }, [load, message])

  useEffect(() => {
    void refresh(q, page)
  }, [q, page]) // eslint-disable-line react-hooks/exhaustive-deps

  function openAdd() {
    const init: Record<string, unknown> = {}
    for (const f of fields) if (f.defaultValue !== undefined) init[f.name] = f.defaultValue
    setFormValues(init)
    setModal({ open: true, row: null })
  }

  function openEdit(row: T) {
    const src = row as Record<string, unknown>
    const init: Record<string, unknown> = {}
    for (const f of fields) init[f.name] = src[f.name] ?? null
    setFormValues(init)
    setModal({ open: true, row })
  }

  async function submit() {
    const editing = modal.row
    setBusy(true)
    try {
      if (editing) {
        await update!(Number(editing.id), formValues)
        message.success('Изменения сохранены')
      } else {
        await create(formValues)
        message.success('Запись добавлена')
      }
      setModal({ open: false, row: null })
      void refresh()
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка сохранения')
    } finally {
      setBusy(false)
    }
  }

  async function onRemove(row: T) {
    try {
      await remove!(row.id)
      message.success('Запись удалена')
      void refresh()
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка удаления')
    }
  }

  async function onDeactivate(row: T) {
    try {
      await deactivate!(row)
      message.success('Запись деактивирована')
      void refresh()
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка')
    }
  }

  function set(name: string, value: unknown) {
    setFormValues((s) => ({ ...s, [name]: value }))
  }

  // Колонка действий (Изменить / Удалить / Деактивировать)
  const actionsColumn: TableColumnsType<T>[number] = {
    title: 'Действия',
    fixed: 'right',
    width: 210,
    render: (_v, row) => (
      <Space size={4}>
        {update && <Button size="small" onClick={() => openEdit(row)}>Изменить</Button>}
        {deactivate && (
          <Button size="small" onClick={() => void onDeactivate(row)}>Скрыть</Button>
        )}
        {remove && (
          <Popconfirm title="Удалить запись?" onConfirm={() => void onRemove(row)}>
            <Button size="small" danger>Удалить</Button>
          </Popconfirm>
        )}
      </Space>
    ),
  }

  // Рендер контрола поля
  function renderControl(f: FieldDef) {
    const v = formValues[f.name]
    if (f.type === 'boolean') {
      return <Switch checked={!!v} onChange={(c) => set(f.name, c)} />
    }
    if (f.type === 'select') {
      return (
        <LazySelect
          load={f.options!}
          value={v as number | string | undefined}
          onChange={(nv) => set(f.name, nv ?? null)}
          placeholder={f.placeholder ?? 'Выберите'}
        />
      )
    }
    if (f.type === 'number') {
      return (
        <Input
          type="number" min={0} step="any"
          value={v as number | undefined}
          onChange={(e) => set(f.name, e.target.value === '' ? 0 : Number(e.target.value))}
          placeholder={f.placeholder ?? f.label}
        />
      )
    }
    if (f.type === 'textarea') {
      return (
        <Input.TextArea
          rows={2}
          value={(v as string) ?? ''}
          onChange={(e) => set(f.name, e.target.value || null)}
          placeholder={f.placeholder ?? f.label}
        />
      )
    }
    return (
      <Input
        value={(v as string) ?? ''}
        onChange={(e) => set(f.name, e.target.value)}
        placeholder={f.placeholder ?? f.label}
      />
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        {title && <h2 style={{ margin: 0 }}>{title}</h2>}
        <Space>
          <Button type="text" icon={<ArrowLeftOutlined />} title="Назад в главное меню" onClick={() => navigate('/')} />
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder={searchPlaceholder ?? 'Поиск…'}
            style={{ width: 300 }}
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1) }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>{addLabel}</Button>
        </Space>
      </div>

      <Table
        rowKey="id"
        size="middle"
        loading={busy}
        columns={[...columns, actionsColumn]}
        dataSource={rows}
        pagination={{
          current: page,
          pageSize: 50,
          total,
          showTotal: (t) => `Всего: ${t}`,
          onChange: (p) => setPage(p),
        }}
        scroll={{ x: 'max-content' }}
      />

      <Modal
        title={modal.row ? 'Изменить' : 'Новая запись'}
        open={modal.open}
        onOk={submit}
        confirmLoading={busy}
        onCancel={() => setModal({ open: false, row: null })}
        okText="Сохранить"
        cancelText="Отмена"
        width={680}
        destroyOnHidden
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 16px', marginTop: 8 }}>
          {fields.map((f) => (
            <div key={f.name} style={f.type === 'textarea' ? { gridColumn: '1 / -1' } : undefined}>
              <div style={{ fontSize: 12, color: '#8a90a6', marginBottom: 2 }}>
                {f.label} {f.required && <span style={{ color: '#e5484d' }}>*</span>}
              </div>
              {renderControl(f)}
            </div>
          ))}
        </div>
      </Modal>
    </div>
  )
}
