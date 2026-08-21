import { useCallback, useEffect, useState } from 'react'
import {
  App as AntApp, Button, Card, DatePicker, Input, Segmented, Select, Space, Table, Tag,
  type GetProps, type TableProps,
} from 'antd'
import { DownloadOutlined, FileExcelOutlined, FilePdfOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { useNavigate, useParams } from 'react-router-dom'
import {
  downloadReport, fetchReport, type ReportColumn, type ReportData, type ReportKind, type ReportParams,
} from '../api/reports'
import { listWarehouses, type Warehouse } from '../api/references'

const { RangePicker } = DatePicker
type RangeValue = GetProps<typeof RangePicker>['value']

const KINDS: { key: ReportKind; label: string }[] = [
  { key: 'balance', label: 'ОСВ (остатки)' },
  { key: 'movement', label: 'Движения' },
  { key: 'turnover', label: 'Оборотка' },
  { key: 'below_min', label: 'Низкие остатки' },
  { key: 'abc', label: 'ABC-анализ' },
  { key: 'turnover_speed', label: 'Оборачиваемость' },
]

// Старые пункты меню 7.1: «Отчет по приходу/расходу/списанию» → движения по типу
const PRESETS: Record<string, { kind: ReportKind; docType: string }> = {
  in: { kind: 'movement', docType: 'in' },
  out: { kind: 'movement', docType: 'out' },
  writeoff: { kind: 'movement', docType: 'writeoff' },
}

const DOC_TYPES = [
  { value: 'all', label: 'Все типы' },
  { value: 'in', label: 'Приход' },
  { value: 'out', label: 'Расход' },
  { value: 'writeoff', label: 'Списание' },
  { value: 'transfer', label: 'Перемещение' },
  { value: 'inventory', label: 'Инвентаризация' },
]

function fmt(v: string | number | null | undefined, kind?: string | null): string {
  if (v == null) return '—'
  if (typeof v !== 'number') return v
  if (kind === 'money') return v.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (kind === 'percent') return `${v.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} %`
  if (kind === 'number') return v.toLocaleString('ru-RU', { maximumFractionDigits: 3 })
  return v.toLocaleString('ru-RU')
}

/** Отчёты: шесть видов + экспорт в Excel/PDF (в 7.1 — листы Otchet* / Osv / Oborotka). */
export default function Reports() {
  const { preset } = useParams()
  const navigate = useNavigate()
  const { message } = AntApp.useApp()
  const presetCfg = PRESETS[preset ?? '']

  const [kind, setKind] = useState<ReportKind>(presetCfg?.kind ?? 'balance')
  const [range, setRange] = useState<RangeValue>(null)
  const [asOf, setAsOf] = useState<Dayjs>(dayjs())
  const [docType, setDocType] = useState(presetCfg?.docType ?? 'all')
  const [whId, setWhId] = useState<number | undefined>(undefined)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState<'excel' | 'pdf' | null>(null)
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])

  useEffect(() => {
    listWarehouses().then(setWarehouses).catch(() => undefined)
  }, [])

  const buildParams = useCallback((): ReportParams => {
    const params: ReportParams = { page }
    if (kind === 'balance') {
      params.as_of = asOf.format('YYYY-MM-DD')
    } else {
      if (range?.[0]) params.date_from = range[0].format('YYYY-MM-DD')
      if (range?.[1]) params.date_to = range[1].format('YYYY-MM-DD')
    }
    if (kind === 'movement') params.doc_type = docType
    if (whId && kind !== 'abc') params.warehouse_id = whId
    if (q && kind !== 'abc') params.q = q
    return params
  }, [kind, page, range, asOf, docType, whId, q])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setData(await fetchReport(kind, buildParams()))
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка загрузки отчёта')
    } finally {
      setLoading(false)
    }
  }, [kind, buildParams]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void refresh()
  }, [refresh])

  const withPage = (p: number) => setPage(p)

  async function onExport(fmt: 'excel' | 'pdf') {
    setExporting(fmt)
    try {
      await downloadReport(kind, fmt, buildParams())
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ошибка экспорта')
    } finally {
      setExporting(null)
    }
  }

  const cols: NonNullable<TableProps<Record<string, unknown>>['columns']> = (data?.columns ?? []).map((c: ReportColumn) => ({
    title: c.title,
    dataIndex: c.key,
    key: c.key,
    width: c.width ?? undefined,
    align: (c.align ?? 'left') as 'left' | 'right',
    render: (v: string | number | null) => fmt(v, c.kind),
  }))

  const showPeriod = kind !== 'balance'
  const showWarehouse = kind !== 'abc'

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>
          Отчёты
          {data && <Tag color="blue" style={{ marginLeft: 8 }}>{data.title}{data.period ? ` — ${data.period}` : ''}</Tag>}
        </h2>
        <Space>
          <Button
            icon={<FileExcelOutlined />}
            loading={exporting === 'excel'}
            onClick={() => void onExport('excel')}
          >
            Экспорт в Excel
          </Button>
          <Button
            icon={<FilePdfOutlined />}
            loading={exporting === 'pdf'}
            onClick={() => void onExport('pdf')}
          >
            Экспорт в PDF
          </Button>
        </Space>
      </div>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Segmented
            options={KINDS.map((k) => ({ value: k.key, label: k.label }))}
            value={kind}
            onChange={(v) => { setKind(v as ReportKind); setPage(1); if (PRESETS[preset ?? '']) navigate('/reports') }}
          />
          <Space wrap>
            {showPeriod && (
              <RangePicker
                value={range ?? undefined}
                onChange={(v) => { setRange(v); setPage(1) }}
              />
            )}
            {kind === 'balance' && (
              <DatePicker
                value={asOf}
                onChange={(d) => { if (d) { setAsOf(d); setPage(1) } }}
              />
            )}
            {kind === 'movement' && (
              <Select
                style={{ width: 170 }}
                value={docType}
                onChange={(v) => { setDocType(v); setPage(1) }}
                options={DOC_TYPES}
              />
            )}
            {showWarehouse && (
              <Select
                allowClear
                showSearch
                optionFilterProp="label"
                placeholder="Склад (все)"
                style={{ width: 180 }}
                value={whId}
                onChange={(v) => { setWhId(v); setPage(1) }}
                options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
              />
            )}
            {showWarehouse && (
              <Input
                allowClear
                prefix={<SearchOutlined />}
                placeholder="Наименование, артикул…"
                style={{ width: 240 }}
                value={q}
                onChange={(e) => { setQ(e.target.value); setPage(1) }}
              />
            )}
            <Button icon={<DownloadOutlined />} type="text" onClick={() => void refresh()}>Обновить</Button>
          </Space>
        </Space>
      </Card>

      <Table
        rowKey={(_r, i) => String(i)}
        size="middle"
        loading={loading}
        dataSource={(data?.rows ?? []).map((r) =>
          Object.fromEntries((data?.columns ?? []).map((c, i) => [c.key, r[i]])))}
        pagination={{
          current: page,
          pageSize: 100,
          total: data?.total ?? 0,
          showTotal: (t) => `Всего строк: ${t}`,
          onChange: withPage,
          hideOnSinglePage: false,
        }}
        scroll={{ x: 'max-content' }}
        columns={cols}
        summary={data?.totals ? () => (
          <Table.Summary fixed>
            <Table.Summary.Row>
              {(data.totals as (string | number | null)[]).map((v, i) => (
                <Table.Summary.Cell key={data!.columns[i].key} index={i} align="right">
                  <b>{fmt(v, data!.columns[i].kind)}</b>
                </Table.Summary.Cell>
              ))}
            </Table.Summary.Row>
          </Table.Summary>
        ) : undefined}
      />
    </div>
  )
}
