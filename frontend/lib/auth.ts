const TOKEN_KEY = 'capresol_token'
const COOKIE_NAME = 'capresol_token'

function setCookie(value: string) {
  // 7 days, accessible by middleware (not httpOnly)
  document.cookie = `${COOKIE_NAME}=${value}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`
}

function clearCookie() {
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0`
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  setCookie(token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  clearCookie()
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

export async function login(username: string, password: string): Promise<void> {
  const backend = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/^http:\/\//, 'https://')
  const url = backend ? `${backend}/auth/login` : '/api/auth/login'
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as any)?.detail ?? 'Login failed')
  }
  const data = await res.json()
  setToken(data.access_token)
}

export function logout(): void {
  clearToken()
  window.location.href = '/login'
}
