import { Tag } from 'antd'
import CrudPage, { type FieldDef } from '../components/CrudPage'
import { listPartners, createPartner, updatePartner, deletePartner, type Partner } from '../api/references'

const KIND_LABEL: Record<Partner['kind'], string> = {
  supplier: 'Поставщик',
  customer: 'Покупатель',
  both: 'Поставщик и покупатель',
}

/** Поля формы контрагента (поля 1-в-1 со старым листом «Поставщики»). */
const FIELDS: FieldDef[] = [
  {
    name: 'kind', label: 'Тип', type: 'select', required: true, defaultValue: 'supplier',
    options: async () => [
      { value: 'supplier', label: 'Поставщик' },
      { value: 'customer', label: 'Покупатель' },
      { value: 'both', label: 'Поставщик и покупатель' },
    ],
  },
  { name: 'full_name', label: 'Наименование', type: 'text', required: true, placeholder: 'Организация / ФИО' },
  { name: 'short_name', label: 'Краткое наименование', type: 'text' },
  { name: 'phone', label: 'Телефон', type: 'text', placeholder: 'Тел/факс' },
  { name: 'email', label: 'E-mail', type: 'text' },
  { name: 'inn', label: 'ИНН', type: 'text' },
  { name: 'ogrn', label: 'ОГРН / ОГРНИП', type: 'text' },
  { name: 'legal_address', label: 'Юридический адрес', type: 'text' },
  { name: 'postal_address', label: 'Почтовый адрес', type: 'text' },
  { name: 'notes', label: 'Примечание', type: 'textarea' },
]

/** Страница «Поставщики»: список контрагентов с поиском и CRUD. */
export default function Partners() {
  return (
    <CrudPage<Partner>
      title="Поставщики"
      searchPlaceholder="Поиск: наименование, ИНН…"
      addLabel="Добавить"
      load={async (q) => ({ rows: await listPartners(q) })}
      create={(d) => createPartner(d as Parameters<typeof createPartner>[0])}
      update={(id, d) => updatePartner(id, d as Parameters<typeof updatePartner>[1])}
      remove={deletePartner}
      columns={[
        {
          title: 'Тип', dataIndex: 'kind', width: 160,
          render: (v: Partner['kind']) => (
            <Tag color={v === 'supplier' ? 'blue' : v === 'customer' ? 'purple' : 'cyan'}>{KIND_LABEL[v]}</Tag>
          ),
        },
        { title: 'Наименование', dataIndex: 'full_name', ellipsis: true },
        { title: 'Кратко', dataIndex: 'short_name', width: 160, ellipsis: true },
        { title: 'Телефон', dataIndex: 'phone', width: 130 },
        { title: 'E-mail', dataIndex: 'email', width: 180, ellipsis: true },
        { title: 'ИНН', dataIndex: 'inn', width: 130 },
        { title: 'ОГРН', dataIndex: 'ogrn', width: 150 },
      ]}
      fields={FIELDS}
    />
  )
}
