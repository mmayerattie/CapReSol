'use client'
import { useEffect, useState, useMemo } from 'react'
import { getDeals, scrapeDeals, predictDeals, Deal, Prediction } from '../../lib/api'

function fmt(n?: number, decimals = 0) {
  if (n == null) return '—'
  return n.toLocaleString('es-ES', { maximumFractionDigits: decimals })
}

type SortField = 'size_sqm' | 'asking_price' | 'price_per_sqm'
type SortDir = 'asc' | 'desc'

const CONDITION_LABEL: Record<string, string> = {
  newdevelopment: 'Nueva',
  good: 'Buen estado',
  renew: 'A reformar',
}

function SortTh({ label, field, sortField, sortDir, onSort }: {
  label: string; field: SortField
  sortField: SortField | null; sortDir: SortDir
  onSort: (f: SortField) => void
}) {
  const active = sortField === field
  return (
    <th
      onClick={() => onSort(field)}
      className="px-4 py-3 text-right cursor-pointer select-none hover:bg-gray-100"
    >
      {label}
      <span className="ml-1 text-gray-400 text-xs">{active ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}</span>
    </th>
  )
}

function Pill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-0.5 rounded text-xs border transition-colors ${
        active ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-600 hover:border-gray-400'
      }`}
    >
      {label}
    </button>
  )
}

function toggleSet<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set)
  next.has(value) ? next.delete(value) : next.add(value)
  return next
}

export default function DealsPage() {
  const [deals, setDeals] = useState<Deal[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [predictions, setPredictions] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState('')
  const [scraping, setScraping] = useState(false)
  const [predicting, setPredicting] = useState(false)
  const [scrapeMsg, setScrapeMsg] = useState('')

  // Filters
  const [filterDistricts, setFilterDistricts] = useState<Set<string>>(new Set())
  const [filterConditions, setFilterConditions] = useState<Set<string>>(new Set())
  const [filterBedrooms, setFilterBedrooms] = useState<Set<number>>(new Set())
  const [filterSqmMin, setFilterSqmMin] = useState('')
  const [filterSqmMax, setFilterSqmMax] = useState('')
  const [filterPriceMin, setFilterPriceMin] = useState('')
  const [filterPriceMax, setFilterPriceMax] = useState('')

  // Sort
  const [sortField, setSortField] = useState<SortField | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  useEffect(() => {
    getDeals()
      .then(setDeals)
      .catch(() => setFetchError('No se pudo conectar al backend. Asegúrate de que está corriendo en el puerto 8000.'))
      .finally(() => setLoading(false))
  }, [])

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

  function toggleAll(checked: boolean) {
    setSelected(checked ? new Set(visibleDeals.map(d => d.id)) : new Set())
  }

  function toggleOne(id: string) {
    setSelected(prev => toggleSet(prev, id))
  }

  async function handleScrape() {
    setScraping(true); setScrapeMsg('')
    try {
      const r = await scrapeDeals()
      setScrapeMsg(`${r.listings_fetched} fetched — ${r.new_deals_inserted} new`)
      setDeals(await getDeals())
    } catch { setScrapeMsg('Scrape failed') }
    finally { setScraping(false) }
  }

  async function handlePredict() {
    if (selected.size === 0) return
    setPredicting(true)
    try {
      const results: Prediction[] = await predictDeals(Array.from(selected))
      const map: Record<string, number> = {}
      results.forEach(p => { map[p.deal_id] = p.predicted_price })
      setPredictions(prev => ({ ...prev, ...map }))
    } finally { setPredicting(false) }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Deals</h1>
        <div className="flex gap-3 items-center">
          {scrapeMsg && <span className="text-sm text-gray-500">{scrapeMsg}</span>}
          <button onClick={handleScrape} disabled={scraping}
            className="px-4 py-2 bg-gray-800 text-white rounded-md text-sm font-medium disabled:opacity-50">
            {scraping ? 'Scraping…' : 'Scrape Idealista'}
          </button>
          <button onClick={handlePredict} disabled={predicting || selected.size === 0}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium disabled:opacity-40">
            {predicting ? 'Calculando…' : `Tasación (${selected.size})`}
          </button>
        </div>
      </div>

      {fetchError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
          {fetchError}
        </div>
      )}

      {!loading && deals.length > 0 && (
        <div className="mb-4 p-4 bg-white rounded-lg border border-gray-200 space-y-3">
          <div className="flex flex-wrap gap-x-6 gap-y-3 items-start">

            <div>
              <p className="text-xs text-gray-500 mb-1 font-medium">Distrito</p>
              <div className="flex flex-wrap gap-1 max-w-sm">
                {allDistricts.map(d => (
                  <Pill key={d} label={d} active={filterDistricts.has(d)}
                    onClick={() => setFilterDistricts(prev => toggleSet(prev, d))} />
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-1 font-medium">Habitaciones</p>
              <div className="flex gap-1">
                {allBedrooms.map(b => (
                  <Pill key={b} label={String(b)} active={filterBedrooms.has(b)}
                    onClick={() => setFilterBedrooms(prev => toggleSet(prev, b))} />
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-1 font-medium">Estado</p>
              <div className="flex gap-1">
                {allConditions.map(c => (
                  <Pill key={c} label={CONDITION_LABEL[c] ?? c} active={filterConditions.has(c)}
                    onClick={() => setFilterConditions(prev => toggleSet(prev, c))} />
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-1 font-medium">m²</p>
              <div className="flex items-center gap-1">
                <input type="number" placeholder="Min" value={filterSqmMin}
                  onChange={e => setFilterSqmMin(e.target.value)}
                  className="w-16 border border-gray-200 rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
                <span className="text-gray-400 text-xs">–</span>
                <input type="number" placeholder="Max" value={filterSqmMax}
                  onChange={e => setFilterSqmMax(e.target.value)}
                  className="w-16 border border-gray-200 rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
              </div>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-1 font-medium">Precio (€)</p>
              <div className="flex items-center gap-1">
                <input type="number" placeholder="Min" value={filterPriceMin}
                  onChange={e => setFilterPriceMin(e.target.value)}
                  className="w-24 border border-gray-200 rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
                <span className="text-gray-400 text-xs">–</span>
                <input type="number" placeholder="Max" value={filterPriceMax}
                  onChange={e => setFilterPriceMax(e.target.value)}
                  className="w-24 border border-gray-200 rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400" />
              </div>
            </div>

            {hasFilters && (
              <div className="flex items-end pb-0.5">
                <button onClick={clearFilters}
                  className="px-3 py-0.5 text-xs text-red-600 border border-red-200 rounded hover:bg-red-50">
                  Limpiar filtros
                </button>
              </div>
            )}
          </div>
          <p className="text-xs text-gray-400">{visibleDeals.length} de {deals.length} deals</p>
        </div>
      )}

      {loading ? (
        <p className="text-gray-400">Cargando…</p>
      ) : (
        <div className="overflow-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
              <tr>
                <th className="px-3 py-3">
                  <input type="checkbox" onChange={e => toggleAll(e.target.checked)} />
                </th>
                <th className="px-4 py-3 text-left">Dirección</th>
                <th className="px-4 py-3 text-left">Distrito</th>
                <SortTh label="m²" field="size_sqm" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
                <th className="px-4 py-3 text-right">Hab.</th>
                <SortTh label="Ask Price" field="asking_price" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
                <SortTh label="€/m² Ask" field="price_per_sqm" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
                <th className="px-4 py-3 text-right">Tasación ML</th>
                <th className="px-4 py-3 text-right">€/m² ML</th>
                <th className="px-4 py-3 text-left">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {visibleDeals.length === 0 && (
                <tr>
                  <td colSpan={10} className="text-center py-10 text-gray-400">
                    {hasFilters ? 'No hay deals con estos filtros' : 'No hay deals — pulsa "Scrape Idealista"'}
                  </td>
                </tr>
              )}
              {visibleDeals.map(deal => {
                const pred = predictions[deal.id]
                const askPsqm = deal.asking_price && deal.size_sqm ? deal.asking_price / deal.size_sqm : undefined
                const predPsqm = pred && deal.size_sqm ? pred / deal.size_sqm : undefined
                return (
                  <tr key={deal.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-center">
                      <input type="checkbox" checked={selected.has(deal.id)} onChange={() => toggleOne(deal.id)} />
                    </td>
                    <td className="px-4 py-2 max-w-xs truncate">
                      {deal.url ? (
                        <a href={deal.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                          {deal.address || deal.url}
                        </a>
                      ) : (deal.address || '—')}
                    </td>
                    <td className="px-4 py-2 text-gray-600">{deal.district || '—'}</td>
                    <td className="px-4 py-2 text-right">{fmt(deal.size_sqm)}</td>
                    <td className="px-4 py-2 text-right">{deal.bedrooms ?? '—'}</td>
                    <td className="px-4 py-2 text-right font-medium">
                      {deal.asking_price ? `€${fmt(deal.asking_price)}` : '—'}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-500">
                      {askPsqm ? `€${fmt(askPsqm)}` : '—'}
                    </td>
                    <td className="px-4 py-2 text-right font-semibold text-emerald-700">
                      {pred ? `€${fmt(pred)}` : '—'}
                    </td>
                    <td className="px-4 py-2 text-right text-emerald-600">
                      {predPsqm ? `€${fmt(predPsqm)}` : '—'}
                    </td>
                    <td className="px-4 py-2 text-gray-500">{CONDITION_LABEL[deal.condition ?? ''] ?? deal.condition ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
