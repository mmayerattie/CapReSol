'use client'
import { useEffect, useState } from 'react'
import { getAnalyses, createAnalysis, Analysis, FlipInput } from '../../lib/api'

function fmt(n?: number | null, decimals = 0) {
  if (n == null) return '—'
  return n.toLocaleString('es-ES', { maximumFractionDigits: decimals })
}
function pct(n?: number | null) {
  if (n == null) return '—'
  return (n * 100).toFixed(1) + '%'
}

// Form state stores percentages as human values (e.g. 7.5 for 7.5%)
// They are divided by 100 on submit before sending to the API
interface FormState {
  name: string
  size_sqm: number
  purchase_price: number
  capex_total: number
  capex_months: number
  project_months: number
  exit_price_per_sqm: number
  monthly_opex: number
  ibi_annual: number
  closing_costs_pct: number  // % e.g. 7.5
  broker_fee_pct: number     // % e.g. 3.63
  tax_rate: number           // % e.g. 0
  mortgage_ltv: number       // % e.g. 60
  mortgage_rate_annual: number    // % e.g. 6.7
  capex_debt: number
  capex_debt_rate_annual: number  // % e.g. 6
}

const EMPTY: FormState = {
  name: '',
  size_sqm: 0,
  purchase_price: 0,
  capex_total: 0,
  capex_months: 10,
  project_months: 18,
  exit_price_per_sqm: 0,
  monthly_opex: 1000,
  ibi_annual: 3000,
  closing_costs_pct: 7.5,
  broker_fee_pct: 3.63,
  tax_rate: 0,
  mortgage_ltv: 0,
  mortgage_rate_annual: 0,
  capex_debt: 0,
  capex_debt_rate_annual: 0,
}

function Field({ label, name, value, onChange, step = 'any', note, placeholder }: {
  label: string; name: string; value: number | string | undefined
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  step?: string; note?: string; placeholder?: string
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">
        {label}{note && <span className="ml-1 text-gray-400 text-xs">{note}</span>}
      </label>
      <input
        name={name} type="number" step={step}
        value={value ?? ''} placeholder={placeholder}
        onChange={onChange}
        className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
      />
    </div>
  )
}

function LinkedPricePair({ labelTotal, labelPsqm, total, psqm, sqm, onTotalChange, onPsqmChange }: {
  labelTotal: string; labelPsqm: string
  total: number; psqm: number; sqm: number
  onTotalChange: (v: number) => void; onPsqmChange: (v: number) => void
}) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="block text-xs text-gray-500 mb-1">{labelTotal}</label>
        <input type="number" step="any" value={total || ''} placeholder="Total €"
          onChange={e => onTotalChange(parseFloat(e.target.value) || 0)}
          className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400" />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">{labelPsqm}</label>
        <input type="number" step="any" value={psqm || ''} placeholder="€/m²"
          onChange={e => onPsqmChange(parseFloat(e.target.value) || 0)}
          className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400" />
      </div>
      {sqm > 0 && total > 0 && (
        <p className="col-span-2 text-xs text-gray-400 -mt-1">
          {sqm} m² × €{fmt(psqm, 0)}/m² = <span className="font-medium text-gray-600">€{fmt(total, 0)}</span>
        </p>
      )}
    </div>
  )
}

export default function AnalysesPage() {
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY)
  const [purchasePsqm, setPurchasePsqm] = useState(0)
  const [exitTotal, setExitTotal] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getAnalyses().then(setAnalyses).catch(() => setError('No se pudo conectar al backend.'))
  }, [])

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target
    const num = parseFloat(value) || 0
    setForm(prev => {
      const updated = { ...prev, [name]: name === 'name' ? value : num }
      if (name === 'size_sqm' && num > 0) {
        if (prev.purchase_price) setPurchasePsqm(Math.round(prev.purchase_price / num))
        if (prev.exit_price_per_sqm) setExitTotal(Math.round(prev.exit_price_per_sqm * num))
      }
      return updated
    })
  }

  function onPurchaseTotalChange(v: number) {
    setForm(prev => ({ ...prev, purchase_price: v }))
    if (form.size_sqm > 0) setPurchasePsqm(Math.round(v / form.size_sqm))
  }
  function onPurchasePsqmChange(v: number) {
    setPurchasePsqm(v)
    setForm(prev => ({ ...prev, purchase_price: Math.round(v * (prev.size_sqm || 0)) }))
  }
  function onExitPsqmChange(v: number) {
    setForm(prev => ({ ...prev, exit_price_per_sqm: v }))
    setExitTotal(Math.round(v * (form.size_sqm || 0)))
  }
  function onExitTotalChange(v: number) {
    setExitTotal(v)
    const psqm = form.size_sqm > 0 ? Math.round(v / form.size_sqm) : 0
    setForm(prev => ({ ...prev, exit_price_per_sqm: psqm }))
  }

  function resetForm() {
    setForm(EMPTY); setPurchasePsqm(0); setExitTotal(0); setError('')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true); setError('')
    try {
      // Convert % display values (0–100) to decimals (0–1) before sending
      const payload: FlipInput = {
        ...form,
        closing_costs_pct: form.closing_costs_pct / 100,
        broker_fee_pct: form.broker_fee_pct / 100,
        tax_rate: form.tax_rate / 100,
        mortgage_ltv: form.mortgage_ltv / 100,
        mortgage_rate_annual: form.mortgage_rate_annual / 100,
        capex_debt_rate_annual: form.capex_debt_rate_annual / 100,
      }
      const result = await createAnalysis(payload)
      setAnalyses(prev => [result, ...prev])
      setShowForm(false)
      resetForm()
    } catch (e: unknown) {
      setError(`Error: ${e instanceof Error ? e.message : 'Error desconocido'}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Análisis Financiero</h1>
        <button onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium">
          + Nuevo Análisis
        </button>
      </div>

      <div className="overflow-auto rounded-lg border border-gray-200 bg-white mb-8">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">Nombre</th>
              <th className="px-4 py-3 text-right">m²</th>
              <th className="px-4 py-3 text-right">Compra</th>
              <th className="px-4 py-3 text-right">Capex</th>
              <th className="px-4 py-3 text-right">Meses</th>
              <th className="px-4 py-3 text-right">Exit €/m²</th>
              <th className="px-4 py-3 text-right">Beneficio</th>
              <th className="px-4 py-3 text-right">IRR</th>
              <th className="px-4 py-3 text-right">MOIC</th>
              <th className="px-4 py-3 text-right">ROE</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {analyses.length === 0 && (
              <tr>
                <td colSpan={10} className="text-center py-10 text-gray-400">
                  No hay análisis guardados — pulsa &quot;+ Nuevo Análisis&quot;
                </td>
              </tr>
            )}
            {analyses.map(a => (
              <tr key={a.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">{a.name}</td>
                <td className="px-4 py-2 text-right">{fmt(a.size_sqm)}</td>
                <td className="px-4 py-2 text-right">€{fmt(a.purchase_price)}</td>
                <td className="px-4 py-2 text-right">€{fmt(a.capex_total)}</td>
                <td className="px-4 py-2 text-right">{a.project_months}</td>
                <td className="px-4 py-2 text-right">€{fmt(a.exit_price_per_sqm)}</td>
                <td className={`px-4 py-2 text-right font-semibold ${a.profit >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                  €{fmt(a.profit)}
                </td>
                <td className="px-4 py-2 text-right font-semibold text-blue-700">{pct(a.irr)}</td>
                <td className="px-4 py-2 text-right">{a.moic.toFixed(2)}x</td>
                <td className="px-4 py-2 text-right">{pct(a.return_on_equity)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-8">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold">Nuevo Análisis Fix &amp; Flip</h2>
              <button onClick={() => { setShowForm(false); resetForm() }} className="text-gray-400 hover:text-gray-700 text-xl">✕</button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nombre</label>
                <input name="name" type="text" value={form.name} onChange={handleChange} required
                  placeholder="Ej: Serrano 81"
                  className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400" />
              </div>

              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase mb-3">Propiedad</p>
                <div className="mb-4">
                  <Field label="Superficie (m²)" name="size_sqm" value={form.size_sqm} onChange={handleChange} />
                </div>
                <LinkedPricePair
                  labelTotal="Precio compra — Total (€)" labelPsqm="Precio compra — €/m²"
                  total={form.purchase_price} psqm={purchasePsqm} sqm={form.size_sqm}
                  onTotalChange={onPurchaseTotalChange} onPsqmChange={onPurchasePsqmChange}
                />
              </div>

              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase mb-3">Reforma</p>
                <div className="grid grid-cols-3 gap-4">
                  <Field label="Capex total (€)" name="capex_total" value={form.capex_total} onChange={handleChange} />
                  <Field label="Duración capex (meses)" name="capex_months" value={form.capex_months} onChange={handleChange} step="1" />
                  <Field label="Duración proyecto (meses)" name="project_months" value={form.project_months} onChange={handleChange} step="1" />
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase mb-3">Salida</p>
                <div className="mb-4">
                  <LinkedPricePair
                    labelTotal="Precio salida — Total (€)" labelPsqm="Precio salida — €/m²"
                    total={exitTotal} psqm={form.exit_price_per_sqm} sqm={form.size_sqm}
                    onTotalChange={onExitTotalChange} onPsqmChange={onExitPsqmChange}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4 mt-3">
                  <Field label="Comisión broker salida (%)" name="broker_fee_pct" value={form.broker_fee_pct}
                    onChange={handleChange} step="0.01" placeholder="ej: 3.63" />
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase mb-3">Gastos corrientes</p>
                <div className="grid grid-cols-3 gap-4">
                  <Field label="Opex mensual (€)" name="monthly_opex" value={form.monthly_opex}
                    onChange={handleChange} note="comunidad + suministros" />
                  <Field label="IBI anual (€)" name="ibi_annual" value={form.ibi_annual} onChange={handleChange} />
                  <Field label="Gastos de cierre (%)" name="closing_costs_pct" value={form.closing_costs_pct}
                    onChange={handleChange} step="0.1" placeholder="ej: 7.5" />
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase mb-3">Financiación (opcional)</p>
                <div className="grid grid-cols-2 gap-4">
                  <Field label="% Financiación hipoteca (LTV)" name="mortgage_ltv" value={form.mortgage_ltv}
                    onChange={handleChange} step="1" placeholder="ej: 60" />
                  <Field label="Tipo hipoteca anual (%)" name="mortgage_rate_annual" value={form.mortgage_rate_annual}
                    onChange={handleChange} step="0.1" placeholder="ej: 6.7" />
                  <Field label="Deuda para reforma (€)" name="capex_debt" value={form.capex_debt} onChange={handleChange} />
                  <Field label="Tipo deuda reforma anual (%)" name="capex_debt_rate_annual" value={form.capex_debt_rate_annual}
                    onChange={handleChange} step="0.1" placeholder="ej: 6" />
                </div>
              </div>

              {error && <p className="text-red-600 text-sm">{error}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => { setShowForm(false); resetForm() }}
                  className="px-4 py-2 border border-gray-200 rounded-md text-sm">
                  Cancelar
                </button>
                <button type="submit" disabled={submitting}
                  className="px-6 py-2 bg-blue-600 text-white rounded-md text-sm font-medium disabled:opacity-50">
                  {submitting ? 'Calculando…' : 'Ejecutar análisis'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
