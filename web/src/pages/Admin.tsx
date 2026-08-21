import { useCallback, useEffect, useState } from 'react'
import {
  Alert, App as AntApp, Button, Card, Col, DatePicker, Input, Modal, Popconfirm, Row, Select,
  Space, Switch, Table, Tabs, Tag, Upload, type TableProps, type GetProps,
} from 'antd'
import { DownloadOutlined, PlusOutlined, UploadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  createAdminUser, downloadBackup, downloadMigrateExport, fetchAudit, getCompany,
  importMigrate, listAdminUsers, listSettings, restoreBackup, saveCompany, saveSetting, updateAdminUser,
  type AdminUser, type AuditRow, type CompanyData, type MigrateReport, type MigrateSection, type Setting,
} from '../api/admin'
import { me, type User } from '../api/auth'
import { listWarehouses, type Warehouse } from '../api/references'

const { RangePicker } = DatePicker

/** Раздел «Админ»: предприятие, пользователи, настройки, аудит, резервные копии. */
export default function Admin() {
  const [user, setUser] = useState<User | null>(null)
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])

  useEffect(() => {
    me().then(setUser).catch(() => setUser(null))
    listWarehouses().then(setWarehouses).catch(() => undefined)
  }, [])

  if (!user) return null
  if (user.role !== 'admin') {
    return <Alert type="warning" showIcon message="Недостаточно прав" description="Раздел «Админ» доступен только администратору." />
  }

  const tabs = [
    { key: 'company', label: 'Карточка предприятия', children: <CompanyTab /> },
    { key: 'users', label: 'Пользователи', children: <UsersTab self={user} /> },
    { key: 'settings', label: 'Настройки', children: <SettingsTab warehouses={warehouses} /> },
    { key: 'audit', label: 'Аудит', children: <AuditTab /> },
    { key: 'backup', label: 'Бэкап', children: <BackupTab /> },
    { key: 'migrate', label: 'Миграция 7.1', children: <MigrateTab /> },
  ]

  return <Tabs items={tabs} />
}

// ---------- Карточка предприятия ----------

const COMPANY_FIELDS: { key: keyof CompanyData; label: string }[] = [
  { key: 'full_name', label: 'Полное наименование' },
  { key: 'short_name', label: 'Сокращённое наименование' },
  { key: 'legal_address', label: 'Юридический адрес' },
  { key: 'postal_address', label: 'Почтовый адрес' },
  { key: 'phone', label: 'Телефон / факс' },
  { key: 'email', label: 'E-mail' },
  { key: 'inn_kpp', label: 'ИНН / КПП' },
  { key: 'ogrn', label: 'ОГРН' },
  { key: 'director', label: 'Руководитель' },
  { key: 'bank', label: 'Банк' },
  { key: 'bik', label: 'БИК' },
  { key: 'account', label: 'Расчётный счёт' },
  { key: 'corr_account', label: 'Корреспондентский счёт' },
]

function CompanyTab() {
  const { message } = AntApp.useApp()
  const [data, setData] = useState<CompanyData | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getCompany().then(setData).catch(() => undefined)
  }, [])

  async function onSave() {
    if (!data) return
    setSaving(true)
    try {
      await saveCompany(data)
      message.success('Карточка предприятия сохранена')
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  if (!data) return null
  const set = (key: keyof CompanyData, value: string) => setData({ ...data, [key]: value || null })

  return (
    <Card size="small">
      <Row gutter={[16, 12]}>
        {COMPANY_FIELDS.map((f) => (
          <Col key={f.key} xs={24} md={12}>
            <Input
              addonBefore={f.label}
              value={data[f.key] ?? ''}
              onChange={(e) => set(f.key, e.target.value)}
              allowClear
            />
          </Col>
        ))}
        <Col xs={24} md={12}>
          <Button type="primary" loading={saving} onClick={() => void onSave()} style={{ width: '100%' }}>
            Записать
          </Button>
        </Col>
      </Row>
    </Card>
  )
}

// ---------- Пользователи ----------

function UsersTab({ self }: { self: User }) {
  const { message } = AntApp.useApp()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [addForm, setAddForm] = useState({ username: '', password: '', full_name: '', role: 'user' as 'admin' | 'user' })
  const [resetFor, setResetFor] = useState<AdminUser | null>(null)
  const [newPass, setNewPass] = useState('')

  const load = useCallback(() => {
    listAdminUsers().then(setUsers).catch(() => undefined)
  }, [])
  useEffect(() => { load() }, [load])

  async function onAdd() {
    try {
      await createAdminUser({
        username: addForm.username.trim(),
        password: addForm.password,
        full_name: addForm.full_name.trim() || undefined,
        role: addForm.role,
      })
      message.success('Пользователь создан')
      setAddOpen(false)
      setAddForm({ username: '', password: '', full_name: '', role: 'user' })
      load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка создания')
    }
  }

  async function onToggleActive(u: AdminUser) {
    try {
      await updateAdminUser(u.id, { active: !u.active })
      message.success(u.active ? 'Пользователь заблокирован' : 'Пользователь разблокирован')
      load()
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка')
    }
  }

  async function onResetPass() {
    if (!resetFor) return
    try {
      await updateAdminUser(resetFor.id, { password: newPass })
      message.success('Пароль изменён')
      setResetFor(null)
      setNewPass('')
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка')
    }
  }

  const cols: NonNullable<TableProps<AdminUser>['columns']> = [
    { title: 'Логин', dataIndex: 'username', width: 160 },
    { title: 'Ф.И.О.', dataIndex: 'full_name', render: (v: string | null) => v || '—' },
    {
      title: 'Роль', dataIndex: 'role', width: 120,
      render: (v: string) => <Tag color={v === 'admin' ? 'gold' : 'default'}>{v === 'admin' ? 'Администратор' : 'Пользователь'}</Tag>,
    },
    {
      title: 'Статус', dataIndex: 'active', width: 120,
      render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? 'Активен' : 'Заблокирован'}</Tag>,
    },
    {
      title: 'Действия', key: 'actions', width: 260,
      render: (_v, u) => {
        const isSelf = u.id === self.id
        return (
          <Space>
            <Button size="small" onClick={() => { setResetFor(u); setNewPass('') }}>Сменить пароль</Button>
            {!isSelf && (
              <Popconfirm
                title={u.active ? `Заблокировать «${u.username}»?` : `Разблокировать «${u.username}»?`}
                onConfirm={() => void onToggleActive(u)}
              >
                <Button size="small" danger={u.active}>
                  {u.active ? 'Заблокировать' : 'Разблокировать'}
                </Button>
              </Popconfirm>
            )}
          </Space>
        )
      },
    },
  ]

  return (
    <Card size="small" title="Пользователи системы">
      <Table
        rowKey="id"
        size="middle"
        columns={cols}
        dataSource={users}
        pagination={false}
        footer={() => (
          <Button icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>Добавить пользователя</Button>
        )}
      />
      <Modal
        title="Новый пользователь"
        open={addOpen}
        onOk={() => void onAdd()}
        onCancel={() => setAddOpen(false)}
        okText="Создать"
        cancelText="Отмена"
        okButtonProps={{ disabled: !addForm.username.trim() || addForm.password.length < 4 }}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Input addonBefore="Логин" value={addForm.username} onChange={(e) => setAddForm({ ...addForm, username: e.target.value })} />
          <Input addonBefore="Ф.И.О." value={addForm.full_name} onChange={(e) => setAddForm({ ...addForm, full_name: e.target.value })} allowClear />
          <Input.Password addonBefore="Пароль" value={addForm.password} onChange={(e) => setAddForm({ ...addForm, password: e.target.value })} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ whiteSpace: 'nowrap' }}>Роль</span>
            <Select
              style={{ flex: 1 }}
              value={addForm.role}
              onChange={(v) => setAddForm({ ...addForm, role: v })}
              options={[{ value: 'user', label: 'Пользователь' }, { value: 'admin', label: 'Администратор' }]}
            />
          </div>
        </Space>
      </Modal>
      <Modal
        title={resetFor ? `Смена пароля: ${resetFor.username}` : ''}
        open={resetFor !== null}
        onOk={() => void onResetPass()}
        onCancel={() => setResetFor(null)}
        okText="Сменить"
        cancelText="Отмена"
        okButtonProps={{ disabled: newPass.length < 4 }}
      >
        <Input.Password
          addonBefore="Новый пароль"
          value={newPass}
          onChange={(e) => setNewPass(e.target.value)}
          placeholder="Минимум 4 символа"
        />
      </Modal>
    </Card>
  )
}

// ---------- Настройки ----------

function SettingsTab({ warehouses }: { warehouses: Warehouse[] }) {
  const { message } = AntApp.useApp()
  const [settings, setSettings] = useState<Setting[]>([])

  useEffect(() => {
    listSettings().then(setSettings).catch(() => undefined)
  }, [])

  const valueOf = (key: string) => settings.find((s) => s.key === key)?.value ?? ''

  async function update(key: string, value: string, text: string) {
    try {
      await saveSetting(key, value)
      setSettings((prev) => prev.map((s) => (s.key === key ? { ...s, value } : s)))
      message.success(text)
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка сохранения')
    }
  }

  return (
    <Card size="small" title="Настройки приложения">
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div>
          <div style={{ marginBottom: 4, fontWeight: 500 }}>Разрешить отрицательный остаток</div>
          <Switch
            checked={valueOf('allow_negative_stock') === 'true'}
            onChange={(v) => void update('allow_negative_stock', v ? 'true' : 'false', 'Настройка сохранена')}
          />
          <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
            Если выключено, приход/расход с получением отрицательного остатка не пройдёт.
          </div>
        </div>
        <div>
          <div style={{ marginBottom: 4, fontWeight: 500 }}>Склад по умолчанию (при создании документов)</div>
          <Select
            style={{ width: 280 }}
            placeholder="— не задан —"
            allowClear
            value={valueOf('default_warehouse_id') ? Number(valueOf('default_warehouse_id')) : undefined}
            onChange={(v) => void update('default_warehouse_id', v ? String(v) : '', 'Настройка сохранена')}
            options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
          />
        </div>
      </Space>
    </Card>
  )
}

// ---------- Аудит ----------

const ACTION_LABELS: Record<string, string> = {
  login: 'Вход', logout: 'Выход', create: 'Создание', update: 'Изменение', delete: 'Удаление',
  post: 'Проведение', cancel: 'Отмена', backup: 'Резервная копия', restore: 'Восстановление',
  import: 'Перенос из 7.1',
}

type AuditRange = GetProps<typeof RangePicker>['value']

function AuditTab() {
  const { message } = AntApp.useApp()
  const [range, setRange] = useState<AuditRange>(null)
  const [userId, setUserId] = useState<number | undefined>(undefined)
  const [action, setAction] = useState<string | undefined>(undefined)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<AuditRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [users, setUsers] = useState<AdminUser[]>([])

  useEffect(() => {
    listAdminUsers().then(setUsers).catch(() => undefined)
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const p = await fetchAudit({
        page,
        size: 50,
        ...(userId ? { user_id: userId } : {}),
        ...(action ? { action } : {}),
        ...(q ? { q } : {}),
        ...(range?.[0] ? { date_from: range[0].format('YYYY-MM-DD') } : {}),
        ...(range?.[1] ? { date_to: range[1].format('YYYY-MM-DD') } : {}),
      })
      setData(p.rows)
      setTotal(p.total)
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка загрузки журнала')
    } finally {
      setLoading(false)
    }
  }, [page, userId, action, q, range]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void refresh() }, [refresh])

  const cols: NonNullable<TableProps<AuditRow>['columns']> = [
    {
      title: 'Когда', dataIndex: 'ts', width: 160,
      render: (v: string) => dayjs(v).format('DD.MM.YYYY HH:mm:ss'),
    },
    { title: 'Пользователь', dataIndex: 'username', width: 140, render: (v: string | null) => v || '—' },
    {
      title: 'Действие', dataIndex: 'action', width: 130,
      render: (v: string) => <Tag color="blue">{ACTION_LABELS[v] ?? v}</Tag>,
    },
    { title: 'Объект', dataIndex: 'entity', width: 130, render: (v: string, r) => (r.entity_id ? `${v} (${r.entity_id})` : v) },
  ]

  return (
    <Card size="small" title="Журнал изменений (аудит)">
      <Space wrap style={{ marginBottom: 12 }}>
        <RangePicker
          value={range ?? undefined}
          onChange={(v) => { setRange(v); setPage(1) }}
        />
        <Select
          allowClear
          placeholder="Пользователь"
          style={{ width: 170 }}
          value={userId}
          onChange={(v) => { setUserId(v); setPage(1) }}
          options={users.map((u) => ({ value: u.id, label: u.username }))}
        />
        <Select
          allowClear
          placeholder="Действие"
          style={{ width: 160 }}
          value={action}
          onChange={(v) => { setAction(v); setPage(1) }}
          options={Object.entries(ACTION_LABELS).map(([value, label]) => ({ value, label }))}
        />
        <Input
          allowClear
          placeholder="Поиск: действие, объект, логин"
          style={{ width: 240 }}
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1) }}
        />
        <Button onClick={() => void refresh()}>Обновить</Button>
      </Space>
      <Table
        rowKey="id"
        size="middle"
        loading={loading}
        columns={cols}
        dataSource={data ?? []}
        pagination={{
          current: page,
          pageSize: 50,
          total,
          showTotal: (t) => `Всего записей: ${t}`,
          onChange: setPage,
        }}
        expandable={{
          expandedRowRender: (r: AuditRow) =>
            r.changes ? <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{tryPretty(r.changes)}</pre> : <span style={{ color: '#999' }}>—</span>,
        }}
      />
    </Card>
  )
}

function tryPretty(json: string): string {
  try { return JSON.stringify(JSON.parse(json), null, 2) } catch { return json }
}

// ---------- Бэкап ----------

function BackupTab() {
  const { message, modal } = AntApp.useApp()
  const [busy, setBusy] = useState<'download' | 'restore' | null>(null)

  async function onDownload() {
    setBusy('download')
    try {
      await downloadBackup()
      message.success('Резервная копия сохранена')
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка копирования')
    } finally {
      setBusy(null)
    }
  }

  function onRestore(file: File) {
    modal.confirm({
      title: 'Восстановление базы',
      content: `Восстановить базу из файла «${file.name}»? Текущие данные будут заменены. Перед заменой автоматически создаётся снимок текущей базы.`,
      okText: 'Восстановить',
      okButtonProps: { danger: true },
      cancelText: 'Отмена',
      onOk: async () => {
        setBusy('restore')
        try {
          await restoreBackup(file)
        } catch (e) {
          message.error(e instanceof Error ? e.message : 'Ошибка восстановления')
          setBusy(null)
        }
      },
    })
    return false
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card size="small" title="Резервная копия">
        <Space>
          <Button type="primary" icon={<DownloadOutlined />} loading={busy === 'download'} onClick={() => void onDownload()}>
            Скачать резервную копию
          </Button>
          <span style={{ color: '#999', fontSize: 12 }}>Файл .db со всей базой: справочники, документы, остатки, журнал.</span>
        </Space>
      </Card>
      <Card size="small" title="Восстановление из файла">
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="Внимание"
          description="Все текущие данные будут заменены содержимым файла. Действие необратимо, кроме сохранённого снимка."
        />
        <Upload.Dragger
          accept=".db"
          showUploadList={false}
          beforeUpload={(f) => onRestore(f)}
          disabled={busy === 'restore'}
        >
          <p className="ant-upload-drag-icon"><UploadOutlined /></p>
          <p className="ant-upload-text">Выберите файл базы .db</p>
          <p className="ant-upload-hint">После восстановления страница перезагрузится</p>
        </Upload.Dragger>
      </Card>
    </Space>
  )
}

// ---------- Миграция 7.1 ----------

function MigrateTab() {
  const { message, modal } = AntApp.useApp()
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<MigrateReport | null>(null)

  function onImport(file: File) {
    modal.confirm({
      title: 'Перенос из 7.1',
      width: 480,
      content: `Импортировать данные из файла «${file.name}»? Номенклатура, поставщики и реестры будут добавлены к текущим данным (реестры — документами прихода/расхода/списания). Всё выполняется одной операцией: либо целиком, либо не выполнено вовсе.`,
      okText: 'Импортировать',
      cancelText: 'Отмена',
      onOk: async () => {
        setBusy(true)
        try {
          setReport(await importMigrate(file))
          message.success('Импорт завершён, отчёт ниже')
        } catch (e) {
          message.error(e instanceof Error ? e.message : 'Ошибка импорта')
        } finally {
          setBusy(false)
        }
      },
    })
    return false
  }

  async function onExport() {
    try {
      await downloadMigrateExport()
      message.success('Файл сохранён')
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка экспорта')
    }
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card size="small" title="Импорт из старого файла (Склад ПРО 7.1)">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="Поддерживаются файлы .xlsm и .xlsx"
          description="Листы «Номенклатура», «Поставщики», «Реестр прихода», «Реестр расхода», «Реестр списания», «Админ» (карточка предприятия и сотрудники)."
        />
        <Upload.Dragger
          accept=".xlsm,.xlsx"
          showUploadList={false}
          beforeUpload={(f) => onImport(f)}
          disabled={busy}
        >
          <p className="ant-upload-drag-icon"><UploadOutlined /></p>
          <p className="ant-upload-text">Выберите файл 7.1 (.xlsm или .xlsx)</p>
          <p className="ant-upload-hint">После импорта ниже появится отчёт: что перенесено, что пропущено и сверка остатков</p>
        </Upload.Dragger>
      </Card>
      <Card size="small" title="Экспорт в формат 7.1">
        <Space>
          <Button type="primary" icon={<DownloadOutlined />} onClick={() => void onExport()}>
            Скачать файл в формате 7.1
          </Button>
          <span style={{ color: '#999', fontSize: 12 }}>
            Текущие данные (номенклатура, остатки, реестры, карточка предприятия) в структуре листов 7.1.
          </span>
        </Space>
      </Card>
      {report && <MigrateReportView report={report} />}
    </Space>
  )
}

function MigrateReportView({ report }: { report: MigrateReport }) {
  const cols: NonNullable<TableProps<MigrateSection>['columns']> = [
    { title: 'Раздел', dataIndex: 'name' },
    { title: 'Строк в файле', dataIndex: 'total', width: 110 },
    { title: 'Создано', dataIndex: 'created', width: 90 },
    { title: 'Уже было', dataIndex: 'kept', width: 90 },
    { title: 'Перенесено', width: 100, render: (_v, s) => s.imported || s.fields },
    { title: 'Документов', dataIndex: 'documents', width: 110 },
    {
      title: 'Пропущено', width: 100,
      render: (_v, s) => s.skipped_rows.length
        ? <Tag color="orange">{s.skipped_rows.length}</Tag>
        : <Tag color="green">0</Tag>,
    },
  ]

  const docTypes = Object.entries(report.documents.by_type)
  const mismatches = report.stock_check.mismatches

  return (
    <Card size="small" title="Отчёт о переносе" style={{ borderColor: '#b7eb8f' }}>
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {report.warnings.length > 0 && (
          <Alert type="warning" showIcon message={report.warnings.join('; ')} />
        )}
        <Table
          rowKey="name"
          size="small"
          columns={cols}
          dataSource={report.sections.filter((s) => s.total > 0 || s.fields > 0 || s.skipped_rows.length > 0)}
          pagination={false}
          expandable={{
            expandedRowRender: (s) => s.skipped_rows.length > 0 ? (
              <Table
                rowKey="row"
                size="small"
                pagination={false}
                columns={[
                  { title: 'Строка', dataIndex: 'row', width: 80 },
                  { title: 'Причина', dataIndex: 'reason' },
                ]}
                dataSource={s.skipped_rows}
              />
            ) : null,
            rowExpandable: (s) => s.skipped_rows.length > 0,
          }}
        />
        <div style={{ fontSize: 13 }}>
          <b>Документы:</b> {report.documents.total}
          {docTypes.length > 0 && (
            <span> ({docTypes.map(([t, n]) => `${t} — ${n}`).join(', ')})</span>
          )}
        </div>
        <div style={{ fontSize: 13 }}>
          <b>Сверка остатков:</b> проверено {report.stock_check.checked} товар(ов)
          {mismatches.length === 0
            ? <Tag color="green" style={{ marginLeft: 8 }}>расхождений нет</Tag>
            : null}
          {mismatches.length > 0 && (
            <Table
              rowKey="item"
              size="small"
              style={{ marginTop: 8 }}
              pagination={false}
              columns={[
                { title: 'Товар', dataIndex: 'item' },
                { title: 'Ожидалось по файлу', dataIndex: 'expected' },
                { title: 'Стало в базе', dataIndex: 'imported' },
                { title: 'Разница', dataIndex: 'diff' },
              ]}
              dataSource={mismatches}
            />
          )}
        </div>
        {report.created.users.length > 0 && (
          <Alert
            type="warning"
            showIcon
            message="Созданы пользователи (пароли из файла 7.1 не переносятся)"
            description={
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {report.created.users.map((u) => (
                  <li key={u.username}><b>{u.username}</b> — временный пароль: <code>{u.password}</code> (смените после входа)</li>
                ))}
              </ul>
            }
          />
        )}
      </Space>
    </Card>
  )
}
