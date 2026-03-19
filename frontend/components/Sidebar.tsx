'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { logout } from '@/lib/auth'

const links = [
  { href: '/',            label: 'Inicio',      exact: true },
  { href: '/deals',       label: 'Deals' },
  { href: '/valuaciones', label: 'Valuaciones' },
  { href: '/analyses',    label: 'Análisis' },
  { href: '/analytics',   label: 'Analytics' },
]

export default function Sidebar() {
  const pathname = usePathname()
  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname.startsWith(href)
  return (
    <aside className="w-48 bg-white border-r border-gray-200 flex flex-col py-8 px-4 gap-2 shrink-0">
      <span className="font-bold text-lg mb-6 tracking-tight">CapReSol</span>
      {links.map(({ href, label, exact }) => (
        <Link
          key={href}
          href={href}
          className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
            isActive(href, exact)
              ? 'bg-blue-50 text-blue-700'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          {label}
        </Link>
      ))}
      <div className="mt-auto">
        <button
          onClick={logout}
          className="w-full px-3 py-2 rounded-md text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 text-left transition-colors"
        >
          Cerrar sesión
        </button>
      </div>
    </aside>
  )
}
