/** @type {import('next').NextConfig} */
if (process.env.VERCEL === "1" && !process.env.NEXT_PUBLIC_API_URL?.startsWith("https://")) {
  throw new Error("Set NEXT_PUBLIC_API_URL to the actual HTTPS Render backend URL before deploying to Vercel.");
}
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  serverRuntimeConfig: {},
  publicRuntimeConfig: {},
};

module.exports = nextConfig;
