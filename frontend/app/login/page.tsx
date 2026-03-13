'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const expected = process.env.NEXT_PUBLIC_AUTH_PASSWORD ?? 'capresolAdmin'
    if (password === expected) {
      document.cookie = 'capresolAuth=1; path=/; max-age=86400'
      router.push('/')
    } else {
      setError('Contraseña incorrecta')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-xl shadow-md p-10 w-full max-w-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-1 tracking-tight">CapReSol</h1>
        <p className="text-sm text-gray-400 mb-8">Acceso privado</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="password"
            placeholder="Contraseña"
            value={password}
            onChange={e => { setPassword(e.target.value); setError('') }}
            className="border border-gray-200 rounded-md px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            autoFocus
          />
          {error && (
            <p className="text-sm text-red-500">{error}</p>
          )}
          <button
            type="submit"
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-md text-sm transition-colors"
          >
            Entrar
          </button>
        </form>
      </div>
    </div>
  )
}
