/** @type {import('next').NextConfig} */
const BACKEND = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/^http:\/\//, 'https://')

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
