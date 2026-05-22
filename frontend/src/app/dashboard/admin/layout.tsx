"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
    FiHome,
    FiUsers,
    FiUserPlus,
    FiList,
    FiCpu,
    FiBriefcase,
    FiShield,
    FiBarChart2,
} from "react-icons/fi";

import { useAuth } from "@/context/AuthContext";
import { LoadingSpinner } from "@/components";

// Admin pages need the auth-gated layout above; force-dynamic prevents
// the sub-sidebar render from being inlined into a static prerender.
export const dynamic = "force-dynamic";

type SubNavItem = {
    href: string;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
};

// Order here drives both the desktop rail and the mobile tab strip.
const SUB_NAV: SubNavItem[] = [
    { href: "/dashboard/admin", label: "Overview", icon: FiHome },
    { href: "/dashboard/admin/users", label: "Users", icon: FiUsers },
    { href: "/dashboard/admin/early-access", label: "Early access", icon: FiUserPlus },
    { href: "/dashboard/admin/audit", label: "Audit log", icon: FiList },
    { href: "/dashboard/admin/ai", label: "AI provider", icon: FiCpu },
    { href: "/dashboard/admin/organization", label: "Organization", icon: FiBriefcase },
    { href: "/dashboard/admin/security", label: "Security", icon: FiShield },
    { href: "/dashboard/admin/model-evaluation", label: "Model eval", icon: FiBarChart2 },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (!isLoading && user && user.role !== "admin") {
            router.replace("/dashboard");
        }
    }, [isLoading, user, router]);

    if (isLoading || !user) {
        return (
            <div className="flex items-center justify-center h-64">
                <LoadingSpinner />
            </div>
        );
    }

    if (user.role !== "admin") {
        return null;
    }

    // Exact match for the Overview index; startsWith with separator for
    // everything else, so /dashboard/admin doesn't stay highlighted when
    // the user is on /dashboard/admin/users.
    const isItemActive = (href: string): boolean => {
        if (pathname === href) return true;
        if (href === "/dashboard/admin") return false;
        return pathname.startsWith(href + "/");
    };

    return (
        <div className="flex flex-col md:flex-row gap-6">
            {/* Mobile top tab strip (horizontal scroll). Desktop layout
                hides this in favour of the left rail below. */}
            <nav
                aria-label="Admin sections"
                className="md:hidden -mx-6 px-6 overflow-x-auto"
            >
                <ul className="flex items-center gap-1 border-b border-[var(--border-default)] pb-1">
                    {SUB_NAV.map((item) => {
                        const isActive = isItemActive(item.href);
                        const Icon = item.icon;
                        return (
                            <li key={item.href} className="shrink-0">
                                <Link
                                    href={item.href}
                                    className={`
                                        flex items-center gap-1.5 px-3 py-2 rounded-md
                                        text-[12.5px] whitespace-nowrap cursor-pointer
                                        transition-colors duration-150
                                        ${
                                            isActive
                                                ? "bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
                                                : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                                        }
                                    `}
                                >
                                    <Icon className="w-3.5 h-3.5 shrink-0" />
                                    <span>{item.label}</span>
                                </Link>
                            </li>
                        );
                    })}
                </ul>
            </nav>

            {/* Desktop left rail. Sticky inside the dashboard scroll
                container so the rail stays in view as the page scrolls. */}
            <aside
                aria-label="Admin sections"
                className="hidden md:block w-[200px] shrink-0"
            >
                <div className="sticky top-20">
                    <p className="microtype px-3 mb-2">Admin</p>
                    <ul className="space-y-0.5">
                        {SUB_NAV.map((item) => {
                            const isActive = isItemActive(item.href);
                            const Icon = item.icon;
                            return (
                                <li key={item.href}>
                                    <Link
                                        href={item.href}
                                        className={`
                                            relative flex items-center gap-2.5 px-3 py-2 rounded-md
                                            text-[13px] cursor-pointer
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
            </aside>

            <div className="flex-1 min-w-0">{children}</div>
        </div>
    );
}
