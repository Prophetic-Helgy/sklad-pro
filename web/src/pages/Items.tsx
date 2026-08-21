import { Tag } from 'antd'
import CrudPage, { type FieldDef } from '../components/CrudPage'
import {
  listItems, createItem, updateItem, deleteItem, deactivateItem,
  listUnits, listCategories, listPartners, type Item,
} from '../api/references'

/** Поля формы товара (соответствуют карточке номенклатуры из Excel 7.1). */
const FIELDS: FieldDef[] = [
  { name: 'name', label: 'Наименование', type: 'text', required: true, placeholder: 'Например: Болт М8' },
  { name: 'sku', label: 'Артикул', type: 'text', required: true, placeholder: 'Артикул' },
  { name: 'barcode', label: 'Штрих-код', type: 'text', placeholder: 'Штрих-код' },
  {
    name: 'unit_id', label: 'Ед. изм.', type: 'select', required: true,
    options: async () => (await listUnits()).map((u) => ({ value: u.id, label: u.name })),
  },
  {
    name: 'category_id', label: 'Категория', type: 'select',
    options: async () => (await listCategories()).map((c) => ({ value: c.id, label: c.name })),
  },
  { name: 'min_qty', label: 'Мин. остаток', type: 'number', defaultValue: 0 },
  { name: 'cost_price', label: 'Себестоимость', type: 'number', defaultValue: 0 },
  { name: 'sale_price', label: 'Цена продажи', type: 'number', defaultValue: 0 },
  {
    name: 'default_partner_id', label: 'Поставщик по умолчанию', type: 'select',
    options: async () => (await listPartners()).map((p) => ({ value: p.id, label: p.full_name })),
  },
  { name: 'notes', label: 'Примечание', type: 'textarea' },
]

/** Страница «Номенклатура»: таблица товаров, поиск, добавление, изменение, деактивация. */
export default function Items() {
  return (
    <CrudPage<Item>
      title="Номенклатура"
      searchPlaceholder="Поиск: наименование, артикул, штрих-код…"
      addLabel="Новая позиция"
      load={async (q, page) => {
        const res = await listItems({ q, page, include_inactive: true })
        return { rows: res.items, total: res.total }
      }}
      create={(d) => createItem(d as Parameters<typeof createItem>[0])}
      update={(id, d) => updateItem(id, d as Parameters<typeof updateItem>[1])}
      remove={deleteItem}
      deactivate={async (row) => deactivateItem(row.id)}
      columns={[
        { title: 'Артикул', dataIndex: 'sku', width: 110 },
        { title: 'Наименование', dataIndex: 'name', ellipsis: true },
        { title: 'Ед. изм.', dataIndex: 'unit_name', width: 90 },
        { title: 'Категория', dataIndex: 'category_name', width: 140 },
        { title: 'Штрих-код', dataIndex: 'barcode', width: 130 },
        { title: 'Мин.', dataIndex: 'min_qty', width: 70, align: 'right' },
        { title: 'Себест.', dataIndex: 'cost_price', width: 90, align: 'right' },
        { title: 'Цена', dataIndex: 'sale_price', width: 90, align: 'right' },
        { title: 'Поставщик', dataIndex: 'default_partner_name', width: 180, ellipsis: true },
        {
          title: 'Статус', dataIndex: 'active', width: 110,
          render: (v: boolean) => (v ? <Tag color="green">Активен</Tag> : <Tag color="default">Неактивен</Tag>),
        },
      ]}
      fields={FIELDS}
    />
  )
}
