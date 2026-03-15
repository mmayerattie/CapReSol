export const maxDuration = 300 // 5 minutes — overrides Next.js proxy timeout

export async function POST(request: Request) {
  const body = await request.json()
  const res = await fetch('http://localhost:8000/deals/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(270_000), // 4.5 min controlled timeout
  })
  const data = await res.json()
  return Response.json(data, { status: res.status })
}
