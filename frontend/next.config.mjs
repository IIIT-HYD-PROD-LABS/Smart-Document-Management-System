/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
    env: {
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    },
    images: {
        maximumDiskCacheSize: 50,  // MB — prevents unbounded cache growth (CVE-2026-27980)
    },
};

export default nextConfig;
