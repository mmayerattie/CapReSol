'use client'
import { useEffect, useState } from 'react'
import { getAnalyticsStats, AnalyticsStats, DistrictStats } from '../../lib/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ReferenceLine,
} from 'recharts'

function fmt(n: number | null | undefined, decimals = 0): string {
  if (n == null) return '—'
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

const CONDITION_COLORS: Record<string, string> = {
  renew: '#f97316',
  good: '#3b82f6',
  new: '#10b981',
}

const MAX_PRICE_PRESETS = [
  { label: '10k', value: 10000 },
  { label: '15k', value: 15000 },
  { label: '20k', value: 20000 },
  { label: '25k', value: 25000 },
  { label: 'Sin límite', value: 0 },
]

const MIN_PRICE_PRESETS = [
  { label: 'Sin mín.', value: 0 },
  { label: '500', value: 500 },
  { label: '1k', value: 1000 },
  { label: '2k', value: 2000 },
]

export default function AnalyticsPage() {
  const [stats, setStats] = useState<AnalyticsStats | null>(null)
  const [error, setError] = useState('')
  const [showMore, setShowMore] = useState(false)
  const [maxPsqm, setMaxPsqm] = useState(25000)
  const [minPsqm, setMinPsqm] = useState(500)

  useEffect(() => {
    setStats(null)
    getAnalyticsStats(maxPsqm || undefined, minPsqm || undefined)
      .then(setStats)
      .catch(() => setError('No se pudieron cargar los datos. ¿Está el backend corriendo?'))
  }, [maxPsqm, minPsqm])

  if (error) {
    return (
      <div className="p-8 text-red-600 text-sm bg-red-50 rounded-lg border border-red-200">
        {error}
      </div>
    )
  }

  if (!stats) {
    return <p className="text-gray-400 text-sm p-8">Cargando analytics…</p>
  }

  // --- Derived data ---

  // Districts sorted descending by avg_price_sqm
  const byPriceDesc = [...stats.by_district]
    .filter(d => d.avg_price_sqm != null)
    .sort((a, b) => (b.avg_price_sqm ?? 0) - (a.avg_price_sqm ?? 0))

  // Districts with reform upside, sorted descending
  const byUpsideDesc = [...stats.by_district]
    .filter(d => d.reform_upside != null && d.reform_upside > 0)
    .sort((a, b) => (b.reform_upside ?? 0) - (a.reform_upside ?? 0))

  // Condition by district sorted by total renew count desc
  const conditionSorted = [...stats.condition_by_district]
    .sort((a, b) => b.renew - a.renew)

  // KPI: highest reform upside
  const topUpside: DistrictStats | undefined = byUpsideDesc[0]

  // KPI: most affordable district (non-null lowest avg_price_sqm)
  const mostAffordable: DistrictStats | undefined = [...stats.by_district]
    .filter(d => d.avg_price_sqm != null)
    .sort((a, b) => (a.avg_price_sqm ?? Infinity) - (b.avg_price_sqm ?? Infinity))[0]

  // Overall condition totals for pie chart
  const totalRenew = stats.condition_by_district.reduce((s, d) => s + d.renew, 0)
  const totalGood = stats.condition_by_district.reduce((s, d) => s + d.good, 0)
  const totalNew = stats.condition_by_district.reduce((s, d) => s + d.new, 0)
  const conditionPieData = [
    { name: 'A reformar', value: totalRenew, color: '#f97316' },
    { name: 'Buen estado', value: totalGood, color: '#3b82f6' },
    { name: 'Nueva', value: totalNew, color: '#10b981' },
  ].filter(d => d.value > 0)
  const conditionTotal = totalRenew + totalGood + totalNew

  // ML vs Ask table
  const mlDistricts = [...stats.by_district]
    .filter(d => d.ml_vs_ask_avg != null)
    .sort((a, b) => (b.ml_vs_ask_avg ?? 0) - (a.ml_vs_ask_avg ?? 0))

  // Amenity rows
  const amenityRows: { label: string; key: keyof typeof stats.amenities }[] = [
    { label: 'Ascensor', key: 'elevator' },
    { label: 'Terraza', key: 'terrace' },
    { label: 'Balcón', key: 'balcony' },
    { label: 'Garaje', key: 'garage' },
    { label: 'Trastero', key: 'storage_room' },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics · Madrid</h1>
          <p className="text-gray-500 text-sm mt-1">
            Análisis de mercado inmobiliario para toma de decisiones de inversión
          </p>
        </div>
        <div className="flex flex-col gap-1.5 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium w-14 text-right">Máx €/m²</span>
            <div className="flex gap-1">
              {MAX_PRICE_PRESETS.map(p => (
                <button
                  key={p.value}
                  onClick={() => setMaxPsqm(p.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    maxPsqm === p.value
                      ? 'bg-gray-900 text-white border-gray-900'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium w-14 text-right">Mín €/m²</span>
            <div className="flex gap-1">
              {MIN_PRICE_PRESETS.map(p => (
                <button
                  key={p.value}
                  onClick={() => setMinPsqm(p.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    minPsqm === p.value
                      ? 'bg-gray-900 text-white border-gray-900'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard
          label="Dataset"
          value={fmt(stats.total_deals)}
          sub={
            (maxPsqm > 0 || minPsqm > 0)
              ? [
                  minPsqm > 0 ? `≥ €${minPsqm}/m²` : '',
                  maxPsqm > 0 ? `≤ €${(maxPsqm / 1000).toFixed(0)}k/m²` : '',
                ].filter(Boolean).join(' · ')
              : 'listings scrapeados'
          }
        />
        <KpiCard
          label="Precio medio €/m²"
          value={stats.market_avg_price_sqm != null ? `€${fmt(stats.market_avg_price_sqm)}` : '—'}
          sub="media ciudad"
        />
        <KpiCard
          label="Mayor upside reforma"
          value={
            topUpside
              ? `${topUpside.district} · €${Math.round(topUpside.reform_upside!).toLocaleString('es-ES')}/m²`
              : '—'
          }
          sub="gap precio reforma→venta"
        />
        <KpiCard
          label="Zona más asequible"
          value={
            mostAffordable
              ? `${mostAffordable.district} · €${Math.round(mostAffordable.avg_price_sqm!).toLocaleString('es-ES')}/m²`
              : '—'
          }
          sub="precio entrada"
        />
      </div>

      {/* Section 1: Precio €/m² por Distrito */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Precio €/m² por Distrito</h2>
        <ResponsiveContainer width="100%" height={520}>
          <BarChart
            data={byPriceDesc}
            layout="vertical"
            margin={{ top: 4, right: 40, left: 0, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`}
              tick={{ fontSize: 11 }}
            />
            <YAxis
              type="category"
              dataKey="district"
              width={130}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              formatter={(v: unknown) => [`€${fmt(typeof v === 'number' ? v : null)}/m²`, 'Precio medio']}
            />
            {stats.market_avg_price_sqm != null && (
              <ReferenceLine
                x={stats.market_avg_price_sqm}
                stroke="#9ca3af"
                strokeDasharray="4 2"
                label={{ value: 'Media', position: 'top', fontSize: 10, fill: '#6b7280' }}
              />
            )}
            <Bar dataKey="avg_price_sqm" name="Precio €/m²" fill="#2563eb" radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Section 2: Upside de Reforma por Distrito */}
      {byUpsideDesc.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Upside de Reforma por Distrito</h2>
          <p className="text-xs text-gray-400 mb-4">
            Diferencia entre precio de venta en buen estado y precio de inmuebles a reformar
          </p>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart
              data={byUpsideDesc}
              layout="vertical"
              margin={{ top: 4, right: 40, left: 0, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis
                type="number"
                tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                type="category"
                dataKey="district"
                width={130}
                tick={{ fontSize: 11 }}
              />
              <Tooltip
                formatter={(v: unknown) => [`€${fmt(typeof v === 'number' ? v : null)}/m² de margen disponible`, 'Upside reforma']}
              />
              <Bar dataKey="reform_upside" name="Upside reforma" fill="#059669" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Section 3: Distribución por Estado de la Propiedad */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Distribución por Estado de la Propiedad</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Stacked bar by district */}
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-3">Por distrito</p>
            <ResponsiveContainer width="100%" height={520}>
              <BarChart
                data={conditionSorted}
                layout="vertical"
                margin={{ top: 4, right: 20, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="district"
                  width={130}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="renew" name="A reformar" stackId="a" fill={CONDITION_COLORS.renew} />
                <Bar dataKey="good" name="Buen estado" stackId="a" fill={CONDITION_COLORS.good} />
                <Bar dataKey="new" name="Nueva" stackId="a" fill={CONDITION_COLORS.new} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Pie chart overall */}
          <div className="flex flex-col items-center justify-center">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-3">Total dataset</p>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={conditionPieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={110}
                  label={({ name, value }) =>
                    conditionTotal > 0 ? `${Math.round((value / conditionTotal) * 100)}%` : ''
                  }
                  labelLine={false}
                >
                  {conditionPieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: unknown) => [fmt(typeof v === 'number' ? v : null), '']} />
                <Legend
                  formatter={(value) => <span style={{ fontSize: 12 }}>{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-4 space-y-1 w-full max-w-xs">
              {conditionPieData.map(d => (
                <div key={d.name} className="flex justify-between text-xs text-gray-600">
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: d.color }} />
                    {d.name}
                  </span>
                  <span className="font-medium">{fmt(d.value)} listings</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Section 8: Mapa de Oportunidades ML */}
      {mlDistricts.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-gray-800">
              Spread ML vs Precio Pedido (por distrito)
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Verde = mercado subestimado según el modelo · Rojo = precio pedido por encima de tasación ML
            </p>
          </div>
          <div className="overflow-auto rounded-lg border border-gray-100">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Distrito</th>
                  <th className="px-4 py-3 text-right">Deals valorados</th>
                  <th className="px-4 py-3 text-right">Spread ML vs Ask</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mlDistricts.map(d => {
                  const spread = d.ml_vs_ask_avg!
                  const spreadPct = (spread * 100).toFixed(1)
                  const sign = spread >= 0 ? '+' : ''
                  const colorClass =
                    spread > 0.05
                      ? 'text-emerald-700 font-semibold'
                      : spread >= 0
                      ? 'text-yellow-700 font-semibold'
                      : 'text-red-600 font-semibold'
                  return (
                    <tr key={d.district} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium text-gray-800">{d.district}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{fmt(d.count)}</td>
                      <td className={`px-4 py-2 text-right ${colorClass}`}>
                        {sign}{spreadPct}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Portfolio Summary */}
      {stats.portfolio_summary.total_analyses > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Cartera analizada</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total análisis</p>
              <p className="text-2xl font-bold text-gray-900">
                {fmt(stats.portfolio_summary.total_analyses)}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">IRR medio</p>
              <p className="text-2xl font-bold text-blue-700">
                {stats.portfolio_summary.avg_irr != null
                  ? `${(stats.portfolio_summary.avg_irr * 100).toFixed(1)}%`
                  : '—'}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">MOIC medio</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats.portfolio_summary.avg_moic != null
                  ? `${fmt(stats.portfolio_summary.avg_moic, 2)}x`
                  : '—'}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">ROE medio</p>
              <p className="text-2xl font-bold text-emerald-700">
                {stats.portfolio_summary.avg_roe != null
                  ? `${(stats.portfolio_summary.avg_roe * 100).toFixed(1)}%`
                  : '—'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Toggle button for secondary charts */}
      <div className="flex justify-center mb-6">
        <button
          onClick={() => setShowMore(s => !s)}
          className="px-4 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-2"
        >
          {showMore ? '▲ Ocultar análisis adicionales' : '▼ Mostrar más análisis'}
        </button>
      </div>

      {showMore && (
        <>
          {/* Section 4: Distribución de Precios */}
          {stats.price_histogram.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-3">Distribución de Precios</h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={stats.price_histogram} margin={{ top: 4, right: 20, left: 0, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="bucket"
                    tick={{ fontSize: 10 }}
                    angle={-40}
                    textAnchor="end"
                    interval={0}
                  />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: unknown) => [`${fmt(typeof v === 'number' ? v : null)} listings`, 'Listings']} />
                  <Bar dataKey="count" name="Listings" fill="#6366f1" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Section 5: Superficies + Habitaciones */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {stats.size_histogram.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-800 mb-3">Distribución de Superficies</h2>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={stats.size_histogram} margin={{ top: 4, right: 16, left: 0, bottom: 36 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="bucket"
                      tick={{ fontSize: 10 }}
                      angle={-35}
                      textAnchor="end"
                      interval={0}
                    />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: unknown) => [`${fmt(typeof v === 'number' ? v : null)} listings`, 'Listings']} />
                    <Bar dataKey="count" name="Listings" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {stats.bedrooms_distribution.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-800 mb-3">Distribución por Habitaciones</h2>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart
                    data={stats.bedrooms_distribution}
                    margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="bedrooms"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v) => `${v} hab.`}
                    />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip
                      labelFormatter={(v) => `${v} habitaciones`}
                      formatter={(v: unknown) => [`${fmt(typeof v === 'number' ? v : null)} listings`, 'Listings']}
                    />
                    <Bar dataKey="count" name="Listings" fill="#0ea5e9" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Section 6: Amenidades */}
          <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Prevalencia de Amenidades</h2>
            <div className="space-y-4 max-w-lg">
              {amenityRows.map(({ label, key }) => {
                const pct = stats.amenities[key]
                const pctDisplay = Math.round(pct * 100)
                return (
                  <div key={key}>
                    <div className="flex justify-between text-sm text-gray-700 mb-1">
                      <span>{label}</span>
                      <span className="font-medium text-gray-900">{pctDisplay}%</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
                      <div
                        className="h-2.5 rounded-full bg-blue-600 transition-all duration-500"
                        style={{ width: `${pctDisplay}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
            <p className="text-xs text-gray-400 mt-4">
              Porcentaje de listings en el dataset con cada amenidad declarada
            </p>
          </div>
        </>
      )}
    </div>
  )
}
