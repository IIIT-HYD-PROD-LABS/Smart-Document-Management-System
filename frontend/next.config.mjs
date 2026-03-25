/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
    poweredByHeader: false,
    env: {
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    },
    async headers() {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        return [
            {
                source: "/(.*)",
                headers: [
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "X-Frame-Options", value: "DENY" },
                    { key: "X-XSS-Protection", value: "0" },
                    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                    { key: "X-DNS-Prefetch-Control", value: "on" },
                    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
                    { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
                    {
                        key: "Content-Security-Policy",
                        value: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' ${apiUrl}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`,
                    },
                ],
            },
        ];
    },
};

export default nextConfig;
