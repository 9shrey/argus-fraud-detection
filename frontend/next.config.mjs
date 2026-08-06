/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Next's dev server otherwise blocks HMR/static-asset requests when the
  // page is loaded via 127.0.0.1 instead of localhost (a same-origin check
  // added in Next 15+) — both are common ways to reach a local dev server.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
