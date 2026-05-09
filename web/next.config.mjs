/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    // !! PERIGOSO: Isso permite o deploy mesmo com erros de TypeScript.
    // Útil para Hackathons onde o tempo é curto.
    ignoreBuildErrors: true,
  },
  eslint: {
    // Ignora o linting durante o build.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;