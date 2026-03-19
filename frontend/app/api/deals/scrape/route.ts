export const maxDuration = 300 // 5 minutes — overrides Next.js proxy timeout

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(request: Request) {
  const body = await request.json()
  const authHeader = request.headers.get('Authorization') ?? ''
  const res = await fetch(`${BACKEND}/deals/scrape`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(270_000), // 4.5 min controlled timeout
  })
  const data = await res.json()
  return Response.json(data, { status: res.status })
}
