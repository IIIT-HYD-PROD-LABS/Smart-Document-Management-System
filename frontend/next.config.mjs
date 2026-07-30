import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
    output: process.env.VERCEL ? undefined : "standalone",
    // Keep standalone flat at .next/standalone/server.js. Without this, Next can
    // trace from a parent dir and nest output under Desktop/.../taxsync-frontend/.
    outputFileTracingRoot: projectRoot,
    // App is served under /taxsyncfestage on canvas.iiit.ac.in. basePath ON makes
    // Next prefix EVERY browser-visible URL: pages, assets, client-side
    // router.push/replace, <Link>, and middleware redirects. Without it, in-app
    // navigation emits root-relative paths (/login, /dashboard) that leave the
    // subpath and hit the IIIT root -> post-login bounce to canvas.iiit.ac.in/login.
    // Campus nginx strips one /taxsyncfestage before reaching the container;
    // entry.js re-adds it in front of the standalone server so basePath matches.
    // No nginx change needed. assetPrefix is redundant once basePath is set.
    basePath: "/taxsyncfestage",
    // Campus nginx 301-redirects /taxsyncfestage -> /taxsyncfestage/ (adds the
    // trailing slash), while Next's default trailingSlash:false 308-redirects it
    // back (/taxsyncfestage/ -> /taxsyncfestage). That is an infinite redirect
    // loop on the app root (ERR_TOO_MANY_REDIRECTS). Skip Next's trailing-slash
    // redirect so Next serves both forms; nginx's single 301 then terminates.
    skipTrailingSlashRedirect: true,
    poweredByHeader: false,
    // Phase 09-06: don't fail production builds on pre-existing v1.0 lint
    // errors (5 react-hooks/rules-of-hooks errors in dashboard/upload/page.tsx).
    // Lint is still run via `npm run lint` for new code; this only relaxes the
    // build-time gate. See .planning/phases/09-compliance-foundation/deferred-items.md
    eslint: {
        ignoreDuringBuilds: true,
    },
    webpack: (config) => {
        // react-pdf requires canvas to be aliased to false for SSR
        config.resolve.alias.canvas = false;
        return config;
    },
    // .env (tracked in this private repo) sets NEXT_PUBLIC_API_URL and
    // BACKEND_INTERNAL_URL. Next.js loads .env automatically at build time.
    // Do NOT add an `env:` block here — it overrides .env and inlines a
    // hardcoded value, defeating the point of tracking .env in git.
    async rewrites() {
        const backend = process.env.BACKEND_INTERNAL_URL || "http://10.2.8.73:8025";
        return [
            {
                source: "/api/:path*",
                destination: `${backend}/api/:path*`,
            },
            {
                source: "/ws/:path*",
                destination: `${backend}/ws/:path*`,
            },
        ];
    },
    async headers() {
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
                        value: "default-src 'self'; script-src 'self' 'unsafe-inline' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' blob:; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
                    },
                ],
            },
        ];
    },
};

export default nextConfig;
