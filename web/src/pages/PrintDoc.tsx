import { useEffect, useState, type CSSProperties } from 'react'
import { Button, Spin } from 'antd'
import { ArrowLeftOutlined, PrinterOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useNavigate, useParams } from 'react-router-dom'
import { getDoc, type Doc } from '../api/documents'
import { getCompany, type Company } from '../api/company'

/** Название печатной формы по типу документа (в 7.1 — лист «Накладная»). */
const TITLES: Record<string, string> = {
  in: 'Приходная накладная',
  out: 'Расходная накладная',
  writeoff: 'Приказ о списании',
  transfer: 'Приказ о перемещении',
  inventory: 'Акт инвентаризации',
}

const fmt = (v: number | null | undefined) =>
  v == null ? '—' : Number(v).toLocaleString('ru-RU')

/** Печатная форма документа: A4, «Печать» → системный диалог (сохранить в PDF). */
export default function PrintDoc() {
  const { type = 'in', id } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState<Doc | null>(null)
  const [company, setCompany] = useState<Company | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getDoc(Number(id)).then(setDoc).catch((e) => setError(e instanceof Error ? e.message : 'Ошибка загрузки'))
    getCompany().then(setCompany).catch(() => setCompany(null))
  }, [id])

  if (error) return <div style={{ padding: 40, color: '#e5484d' }}>Не удалось открыть документ: {error}</div>
  if (!doc) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />

  const title = TITLES[type] ?? doc.type
  const isMoney = type === 'in' || type === 'out'
  const totalSum = doc.items.reduce((s, li) => s + li.qty * (li.price ?? 0), 0)
  const companyLine = [company?.short_name ?? company?.full_name, company?.inn_kpp].filter(Boolean).join(', ')

  // Шапка «от / кому / кто»
  const meta: [string, string][] = []
  if (type === 'in') {
    meta.push(['От (поставщик)', doc.partner_name ?? '—'])
    if (doc.warehouse_name) meta.push(['Склад', doc.warehouse_name])
    if (doc.doc_ref) meta.push(['Накладная №', doc.doc_ref])
    if (doc.received_by) meta.push(['Получил', doc.received_by])
  } else if (type === 'out') {
    meta.push(['От', companyLine || '—'])
    meta.push(['Кому', doc.received_by ?? doc.partner_name ?? '—'])
    if (doc.out_by_name) meta.push(['Отпустил', doc.out_by_name])
    if (doc.doc_ref) meta.push(['Накладная №', doc.doc_ref])
  } else if (type === 'writeoff') {
    if (doc.warehouse_name) meta.push(['Склад', doc.warehouse_name])
    if (doc.doc_ref) meta.push(['Накладная №', doc.doc_ref])
    if (doc.reason) meta.push(['Причина списания', doc.reason])
  } else if (type === 'transfer') {
    if (doc.doc_ref) meta.push(['Накладная №', doc.doc_ref])
  } else if (type === 'inventory') {
    if (doc.warehouse_name) meta.push(['Склад', doc.warehouse_name])
  }

  // Подписи
  const signs: [string, string][] = []
  if (type === 'in') {
    signs.push(['Получил', doc.received_by ?? ''])
    signs.push(['Дал', ''])
  } else if (type === 'out') {
    signs.push(['Отпустил', doc.out_by_name ?? ''])
    signs.push(['Получил', doc.received_by ?? ''])
  } else if (type === 'writeoff') {
    signs.push(['Издал', company?.director ?? ''])
    signs.push(['Составил', doc.out_by_name ?? ''])
  } else if (type === 'transfer') {
    signs.push(['Отпустил', doc.out_by_name ?? ''])
    signs.push(['Получил', doc.received_by ?? ''])
  } else if (type === 'inventory') {
    signs.push(['Председатель комиссии', company?.director ?? ''])
    signs.push(['Член комиссии', ''])
  }

  const cell: CSSProperties = { border: '1px solid #333', padding: '4px 8px' }
  const head: CSSProperties = { ...cell, fontWeight: 600, background: '#f2f2f2' }

  return (
    <div>
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: #fff !important; }
          .print-doc { box-shadow: none !important; margin: 0 !important; width: auto !important; min-height: 0 !important; }
          @page { size: A4; margin: 14mm; }
        }
      `}</style>
      <div className="no-print" style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 24px', maxWidth: 900, margin: '0 auto' }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>Назад к документу</Button>
        <Button type="primary" icon={<PrinterOutlined />} onClick={() => window.print()}>Печать</Button>
      </div>

      <div className="print-doc" style={{
        maxWidth: 900, margin: '0 auto 40px', padding: '40px 48px',
        background: '#fff', color: '#111', fontFamily: '"Times New Roman", Georgia, serif',
        fontSize: 14, boxShadow: '0 2px 12px rgba(0,0,0,.15)', minHeight: 560,
      }}>
        {/* Шапка: карточка предприятия */}
        {company && (
          <div style={{ marginBottom: 20, fontSize: 12, lineHeight: 1.5 }}>
            <div>{company.full_name}</div>
            {company.legal_address && <div>Адрес: {company.legal_address}</div>}
            <div>{[company.inn_kpp, company.ogrn, company.phone].filter(Boolean).join(' | ')}</div>
          </div>
        )}

        <h2 style={{ textAlign: 'center', margin: '8px 0 4px', fontSize: 18, textTransform: 'uppercase' }}>
          {title}
        </h2>
        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          № {doc.number ?? '—'} от {dayjs(doc.date).format('DD.MM.YYYY')}
        </div>

        {meta.length > 0 && (
          <table style={{ borderCollapse: 'collapse', marginBottom: 16, width: '100%' }}>
            <tbody>
              {meta.map(([k, v]) => (
                <tr key={k}>
                  <td style={{ ...cell, width: '35%', verticalAlign: 'top' }}>{k}:</td>
                  <td style={cell}>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Таблица позиций */}
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th style={{ ...head, width: 40 }}>№</th>
              <th style={head}>Наименование</th>
              <th style={{ ...head, width: 70 }}>Ед. изм.</th>
              {type === 'inventory' ? (
                <>
                  <th style={{ ...head, width: 100 }}>Кол-во (нач)</th>
                  <th style={{ ...head, width: 100 }}>Остаток (факт)</th>
                  <th style={{ ...head, width: 100 }}>Расхождение</th>
                </>
              ) : (
                <>
                  <th style={{ ...head, width: 90 }}>Кол-во</th>
                  {isMoney && <th style={{ ...head, width: 100 }}>Цена, руб.</th>}
                  {type === 'transfer' && <th style={head}>Откуда</th>}
                  {type === 'transfer' && <th style={head}>Куда</th>}
                  {isMoney && <th style={{ ...head, width: 110 }}>Сумма, руб.</th>}
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {type === 'inventory' ? (
              doc.results.map((r, i) => (
                <tr key={r.id ?? i}>
                  <td style={cell}>{i + 1}</td>
                  <td style={cell}>{r.item_name}</td>
                  <td style={cell}>{r.unit_name ?? ''}</td>
                  <td style={{ ...cell, textAlign: 'right' }}>{fmt(r.diff_qty != null ? r.counted_qty - r.diff_qty : null)}</td>
                  <td style={{ ...cell, textAlign: 'right' }}>{fmt(r.counted_qty)}</td>
                  <td style={{ ...cell, textAlign: 'right', fontWeight: r.diff_qty ? 700 : 400 }}>
                    {r.diff_qty == null ? '' : (r.diff_qty > 0 ? '+' : '') + fmt(r.diff_qty)}
                  </td>
                </tr>
              ))
            ) : (
              doc.items.map((li, i) => (
                <tr key={li.id ?? i}>
                  <td style={cell}>{i + 1}</td>
                  <td style={cell}>{li.item_name}</td>
                  <td style={cell}>{li.unit_name ?? ''}</td>
                  <td style={{ ...cell, textAlign: 'right' }}>{fmt(li.qty)}</td>
                  {isMoney && <td style={{ ...cell, textAlign: 'right' }}>{fmt(li.price)}</td>}
                  {type === 'transfer' && <td style={cell}>{li.warehouse_from_name ?? ''}</td>}
                  {type === 'transfer' && <td style={cell}>{li.warehouse_to_name ?? ''}</td>}
                  {isMoney && <td style={{ ...cell, textAlign: 'right' }}>{fmt(li.qty * (li.price ?? 0))}</td>}
                </tr>
              ))
            )}
          </tbody>
        </table>

        <div style={{ marginTop: 12 }}>
          Всего наименований: <b>{type === 'inventory' ? doc.results.length : doc.items.length}</b>
          {isMoney && <> &nbsp;•&nbsp; Сумма: <b>{fmt(totalSum)} руб.</b></>}
        </div>

        {/* Подписи */}
        <table style={{ width: '100%', marginTop: 56, borderCollapse: 'collapse' }}>
          <tbody>
            <tr>
              {signs.map(([role, who]) => (
                <td key={role} style={{ textAlign: 'center' }}>
                  <div style={{ marginBottom: 36 }}>{role}</div>
                  <div style={{ borderTop: '1px solid #333', paddingTop: 4, fontSize: 12 }}>
                    {who ? `(___) ${who}` : '(подпись)'}
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>

        <div style={{ marginTop: 40, fontSize: 11, color: '#555' }}>
          Сформировано в «Склад ПРО» {dayjs().format('DD.MM.YYYY HH:mm')}
        </div>
      </div>
    </div>
  )
}
