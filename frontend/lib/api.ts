const BASE = '/api'

export interface Deal {
  id: string
  address?: string
  city?: string
  district?: string
  zone?: string
  property_type?: string
  size_sqm?: number
  bedrooms?: number
  bathrooms?: number
  floor?: number
  asking_price?: number
  condition?: string
  listed_date?: string
  url?: string
  created_at: string
}

export interface Prediction {
  id: string
  deal_id: string
  predicted_price: number
  model_version?: string
  created_at: string
}

export interface Analysis {
  id: string
  deal_id?: string
  name: string
  size_sqm: number
  purchase_price: number
  capex_total: number
  project_months: number
  exit_price_per_sqm: number
  mortgage_ltv: number
  mortgage_rate_annual: number
  capex_debt: number
  irr?: number
  moic: number
  return_on_equity: number
  gross_margin: number
  profit: number
  gross_exit_price: number
  net_exit_price: number
  total_dev_cost: number
  max_equity_exposure: number
  closing_costs: number
  broker_fee: number
  mortgage_debt: number
  total_debt: number
  created_at: string
}

export interface FlipInput {
  deal_id?: string
  name?: string
  size_sqm: number
  purchase_price: number
  capex_total: number
  capex_months: number
  project_months: number
  exit_price_per_sqm: number
  monthly_opex: number
  ibi_annual: number
  closing_costs_pct?: number
  broker_fee_pct?: number
  tax_rate?: number
  mortgage_ltv?: number
  mortgage_rate_annual?: number
  capex_debt?: number
  capex_debt_rate_annual?: number
}

export async function getDeals(): Promise<Deal[]> {
  const res = await fetch(`${BASE}/deals`)
  if (!res.ok) throw new Error('Failed to fetch deals')
  return res.json()
}

export async function scrapeDeals(): Promise<{ listings_fetched: number; new_deals_inserted: number }> {
  const res = await fetch(`${BASE}/deals/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_html_fallback: true, max_pages: 2 }),
  })
  if (!res.ok) throw new Error('Scrape failed')
  return res.json()
}

export async function predictDeals(dealIds: string[]): Promise<Prediction[]> {
  const res = await fetch(`${BASE}/deals/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ deal_ids: dealIds }),
  })
  if (!res.ok) throw new Error('Prediction failed')
  return res.json()
}

export async function getAnalyses(): Promise<Analysis[]> {
  const res = await fetch(`${BASE}/analyses`)
  if (!res.ok) throw new Error('Failed to fetch analyses')
  return res.json()
}

export async function createAnalysis(data: FlipInput): Promise<Analysis> {
  const res = await fetch(`${BASE}/analyses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}
