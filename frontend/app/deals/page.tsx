'use client'
import { useEffect, useState, useMemo } from 'react'
import { getDeals, Deal } from '../../lib/api'
import * as XLSX from 'xlsx'

function fmt(n?: number, decimals = 0) {
  if (n == null) return '—'
  return n.toLocaleString('es-ES', { maximumFractionDigits: decimals })
}

function getSource(url?: string): string {
  if (!url) return '—'
  if (url.includes('idealista.com')) return 'Idealista'
  if (url.includes('redpiso.es')) return 'Redpiso'
  if (url.includes('fotocasa.es')) return 'Fotocasa'
  if (url.includes('pisos.com')) return 'Pisos.com'
  return 'Manual'
}

const ALL_COLUMNS = [
  { key: 'address', label: 'Dirección' },
  { key: 'district', label: 'Distrito' },
  { key: 'zone', label: 'Zona' },
  { key: 'size_sqm', label: 'm²' },
  { key: 'bedrooms', label: 'Hab.' },
  { key: 'bathrooms', label: 'Baños' },
  { key: 'floor', label: 'Planta' },
  { key: 'asking_price', label: 'Precio' },
  { key: 'price_per_sqm', label: '€/m²' },
  { key: 'condition', label: 'Estado' },
  { key: 'amenities', label: 'Amenidades' },
  { key: 'source', label: 'Fuente' },
  { key: 'listed_date', label: 'Fecha Listing' },
] as const

type ColKey = typeof ALL_COLUMNS[number]['key']

const DEFAULT_VISIBLE: ColKey[] = [
  'address', 'district', 'zone', 'size_sqm', 'bedrooms', 'bathrooms',
  'floor', 'asking_price', 'price_per_sqm', 'condition', 'source', 'listed_date'
]

type SortField = 'size_sqm' | 'asking_price' | 'price_per_sqm'
type SortDir = 'asc' | 'desc'
type FilterKey = 'distrito' | 'habitaciones' | 'banos' | 'estado' | 'sqm' | 'precio' | 'fuente' | 'amenidades' | 'planta'

const CONDITION_BADGE: Record<string, { label: string; className: string }> = {
  newdevelopment: { label: 'Nueva', className: 'bg-emerald-100 text-emerald-700' },
  good:           { label: 'Buen estado', className: 'bg-blue-100 text-blue-700' },
  renew:          { label: 'A reformar', className: 'bg-orange-100 text-orange-700' },
}

function ConditionBadge({ condition }: { condition: string | null | undefined }) {
  const cfg = CONDITION_BADGE[condition ?? '']
  if (!cfg) return <span className="text-gray-400 text-xs">{condition ?? '—'}</span>
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

function AmenityBadges({ deal }: { deal: any }) {
  const items = [
    { key: 'elevator', label: 'A' },
    { key: 'terrace',  label: 'T' },
    { key: 'garage',   label: 'G' },
  ]
  return (
    <div className="flex gap-0.5">
      {items.map(({ key, label }) => (
        <span
          key={key}
          className={`inline-flex w-5 h-5 rounded text-[10px] font-bold items-center justify-center ${
            deal[key] ? 'bg-gray-700 text-white' : 'bg-gray-100 text-gray-300'
          }`}
        >
          {label}
        </span>
      ))}
    </div>
  )
}

function toggleSet<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set)
  next.has(value) ? next.delete(value) : next.add(value)
  return next
}

function SortTh({ label, field, sortField, sortDir, onSort }: {
  label: string; field: SortField
  sortField: SortField | null; sortDir: SortDir
  onSort: (f: SortField) => void
}) {
  const active = sortField === field
  return (
    <th onClick={() => onSort(field)} className="px-4 py-3 text-right cursor-pointer select-none hover:bg-gray-100">
      {label}
      <span className="ml-1 text-gray-400 text-xs" style={{ fontFamily: 'monospace' }}>
        {active ? (sortDir === 'asc' ? '▲' : '▼') : '▲▼'}
      </span>
    </th>
  )
}

function FilterTh({
  label, filterKey, openFilter, setOpenFilter, active, align = 'left', children,
}: {
  label: string
  filterKey: FilterKey
  openFilter: FilterKey | null
  setOpenFilter: (k: FilterKey | null) => void
  active: boolean
  align?: 'left' | 'right'
  children: React.ReactNode
}) {
  const isOpen = openFilter === filterKey
  return (
    <th className={`px-4 py-3 text-${align} relative`}>
      <span
        data-filter-btn
        className={`inline-flex items-center gap-1 select-none cursor-pointer hover:text-gray-800 ${active ? 'text-blue-600 font-semibold' : 'text-gray-500'}`}
        onClick={e => { e.stopPropagation(); setOpenFilter(isOpen ? null : filterKey) }}
      >
        {label} <span className="text-[10px]">▾</span>
      </span>
      {isOpen && (
        <div
          data-filter-dropdown
          className={`absolute top-full ${align === 'right' ? 'right-0' : 'left-0'} z-50 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 min-w-[140px]`}
          onClick={e => e.stopPropagation()}
        >
          {children}
        </div>
      )}
    </th>
  )
}

function SortFilterTh({
  label, field, sortField, sortDir, onSort,
  filterKey, openFilter, setOpenFilter, active, children,
}: {
  label: string; field: SortField
  sortField: SortField | null; sortDir: SortDir
  onSort: (f: SortField) => void
  filterKey: FilterKey
  openFilter: FilterKey | null
  setOpenFilter: (k: FilterKey | null) => void
  active: boolean
  children: React.ReactNode
}) {
  const isOpen = openFilter === filterKey
  const sortActive = sortField === field
  return (
    <th className="px-4 py-3 text-right relative">
      <span className="inline-flex items-center gap-1 justify-end select-none">
        <span
          data-filter-btn
          onClick={e => { e.stopPropagation(); setOpenFilter(isOpen ? null : filterKey) }}
          className={`cursor-pointer hover:text-gray-800 ${active ? 'text-blue-600 font-semibold' : ''}`}
        >
          {label} <span className="text-[10px]">▾</span>
        </span>
        <span
          onClick={() => onSort(field)}
          className="cursor-pointer text-gray-400 text-xs hover:text-gray-600"
          style={{ fontFamily: 'monospace' }}
        >
          {sortActive ? (sortDir === 'asc' ? '▲' : '▼') : '▲▼'}
        </span>
      </span>
      {isOpen && (
        <div
          data-filter-dropdown
          className="absolute top-full right-0 z-50 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 min-w-[160px]"
          onClick={e => e.stopPropagation()}
        >
          {children}
        </div>
      )}
    </th>
  )
}

const PAGE_SIZES = [25, 50, 100, 0]

export default function DealsPage() {
  const [deals, setDeals] = useState<Deal[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState('')

  const [filterDistricts, setFilterDistricts] = useState<Set<string>>(new Set())
  const [filterConditions, setFilterConditions] = useState<Set<string>>(new Set())
  const [filterBedrooms, setFilterBedrooms] = useState<Set<number>>(new Set())
  const [filterBaths, setFilterBaths] = useState<Set<number>>(new Set())
  const [filterSources, setFilterSources] = useState<Set<string>>(new Set())
  const [filterFloors, setFilterFloors] = useState<Set<number>>(new Set())
  const [filterElevator, setFilterElevator] = useState<boolean | null>(null)
  const [filterTerrace, setFilterTerrace] = useState<boolean | null>(null)
  const [filterGarage, setFilterGarage] = useState<boolean | null>(null)
  const [filterIncludeNullCondition, setFilterIncludeNullCondition] = useState(false)
  const [filterIncludeNullDistrict, setFilterIncludeNullDistrict] = useState(false)
  const [filterIncludeNullBedrooms, setFilterIncludeNullBedrooms] = useState(false)
  const [filterIncludeNullBaths, setFilterIncludeNullBaths] = useState(false)
  const [filterIncludeNullSource, setFilterIncludeNullSource] = useState(false)
  const [filterSqmMin, setFilterSqmMin] = useState('')
  const [filterSqmMax, setFilterSqmMax] = useState('')
  const [filterPriceMin, setFilterPriceMin] = useState('')
  const [filterPriceMax, setFilterPriceMax] = useState('')

  const [openFilter, setOpenFilter] = useState<FilterKey | null>(null)

  const [sortField, setSortField] = useState<SortField | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  const [visibleCols, setVisibleCols] = useState<ColKey[]>(() => {
    if (typeof window === 'undefined') return DEFAULT_VISIBLE
    try {
      const saved = localStorage.getItem('deals_visible_cols')
      return saved ? JSON.parse(saved) : DEFAULT_VISIBLE
    } catch { return DEFAULT_VISIBLE }
  })
  const [showColPicker, setShowColPicker] = useState(false)

  function toggleCol(key: ColKey) {
    setVisibleCols(prev => {
      const next = prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
      localStorage.setItem('deals_visible_cols', JSON.stringify(next))
      return next
    })
  }

  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      const target = e.target as Element
      if (!target.closest('[data-filter-dropdown]') && !target.closest('[data-filter-btn]')) {
        setOpenFilter(null)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [])

  useEffect(() => {
    if (!showColPicker) return
    function handleClick(e: MouseEvent) {
      const target = e.target as HTMLElement
      if (!target.closest('[data-col-picker]')) setShowColPicker(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showColPicker])

  useEffect(() => {
    getDeals()
      .then(setDeals)
      .catch(() => setFetchError('No se pudo conectar al backend. Asegúrate de que está corriendo en el puerto 8000.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { setPage(1) }, [
    filterDistricts, filterConditions, filterBedrooms, filterBaths, filterSources, filterFloors,
    filterElevator, filterTerrace, filterGarage,
    filterIncludeNullCondition, filterIncludeNullDistrict, filterIncludeNullBedrooms,
    filterIncludeNullBaths, filterIncludeNullSource,
    filterSqmMin, filterSqmMax, filterPriceMin, filterPriceMax,
    sortField, sortDir, pageSize,
  ])

  const allDistricts = useMemo(
    () => Array.from(new Set(deals.map(d => d.district).filter(Boolean))).sort() as string[],
    [deals]
  )
  const allConditions = useMemo(
    () => Array.from(new Set(deals.map(d => d.condition).filter(Boolean))).sort() as string[],
    [deals]
  )
  const allBedrooms = useMemo(
    () => (Array.from(new Set(deals.map(d => d.bedrooms).filter(b => b != null))) as number[]).sort((a, b) => a - b),
    [deals]
  )
  const allBaths = useMemo(
    () => (Array.from(new Set(deals.map(d => d.bathrooms).filter(b => b != null))) as number[]).sort((a, b) => a - b),
    [deals]
  )
  const allSources = useMemo(
    () => ['Idealista', 'Redpiso', 'Fotocasa', 'Pisos.com', 'Manual'].filter(src =>
      deals.some(d => getSource(d.url) === src)
    ),
    [deals]
  )
  const allFloors = useMemo(
    () => (Array.from(new Set(deals.map(d => d.floor).filter(f => f != null))) as number[]).sort((a, b) => a - b),
    [deals]
  )
  const nullConditionCount = useMemo(
    () => deals.filter(d => d.condition == null || d.condition === '').length,
    [deals]
  )
  const nullDistrictCount = useMemo(
    () => deals.filter(d => d.district == null || d.district === '').length,
    [deals]
  )
  const nullBedsCount = useMemo(() => deals.filter(d => d.bedrooms == null).length, [deals])
  const nullBathsCount = useMemo(() => deals.filter(d => d.bathrooms == null).length, [deals])

  const visibleDeals = useMemo(() => {
    let result = deals.filter(d => {
      // District filter
      if (filterDistricts.size > 0) {
        const distMatch = filterDistricts.has(d.district ?? '')
        const nullMatch = filterIncludeNullDistrict && (d.district == null || d.district === '')
        if (!distMatch && !nullMatch) return false
      }
      // Estado filter
      if (filterConditions.size > 0) {
        const condMatch = filterConditions.has(d.condition ?? '')
        const nullMatch = filterIncludeNullCondition && (d.condition == null || d.condition === '')
        if (!condMatch && !nullMatch) return false
      }
      // Bedrooms filter
      if (filterBedrooms.size > 0) {
        const bedsMatch = d.bedrooms != null && filterBedrooms.has(d.bedrooms)
        const nullMatch = filterIncludeNullBedrooms && d.bedrooms == null
        if (!bedsMatch && !nullMatch) return false
      }
      // Bathrooms filter
      if (filterBaths.size > 0) {
        const bathsMatch = d.bathrooms != null && filterBaths.has(d.bathrooms)
        const nullMatch = filterIncludeNullBaths && d.bathrooms == null
        if (!bathsMatch && !nullMatch) return false
      }
      // Source filter
      if (filterSources.size > 0) {
        const src = getSource(d.url)
        const srcMatch = filterSources.has(src)
        const nullMatch = filterIncludeNullSource && src === '—'
        if (!srcMatch && !nullMatch) return false
      }
      // Floor filter
      if (filterFloors.size > 0 && !filterFloors.has(d.floor ?? -999)) return false
      // Amenity filters
      if (filterElevator !== null && d.elevator !== filterElevator) return false
      if (filterTerrace !== null && d.terrace !== filterTerrace) return false
      if (filterGarage !== null && d.garage !== filterGarage) return false
      // Range filters
      if (filterSqmMin && (d.size_sqm ?? 0) < parseFloat(filterSqmMin)) return false
      if (filterSqmMax && (d.size_sqm ?? Infinity) > parseFloat(filterSqmMax)) return false
      if (filterPriceMin && (d.asking_price ?? 0) < parseFloat(filterPriceMin)) return false
      if (filterPriceMax && (d.asking_price ?? Infinity) > parseFloat(filterPriceMax)) return false
      return true
    })
    if (sortField) {
      result = [...result].sort((a, b) => {
        let va = 0, vb = 0
        if (sortField === 'size_sqm') { va = a.size_sqm ?? 0; vb = b.size_sqm ?? 0 }
        else if (sortField === 'asking_price') { va = a.asking_price ?? 0; vb = b.asking_price ?? 0 }
        else {
          va = a.asking_price && a.size_sqm ? a.asking_price / a.size_sqm : 0
          vb = b.asking_price && b.size_sqm ? b.asking_price / b.size_sqm : 0
        }
        return sortDir === 'asc' ? va - vb : vb - va
      })
    }
    return result
  }, [
    deals,
    filterDistricts, filterIncludeNullDistrict,
    filterConditions, filterIncludeNullCondition,
    filterBedrooms, filterIncludeNullBedrooms,
    filterBaths, filterIncludeNullBaths,
    filterSources, filterIncludeNullSource,
    filterFloors, filterElevator, filterTerrace, filterGarage,
    filterSqmMin, filterSqmMax, filterPriceMin, filterPriceMax,
    sortField, sortDir,
  ])

  const totalPages = pageSize === 0 ? 1 : Math.ceil(visibleDeals.length / pageSize)
  const pagedDeals = pageSize === 0 ? visibleDeals : visibleDeals.slice((page - 1) * pageSize, page * pageSize)

  function handleSort(field: SortField) {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  const hasFilters = filterDistricts.size > 0 || filterConditions.size > 0 || filterBedrooms.size > 0
    || filterBaths.size > 0 || filterSources.size > 0 || filterFloors.size > 0
    || filterSqmMin || filterSqmMax || filterPriceMin || filterPriceMax
    || filterIncludeNullCondition || filterIncludeNullDistrict || filterIncludeNullBedrooms
    || filterIncludeNullBaths || filterIncludeNullSource
    || filterElevator !== null || filterTerrace !== null || filterGarage !== null

  function clearFilters() {
    setFilterDistricts(new Set()); setFilterConditions(new Set()); setFilterBedrooms(new Set())
    setFilterBaths(new Set()); setFilterSources(new Set()); setFilterFloors(new Set())
    setFilterSqmMin(''); setFilterSqmMax(''); setFilterPriceMin(''); setFilterPriceMax('')
    setFilterIncludeNullCondition(false); setFilterIncludeNullDistrict(false)
    setFilterIncludeNullBedrooms(false); setFilterIncludeNullBaths(false)
    setFilterIncludeNullSource(false)
    setFilterElevator(null); setFilterTerrace(null); setFilterGarage(null)
  }

  function handleExportCSV() {
    const headers = ['Dirección', 'URL', 'Distrito', 'Zona', 'm²', 'Hab.', 'Baños', 'Planta', 'Precio (€)', '€/m²', 'Condición', 'Fecha']
    const rows = visibleDeals.map(d => [
      d.address ?? '',
      d.url ?? '',
      d.district ?? '',
      d.zone ?? '',
      d.size_sqm ?? '',
      d.bedrooms ?? '',
      d.bathrooms ?? '',
      d.floor ?? '',
      d.asking_price ?? '',
      d.asking_price && d.size_sqm ? Math.round(d.asking_price / d.size_sqm) : '',
      d.condition ?? '',
      d.listed_date ?? '',
    ])
    const csv = [headers, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `capresol-deals-${new Date().toISOString().slice(0,10)}.csv`
    a.click(); URL.revokeObjectURL(url)
  }

  function handleExportXLSX() {
    const rows = visibleDeals.map(d => ({
      'Dirección': d.address ?? '',
      'URL': d.url ?? '',
      'Distrito': d.district ?? '',
      'Zona': d.zone ?? '',
      'm²': d.size_sqm ?? '',
      'Hab.': d.bedrooms ?? '',
      'Baños': d.bathrooms ?? '',
      'Planta': d.floor ?? '',
      'Precio (€)': d.asking_price ?? '',
      '€/m²': d.asking_price && d.size_sqm ? Math.round(d.asking_price / d.size_sqm) : '',
      'Condición': d.condition ?? '',
      'Fecha': d.listed_date ?? '',
    }))
    const ws = XLSX.utils.json_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Deals')
    XLSX.writeFile(wb, `capresol-deals-${new Date().toISOString().slice(0,10)}.xlsx`)
  }

  const checkboxClass = 'w-3.5 h-3.5 accent-blue-600 cursor-pointer shrink-0'
  const checkRowClass = 'flex items-center gap-2 px-1 py-1 rounded hover:bg-gray-50 cursor-pointer text-xs font-normal normal-case text-gray-700'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Deals</h1>
          {!loading && <span className="text-sm text-gray-400">{visibleDeals.length} de {deals.length}</span>}
          {hasFilters && (
            <button onClick={clearFilters} className="text-xs text-red-500 hover:text-red-700 underline">
              Limpiar filtros
            </button>
          )}
        </div>
        <div className="flex gap-1 items-center">
          <button onClick={handleExportCSV} title={`Exportar ${visibleDeals.length} deals a CSV`}
            className="px-3 py-2 border border-gray-300 text-gray-600 rounded-md text-xs font-medium hover:bg-gray-50">
            ↓ CSV
          </button>
          <button onClick={handleExportXLSX} title={`Exportar ${visibleDeals.length} deals a Excel`}
            className="px-3 py-2 border border-gray-300 text-gray-600 rounded-md text-xs font-medium hover:bg-gray-50">
            ↓ Excel
          </button>
          {/* Column picker */}
          <div className="relative" data-col-picker>
            <button
              onClick={() => setShowColPicker(v => !v)}
              className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 border border-gray-300"
            >
              Columnas ⚙
            </button>
            {showColPicker && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-white border border-gray-200 rounded shadow-lg p-3 w-48">
                {ALL_COLUMNS.map(col => (
                  <label key={col.key} className="flex items-center gap-2 py-1 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={visibleCols.includes(col.key)}
                      onChange={() => toggleCol(col.key)}
                      className="rounded"
                    />
                    {col.label}
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {fetchError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
          {fetchError}
        </div>
      )}

      {loading ? (
        <p className="text-gray-400">Cargando…</p>
      ) : (
        <>
          <div className="overflow-auto rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
                <tr>
                  {visibleCols.includes('address') && <th className="px-4 py-3 text-left">Dirección</th>}

                  {visibleCols.includes('district') && (
                    <FilterTh label="Distrito" filterKey="distrito" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={filterDistricts.size > 0 || filterIncludeNullDistrict}>
                      <div className="max-h-52 overflow-y-auto">
                        {allDistricts.map(d => (
                          <label key={d} className={checkRowClass}>
                            <input type="checkbox" className={checkboxClass}
                              checked={filterDistricts.has(d)}
                              onChange={() => setFilterDistricts(prev => toggleSet(prev, d))} />
                            {d}
                          </label>
                        ))}
                        {nullDistrictCount > 0 && (
                          <label className={checkRowClass + ' mt-1 pt-1 border-t border-gray-100'}>
                            <input type="checkbox" className={checkboxClass}
                              checked={filterIncludeNullDistrict}
                              onChange={() => setFilterIncludeNullDistrict(v => !v)} />
                            <span className="text-gray-400 italic">Sin distrito ({nullDistrictCount})</span>
                          </label>
                        )}
                      </div>
                    </FilterTh>
                  )}

                  {visibleCols.includes('zone') && <th className="px-4 py-3 text-left">Zona</th>}

                  {visibleCols.includes('size_sqm') && (
                    <SortFilterTh label="m²" field="size_sqm" sortField={sortField} sortDir={sortDir} onSort={handleSort}
                      filterKey="sqm" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={!!(filterSqmMin || filterSqmMax)}>
                      <div className="flex flex-col gap-1.5">
                        <p className="text-[10px] text-gray-400 uppercase font-medium px-1">m²</p>
                        <div className="flex items-center gap-1">
                          <input type="number" placeholder="Min" value={filterSqmMin}
                            onChange={e => setFilterSqmMin(e.target.value)}
                            className="w-16 border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
                          <span className="text-gray-400 text-xs">–</span>
                          <input type="number" placeholder="Max" value={filterSqmMax}
                            onChange={e => setFilterSqmMax(e.target.value)}
                            className="w-16 border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
                        </div>
                      </div>
                    </SortFilterTh>
                  )}

                  {visibleCols.includes('bedrooms') && (
                    <FilterTh label="Hab." filterKey="habitaciones" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={filterBedrooms.size > 0 || filterIncludeNullBedrooms} align="right">
                      <div className="flex flex-wrap gap-1 px-1">
                        {allBedrooms.map(b => (
                          <label key={b} className="flex items-center gap-1 text-xs font-normal normal-case text-gray-700 cursor-pointer">
                            <input type="checkbox" className={checkboxClass}
                              checked={filterBedrooms.has(b)}
                              onChange={() => setFilterBedrooms(prev => toggleSet(prev, b))} />
                            {b}
                          </label>
                        ))}
                      </div>
                      {nullBedsCount > 0 && (
                        <label className="flex items-center gap-1 text-xs font-normal normal-case text-gray-400 italic cursor-pointer mt-1 pt-1 border-t border-gray-100 w-full px-1">
                          <input type="checkbox" className={checkboxClass}
                            checked={filterIncludeNullBedrooms}
                            onChange={() => setFilterIncludeNullBedrooms(v => !v)} />
                          Sin datos ({nullBedsCount})
                        </label>
                      )}
                    </FilterTh>
                  )}

                  {visibleCols.includes('bathrooms') && (
                    <FilterTh label="Baños" filterKey="banos" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={filterBaths.size > 0 || filterIncludeNullBaths} align="right">
                      <div className="flex flex-wrap gap-1 px-1">
                        {allBaths.map(b => (
                          <label key={b} className="flex items-center gap-1 text-xs font-normal normal-case text-gray-700 cursor-pointer">
                            <input type="checkbox" className={checkboxClass}
                              checked={filterBaths.has(b)}
                              onChange={() => setFilterBaths(prev => toggleSet(prev, b))} />
                            {b}
                          </label>
                        ))}
                      </div>
                      {nullBathsCount > 0 && (
                        <label className="flex items-center gap-1 text-xs font-normal normal-case text-gray-400 italic cursor-pointer mt-1 pt-1 border-t border-gray-100 w-full px-1">
                          <input type="checkbox" className={checkboxClass}
                            checked={filterIncludeNullBaths}
                            onChange={() => setFilterIncludeNullBaths(v => !v)} />
                          Sin datos ({nullBathsCount})
                        </label>
                      )}
                    </FilterTh>
                  )}

                  {visibleCols.includes('floor') && (
                    <FilterTh label="Planta" filterKey="planta" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={filterFloors.size > 0} align="right">
                      <div className="max-h-40 overflow-y-auto">
                        {allFloors.map(f => (
                          <label key={f} className={checkRowClass}>
                            <input type="checkbox" className={checkboxClass}
                              checked={filterFloors.has(f)}
                              onChange={() => setFilterFloors(prev => toggleSet(prev, f))} />
                            {f}
                          </label>
                        ))}
                      </div>
                    </FilterTh>
                  )}

                  {visibleCols.includes('asking_price') && (
                    <SortFilterTh label="Precio" field="asking_price" sortField={sortField} sortDir={sortDir} onSort={handleSort}
                      filterKey="precio" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={!!(filterPriceMin || filterPriceMax)}>
                      <div className="flex flex-col gap-1.5">
                        <p className="text-[10px] text-gray-400 uppercase font-medium px-1">Precio (€)</p>
                        <div className="flex items-center gap-1">
                          <input type="number" placeholder="Min" value={filterPriceMin}
                            onChange={e => setFilterPriceMin(e.target.value)}
                            className="w-24 border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
                          <span className="text-gray-400 text-xs">–</span>
                          <input type="number" placeholder="Max" value={filterPriceMax}
                            onChange={e => setFilterPriceMax(e.target.value)}
                            className="w-24 border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
                        </div>
                      </div>
                    </SortFilterTh>
                  )}

                  {visibleCols.includes('price_per_sqm') && (
                    <SortTh label="€/m²" field="price_per_sqm" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
                  )}

                  {visibleCols.includes('condition') && (
                    <FilterTh label="Estado" filterKey="estado" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={filterConditions.size > 0 || filterIncludeNullCondition}>
                      <div>
                        {allConditions.map(c => (
                          <label key={c} className={checkRowClass}>
                            <input type="checkbox" className={checkboxClass}
                              checked={filterConditions.has(c)}
                              onChange={() => setFilterConditions(prev => toggleSet(prev, c))} />
                            {CONDITION_BADGE[c]?.label ?? c}
                          </label>
                        ))}
                        {nullConditionCount > 0 && (
                          <label className={checkRowClass + ' mt-1 pt-1 border-t border-gray-100'}>
                            <input type="checkbox" className={checkboxClass}
                              checked={filterIncludeNullCondition}
                              onChange={() => setFilterIncludeNullCondition(v => !v)} />
                            <span className="text-gray-400 italic">Sin estado ({nullConditionCount})</span>
                          </label>
                        )}
                      </div>
                    </FilterTh>
                  )}

                  {visibleCols.includes('amenities') && (
                    <FilterTh label="Amenidades" filterKey="amenidades" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={filterElevator !== null || filterTerrace !== null || filterGarage !== null}>
                      <div className="space-y-1 px-1 text-xs font-normal normal-case text-gray-700">
                        <p className="text-[10px] text-gray-400 uppercase font-medium mb-2">Mostrar solo con:</p>
                        {([
                          { label: 'Ascensor', state: filterElevator, setter: setFilterElevator },
                          { label: 'Terraza', state: filterTerrace, setter: setFilterTerrace },
                          { label: 'Garaje', state: filterGarage, setter: setFilterGarage },
                        ] as const).map(({ label, state, setter }) => (
                          <label key={label} className="flex items-center gap-2 py-0.5 cursor-pointer">
                            <input type="checkbox" className={checkboxClass}
                              checked={state === true}
                              onChange={() => setter(prev => prev === true ? null : true)} />
                            {label}
                          </label>
                        ))}
                      </div>
                    </FilterTh>
                  )}

                  {visibleCols.includes('source') && (
                    <FilterTh label="Fuente" filterKey="fuente" openFilter={openFilter} setOpenFilter={setOpenFilter}
                      active={filterSources.size > 0 || filterIncludeNullSource}>
                      <div>
                        {allSources.map(src => (
                          <label key={src} className={checkRowClass}>
                            <input type="checkbox" className={checkboxClass}
                              checked={filterSources.has(src)}
                              onChange={() => setFilterSources(prev => toggleSet(prev, src))} />
                            {src}
                          </label>
                        ))}
                      </div>
                    </FilterTh>
                  )}
                  {visibleCols.includes('listed_date') && <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">F. Listing</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {pagedDeals.length === 0 && (
                  <tr>
                    <td colSpan={11} className="text-center py-10 text-gray-400">
                      {hasFilters ? 'No hay deals con estos filtros' : 'No hay deals'}
                    </td>
                  </tr>
                )}
                {pagedDeals.map(deal => {
                  const askPsqm = deal.asking_price && deal.size_sqm ? deal.asking_price / deal.size_sqm : undefined
                  return (
                    <tr key={deal.id} className="hover:bg-gray-50">
                      {visibleCols.includes('address') && (
                        <td className="px-4 py-2 max-w-xs truncate">
                          {deal.url ? (
                            <a href={deal.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                              {deal.address || deal.url}
                            </a>
                          ) : (deal.address || '—')}
                        </td>
                      )}
                      {visibleCols.includes('district') && <td className="px-4 py-2 text-gray-600">{deal.district || '—'}</td>}
                      {visibleCols.includes('zone') && <td className="px-4 py-2 text-gray-500">{deal.zone ?? '—'}</td>}
                      {visibleCols.includes('size_sqm') && <td className="px-4 py-2 text-right">{fmt(deal.size_sqm)}</td>}
                      {visibleCols.includes('bedrooms') && <td className="px-4 py-2 text-right">{deal.bedrooms ?? '—'}</td>}
                      {visibleCols.includes('bathrooms') && <td className="px-4 py-2 text-right">{deal.bathrooms ?? '—'}</td>}
                      {visibleCols.includes('floor') && <td className="px-4 py-2 text-right">{deal.floor ?? '—'}</td>}
                      {visibleCols.includes('asking_price') && (
                        <td className="px-4 py-2 text-right font-medium">
                          {deal.asking_price ? `€${fmt(deal.asking_price)}` : '—'}
                        </td>
                      )}
                      {visibleCols.includes('price_per_sqm') && (
                        <td className="px-4 py-2 text-right text-gray-500">
                          {askPsqm ? `€${fmt(askPsqm)}` : '—'}
                        </td>
                      )}
                      {visibleCols.includes('condition') && (
                        <td className="px-4 py-2">
                          <ConditionBadge condition={deal.condition} />
                        </td>
                      )}
                      {visibleCols.includes('amenities') && (
                        <td className="px-4 py-2">
                          <AmenityBadges deal={deal} />
                        </td>
                      )}
                      {visibleCols.includes('source') && (
                        <td className="px-4 py-2 text-sm text-gray-600 whitespace-nowrap">{getSource(deal.url)}</td>
                      )}
                      {visibleCols.includes('listed_date') && (
                        <td className="px-4 py-2 text-sm text-gray-600 whitespace-nowrap">
                          {deal.listed_date ? new Date(deal.listed_date).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '—'}
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-3 text-sm text-gray-500">
            <div className="flex items-center gap-2">
              <span>Mostrar</span>
              <select
                value={pageSize}
                onChange={e => setPageSize(Number(e.target.value))}
                className="border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {PAGE_SIZES.map(s => (
                  <option key={s} value={s}>{s === 0 ? 'Todos' : s}</option>
                ))}
              </select>
              <span>por página</span>
            </div>

            {pageSize !== 0 && totalPages > 1 && (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-2 py-1 rounded border border-gray-200 text-xs disabled:opacity-40 hover:bg-gray-50"
                >
                  ‹
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let p: number
                  if (totalPages <= 7) p = i + 1
                  else if (page <= 4) p = i + 1
                  else if (page >= totalPages - 3) p = totalPages - 6 + i
                  else p = page - 3 + i
                  return (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      className={`px-2 py-1 rounded border text-xs min-w-[28px] ${
                        p === page
                          ? 'bg-gray-800 text-white border-gray-800'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      {p}
                    </button>
                  )
                })}
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-2 py-1 rounded border border-gray-200 text-xs disabled:opacity-40 hover:bg-gray-50"
                >
                  ›
                </button>
                <span className="ml-2 text-xs text-gray-400">
                  Pág. {page} de {totalPages}
                </span>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
