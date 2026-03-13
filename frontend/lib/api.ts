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

export async function scrapeDeals(
  portal: 'idealista' | 'redpiso' | 'fotocasa' | 'pisos' | 'idealista_html' = 'idealista',
  pageFrom = 1,
): Promise<{ source: string; listings_fetched: number; new_deals_inserted: number }> {
  const body = portal === 'redpiso'
    ? { portal: 'redpiso', page_from: pageFrom, max_pages: 9 }
    : portal === 'fotocasa'
    ? { portal: 'fotocasa', page_from: pageFrom, max_pages: 3 }
    : portal === 'pisos'
    ? { portal: 'pisos', page_from: pageFrom, max_pages: 3 }
    : portal === 'idealista_html'
    ? { portal: 'idealista_html', page_from: pageFrom, max_pages: 3 }
    : { portal: 'idealista', max_pages: 10 }
  const res = await fetch(`${BASE}/deals/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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

export interface DistrictStats {
  district: string
  count: number
  avg_price_sqm: number | null
  avg_size_sqm: number | null
  pct_renew: number
  pct_good: number
  pct_new: number
  avg_price_renew: number | null
  avg_price_good: number | null
  reform_upside: number | null
  ml_vs_ask_avg: number | null
}

export interface ConditionByDistrict {
  district: string
  renew: number
  good: number
  new: number
}

export interface AnalyticsStats {
  total_deals: number
  deals_with_prediction: number
  market_avg_price_sqm: number | null
  by_district: DistrictStats[]
  condition_by_district: ConditionByDistrict[]
  price_histogram: { bucket: string; count: number }[]
  size_histogram: { bucket: string; count: number }[]
  bedrooms_distribution: { bedrooms: number; count: number }[]
  amenities: { elevator: number; terrace: number; balcony: number; garage: number; storage_room: number }
  listed_over_time: { month: string; count: number }[]
  portfolio_summary: { total_analyses: number; avg_irr: number | null; avg_moic: number | null; avg_roe: number | null }
}

export async function getAnalyticsStats(maxPriceSqm?: number, minPriceSqm?: number): Promise<AnalyticsStats> {
  const params = new URLSearchParams()
  if (maxPriceSqm != null) params.set('max_price_sqm', String(maxPriceSqm))
  if (minPriceSqm != null) params.set('min_price_sqm', String(minPriceSqm))
  const qs = params.toString()
  const res = await fetch(`${BASE}/analytics${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface PredictionWithDeal {
  id: string
  deal_id: string
  predicted_price: number
  model_version?: string
  created_at: string
  address?: string
  district?: string
  size_sqm?: number
  asking_price?: number
  condition?: string
  url?: string
}

export async function getPredictions(): Promise<PredictionWithDeal[]> {
  const res = await fetch(`${BASE}/deals/predictions`)
  if (!res.ok) throw new Error('Failed to fetch predictions')
  return res.json()
}
