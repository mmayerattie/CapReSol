'use client'
import { useEffect, useState, useMemo } from 'react'
import Link from 'next/link'
import { getDeals, scrapeDeals, Deal } from '../lib/api'

const CONDITION_LABEL: Record<string, string> = {
  newdevelopment: 'Nueva',
  good: 'Buen estado',
  renew: 'A reformar',
}

export default function HomePage() {
  const [deals, setDeals] = useState<Deal[]>([])
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [scrapeMsg, setScrapeMsg] = useState('')

  const currentDayAndDate = new Date().toLocaleDateString('es-ES', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  })

  useEffect(() => {
    getDeals()
      .then(setDeals)
      .finally(() => setLoading(false))
  }, [])

  const distinctDistricts = useMemo(
    () => new Set(deals.map(d => d.district).filter(Boolean)).size,
    [deals]
  )

  const avgPsqm = useMemo(() => {
    const valid = deals.filter(d => d.asking_price != null && d.size_sqm != null)
    if (valid.length === 0) return null
    return valid.reduce((sum, d) => sum + d.asking_price! / d.size_sqm!, 0) / valid.length
  }, [deals])

  const recentDeals = useMemo(() => deals.slice(0, 5), [deals])

  async function handleNewListings() {
    setScraping(true); setScrapeMsg('Scraping Idealista…')
    let totalFetched = 0, totalNew = 0
    try {
      const idealista = await scrapeDeals('idealista')
      totalFetched += idealista.listings_fetched
      totalNew += idealista.new_deals_inserted

      // Redpiso: 26 pages total, chunked 9 at a time to stay under proxy timeout
      const redpisoChunks = [1, 10, 19] as const
      for (const pageFrom of redpisoChunks) {
        const chunkLabel = `${pageFrom}–${Math.min(pageFrom + 8, 26)}`
        setScrapeMsg(`Idealista: ${idealista.new_deals_inserted} new — Redpiso páginas ${chunkLabel}…`)
        const chunk = await scrapeDeals('redpiso', pageFrom)
        totalFetched += chunk.listings_fetched
        totalNew += chunk.new_deals_inserted
      }

      // Fotocasa: 3 pages per chunk via Firecrawl (slower due to JS rendering)
      const fotocasaChunks = [1, 4, 7] as const
      for (const pageFrom of fotocasaChunks) {
        setScrapeMsg(`${totalNew} new so far — Fotocasa páginas ${pageFrom}–${pageFrom + 2}…`)
        try {
          const fc = await scrapeDeals('fotocasa', pageFrom)
          totalFetched += fc.listings_fetched
          totalNew += fc.new_deals_inserted
          if (fc.listings_fetched === 0) break
        } catch {
          break
        }
      }

      // Pisos.com: 3 pages per chunk via Firecrawl
      const pisosChunks = [1, 4, 7] as const
      for (const pageFrom of pisosChunks) {
        setScrapeMsg(`${totalNew} new so far — Pisos.com páginas ${pageFrom}–${pageFrom + 2}…`)
        try {
          const ps = await scrapeDeals('pisos', pageFrom)
          totalFetched += ps.listings_fetched
          totalNew += ps.new_deals_inserted
          if (ps.listings_fetched === 0) break
        } catch {
          break
        }
      }

      // Idealista HTML: 3 pages per chunk via Firecrawl (bypasses API quota)
      const idealistaHtmlChunks = [1, 4, 7] as const
      for (const pageFrom of idealistaHtmlChunks) {
        setScrapeMsg(`${totalNew} new so far — Idealista HTML páginas ${pageFrom}–${pageFrom + 2}…`)
        try {
          const ih = await scrapeDeals('idealista_html', pageFrom)
          totalFetched += ih.listings_fetched
          totalNew += ih.new_deals_inserted
          if (ih.listings_fetched === 0) break
        } catch {
          break
        }
      }

      setScrapeMsg(`${totalFetched} fetched — ${totalNew} new`)
      setDeals(await getDeals())
    } catch { setScrapeMsg('Scrape failed') }
    finally { setScraping(false) }
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <p className="text-xs text-gray-400 uppercase tracking-widest mb-1">{currentDayAndDate}</p>
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Bienvenido de nuevo</h1>
        <p className="text-gray-400 mt-0.5 text-sm">Panel de inversión inmobiliaria · Madrid</p>
      </div>

      {/* Search box (UI stub) */}
      <div className="mb-8">
        <form onSubmit={e => e.preventDefault()} className="relative">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
          </svg>
          <input
            type="text"
            placeholder="Busca propiedades… ej: 'Pisos en Chamberí, 3 hab., menos de 400k'"
            className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 placeholder-gray-400"
            disabled
          />
        </form>
        <p className="text-xs text-gray-400 mt-1.5 ml-1">Búsqueda por lenguaje natural — próximamente</p>
      </div>

      {/* Action row */}
      <div className="flex flex-wrap items-center gap-3 mb-8">
        <button
          onClick={handleNewListings}
          disabled={scraping}
          className="px-5 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-gray-700 transition-colors"
        >
          {scraping ? 'Scraping…' : 'New listings'}
        </button>
        {scrapeMsg && <span className="text-sm text-gray-500">{scrapeMsg}</span>}
      </div>

      {/* Quick stats row */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
        <span className="font-medium text-gray-800">{deals.length.toLocaleString('es-ES')}</span>
        <span>listings</span>
        <span className="text-gray-300">·</span>
        <span className="font-medium text-gray-800">{distinctDistricts}</span>
        <span>distritos</span>
        <span className="text-gray-300">·</span>
        <span>Precio medio</span>
        <span className="font-medium text-gray-800">
          {avgPsqm != null ? `€${Math.round(avgPsqm).toLocaleString('es-ES')}/m²` : '—'}
        </span>
      </div>

      {/* Recent deals table */}
      <div className="bg-white rounded-xl border border-gray-200 mb-8">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Últimos deals</h2>
          <Link href="/deals" className="text-xs text-blue-600 hover:underline">Ver todos →</Link>
        </div>
        {loading ? (
          <p className="px-5 py-4 text-sm text-gray-400">Cargando…</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-400 uppercase">
              <tr>
                <th className="px-5 py-2.5 text-left font-medium">Dirección</th>
                <th className="px-5 py-2.5 text-left font-medium">Distrito</th>
                <th className="px-5 py-2.5 text-right font-medium">Precio</th>
                <th className="px-5 py-2.5 text-left font-medium">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {recentDeals.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-5 py-4 text-center text-gray-400">
                    Sin deals — pulsa &apos;New listings&apos; para importar
                  </td>
                </tr>
              ) : (
                recentDeals.map(deal => (
                  <tr key={deal.id} className="hover:bg-gray-50">
                    <td className="px-5 py-2.5 max-w-xs truncate">
                      {deal.url ? (
                        <a href={deal.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                          {deal.address || deal.url}
                        </a>
                      ) : (deal.address || '—')}
                    </td>
                    <td className="px-5 py-2.5 text-gray-600">{deal.district || '—'}</td>
                    <td className="px-5 py-2.5 text-right font-medium text-gray-800">
                      {deal.asking_price ? `€${deal.asking_price.toLocaleString('es-ES')}` : '—'}
                    </td>
                    <td className="px-5 py-2.5 text-gray-500">
                      {CONDITION_LABEL[deal.condition ?? ''] ?? deal.condition ?? '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Quick nav cards */}
      <div className="grid grid-cols-4 gap-3 mt-8">
        {[
          { href: '/deals', label: 'Deals', desc: 'Explorar propiedades' },
          { href: '/valuaciones', label: 'Valuaciones', desc: 'Tasación ML por deal' },
          { href: '/analyses', label: 'Análisis', desc: 'Fix & Flip financiero' },
          { href: '/analytics', label: 'Analytics', desc: 'Estadísticas del mercado' },
        ].map(({ href, label, desc }) => (
          <Link key={href} href={href}
            className="flex flex-col gap-1 bg-white border border-gray-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-sm transition-all">
            <span className="text-sm font-semibold text-gray-800">{label}</span>
            <span className="text-xs text-gray-400">{desc}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
