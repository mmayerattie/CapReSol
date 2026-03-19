'use client'
import { useEffect, useState, useMemo } from 'react'
import { getAnalyticsStats, AnalyticsStats } from '../../lib/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ReferenceLine, LineChart, Line,
} from 'recharts'

function fmt(n: number | null | undefined, decimals = 0): string {
  if (n == null) return '---'
  return n.toLocaleString('es-ES', { maximumFractionDigits: decimals })
}

function KpiCard({ label, value, sub }: { label: string; value: React.ReactNode; sub: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-900 truncate">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  )
}

const MAX_PRICE_PRESETS = [
  { label: '10k', value: 10000 },
  { label: '15k', value: 15000 },
  { label: '20k', value: 20000 },
  { label: '25k', value: 25000 },
  { label: 'Sin limite', value: 0 },
]
const MIN_PRICE_PRESETS = [
  { label: 'Sin min.', value: 0 },
  { label: '500', value: 500 },
  { label: '1k', value: 1000 },
  { label: '2k', value: 2000 },
]

// Reusable opportunity table component
function OpportunityTable({
  title,
  subtitle,
  data,
  buyLabel,
  sellLabel,
  showListings,
}: {
  title: string
  subtitle: string
  data: { district: string; buy: number; sell: number; upside: number; pct: number; listings?: number }[]
  buyLabel: string
  sellLabel: string
  showListings?: boolean
}) {
  if (data.length === 0) return null
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
      <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
      <p className="text-xs text-gray-400 mt-0.5 mb-4">{subtitle}</p>
      <div className="overflow-auto rounded-lg border border-gray-100">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Distrito</th>
              <th className="px-4 py-3 text-right">{buyLabel}</th>
              <th className="px-4 py-3 text-right">{sellLabel}</th>
              <th className="px-4 py-3 text-right">Upside /m2</th>
              <th className="px-4 py-3 text-right">Upside %</th>
              {showListings && <th className="px-4 py-3 text-right">Listings</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.map((d, i) => (
              <tr key={d.district} className={`hover:bg-gray-50 ${i < 3 ? 'bg-emerald-50/40' : ''}`}>
                <td className="px-4 py-2.5 font-medium text-gray-800">
                  {i < 3 && <span className="mr-1.5 text-gray-400">{i + 1}.</span>}
                  {d.district}
                </td>
                <td className="px-4 py-2.5 text-right text-gray-600">{fmt(d.buy)}</td>
                <td className="px-4 py-2.5 text-right text-gray-600">{fmt(d.sell)}</td>
                <td className="px-4 py-2.5 text-right font-semibold text-emerald-700">+{fmt(d.upside)}</td>
                <td className="px-4 py-2.5 text-right font-medium text-emerald-700">+{d.pct.toFixed(1)}%</td>
                {showListings && (
                  <td className="px-4 py-2.5 text-right">
                    <a href={`/deals?district=${encodeURIComponent(d.district)}&condition=renew`}
                      className="text-blue-600 hover:text-blue-800 hover:underline font-medium">
                      {d.listings ?? 0} &rarr;
                    </a>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function AnalyticsPage() {
  const [stats, setStats] = useState<AnalyticsStats | null>(null)
  const [error, setError] = useState('')
  const [showMore, setShowMore] = useState(false)
  const [maxPsqm, setMaxPsqm] = useState(25000)
  const [minPsqm, setMinPsqm] = useState(500)
  const [notaryType, setNotaryType] = useState('segunda_mano')
  const [notaryClass, setNotaryClass] = useState('pisos')

  useEffect(() => {
    setStats(null)
    getAnalyticsStats(maxPsqm || undefined, minPsqm || undefined, notaryType, notaryClass)
      .then(setStats)
      .catch(() => setError('No se pudieron cargar los datos.'))
  }, [maxPsqm, minPsqm, notaryType, notaryClass])

  // ---- Chart 1: Ask reformar vs Closing segunda mano (conservative upside) ----
  const chart1 = useMemo(() => {
    if (!stats) return []
    return stats.by_district
      .map(d => {
        const buy = d.avg_price_renew
        const sell = stats.notary_prices_by_type?.nueva?.[d.district] ?? null
        if (buy == null || sell == null || sell <= buy) return null
        return { district: d.district, buy, sell, upside: sell - buy, pct: ((sell - buy) / buy) * 100, listings: d.n_renew }
      })
      .filter((d): d is NonNullable<typeof d> => d !== null)
      .sort((a, b) => b.upside - a.upside)
  }, [stats])

  // ---- Chart 2: Ask reformar vs Ask buen estado (optimistic upside) ----
  const chart2 = useMemo(() => {
    if (!stats) return []
    return stats.by_district
      .map(d => {
        const buy = d.avg_price_renew
        const sell = d.avg_price_good
        if (buy == null || sell == null || sell <= buy) return null
        return { district: d.district, buy, sell, upside: sell - buy, pct: ((sell - buy) / buy) * 100, listings: d.n_renew }
      })
      .filter((d): d is NonNullable<typeof d> => d !== null)
      .sort((a, b) => b.upside - a.upside)
  }, [stats])

  // ---- Chart 3: Closing segunda mano vs Closing nueva (market upside) ----
  const chart3 = useMemo(() => {
    if (!stats) return []
    return stats.by_district
      .map(d => {
        const buy = stats.notary_prices_by_type?.segunda_mano?.[d.district] ?? null
        const sell = stats.notary_prices_by_type?.nueva?.[d.district] ?? null
        if (buy == null || sell == null || sell <= buy) return null
        return { district: d.district, buy, sell, upside: sell - buy, pct: ((sell - buy) / buy) * 100 }
      })
      .filter((d): d is NonNullable<typeof d> => d !== null)
      .sort((a, b) => b.upside - a.upside)
  }, [stats])

  if (error) {
    return <div className="p-8 text-red-600 text-sm bg-red-50 rounded-lg border border-red-200">{error}</div>
  }
  if (!stats) {
    return <p className="text-gray-400 text-sm p-8">Cargando analytics...</p>
  }

  // Derived
  const byPriceDesc = [...stats.by_district]
    .filter(d => d.avg_price_sqm != null)
    .sort((a, b) => (b.avg_price_sqm ?? 0) - (a.avg_price_sqm ?? 0))

  const mostAffordable = [...stats.by_district]
    .filter(d => d.avg_price_sqm != null)
    .sort((a, b) => (a.avg_price_sqm ?? Infinity) - (b.avg_price_sqm ?? Infinity))[0]

  const topOpp = chart1[0]

  // Condition pie
  const totalRenew = stats.condition_by_district.reduce((s, d) => s + d.renew, 0)
  const totalGood = stats.condition_by_district.reduce((s, d) => s + d.good, 0)
  const totalNew = stats.condition_by_district.reduce((s, d) => s + d.new, 0)
  const conditionPieData = [
    { name: 'A reformar', value: totalRenew, color: '#f97316' },
    { name: 'Buen estado', value: totalGood, color: '#3b82f6' },
    { name: 'Nueva', value: totalNew, color: '#10b981' },
  ].filter(d => d.value > 0)
  const conditionTotal = totalRenew + totalGood + totalNew

  // ML spread
  const mlDistricts = [...stats.by_district]
    .filter(d => d.ml_vs_ask_avg != null)
    .sort((a, b) => (b.ml_vs_ask_avg ?? 0) - (a.ml_vs_ask_avg ?? 0))

  const amenityRows: { label: string; key: keyof typeof stats.amenities }[] = [
    { label: 'Ascensor', key: 'elevator' },
    { label: 'Terraza', key: 'terrace' },
    { label: 'Balcon', key: 'balcony' },
    { label: 'Garaje', key: 'garage' },
    { label: 'Trastero', key: 'storage_room' },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics - Madrid</h1>
          <p className="text-gray-500 text-sm mt-1">Busqueda de oportunidades de inversion inmobiliaria</p>
        </div>
        <div className="flex flex-col gap-1.5 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium w-14 text-right">Max /m2</span>
            <div className="flex gap-1">
              {MAX_PRICE_PRESETS.map(p => (
                <button key={p.value} onClick={() => setMaxPsqm(p.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${maxPsqm === p.value ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'}`}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium w-14 text-right">Min /m2</span>
            <div className="flex gap-1">
              {MIN_PRICE_PRESETS.map(p => (
                <button key={p.value} onClick={() => setMinPsqm(p.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${minPsqm === p.value ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'}`}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium w-14 text-right">Finca</span>
            <div className="flex gap-1">
              {[{ label: 'Pisos', value: 'pisos' }, { label: 'Casas', value: 'casas' }, { label: 'Todos', value: 'todos' }].map(p => (
                <button key={p.value} onClick={() => setNotaryClass(p.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${notaryClass === p.value ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'}`}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard label="Dataset" value={fmt(stats.total_deals)}
          sub="listings en el sistema" />
        <KpiCard label="A reformar" value={totalRenew}
          sub="oportunidades disponibles" />
        <KpiCard label="Mayor oportunidad" value={topOpp ? topOpp.district : '---'}
          sub={topOpp ? `+${fmt(topOpp.upside)}/m2 de upside` : 'sin datos notariales'} />
        <KpiCard label="Zona mas asequible" value={mostAffordable ? mostAffordable.district : '---'}
          sub={mostAffordable?.avg_price_sqm ? `${fmt(mostAffordable.avg_price_sqm)}/m2` : ''} />
      </div>

      {/* ================================================================ */}
      {/* CHART 1: Oportunidad real (conservador)                          */}
      {/* Ask reformar vs Closing segunda mano                             */}
      {/* ================================================================ */}
      <OpportunityTable
        title="Oportunidad real por distrito"
        subtitle="Compras al precio de portal (a reformar) y vendes al precio real de cierre notarial (nuevo). Upside conservador: el precio de compra en portal suele ser mayor al de cierre real."
        data={chart1}
        buyLabel="Reformar (portal)"
        sellLabel="Nuevo (escritura)"
        showListings
      />

      {/* ================================================================ */}
      {/* CHART 2: Upside en portales                                      */}
      {/* Ask reformar vs Ask buen estado                                  */}
      {/* ================================================================ */}
      <OpportunityTable
        title="Upside en portales"
        subtitle="Compras al precio de portal (a reformar) y vendes al precio de portal (buen estado). Upside optimista: los precios pedidos no reflejan el cierre real."
        data={chart2}
        buyLabel="Reformar (portal)"
        sellLabel="Buen estado (portal)"
        showListings
      />

      {/* ================================================================ */}
      {/* CHART 3: Upside del mercado (notarial)                           */}
      {/* Closing segunda mano vs Closing nueva                            */}
      {/* ================================================================ */}
      <OpportunityTable
        title="Upside del mercado"
        subtitle="Precio real de cierre segunda mano vs obra nueva. El margen que existe en el mercado segun escrituras notariales. Sin oportunidad directa: es el techo del upside."
        data={chart3}
        buyLabel="2a mano (escritura)"
        sellLabel="Nueva (escritura)"
      />

      {/* ================================================================ */}
      {/* Precio Pedido vs Escritura (spread table)                        */}
      {/* ================================================================ */}
      {stats.notary_by_district.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <div className="mb-4 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-lg font-semibold text-gray-800">Margen de negociacion por distrito</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Cuanto se puede negociar: diferencia entre precio pedido en portales y precio real de cierre
              </p>
            </div>
            <div>
              <select value={notaryType} onChange={e => setNotaryType(e.target.value)}
                className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white">
                <option value="todos">Todos</option>
                <option value="segunda_mano">Segunda mano</option>
                <option value="nueva">Obra nueva</option>
              </select>
            </div>
          </div>
          <div className="overflow-auto rounded-lg border border-gray-100">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Distrito</th>
                  <th className="px-4 py-3 text-right">/m2 pedido</th>
                  <th className="px-4 py-3 text-right">/m2 escritura</th>
                  <th className="px-4 py-3 text-right">Diferencia</th>
                  <th className="px-4 py-3 text-right">Transacciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {stats.notary_by_district.map(d => {
                  const colorClass = d.spread_pct > 15 ? 'text-red-600 font-semibold'
                    : d.spread_pct > 5 ? 'text-yellow-700 font-semibold'
                    : 'text-emerald-700 font-semibold'
                  return (
                    <tr key={d.district} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium text-gray-800">{d.district}</td>
                      <td className="px-4 py-2 text-right text-gray-700">{fmt(d.avg_asking_psqm)}</td>
                      <td className="px-4 py-2 text-right text-gray-700">{fmt(d.avg_notary_psqm)}</td>
                      <td className={`px-4 py-2 text-right ${colorClass}`}>
                        {d.spread_pct >= 0 ? '+' : ''}{d.spread_pct.toFixed(1)}%
                      </td>
                      <td className="px-4 py-2 text-right text-gray-500">{fmt(d.notary_transactions)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-400 mt-3">Mayor % = mas margen de negociacion disponible</p>
        </div>
      )}

      {/* ================================================================ */}
      {/* ML Spread                                                         */}
      {/* ================================================================ */}
      {mlDistricts.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800">Valoracion ML vs precio pedido</h2>
          <p className="text-xs text-gray-400 mt-0.5 mb-4">
            El modelo de Machine Learning identifica distritos donde los precios pedidos estan por debajo de su valoracion ({stats.deals_with_prediction} deals analizados)
          </p>
          <div className="overflow-auto rounded-lg border border-gray-100">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Distrito</th>
                  <th className="px-4 py-3 text-right">Deals valorados</th>
                  <th className="px-4 py-3 text-right">Spread ML</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mlDistricts.map(d => {
                  const spread = d.ml_vs_ask_avg!
                  const c = spread > 0.05 ? 'text-emerald-700 font-semibold'
                    : spread >= 0 ? 'text-yellow-700 font-semibold' : 'text-red-600 font-semibold'
                  return (
                    <tr key={d.district} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium text-gray-800">{d.district}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{fmt(d.count)}</td>
                      <td className={`px-4 py-2 text-right ${c}`}>{spread >= 0 ? '+' : ''}{(spread * 100).toFixed(1)}%</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/* Estado + Timeline + Portfolio                                     */}
      {/* ================================================================ */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Estado de la propiedad</h2>
        <div className="flex items-center gap-8 flex-wrap">
          <div className="shrink-0">
            <ResponsiveContainer width={260} height={260}>
              <PieChart>
                <Pie data={conditionPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100}
                  label={({ value }) => conditionTotal > 0 ? `${Math.round((value / conditionTotal) * 100)}%` : ''} labelLine={false}>
                  {conditionPieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip formatter={(v: unknown) => [fmt(typeof v === 'number' ? v : null), '']} />
                <Legend formatter={(value) => <span style={{ fontSize: 12 }}>{value}</span>} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-2 flex-1">
            {conditionPieData.map(d => (
              <div key={d.name} className="flex items-center gap-3">
                <span className="inline-block w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: d.color }} />
                <span className="text-sm text-gray-700 w-24">{d.name}</span>
                <span className="text-sm font-medium text-gray-900">{fmt(d.value)}</span>
                <span className="text-xs text-gray-400">({conditionTotal > 0 ? Math.round((d.value / conditionTotal) * 100) : 0}%)</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {stats.listed_over_time.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Nuevos listings por mes</h2>
          <p className="text-xs text-gray-400 mb-4">Fecha de publicacion en portales</p>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={stats.listed_over_time} margin={{ top: 4, right: 20, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: unknown) => [`${fmt(typeof v === 'number' ? v : null)}`, 'Listings']} />
              <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {stats.portfolio_summary.total_analyses > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Cartera analizada</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Total analisis', value: fmt(stats.portfolio_summary.total_analyses), color: 'text-gray-900' },
              { label: 'IRR medio', value: stats.portfolio_summary.avg_irr != null ? `${(stats.portfolio_summary.avg_irr * 100).toFixed(1)}%` : '---', color: 'text-blue-700' },
              { label: 'MOIC medio', value: stats.portfolio_summary.avg_moic != null ? `${fmt(stats.portfolio_summary.avg_moic, 2)}x` : '---', color: 'text-gray-900' },
              { label: 'ROE medio', value: stats.portfolio_summary.avg_roe != null ? `${(stats.portfolio_summary.avg_roe * 100).toFixed(1)}%` : '---', color: 'text-emerald-700' },
            ].map(kpi => (
              <div key={kpi.label} className="bg-gray-50 rounded-lg p-4">
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{kpi.label}</p>
                <p className={`text-2xl font-bold ${kpi.color}`}>{kpi.value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Toggle */}
      <div className="flex justify-center mb-6">
        <button onClick={() => setShowMore(s => !s)}
          className="px-4 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50">
          {showMore ? '^ Ocultar' : 'v Mostrar mas analisis'}
        </button>
      </div>

      {showMore && (
        <>
          <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-3">Precio /m2 por distrito</h2>
            <ResponsiveContainer width="100%" height={520}>
              <BarChart data={byPriceDesc} layout="vertical" margin={{ top: 4, right: 40, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="district" width={130} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: unknown) => [`${fmt(typeof v === 'number' ? v : null)}/m2`, 'Precio medio']} />
                {stats.market_avg_price_sqm != null && (
                  <ReferenceLine x={stats.market_avg_price_sqm} stroke="#9ca3af" strokeDasharray="4 2"
                    label={{ value: 'Media', position: 'top', fontSize: 10, fill: '#6b7280' }} />
                )}
                <Bar dataKey="avg_price_sqm" name="Precio /m2" fill="#2563eb" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {stats.price_histogram.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-3">Distribucion de precios</h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={stats.price_histogram} margin={{ top: 4, right: 20, left: 0, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="bucket" tick={{ fontSize: 10 }} angle={-40} textAnchor="end" interval={0} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: unknown) => [`${fmt(typeof v === 'number' ? v : null)}`, 'Listings']} />
                  <Bar dataKey="count" fill="#6366f1" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {stats.size_histogram.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-800 mb-3">Distribucion de superficies</h2>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={stats.size_histogram} margin={{ top: 4, right: 16, left: 0, bottom: 36 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="bucket" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            {stats.bedrooms_distribution.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-800 mb-3">Distribucion por habitaciones</h2>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={stats.bedrooms_distribution} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="bedrooms" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v} hab.`} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Bar dataKey="count" fill="#0ea5e9" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Prevalencia de amenidades</h2>
            <div className="space-y-4 max-w-lg">
              {amenityRows.map(({ label, key }) => {
                const pct = Math.round(stats.amenities[key] * 100)
                return (
                  <div key={key}>
                    <div className="flex justify-between text-sm text-gray-700 mb-1">
                      <span>{label}</span>
                      <span className="font-medium text-gray-900">{pct}%</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
                      <div className="h-2.5 rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
