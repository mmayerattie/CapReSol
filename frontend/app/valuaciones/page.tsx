'use client'
import { useEffect, useState, useMemo } from 'react'
import Link from 'next/link'
import { getPredictions, getDeals, predictDeals, deletePrediction, PredictionWithDeal, Deal } from '../../lib/api'

function fmt(n?: number | null, decimals = 0) {
  if (n == null) return '—'
  return n.toLocaleString('es-ES', { maximumFractionDigits: decimals })
}

const CONDITION_LABEL: Record<string, string> = {
  newdevelopment: 'Nueva',
  good: 'Buen estado',
  renew: 'A reformar',
}

function SpreadBadge({ ask, ml }: { ask?: number | null; ml: number }) {
  if (!ask) return <span className="text-gray-300 text-xs">—</span>
  const pct = (ml - ask) / ask * 100
  if (pct > 5) return (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700 whitespace-nowrap">
      Infravalorado +{pct.toFixed(1)}%
    </span>
  )
  if (pct >= 0) return (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-700 whitespace-nowrap">
      +{pct.toFixed(1)}%
    </span>
  )
  return (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-600 whitespace-nowrap">
      Sobrevalorado {pct.toFixed(1)}%
    </span>
  )
}

// ---------------------------------------------------------------------------
// Deal-picker modal (for new valuations)
// ---------------------------------------------------------------------------

function toggleSet<T>(set: Set<T>, v: T): Set<T> {
  const next = new Set(set); next.has(v) ? next.delete(v) : next.add(v); return next
}

const CONDITION_BADGE: Record<string, { label: string; cls: string }> = {
  newdevelopment: { label: 'Nueva', cls: 'bg-emerald-100 text-emerald-700' },
  good:           { label: 'Buen estado', cls: 'bg-blue-100 text-blue-700' },
  renew:          { label: 'A reformar', cls: 'bg-orange-100 text-orange-700' },
}

function DealPickerModal({
  onClose, onDone,
}: {
  onClose: () => void
  onDone: (count: number) => void
}) {
  const [deals, setDeals] = useState<Deal[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [predicting, setPredicting] = useState(false)
  const [predictError, setPredictError] = useState('')
  const [filterDistricts, setFilterDistricts] = useState<Set<string>>(new Set())
  const [filterConditions, setFilterConditions] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 25

  useEffect(() => {
    getDeals().then(setDeals).finally(() => setLoading(false))
  }, [])

  const allDistricts = useMemo(
    () => Array.from(new Set(deals.map(d => d.district).filter(Boolean))).sort() as string[],
    [deals]
  )
  const allConditions = useMemo(
    () => Array.from(new Set(deals.map(d => d.condition).filter(Boolean))).sort() as string[],
    [deals]
  )

  const visible = useMemo(() => deals.filter(d => {
    if (filterDistricts.size > 0 && !filterDistricts.has(d.district ?? '')) return false
    if (filterConditions.size > 0 && !filterConditions.has(d.condition ?? '')) return false
    return true
  }), [deals, filterDistricts, filterConditions])

  const totalPages = Math.ceil(visible.length / PAGE_SIZE)
  const paged = visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const MAX_BULK = 25

  async function handleTasar() {
    if (selected.size === 0) return
    if (selected.size > MAX_BULK) {
      setPredictError(`Maximo ${MAX_BULK} predicciones a la vez. Seleccionaste ${selected.size}.`)
      return
    }
    setPredicting(true)
    setPredictError('')
    try {
      await predictDeals(Array.from(selected))
      onDone(selected.size)
    } catch (e: unknown) {
      setPredictError(e instanceof Error ? e.message : 'Error al tasar — revisa el backend')
    } finally {
      setPredicting(false)
    }
  }

  const checkboxCls = 'w-3.5 h-3.5 accent-blue-600 cursor-pointer'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl mx-4 flex flex-col max-h-[90vh]">
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0">
          <h2 className="text-lg font-semibold text-gray-800">Seleccionar propiedades para tasar</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl font-bold leading-none">×</button>
        </div>

        {/* Filters */}
        <div className="flex items-start gap-6 px-6 py-3 border-b border-gray-100 shrink-0 bg-gray-50">
          <div>
            <p className="text-[10px] text-gray-400 uppercase font-medium mb-1.5">Distrito</p>
            <div className="max-h-24 overflow-y-auto flex flex-col gap-0.5 min-w-[160px]">
              {allDistricts.map(d => (
                <label key={d} className="flex items-center gap-1.5 text-xs text-gray-700 cursor-pointer hover:bg-gray-100 px-1 py-0.5 rounded">
                  <input type="checkbox" className="w-3 h-3 accent-blue-600"
                    checked={filterDistricts.has(d)}
                    onChange={() => { setFilterDistricts(prev => toggleSet(prev, d)); setPage(1) }} />
                  {d}
                </label>
              ))}
            </div>
          </div>
          <div>
            <p className="text-[10px] text-gray-400 uppercase font-medium mb-1.5">Estado</p>
            <div className="flex flex-col gap-0.5 min-w-[120px]">
              {allConditions.map(c => (
                <label key={c} className="flex items-center gap-1.5 text-xs text-gray-700 cursor-pointer hover:bg-gray-100 px-1 py-0.5 rounded">
                  <input type="checkbox" className="w-3 h-3 accent-blue-600"
                    checked={filterConditions.has(c)}
                    onChange={() => { setFilterConditions(prev => toggleSet(prev, c)); setPage(1) }} />
                  {CONDITION_BADGE[c]?.label ?? c}
                </label>
              ))}
            </div>
          </div>
          <span className="text-xs text-gray-400 ml-auto self-center">{visible.length} propiedades · {selected.size} seleccionadas</span>
        </div>

        {/* Table */}
        <div className="overflow-auto flex-1">
          {loading ? (
            <p className="text-center py-8 text-gray-400 text-sm">Cargando…</p>
          ) : (
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 uppercase text-xs sticky top-0">
                <tr>
                  <th className="px-4 py-2.5">
                    <input type="checkbox" className={checkboxCls}
                      onChange={e => setSelected(e.target.checked ? new Set(paged.map(d => d.id)) : new Set())} />
                  </th>
                  <th className="px-4 py-2.5 text-left">Dirección</th>
                  <th className="px-4 py-2.5 text-left">Distrito</th>
                  <th className="px-4 py-2.5 text-right">m²</th>
                  <th className="px-4 py-2.5 text-right">Hab.</th>
                  <th className="px-4 py-2.5 text-right">Precio</th>
                  <th className="px-4 py-2.5 text-left">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {paged.map(deal => {
                  const cfg = CONDITION_BADGE[deal.condition ?? '']
                  return (
                    <tr key={deal.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setSelected(prev => toggleSet(prev, deal.id))}>
                      <td className="px-4 py-2 text-center">
                        <input type="checkbox" className={checkboxCls} checked={selected.has(deal.id)} onChange={() => {}} />
                      </td>
                      <td className="px-4 py-2 max-w-[200px] truncate text-gray-700">{deal.address || deal.url || '—'}</td>
                      <td className="px-4 py-2 text-gray-500 text-xs">{deal.district || '—'}</td>
                      <td className="px-4 py-2 text-right">{fmt(deal.size_sqm)}</td>
                      <td className="px-4 py-2 text-right">{deal.bedrooms ?? '—'}</td>
                      <td className="px-4 py-2 text-right font-medium">{deal.asking_price ? `€${fmt(deal.asking_price)}` : '—'}</td>
                      <td className="px-4 py-2">
                        {cfg ? (
                          <span className={`inline-block px-1.5 py-0.5 rounded-full text-[10px] font-medium ${cfg.cls}`}>{cfg.label}</span>
                        ) : <span className="text-gray-400 text-xs">{deal.condition || '—'}</span>}
                      </td>
                    </tr>
                  )
                })}
                {paged.length === 0 && (
                  <tr><td colSpan={7} className="text-center py-8 text-gray-400">Sin propiedades</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* Modal footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 shrink-0">
          <div className="flex items-center gap-1 text-sm text-gray-500">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-2 py-1 rounded border border-gray-200 text-xs disabled:opacity-40 hover:bg-gray-50">‹</button>
            <span className="px-2 text-xs">Pág. {page} de {Math.max(1, totalPages)}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
              className="px-2 py-1 rounded border border-gray-200 text-xs disabled:opacity-40 hover:bg-gray-50">›</button>
          </div>
          {predictError && <span className="text-xs text-red-600">{predictError}</span>}
          <button
            onClick={handleTasar}
            disabled={predicting || selected.size === 0 || selected.size > MAX_BULK}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-40 hover:bg-blue-700"
          >
            {predicting ? 'Tasando...' : selected.size > MAX_BULK ? `Max ${MAX_BULK} (${selected.size} selec.)` : `Tasar ${selected.size} seleccionado${selected.size !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Valuaciones page — history of past predictions
// ---------------------------------------------------------------------------

export default function ValuacionesPage() {
  const [predictions, setPredictions] = useState<PredictionWithDeal[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [deleting, setDeleting] = useState(false)

  function load() {
    setLoading(true)
    getPredictions().then(data => {
      // Sort by created_at descending so newest predictions appear first
      data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      setPredictions(data)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleDeletePrediction(id: string) {
    try {
      await deletePrediction(id)
      setPredictions(prev => prev.filter(p => p.id !== id))
      setSelected(prev => { const n = new Set(prev); n.delete(id); return n })
      setConfirmDeleteId(null)
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : 'Error al eliminar')
      setTimeout(() => setDeleteError(''), 4000)
    }
  }

  async function handleDeleteSelected() {
    setDeleting(true)
    try {
      const ids = Array.from(selected)
      for (const id of ids) {
        await deletePrediction(id)
      }
      setPredictions(prev => prev.filter(p => !selected.has(p.id)))
      setSuccessMsg(`${ids.length} tasacion${ids.length !== 1 ? 'es' : ''} eliminada${ids.length !== 1 ? 's' : ''}`)
      setTimeout(() => setSuccessMsg(''), 4000)
      setSelected(new Set())
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : 'Error al eliminar')
      setTimeout(() => setDeleteError(''), 4000)
    } finally {
      setDeleting(false)
    }
  }

  async function handleDeleteAll() {
    setDeleting(true)
    try {
      for (const p of predictions) {
        await deletePrediction(p.id)
      }
      setPredictions([])
      setSelected(new Set())
      setConfirmDeleteAll(false)
      setSuccessMsg('Todas las tasaciones eliminadas')
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : 'Error al eliminar')
      setTimeout(() => setDeleteError(''), 4000)
    } finally {
      setDeleting(false)
    }
  }

  function handleModalDone(count: number) {
    setShowModal(false)
    setSuccessMsg(`${count} deal${count !== 1 ? 's' : ''} tasado${count !== 1 ? 's' : ''} correctamente`)
    setTimeout(() => setSuccessMsg(''), 4000)
    load()
  }

  const allSelected = predictions.length > 0 && selected.size === predictions.length

  return (
    <div>
      {showModal && (
        <DealPickerModal
          onClose={() => setShowModal(false)}
          onDone={handleModalDone}
        />
      )}

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Valuaciones</h1>
          {!loading && <span className="text-sm text-gray-400">{predictions.length} tasaciones</span>}
        </div>
        <div className="flex items-center gap-3">
          {successMsg && <span className="text-sm text-emerald-600">{successMsg}</span>}
          {selected.size > 0 && (
            <button
              onClick={handleDeleteSelected}
              disabled={deleting}
              className="px-3 py-1.5 bg-red-50 text-red-600 border border-red-200 rounded-md text-xs font-medium hover:bg-red-100 disabled:opacity-40"
            >
              {deleting ? 'Eliminando...' : `Eliminar ${selected.size} seleccionada${selected.size !== 1 ? 's' : ''}`}
            </button>
          )}
          {predictions.length > 0 && selected.size === 0 && (
            confirmDeleteAll ? (
              <span className="flex items-center gap-2 text-xs">
                <button onClick={handleDeleteAll} disabled={deleting}
                  className="text-red-600 font-medium hover:underline disabled:opacity-40">
                  {deleting ? 'Eliminando...' : 'Confirmar eliminar todo'}
                </button>
                <button onClick={() => setConfirmDeleteAll(false)}
                  className="text-gray-400 hover:text-gray-600">Cancelar</button>
              </span>
            ) : (
              <button
                onClick={() => setConfirmDeleteAll(true)}
                className="px-3 py-1.5 text-gray-400 border border-gray-200 rounded-md text-xs hover:text-red-500 hover:border-red-200"
              >
                Eliminar todo
              </button>
            )
          )}
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
          >
            + Nueva Valuacion
          </button>
        </div>
      </div>
      {deleteError && <p className="text-red-500 text-sm mt-2 mb-4">{deleteError}</p>}

      {loading ? (
        <p className="text-gray-400">Cargando...</p>
      ) : predictions.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg mb-2">Sin tasaciones todavia</p>
          <p className="text-sm">Haz clic en <span className="font-medium text-gray-600">"+ Nueva Valuacion"</span> para seleccionar propiedades y ejecutar el modelo ML.</p>
        </div>
      ) : (
        <div className="overflow-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 w-8">
                  <input type="checkbox"
                    className="w-3.5 h-3.5 accent-blue-600"
                    checked={allSelected}
                    onChange={() => setSelected(allSelected ? new Set() : new Set(predictions.map(p => p.id)))} />
                </th>
                <th className="px-4 py-3 text-left">Direccion</th>
                <th className="px-4 py-3 text-left">Distrito</th>
                <th className="px-4 py-3 text-right">m2</th>
                <th className="px-4 py-3 text-right">Ask Price</th>
                <th className="px-4 py-3 text-right">Ask EUR/m2</th>
                <th className="px-4 py-3 text-right">Tasacion ML</th>
                <th className="px-4 py-3 text-right">ML EUR/m2</th>
                <th className="px-4 py-3 text-left">Spread</th>
                <th className="px-4 py-3 text-left">Estado</th>
                <th className="px-4 py-3 text-left">Fecha</th>
                <th className="px-4 py-3"></th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {predictions.map(p => {
                const askPsqm = p.asking_price && p.size_sqm ? p.asking_price / p.size_sqm : null
                const mlPsqm = p.size_sqm ? p.predicted_price / p.size_sqm : null
                const dateStr = new Date(p.created_at).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: '2-digit' })
                return (
                  <tr key={p.id} className={`hover:bg-gray-50 ${selected.has(p.id) ? 'bg-blue-50' : ''}`}>
                    <td className="px-4 py-2 text-center">
                      <input type="checkbox"
                        className="w-3.5 h-3.5 accent-blue-600"
                        checked={selected.has(p.id)}
                        onChange={() => setSelected(prev => toggleSet(prev, p.id))} />
                    </td>
                    <td className="px-4 py-2 max-w-xs truncate">
                      {p.url ? (
                        <a href={p.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                          {p.address || p.url}
                        </a>
                      ) : (p.address || '—')}
                    </td>
                    <td className="px-4 py-2 text-gray-600 text-xs">{p.district || '—'}</td>
                    <td className="px-4 py-2 text-right">{fmt(p.size_sqm)}</td>
                    <td className="px-4 py-2 text-right font-medium">{p.asking_price ? `EUR${fmt(p.asking_price)}` : '—'}</td>
                    <td className="px-4 py-2 text-right text-gray-500">{askPsqm ? `EUR${fmt(askPsqm)}` : '—'}</td>
                    <td className="px-4 py-2 text-right font-semibold text-emerald-700">{`EUR${fmt(p.predicted_price)}`}</td>
                    <td className="px-4 py-2 text-right text-emerald-600">{mlPsqm ? `EUR${fmt(mlPsqm)}` : '—'}</td>
                    <td className="px-4 py-2">
                      <SpreadBadge ask={p.asking_price} ml={p.predicted_price} />
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs">{CONDITION_LABEL[p.condition ?? ''] ?? p.condition ?? '—'}</td>
                    <td className="px-4 py-2 text-gray-400 text-xs whitespace-nowrap">{dateStr}</td>
                    <td className="px-4 py-2">
                      <Link href={`/analyses?deal_id=${p.deal_id}`}
                        className="text-xs text-gray-400 hover:text-blue-600 hover:underline whitespace-nowrap">
                        Analizar
                      </Link>
                    </td>
                    <td className="px-4 py-2" onClick={e => e.stopPropagation()}>
                      {confirmDeleteId === p.id ? (
                        <span className="flex items-center gap-1 text-xs">
                          <button
                            onClick={() => handleDeletePrediction(p.id)}
                            className="text-red-600 font-medium hover:underline"
                          >Eliminar</button>
                          <span className="text-gray-300">/</span>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="text-gray-400 hover:text-gray-600"
                          >Cancelar</button>
                        </span>
                      ) : (
                        <button
                          onClick={() => setConfirmDeleteId(p.id)}
                          title="Eliminar tasacion"
                          className="text-gray-300 hover:text-red-500 transition-colors"
                        >&#128465;</button>
                      )}
                    </td>
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
