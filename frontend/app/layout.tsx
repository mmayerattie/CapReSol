import type { Metadata } from 'next'
import '../styles/globals.css'
import Sidebar from '../components/Sidebar'

export const metadata: Metadata = { title: 'CapReSol' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-screen bg-gray-50 text-gray-900">
        <Sidebar />
        <main className="flex-1 overflow-auto p-8">{children}</main>
      </body>
    </html>
  )
}
