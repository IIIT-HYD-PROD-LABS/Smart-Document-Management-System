"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
    QueryClient,
    QueryClientProvider,
    useQuery,
    useQueryClient,
} from "@tanstack/react-query";
import { LoadingSpinner, Skeleton } from "@/components";
import { documentsApi } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import AIChatFloating from "@/components/AIChatFloating";
import { UserMenu } from "@/components/UserMenu";
import { ClientSwitcher } from "@/components/compliance/ClientSwitcher";
import { useCurrentClient } from "@/stores/currentClientStore";
import { complianceApi } from "@/lib/api/compliance";
import type { ClientDetail } from "@/types/compliance";
import {
    FiHome,
    FiBarChart2,
    FiFileText,
    FiShield,
    FiMenu,
    FiX,
    FiUserCheck,
    FiCalendar,
    FiActivity,
    FiGlobe,
} from "react-icons/fi";

/**
 * Compliance Noir sidebar — refined.
 *
 * Nav grouped into 4 sections with microtype dividers so a CA scanning
 * the rail has a visual hierarchy that matches her mental model.
 *
 * Active item gets a 2px brand-blue accent bar on the left edge plus a
 * subtle background tint. Hover is colour-only, no layout shift.
 */
type NavItem = {
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    roles: string[];
};

type NavGroup = {
    label: string;
    items: NavItem[];
};

// Phase 17 sidebar IA: only daily-use task navigation lives in the
// sidebar. Profile (Account, Email center, AI assistant) and Admin
// (Admin panel, Organizations, Model eval) live in the UserMenu popover
// off the user cluster at the bottom of the sidebar -- one click away
// without cluttering the daily nav.
const NAV_GROUPS: NavGroup[] = [
    {
        label: "Core",
        items: [
            { href: "/dashboard", icon: FiHome, label: "Overview", roles: ["admin", "editor", "viewer"] },
        ],
    },
    {
        label: "Workspace",
        items: [
            // Documents page exposes Upload / Shared / Search as inline
            // action buttons so the four document workflows live on one page.
            { href: "/dashboard/documents", icon: FiFileText, label: "Documents", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/analytics", icon: FiBarChart2, label: "Analytics", roles: ["admin", "editor", "viewer"] },
        ],
    },
    {
        label: "Compliance",
        items: [
            { href: "/dashboard/compliance", icon: FiShield, label: "Notices", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/compliance/review", icon: FiUserCheck, label: "Review queue", roles: ["admin", "editor"] },
            { href: "/dashboard/compliance/calendar", icon: FiCalendar, label: "Calendar", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/compliance/audit", icon: FiActivity, label: "Audit log", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/compliance/reports", icon: FiBarChart2, label: "Reports", roles: ["admin", "editor", "viewer"] },
        ],
    },
];

// Dashboard pages are all auth-gated (redirect to /login on unauthenticated
// access). They have no business being statically prerendered — the Phase 16
// useQuery in the co-brand sidebar would crash at build time. force-dynamic
// is the cheapest correct knob; cascades to every nested dashboard route.
export const dynamic = "force-dynamic";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    // One QueryClient for the entire dashboard tree — covers the sidebar
    // active-client fetch, the AI credential lookup, every notice/invoice
    // detail query. Compliance pages inside used to mount their own client;
    // that's now redundant but kept for backwards-compat without breakage.
    const [queryClient] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        // Bumped 30s → 60s: the data source is a remote
                        // Supabase pooler reached over the WARP tunnel, so
                        // each refetch costs ~0.7–3s. A longer stale window
                        // makes a revisit inside 60s render cached data
                        // instantly instead of re-spinning.
                        staleTime: 60_000,
                        // Keep results in cache for 5 min after a query goes
                        // unused so back/forward navigation between dashboard
                        // pages restores instantly rather than refetching.
                        gcTime: 300_000,
                        // NOTE: deliberately NOT setting placeholderData:
                        // keepPreviousData globally. The always-mounted
                        // ["client", activeClientId] query re-keys in place on
                        // a client switch; keepPreviousData would then render
                        // the PREVIOUS tenant's name/logo (and a deep-link to
                        // it) for the whole refetch window — a multi-tenant
                        // identity-confusion bug. Scope keepPreviousData to a
                        // specific paginated query if one ever needs it.
                        refetchOnWindowFocus: false,
                        refetchOnReconnect: true,
                        retry: 1,
                    },
                },
            }),
    );

    return (
        <QueryClientProvider client={queryClient}>
            <DashboardLayoutInner>{children}</DashboardLayoutInner>
        </QueryClientProvider>
    );
}

function DashboardLayoutInner({ children }: { children: React.ReactNode }) {
    const { user, isLoading, logout } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const [sidebarOpen, setSidebarOpen] = useState(false);

    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const crossClientMode = useCurrentClient((s) => s.crossClientMode);
    const setActiveClientId = useCurrentClient((s) => s.setActiveClientId);
    const queryClient = useQueryClient();

    // Bootstrap active organization for the whole dashboard (not only email /
    // compliance). Without this, pages that send X-Client-Id stay blank until
    // the user opens Compliance first.
    useEffect(() => {
        if (!user || activeClientId !== null || crossClientMode) return;
        let cancelled = false;
        complianceApi
            .listMyMemberships()
            .then((r) => {
                if (cancelled) return;
                const first = r.data?.[0];
                if (first?.client_id) setActiveClientId(first.client_id);
            })
            .catch(() => {
                /* membership bootstrap is best-effort */
            });
        return () => {
            cancelled = true;
        };
    }, [user, activeClientId, crossClientMode, setActiveClientId]);

    // Data prefetch on link hover/focus. <Link> already prefetches the route
    // JS+RSC, but the page's data is what costs ~1s against the remote DB.
    // Warming the React Query cache on intent (hover/focus, before the click)
    // makes these high-traffic destinations render instantly on arrival.
    // Keyed to the same queryKey + queryFn the destination page uses, so the
    // click is a cache hit, not a duplicate fetch.
    const prefetchByHref: Record<string, () => void> = {
        "/dashboard": () =>
            void queryClient.prefetchQuery({
                queryKey: ["dashboard", "stats"],
                queryFn: () => documentsApi.getStats().then((r) => r.data),
            }),
        "/dashboard/documents": () =>
            void queryClient.prefetchQuery({
                queryKey: ["documents", "all"],
                // Must mirror DocumentsPage's queryFn exactly (same key +
                // same result shape) so the click is a cache hit, not a
                // shape mismatch.
                queryFn: () =>
                    documentsApi.getAll().then((r) => r.data.documents ?? []),
            }),
        "/dashboard/analytics": () => {
            // AnalyticsPage fires two queries; warm both. Keys + queryFns
            // mirror analytics/page.tsx exactly so arrival is a cache hit.
            void queryClient.prefetchQuery({
                queryKey: ["docs", "stats"],
                queryFn: () => documentsApi.getStats().then((r) => r.data),
            });
            void queryClient.prefetchQuery({
                queryKey: ["docs", "trends", 12],
                queryFn: () => documentsApi.getTrends(12).then((r) => r.data),
            });
        },
        "/dashboard/compliance": () => {
            // Notices dashboard is scoped to the active client. Mirror the
            // page's enabled:(activeClientId !== null) guard so we never fire
            // the null-client fetch the page itself skips.
            if (activeClientId === null) return;
            void queryClient.prefetchQuery({
                queryKey: ["client-dashboard", activeClientId],
                queryFn: () =>
                    complianceApi
                        .getClientDashboard(activeClientId)
                        .then((r) => r.data),
            });
        },
        "/dashboard/compliance/review": () =>
            void queryClient.prefetchQuery({
                queryKey: ["compliance-review-pending"],
                queryFn: () =>
                    complianceApi.listPendingReview(1, 200).then((r) => r.data),
            }),
    };

    // Co-brand cluster: fetch the active client's name + logo so the
    // sidebar can render its identity. Stays empty until a client is
    // picked; cross-client mode skips the fetch and shows an "All
    // clients" pill instead.
    const { data: activeClient } = useQuery<ClientDetail>({
        // Shared queryKey with ClientSwitcher and the clients/[id] route so
        // React Query dedups — was emitting two GET /api/compliance/clients/{id}
        // per page render before this alignment.
        queryKey: ["client", activeClientId],
        queryFn: () =>
            complianceApi.getClient(activeClientId as number).then((r) => r.data),
        enabled:
            Boolean(activeClientId) && !crossClientMode && !!user,
        staleTime: 60_000,
    });

    useEffect(() => {
        if (!isLoading && !user) router.push("/login");
    }, [user, isLoading, router]);

    // Soft-logout on expired-session event from the axios interceptor.
    // Replaces a hard window.location reload so the React tree, query
    // cache, and theme state survive the redirect.
    useEffect(() => {
        const handler = () => router.push("/login");
        window.addEventListener("auth:session-expired", handler);
        return () => window.removeEventListener("auth:session-expired", handler);
    }, [router]);

    // Close sidebar on route change (mobile)
    useEffect(() => {
        setSidebarOpen(false);
    }, [pathname]);

    if (isLoading) {
        // App-shell skeleton, not a lonely centered spinner. On a hard load
        // (refresh / direct URL / post-login) the session check costs ~2-3s
        // against the remote backend; showing the sidebar frame + a content
        // skeleton reads as "TaxSync is booting", not a blank page. Mirrors
        // the real <aside w-60> + <main md:ml-60> chrome below.
        return (
            <div
                className="min-h-screen bg-[var(--bg-page)] flex"
                role="status"
                aria-busy="true"
                aria-live="polite"
            >
                <span className="sr-only">Loading TaxSync</span>
                <aside className="hidden md:flex w-60 fixed left-0 top-0 h-full bg-[var(--bg-surface)] border-r border-[var(--border-default)] flex-col z-50">
                    <div className="h-16 px-4 flex items-center gap-3 border-b border-[var(--border-default)]">
                        <Skeleton className="w-8 h-8 rounded-md" />
                        <div className="flex-1">
                            <Skeleton className="h-3 w-24" />
                            <Skeleton className="h-2 w-16 mt-2" />
                        </div>
                    </div>
                    <div className="flex-1 px-3 py-4 space-y-6">
                        {[3, 2, 4].map((n, gi) => (
                            <div key={gi} className="space-y-2">
                                <Skeleton className="h-2 w-16 ml-2 mb-1" />
                                {Array.from({ length: n }).map((_, i) => (
                                    <Skeleton key={i} className="h-8 w-full rounded-md" />
                                ))}
                            </div>
                        ))}
                    </div>
                    <div className="px-3 py-4 border-t border-[var(--border-default)]">
                        <Skeleton className="h-10 w-full rounded-md" />
                    </div>
                </aside>
                <main className="flex-1 min-w-0 md:ml-60 mt-14 md:mt-0">
                    <div className="hidden md:flex h-14 px-6 lg:px-10 items-center justify-end border-b border-[var(--border-default)]">
                        <Skeleton className="h-8 w-20 rounded-md" />
                    </div>
                    <div className="p-6 md:p-10">
                        <div className="max-w-7xl mx-auto space-y-8">
                            <div>
                                <Skeleton className="h-3 w-44" />
                                <Skeleton className="h-8 w-72 mt-3" />
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                {Array.from({ length: 4 }).map((_, i) => (
                                    <Skeleton key={i} className="h-[140px]" />
                                ))}
                            </div>
                            <Skeleton className="h-72 w-full" />
                        </div>
                    </div>
                </main>
            </div>
        );
    }

    if (!user) {
        // Session resolved to "no user" (expired/cleared). The redirect to
        // /login fires from the effect above; render a spinner in the meantime
        // instead of a blank white screen during that hand-off.
        return (
            <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center">
                <LoadingSpinner />
            </div>
        );
    }

    const role = user.role || "viewer";

    /** Pixel-perfect active state — exact match for index pages,
     *  startsWith with separator for nested. Avoids /dashboard
     *  staying highlighted when the user is on /dashboard/upload. */
    const isItemActive = (href: string): boolean => {
        if (pathname === href) return true;
        if (href === "/dashboard") return false;
        return pathname.startsWith(href + "/");
    };

    return (
        <div className="min-h-screen bg-[var(--bg-page)] flex">
            {/* Mobile top bar */}
            <div className="fixed top-0 left-0 right-0 h-14 bg-[var(--bg-page)]/95 backdrop-blur border-b border-[var(--border-default)] flex items-center px-4 z-50 md:hidden">
                <button
                    onClick={() => setSidebarOpen(true)}
                    className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 cursor-pointer"
                    aria-label="Open menu"
                >
                    <FiMenu className="w-5 h-5" />
                </button>
                <span className="ml-3 text-sm font-semibold text-[var(--text-primary)] tracking-tight">
                    TaxSync
                </span>
                <div className="ml-auto">
                    <ThemeToggle />
                </div>
            </div>

            {/* Mobile backdrop */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 bg-[var(--text-primary)]/40 backdrop-blur-sm z-40 md:hidden"
                    onClick={() => setSidebarOpen(false)}
                    aria-hidden
                />
            )}

            {/* Sidebar */}
            <aside
                className={`
                    w-60 fixed left-0 top-0 h-full
                    bg-[var(--bg-surface)] border-r border-[var(--border-default)]
                    flex flex-col z-50
                    transition-transform duration-200 ease-in-out
                    ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
                    md:translate-x-0
                `}
            >
                {/* Brand — TaxSync is enterprise; the tenant company's
                 * identity sits at the top of the sidebar. TaxSync moves
                 * to a subtle "Powered by" treatment near the user
                 * cluster (see bottom of this file). */}
                <div className="px-4 h-14 flex items-center justify-between border-b border-[var(--border-default)] gap-2">
                    {crossClientMode ? (
                        <div className="flex items-center gap-2 min-w-0">
                            <span className="w-8 h-8 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0">
                                <FiGlobe className="w-4 h-4 text-[var(--accent)]" />
                            </span>
                            <div className="min-w-0">
                                <p className="text-[13.5px] font-semibold text-[var(--text-primary)] tracking-tight truncate">
                                    All clients
                                </p>
                                <p className="text-[10.5px] text-[var(--text-subtle)] truncate">
                                    Cross-client mode
                                </p>
                            </div>
                        </div>
                    ) : activeClient ? (
                        <Link
                            href={`/dashboard/compliance/clients/${activeClient.id}`}
                            className="flex items-center gap-2 min-w-0 group"
                            aria-label={`Open ${activeClient.name} branding`}
                        >
                            {activeClient.logo_url ? (
                                <span className="w-8 h-8 rounded-md bg-white border border-[var(--border-default)] flex items-center justify-center overflow-hidden shrink-0">
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img
                                        src={activeClient.logo_url}
                                        alt=""
                                        className="max-w-full max-h-full object-contain p-0.5"
                                    />
                                </span>
                            ) : (
                                <span className="w-8 h-8 rounded-md bg-[var(--accent)] flex items-center justify-center text-[12px] font-semibold text-white shrink-0 shadow-sm">
                                    {activeClient.name?.[0]?.toUpperCase() || "C"}
                                </span>
                            )}
                            <div className="min-w-0">
                                <p className="text-[13.5px] font-semibold text-[var(--text-primary)] tracking-tight truncate group-hover:text-[var(--accent)] transition-colors">
                                    {activeClient.name}
                                </p>
                                {activeClient.industry && (
                                    <p className="text-[10.5px] text-[var(--text-subtle)] truncate">
                                        {activeClient.industry}
                                    </p>
                                )}
                            </div>
                        </Link>
                    ) : (
                        <Link
                            href="/dashboard"
                            className="flex items-center gap-2 min-w-0"
                            aria-label="TaxSync home"
                        >
                            <span className="w-8 h-8 rounded-md bg-[var(--accent)] flex items-center justify-center shadow-sm shrink-0">
                                <span className="font-mono text-[13px] font-semibold text-white">
                                    Tx
                                </span>
                            </span>
                            <span className="text-[14px] font-semibold text-[var(--text-primary)] tracking-tight truncate">
                                TaxSync
                            </span>
                        </Link>
                    )}
                    <button
                        onClick={() => setSidebarOpen(false)}
                        className="text-[var(--text-subtle)] hover:text-[var(--text-primary)] md:hidden cursor-pointer shrink-0"
                        aria-label="Close menu"
                    >
                        <FiX className="w-4 h-4" />
                    </button>
                </div>

                {/* Nav (scrollable when long) */}
                <nav className="flex-1 px-3 py-4 overflow-y-auto">
                    {NAV_GROUPS.map((group, gi) => {
                        const groupItems = group.items.filter((it) =>
                            it.roles.includes(role)
                        );
                        if (groupItems.length === 0) return null;

                        return (
                            <div key={group.label} className={gi === 0 ? "" : "mt-5"}>
                                <h2 className="microtype px-3 mb-1.5">{group.label}</h2>
                                <ul className="space-y-0.5">
                                    {groupItems.map((item) => {
                                        const isActive = isItemActive(item.href);
                                        const Icon = item.icon;
                                        return (
                                            <li key={item.href}>
                                                <Link
                                                    href={item.href}
                                                    onMouseEnter={prefetchByHref[item.href]}
                                                    onFocus={prefetchByHref[item.href]}
                                                    className={`
                                                        relative flex items-center gap-2.5 px-3 py-2 rounded-md
                                                        text-[13.5px] cursor-pointer
                                                        transition-colors duration-150
                                                        ${
                                                            isActive
                                                                ? "bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
                                                                : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                                                        }
                                                    `}
                                                >
                                                    {isActive && (
                                                        <span
                                                            className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-r bg-[var(--accent)]"
                                                            aria-hidden
                                                        />
                                                    )}
                                                    <Icon className="w-4 h-4 shrink-0" />
                                                    <span className="truncate">{item.label}</span>
                                                </Link>
                                            </li>
                                        );
                                    })}
                                </ul>
                            </div>
                        );
                    })}
                </nav>

                {/* User cluster — click to open the account popover with
                 * Profile (Account, Email, AI) and Admin (when role
                 * permits). Sign out lives in the popover too. */}
                <div className="border-t border-[var(--border-default)] p-3">
                    <UserMenu
                        user={user}
                        organizationHref={
                            activeClientId
                                ? `/dashboard/compliance/clients/${activeClientId}`
                                : "/dashboard/compliance/clients"
                        }
                        onSignOut={async () => {
                            await logout();
                            router.push("/login");
                        }}
                    />
                    <Link
                        href="/dashboard"
                        className="
                            mt-2 flex items-center gap-1.5 px-3 py-1.5
                            text-[10.5px] text-[var(--text-subtle)]
                            hover:text-[var(--text-muted)]
                            transition-colors duration-150 cursor-pointer
                            border-t border-[var(--border-subtle)] pt-2
                        "
                        aria-label="TaxSync home"
                    >
                        <span className="w-3.5 h-3.5 rounded-sm bg-[var(--accent-soft)] flex items-center justify-center shrink-0">
                            <span className="font-mono text-[8px] font-semibold text-[var(--accent)]">
                                Tx
                            </span>
                        </span>
                        <span>Powered by TaxSync</span>
                    </Link>
                </div>
            </aside>

            <main className="flex-1 min-w-0 md:ml-60 ml-0 mt-14 md:mt-0">
                {/* Desktop topbar — org switcher + theme. ClientSwitcher was
                    previously only on /compliance/**, so "Your organization"
                    looked broken everywhere else. */}
                <div className="hidden md:flex sticky top-0 z-30 h-14 px-6 lg:px-10 items-center justify-end gap-3 border-b border-[var(--border-default)] bg-[var(--bg-page)]/85 backdrop-blur">
                    <ClientSwitcher />
                    <ThemeToggle />
                </div>
                {/* Mobile: org pill under the top bar so it stays reachable. */}
                <div className="md:hidden sticky top-14 z-20 flex items-center justify-end gap-2 px-4 py-2 border-b border-[var(--border-default)] bg-[var(--bg-page)]/90 backdrop-blur">
                    <ClientSwitcher />
                </div>
                <div className="p-6 md:p-10">
                    <div className="max-w-7xl mx-auto">{children}</div>
                </div>
            </main>

            {/* Floating Ask AI — persists across every dashboard route. */}
            <AIChatFloating />
        </div>
    );
}
