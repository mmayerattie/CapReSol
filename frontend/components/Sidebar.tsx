'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const links = [
  { href: '/deals', label: 'Deals' },
  { href: '/analyses', label: 'Análisis' },
]

export default function Sidebar() {
  const pathname = usePathname()
  return (
    <aside className="w-48 bg-white border-r border-gray-200 flex flex-col py-8 px-4 gap-2 shrink-0">
      <span className="font-bold text-lg mb-6 tracking-tight">CapReSol</span>
      {links.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
            pathname.startsWith(href)
              ? 'bg-blue-50 text-blue-700'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          {label}
        </Link>
      ))}
    </aside>
  )
}
