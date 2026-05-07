"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { LoadingSpinner } from "@/components";
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
    FiCreditCard,
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

const NAV_GROUPS: NavGroup[] = [
    {
        label: "Core",
        items: [
            { href: "/dashboard", icon: FiHome, label: "Overview", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/search", icon: FiSearch, label: "Search", roles: ["admin", "editor", "viewer"] },
        ],
    },
    {
        label: "Documents",
        items: [
            { href: "/dashboard/upload", icon: FiUpload, label: "Upload", roles: ["admin", "editor"] },
            { href: "/dashboard/documents", icon: FiFileText, label: "Documents", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/shared", icon: FiShare2, label: "Shared", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/analytics", icon: FiBarChart2, label: "Analytics", roles: ["admin", "editor", "viewer"] },
        ],
    },
    {
        label: "Email",
        items: [
            { href: "/dashboard/email/connect", icon: FiMail, label: "Connect", roles: ["admin", "editor"] },
            { href: "/dashboard/email/settings", icon: FiSettings, label: "Settings", roles: ["admin", "editor"] },
            { href: "/dashboard/email/activity", icon: FiInbox, label: "Activity", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/email/bills", icon: FiCreditCard, label: "Bills", roles: ["admin", "editor", "viewer"] },
        ],
    },
    {
        label: "Compliance",
        items: [
            { href: "/dashboard/compliance", icon: FiShield, label: "Notices", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/compliance/clients", icon: FiBriefcase, label: "Clients", roles: ["admin", "editor"] },
            { href: "/dashboard/compliance/review", icon: FiUserCheck, label: "Review queue", roles: ["admin", "editor"] },
            { href: "/dashboard/compliance/calendar", icon: FiCalendar, label: "Calendar", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/compliance/search", icon: FiBookOpen, label: "Cross-entity", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/compliance/audit", icon: FiActivity, label: "Audit log", roles: ["admin", "editor", "viewer"] },
            { href: "/dashboard/compliance/reports", icon: FiBarChart2, label: "Reports", roles: ["admin", "editor", "viewer"] },
        ],
    },
    {
        label: "Admin",
        items: [
            { href: "/dashboard/admin", icon: FiShield, label: "Admin", roles: ["admin"] },
            { href: "/dashboard/model-evaluation", icon: FiBarChart2, label: "Model eval", roles: ["admin"] },
        ],
    },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const { user, isLoading, logout } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const [sidebarOpen, setSidebarOpen] = useState(false);

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
                    className="text-[var(--text-muted)] hover:text-white p-1 cursor-pointer"
                    aria-label="Open menu"
                >
                    <FiMenu className="w-5 h-5" />
                </button>
                <span className="ml-3 text-sm font-semibold text-white tracking-tight">
                    TaxSync
                </span>
            </div>

            {/* Mobile backdrop */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 bg-black/60 z-40 md:hidden"
                    onClick={() => setSidebarOpen(false)}
                    aria-hidden
                />
            )}

            {/* Sidebar */}
            <aside
                className={`
                    w-60 fixed left-0 top-0 h-full
                    bg-[var(--bg-page)] border-r border-[var(--border-default)]
                    flex flex-col z-50
                    transition-transform duration-200 ease-in-out
                    ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
                    md:translate-x-0
                `}
            >
                {/* Brand */}
                <div className="px-5 h-14 flex items-center justify-between border-b border-[var(--border-default)]">
                    <Link
                        href="/dashboard"
                        className="flex items-center gap-2 group"
                        aria-label="TaxSync home"
                    >
                        <span className="w-6 h-6 rounded-md bg-[var(--accent-soft)] border border-[var(--accent-edge)] flex items-center justify-center">
                            <span className="font-mono text-[11px] font-semibold text-[var(--accent)]">
                                Tx
                            </span>
                        </span>
                        <span className="text-[13px] font-semibold text-white tracking-tight group-hover:text-[var(--text-primary)]">
                            TaxSync
                        </span>
                    </Link>
                    <button
                        onClick={() => setSidebarOpen(false)}
                        className="text-[var(--text-subtle)] hover:text-white md:hidden cursor-pointer"
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
                                                        relative flex items-center gap-2.5 px-3 py-1.5 rounded-md
                                                        text-[13px] cursor-pointer
                                                        transition-colors duration-150
                                                        ${
                                                            isActive
                                                                ? "bg-[var(--bg-hover)] text-white font-medium"
                                                                : "text-[var(--text-subtle)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
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

                {/* User cluster */}
                <div className="border-t border-[var(--border-default)] p-3">
                    <div className="flex items-center gap-2.5 px-2 py-2 mb-1 rounded-md hover:bg-[var(--bg-elevated)] transition-colors">
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[var(--accent-soft)] to-[var(--bg-hover)] border border-[var(--border-emphasis)] flex items-center justify-center text-[11px] font-medium text-white shrink-0">
                            {user.username?.[0]?.toUpperCase() || "U"}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-[12.5px] font-medium text-white truncate">
                                {user.username}
                            </p>
                            <div className="flex items-center gap-1.5 text-[10.5px] text-[var(--text-disabled)]">
                                <span className="truncate">{user.email}</span>
                            </div>
                        </div>
                        {user.role && (
                            <span className="microtype shrink-0 px-1.5 py-0.5 rounded bg-[var(--bg-hover)] border border-[var(--border-emphasis)] text-[var(--text-subtle)]">
                                {user.role}
                            </span>
                        )}
                    </div>
                    <button
                        onClick={async () => {
                            await logout();
                            router.push("/login");
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-[12.5px] text-[var(--text-disabled)] hover:text-[var(--danger)] rounded-md hover:bg-[var(--bg-elevated)] transition-colors cursor-pointer"
                    >
                        <FiLogOut className="w-3.5 h-3.5" />
                        Sign out
                    </button>
                </div>
            </aside>

            <main className="flex-1 md:ml-60 ml-0 p-6 md:p-10 mt-14 md:mt-0">
                <div className="max-w-6xl">{children}</div>
            </main>
        </div>
    );
}
