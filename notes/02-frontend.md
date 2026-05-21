# 02 · FRONTEND

> Next.js 15 App Router · React 19 · TypeScript · Tailwind · TanStack Query · Zustand

## ★ Remember
- Server-first (RSC) — opt into client with `"use client"`
- App Router only (no Pages Router)
- Server state ≠ Client state — pick the right tool
- Cookies (`js-cookie`) for auth, NOT `localStorage`
- Standalone output for Docker image

---

## 1. Stack snapshot

| What             | Tool                       |
|------------------|-----------------------------|
| Framework        | Next.js 15.5                |
| UI lib           | React 19                    |
| Lang             | TypeScript 5.5              |
| Styles           | Tailwind 3.4 + globals.css  |
| Server state     | TanStack Query v5           |
| Client state     | Zustand 5                   |
| Forms            | react-hook-form + Zod       |
| HTTP             | Axios (with interceptors)   |
| Date picker      | react-day-picker v9         |
| Tables           | TanStack Table v8           |
| Charts           | recharts                    |
| Drag/drop upload | react-dropzone              |
| Animation        | framer-motion               |
| Toasts           | react-hot-toast             |

---

## 2. Route tree

```
src/app/
├ page.tsx              landing
├ login/
├ register/
├ oauth/                callback page
├ oauth-setup/          diag page
└ dashboard/
   ├ layout.tsx         auth gate + QueryClient provider
   ├ page.tsx           dashboard home
   ├ documents/         hub: Upload / Shared / Search
   ├ upload/
   ├ shared/
   ├ search/
   ├ analytics/
   ├ profile/
   ├ admin/             RBAC: admin only
   ├ model-evaluation/
   ├ email/             Gmail MCP — bills / connect / activity / settings
   ├ settings/ai/       BYOK config
   └ compliance/
      ├ clients/
      ├ notices/
      ├ reports/
      ├ calendar/
      ├ review/
      ├ search/
      └ audit/
```

---

## 3. Rendering modes

- **Server Component (RSC)** is the default — fetches data on Node, ships HTML
- `"use client"` is required for components using hooks, state, or browser APIs
- `export const dynamic = "force-dynamic"` is set on `dashboard/layout.tsx` — auth-gated pages can never be statically generated
- `middleware.ts` runs at the edge: cookie check redirects unauth users to `/login` and authed users away from `/login` and `/register`
- Standalone build → small Docker image for self-hosted prod

---

## 4. State management — server vs client

```
SERVER state  ──►  TanStack Query
  caches HTTP responses, dedupes, refetches
  • queryKey = ['documents', filters]
  • staleTime + gcTime per resource
  • invalidate on mutation

CLIENT state  ──►  Zustand stores
  currentClientStore       active tenant ID
  onboardingWizardStore    wizard step + draft
  (no Redux — Zustand is ~1 KB, no Provider)
```

**Rule of thumb:** if the value comes from the API, it lives in TanStack Query. If it's UI/local (selection, wizard step, modal open), it lives in Zustand or `useState`.

---

## 5. Auth flow (client side)

```
1. User submits /login    → POST /api/auth/login
2. Backend returns        → { access_token, refresh_token, user }
3. Frontend writes BOTH to js-cookie
4. middleware.ts sees cookie → allows /dashboard/*
5. Axios interceptor injects Authorization: Bearer <jwt>
6. On 401 → POST /api/auth/refresh (rotation + reuse-detect)
7. Logout → POST /api/auth/logout + clear cookies
```

OAuth path:
- Click "Sign in with Google"
- `GET /api/auth/oauth/google` returns provider URL + state JWT
- Provider redirect → backend `/callback/google`
- Backend redirects → `/oauth/callback?code=XYZ&token=JWT`
- Frontend exchanges → `POST /api/auth/oauth/exchange` (one-shot, replay-protected)

---

## 6. Sidebar IA (v2.1.1)

Reset 2026-05-09 from 19 → 14 items. Documents became a **hub**.

- Dashboard
- **Documents** (Upload · Shared · Search)
- Analytics
- Compliance ▾ (Clients · Notices · Reports · Calendar · Review · Audit · Search)
- Vendor invoices *(renamed from Bills)*
- AI assistant *(BYOK)*
- Email *(Gmail MCP)*
- Model evaluation
- Admin *(admin only)*
- Profile cluster (avatar)
- Co-brand cluster *(tenant logo)*

---

## 7. Component map

```
components/
├ admin/              DeleteUserModal
├ compliance/         23 files: NoticeTable, StatusWorkflow,
│                     ApprovalStageStrip, NotificationBell,
│                     RiskTierDot, WhyThisRiskScore, BulkActionBar,
│                     OnboardingWizard, NoticeAISection, …
├ email/              Gmail viewer panels
├ landing/            Hero, Navbar, ProcessFlow, Footer, DemoWorkspace
├ AIChatFloating.tsx  global AI panel
├ CategoryBadge.tsx
├ StatusBadge.tsx
├ ThemeToggle.tsx
├ UserMenu.tsx
└ ConfidenceBadge.tsx
```

---

## 8. Hooks & API layer

```
src/lib/
├ api.ts            axios instance + interceptors
├ email-api.ts      Gmail endpoints
└ api/
   ├ ai.ts          BYOK AI calls
   └ compliance.ts  clients · notices · reports

src/hooks/
└ useNotificationStream.ts   WebSocket /ws/notifications
                              auto-reconnect w/ exponential backoff
```

- Single Axios instance
- Interceptor attaches JWT, handles 401 by calling refresh, redirects on hard fail
- WebSocket hook auto-reconnects with exponential backoff

---

## 9. Styling system

- Tailwind 3.4 (JIT compile)
- `tailwind.config.ts` defines tokens (colors, fonts, breakpoints)
- `globals.css` for CSS variables + base resets
- Dark mode via `ThemeToggle.tsx` (Tailwind class strategy)
- Custom utility classes co-located with components
- `framer-motion` for page transitions and drawer slide-ins

---

## 10. Key patterns

| Pattern | Where / Why |
|---------|-------------|
| `QueryClient` hoisted to `dashboard/layout.tsx` | Sidebar uses `useQuery` → needs a provider above it |
| Shared `queryKey` across sidebar + dashboard | Dedupes the active-client query — perf fix v2.1.1 |
| Optimistic UI on status changes | NoticeTable updates instantly; reverts on failure |
| Suspense boundaries around fetches | Lets RSC stream while client islands hydrate |
| Zod schema mirrors backend Pydantic | Catches contract drift at compile time |
| Conditional sidebar items by role | Admin · compliance roles see different nav |

---

## 11. Gotchas / fixes shipped

- **SSG break on auth pages** — `export const dynamic = "force-dynamic"` on `dashboard/layout.tsx`
- **QueryClientProvider missing for sidebar** — hoisted from `compliance/layout` to `dashboard/layout`
- **Tenant listener round-trips** — batched 3 `set_config` calls into one SQL + dirty-bit cleanup skip → ~2× `/api/health`
- **Active-client double-fetch** — shared queryKey across sidebar + dashboard
- **OAuth replay** — exchange code is single-use, tracked in Redis (in-memory fallback if Redis down)

---

> "Server Components are the default. You opt into the client. Not the other way around."
