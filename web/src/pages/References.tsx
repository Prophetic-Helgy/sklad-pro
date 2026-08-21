import { Tag, Tabs } from 'antd'
import CrudPage from '../components/CrudPage'
import {
  listUnits, createUnit, updateUnit, deleteUnit,
  listCategories, createCategory, updateCategory, deleteCategory,
  listWarehouses, createWarehouse, updateWarehouse, deleteWarehouse,
  type Unit, type Category, type Warehouse,
} from '../api/references'

/** Единицы измерения: одно поле — наименование. */
function UnitsTab() {
  return (
    <CrudPage<Unit>
      load={async () => ({ rows: await listUnits() })}
      create={(d) => createUnit(d as { name: string })}
      update={(id, d) => updateUnit(id, d as { name: string })}
      remove={deleteUnit}
      columns={[{ title: 'Наименование', dataIndex: 'name', width: 200 }]}
      fields={[{ name: 'name', label: 'Наименование', type: 'text', required: true, placeholder: 'Например: шт, кг, м' }]}
      searchPlaceholder="Поиск…"
    />
  )
}

/** Категории: наименование + родитель (опционально). */
function CategoriesTab() {
  return (
    <CrudPage<Category & { parent_name: string }>
      load={async () => {
        const cats = await listCategories()
        const byId = new Map(cats.map((c) => [c.id, c.name]))
        return {
          rows: cats.map((c) => ({ ...c, parent_name: c.parent_id ? byId.get(c.parent_id) ?? '—' : '' })),
        }
      }}
      create={(d) => createCategory(d as { name: string; parent_id: number | null })}
      update={(id, d) => updateCategory(id, d as { name: string; parent_id: number | null })}
      remove={deleteCategory}
      columns={[
        { title: 'Наименование', dataIndex: 'name' },
        { title: 'Родитель', dataIndex: 'parent_name', width: 200 },
      ]}
      fields={[
        { name: 'name', label: 'Наименование', type: 'text', required: true },
        {
          name: 'parent_id', label: 'Родительская категория', type: 'select',
          options: async () => (await listCategories()).map((c) => ({ value: c.id, label: c.name })),
        },
      ]}
      searchPlaceholder="Поиск…"
    />
  )
}

/** Склады: наименование + флаг активности. */
function WarehousesTab() {
  return (
    <CrudPage<Warehouse>
      load={async () => ({ rows: await listWarehouses() })}
      create={(d) => createWarehouse(d as { name: string; active: boolean })}
      update={(id, d) => updateWarehouse(id, d as { name: string; active: boolean })}
      remove={deleteWarehouse}
      columns={[
        { title: 'Наименование', dataIndex: 'name', width: 250 },
        {
          title: 'Статус', dataIndex: 'active', width: 110,
          render: (v: boolean) => (v ? <Tag color="green">Активен</Tag> : <Tag color="default">Неактивен</Tag>),
        },
      ]}
      fields={[
        { name: 'name', label: 'Наименование', type: 'text', required: true, placeholder: 'Например: Основной' },
        { name: 'active', label: 'Активен', type: 'boolean', defaultValue: true },
      ]}
      searchPlaceholder="Поиск…"
    />
  )
}

/** Страница «Справочники»: вкладки для малых справочников. */
export default function References() {
  return (
    <div>
      <h2 style={{ marginBottom: 8 }}>Справочники</h2>
      <Tabs
        defaultActiveKey="units"
        items={[
          { key: 'units', label: 'Единицы измерения', children: <UnitsTab /> },
          { key: 'categories', label: 'Категории', children: <CategoriesTab /> },
          { key: 'warehouses', label: 'Склады', children: <WarehousesTab /> },
        ]}
      />
    </div>
  )
}
