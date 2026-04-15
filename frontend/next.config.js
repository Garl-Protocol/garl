/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  skipTrailingSlashRedirect: true,
  async redirects() {
    return [
      { source: "/for_code", destination: "/for-code", permanent: true },
      { source: "/ai-code", destination: "/for-code", permanent: true },
      { source: "/code", destination: "/for-code", permanent: true },
    ];
  },
};

module.exports = nextConfig;
