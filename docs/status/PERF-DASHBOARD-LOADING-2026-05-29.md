# Dashboard perceived performance pass (2026-05-29)

## Symptom

Opening a dashboard page felt slow and frequently showed a blank screen
before content appeared.

## Root cause (evidence based)

1. The backend talks to Supabase over the WARP tunnel
   (aws-1-ap-south-1.pooler.supabase.com). Even `/api/health` measured
   2.0s to 3.2s, so every page that fetches on mount blocks content for
   roughly 2s to 3s.
2. Most dashboard pages had no instant feedback during that wait:
   several returned a bare centered spinner on an otherwise empty area,
   a few rendered nothing (`return null` or an unguarded empty layout),
   and the App Router had zero `loading.tsx` boundaries.
3. The layout auth gate (`useAuth` silent token refresh) showed a lone
   centered spinner on a fully blank page during the 2s to 3s refresh
   that runs whenever the 30 minute access token has expired.
4. Only 2 of the high traffic sidebar routes warmed their data on
   hover; the rest paid a full cold round trip on every visit.

A 37 page audit classified each page (data fetch pattern, loading
state, blank risk). Three pages were high blank risk (analytics,
admin/users, admin/users/[id]); several more were medium.

## Changes

Instant feedback (no more blank content area):
- `analytics/page.tsx`: spinner replaced with a skeleton matching the
  real layout (header, four stat cards, trends chart, two up row).
- `compliance/calendar/page.tsx`: the month grid now renders shimmer
  pills while loading instead of a silent empty month.
- `admin/users/page.tsx`, `admin/users/[id]/page.tsx`,
  `documents/[id]/page.tsx`, `documents/[id]/preview/page.tsx`,
  `shared/page.tsx`, `admin/early-access/page.tsx`,
  `admin/model-evaluation/page.tsx`: full page spinners replaced with
  shape matched skeletons.
- `compliance/clients/[id]/page.tsx`: loading guard widened to
  `isLoading || !tenantReady` so a direct or stale store navigation no
  longer flashes the "could not load this client" error branch.
- `dashboard/loading.tsx` (new): route transition Suspense fallback for
  the whole dashboard subtree. Because the layout is force-dynamic, the
  App Router paints this the instant a link is clicked while the next
  segment streams.
- `layout.tsx` auth gate: the bare `isLoading` spinner is now an app
  shell skeleton (sidebar frame plus content skeleton) so a hard load or
  token refresh reads as "TaxSync is booting", not a blank page.

Lower actual wait (warm cache on intent):
- `layout.tsx` hover and focus prefetch extended from 2 routes to the
  main sidebar set: Analytics (`["docs","stats"]` and
  `["docs","trends",12]`), Notices dashboard
  (`["client-dashboard", activeClientId]`, guarded on a non null client),
  and Review queue (`["compliance-review-pending"]`). Each prefetch key
  and queryFn mirrors the destination page exactly so arrival is a cache
  hit, not a duplicate fetch. The existing 60s staleTime plus 5 min
  gcTime keep a revisit instant.

## Verification

- `tsc --noEmit`: clean.
- `next lint` on all changed files: clean.
- Production Docker build (`docker compose up -d --build frontend`):
  succeeded (this re runs typecheck and lint over the whole app).
- Visual (Playwright against the running production container):
  analytics skeleton, dashboard skeleton, calendar loaded grid, and the
  app shell skeleton (captured during a real silent token refresh) all
  render correctly with the sidebar intact. Session self recovered after
  the refresh.

## Not done

- documents/[id] and a few admin pages still fetch via useEffect rather
  than React Query, so they cannot be hover prefetched yet. Their blank
  screen is fixed (skeleton), but a future pass could migrate them to
  React Query for warm navigation.
- Nothing committed (awaiting explicit request).
