'use client'
import { useEffect, useState, useMemo } from 'react'
import { getDeals, Deal } from '../../lib/api'
import * as XLSX from 'xlsx'

function fmt(n?: number, decimals = 0) {
  if (n == null) return '—'
  return n.toLocaleString('es-ES', { maximumFractionDigits: decimals })
}

type SortField = 'size_sqm' | 'asking_price' | 'price_per_sqm'
type SortDir = 'asc' | 'desc'
type FilterKey = 'distrito' | 'habitaciones' | 'estado' | 'sqm' | 'precio'

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
  const [filterSqmMin, setFilterSqmMin] = useState('')
  const [filterSqmMax, setFilterSqmMax] = useState('')
  const [filterPriceMin, setFilterPriceMin] = useState('')
  const [filterPriceMax, setFilterPriceMax] = useState('')

  const [openFilter, setOpenFilter] = useState<FilterKey | null>(null)

  const [sortField, setSortField] = useState<SortField | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

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
    getDeals()
      .then(setDeals)
      .catch(() => setFetchError('No se pudo conectar al backend. Asegúrate de que está corriendo en el puerto 8000.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { setPage(1) }, [
    filterDistricts, filterConditions, filterBedrooms,
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

  const visibleDeals = useMemo(() => {
    let result = deals.filter(d => {
      if (filterDistricts.size > 0 && !filterDistricts.has(d.district ?? '')) return false
      if (filterConditions.size > 0 && !filterConditions.has(d.condition ?? '')) return false
      if (filterBedrooms.size > 0 && !filterBedrooms.has(d.bedrooms ?? -1)) return false
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
  }, [deals, filterDistricts, filterConditions, filterBedrooms, filterSqmMin, filterSqmMax, filterPriceMin, filterPriceMax, sortField, sortDir])

  const totalPages = pageSize === 0 ? 1 : Math.ceil(visibleDeals.length / pageSize)
  const pagedDeals = pageSize === 0 ? visibleDeals : visibleDeals.slice((page - 1) * pageSize, page * pageSize)

  function handleSort(field: SortField) {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  const hasFilters = filterDistricts.size > 0 || filterConditions.size > 0 || filterBedrooms.size > 0
    || filterSqmMin || filterSqmMax || filterPriceMin || filterPriceMax

  function clearFilters() {
    setFilterDistricts(new Set()); setFilterConditions(new Set()); setFilterBedrooms(new Set())
    setFilterSqmMin(''); setFilterSqmMax(''); setFilterPriceMin(''); setFilterPriceMax('')
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
        <div className="flex gap-1">
          <button onClick={handleExportCSV} title={`Exportar ${visibleDeals.length} deals a CSV`}
            className="px-3 py-2 border border-gray-300 text-gray-600 rounded-md text-xs font-medium hover:bg-gray-50">
            ↓ CSV
          </button>
          <button onClick={handleExportXLSX} title={`Exportar ${visibleDeals.length} deals a Excel`}
            className="px-3 py-2 border border-gray-300 text-gray-600 rounded-md text-xs font-medium hover:bg-gray-50">
            ↓ Excel
          </button>
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
                  <th className="px-4 py-3 text-left">Dirección</th>

                  <FilterTh label="Distrito" filterKey="distrito" openFilter={openFilter} setOpenFilter={setOpenFilter}
                    active={filterDistricts.size > 0}>
                    <div className="max-h-52 overflow-y-auto">
                      {allDistricts.map(d => (
                        <label key={d} className={checkRowClass}>
                          <input type="checkbox" className={checkboxClass}
                            checked={filterDistricts.has(d)}
                            onChange={() => setFilterDistricts(prev => toggleSet(prev, d))} />
                          {d}
                        </label>
                      ))}
                    </div>
                  </FilterTh>

                  <th className="px-4 py-3 text-left">Zona</th>

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

                  <FilterTh label="Hab." filterKey="habitaciones" openFilter={openFilter} setOpenFilter={setOpenFilter}
                    active={filterBedrooms.size > 0} align="right">
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
                  </FilterTh>

                  <th className="px-4 py-3 text-right">Baños</th>
                  <th className="px-4 py-3 text-right">Planta</th>

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

                  <SortTh label="€/m²" field="price_per_sqm" sortField={sortField} sortDir={sortDir} onSort={handleSort} />

                  <FilterTh label="Estado" filterKey="estado" openFilter={openFilter} setOpenFilter={setOpenFilter}
                    active={filterConditions.size > 0}>
                    <div>
                      {allConditions.map(c => (
                        <label key={c} className={checkRowClass}>
                          <input type="checkbox" className={checkboxClass}
                            checked={filterConditions.has(c)}
                            onChange={() => setFilterConditions(prev => toggleSet(prev, c))} />
                          {CONDITION_BADGE[c]?.label ?? c}
                        </label>
                      ))}
                    </div>
                  </FilterTh>

                  <th className="px-4 py-3 text-left">Amenidades</th>
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
                      <td className="px-4 py-2 max-w-xs truncate">
                        {deal.url ? (
                          <a href={deal.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                            {deal.address || deal.url}
                          </a>
                        ) : (deal.address || '—')}
                      </td>
                      <td className="px-4 py-2 text-gray-600">{deal.district || '—'}</td>
                      <td className="px-4 py-2 text-gray-500">{deal.zone ?? '—'}</td>
                      <td className="px-4 py-2 text-right">{fmt(deal.size_sqm)}</td>
                      <td className="px-4 py-2 text-right">{deal.bedrooms ?? '—'}</td>
                      <td className="px-4 py-2 text-right">{deal.bathrooms ?? '—'}</td>
                      <td className="px-4 py-2 text-right">{deal.floor ?? '—'}</td>
                      <td className="px-4 py-2 text-right font-medium">
                        {deal.asking_price ? `€${fmt(deal.asking_price)}` : '—'}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-500">
                        {askPsqm ? `€${fmt(askPsqm)}` : '—'}
                      </td>
                      <td className="px-4 py-2">
                        <ConditionBadge condition={deal.condition} />
                      </td>
                      <td className="px-4 py-2">
                        <AmenityBadges deal={deal} />
                      </td>
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
