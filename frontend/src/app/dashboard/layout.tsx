"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
    QueryClient,
    QueryClientProvider,
    useQuery,
} from "@tanstack/react-query";
import { LoadingSpinner } from "@/components";
import { ThemeToggle } from "@/components/ThemeToggle";
import AIChatFloating from "@/components/AIChatFloating";
import { useCurrentClient } from "@/stores/currentClientStore";
import { complianceApi } from "@/lib/api/compliance";
import type { ClientDetail } from "@/types/compliance";
import {
    FiHome,
    FiUpload,
    FiSearch,
    FiBarChart2,
    FiLogOut,
    FiFileText,
    FiShield,
    FiShare2,
    FiMenu,
    FiX,
    FiBriefcase,
    FiUserCheck,
    FiCalendar,
    FiActivity,
    FiBookOpen,
    FiMail,
    FiSettings,
    FiInbox,
    FiClipboard,
    FiGlobe,
    FiCpu,
    FiUser,
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

// Single-tenant deployment model: each customer gets their own deployment
// with their own org, so cross-client navigation (Clients list,
// Cross-entity search) is intentionally not surfaced in the sidebar.
// Routes still exist for direct admin access; the multi-tenant RLS
// machinery underneath stays intact.
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
    {
        label: "Profile",
        items: [
            { href: "/dashboard/profile", icon: FiUser, label: "Account", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/email", icon: FiMail, label: "Email center", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/settings/ai", icon: FiCpu, label: "AI assistant", roles: ["admin", "editor", "viewer"] },
        ],
    },
    {
        label: "Admin",
        items: [
            { href: "/dashboard/admin", icon: FiShield, label: "Admin", roles: ["admin"] },
            { href: "/dashboard/compliance/clients", icon: FiBriefcase, label: "Clients", roles: ["admin"] },
            { href: "/dashboard/model-evaluation", icon: FiBarChart2, label: "Model eval", roles: ["admin"] },
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
                        staleTime: 30_000,
                        refetchOnWindowFocus: false,
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

    // Close sidebar on route change (mobile)
    useEffect(() => {
        setSidebarOpen(false);
    }, [pathname]);

    if (isLoading) {
        return (
            <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center">
                <LoadingSpinner />
            </div>
        );
    }

    if (!user) {
        return null;
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

                {/* User + Sign-out + subtle "Powered by TaxSync".
                 * Active client identity moved to the top brand block;
                 * this footer is just the human + the platform mark. */}
                <div className="border-t border-[var(--border-default)] p-3">
                    <div className="flex items-center gap-2.5 px-2 py-2 mb-1 rounded-md hover:bg-[var(--bg-hover)] transition-colors">
                        <div className="w-8 h-8 rounded-full bg-[var(--accent)] flex items-center justify-center text-[12px] font-semibold text-white shrink-0 shadow-sm">
                            {user.username?.[0]?.toUpperCase() || "U"}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-[13px] font-medium text-[var(--text-primary)] truncate">
                                {user.username}
                            </p>
                            <div className="flex items-center gap-1.5 text-[11.5px] text-[var(--text-subtle)]">
                                <span className="truncate">{user.email}</span>
                            </div>
                        </div>
                        {user.role && (
                            <span className="microtype shrink-0 px-1.5 py-0.5 rounded bg-[var(--bg-hover)] border border-[var(--border-default)] text-[var(--text-muted)]">
                                {user.role}
                            </span>
                        )}
                    </div>
                    <button
                        onClick={async () => {
                            await logout();
                            router.push("/login");
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-[13px] text-[var(--text-muted)] hover:text-[var(--danger)] rounded-md hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
                    >
                        <FiLogOut className="w-3.5 h-3.5" />
                        Sign out
                    </button>
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

            <main className="flex-1 md:ml-60 ml-0 mt-14 md:mt-0">
                {/* Desktop topbar — theme toggle lives here */}
                <div className="hidden md:flex sticky top-0 z-30 h-14 px-6 lg:px-10 items-center justify-end gap-3 border-b border-[var(--border-default)] bg-[var(--bg-page)]/85 backdrop-blur">
                    <ThemeToggle />
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
