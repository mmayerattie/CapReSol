/** @type {import('next').NextConfig} */
const _raw = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const BACKEND = _raw.includes('localhost') ? _raw : _raw.replace(/^http:\/\//, 'https://')

const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND}/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
