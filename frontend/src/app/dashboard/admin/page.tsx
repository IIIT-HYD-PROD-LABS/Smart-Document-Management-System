"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
    FiUsers,
    FiUserCheck,
    FiFileText,
    FiUserPlus,
    FiList,
    FiCpu,
    FiBriefcase,
    FiShield,
    FiBarChart2,
    FiArrowRight,
    FiClock,
} from "react-icons/fi";

import { adminApi } from "@/lib/api";
import { LoadingSpinner } from "@/components";

export const dynamic = "force-dynamic";

interface AdminStats {
    total_users: number;
    active_users: number;
    users_by_role: Record<string, number>;
    total_documents: number;
    documents_by_status: Record<string, number>;
}

interface EarlyAccessStats {
    pending: number;
    approved: number;
    rejected: number;
    total: number;
}

interface AuditLogItem {
    id: number;
    user_id: number | null;
    action: string;
    resource_type: string | null;
    resource_id: number | null;
    details: Record<string, unknown> | null;
    ip_address: string | null;
    created_at: string;
}

interface AuditLogList {
    items: AuditLogItem[];
    total: number;
    page: number;
    per_page: number;
}

function StatCard({
    label,
    value,
    icon: Icon,
    hint,
}: {
    label: string;
    value: number | string;
    icon: React.ComponentType<{ className?: string }>;
    hint?: string;
}) {
    return (
        <div className="surface-card p-5 min-w-0">
            <div className="flex items-center gap-3 mb-2 min-w-0">
                <Icon className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
                <p className="microtype text-[var(--text-muted)] truncate">{label}</p>
            </div>
            <p className="text-2xl font-semibold text-[var(--text-primary)] tabular-nums">
                {value}
            </p>
            {hint && (
                <p className="text-[11.5px] text-[var(--text-subtle)] mt-1 truncate">
                    {hint}
                </p>
            )}
        </div>
    );
}

const QUICK_ACTIONS: Array<{
    href: string;
    label: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
}> = [
    {
        href: "/dashboard/admin/users",
        label: "Users",
        description: "Manage members, roles, and access.",
        icon: FiUsers,
    },
    {
        href: "/dashboard/admin/early-access",
        label: "Early access",
        description: "Review pending invitation requests.",
        icon: FiUserPlus,
    },
    {
        href: "/dashboard/admin/audit",
        label: "Audit log",
        description: "Search the immutable activity trail.",
        icon: FiList,
    },
    {
        href: "/dashboard/admin/ai",
        label: "AI provider",
        description: "Connect Claude or Gemini for this tenant.",
        icon: FiCpu,
    },
    {
        href: "/dashboard/admin/organization",
        label: "Organization",
        description: "Tenant policies and defaults.",
        icon: FiBriefcase,
    },
    {
        href: "/dashboard/admin/security",
        label: "Security",
        description: "Login policies and providers.",
        icon: FiShield,
    },
    {
        href: "/dashboard/admin/model-evaluation",
        label: "Model evaluation",
        description: "Classification metrics for the document model.",
        icon: FiBarChart2,
    },
];

function formatAction(action: string): string {
    return action.replace(/_/g, " ");
}

function formatTimestamp(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function truncate(s: string, n: number): string {
    return s.length > n ? s.slice(0, n - 1) + "..." : s;
}

export default function AdminOverviewPage() {
    const statsQuery = useQuery<AdminStats>({
        queryKey: ["admin", "stats"],
        queryFn: () => adminApi.getStats().then((r) => r.data),
    });

    const eaStatsQuery = useQuery<EarlyAccessStats>({
        queryKey: ["admin", "early-access-stats"],
        queryFn: () => adminApi.getEarlyAccessStats().then((r) => r.data),
    });

    const recentAuditQuery = useQuery<AuditLogList>({
        queryKey: ["admin", "audit", { limit: 5 }],
        queryFn: () =>
            adminApi.getAuditLogs({ page: 1, perPage: 5 }).then((r) => r.data),
    });

    const stats = statsQuery.data;
    const ea = eaStatsQuery.data;
    const audit = recentAuditQuery.data;

    const statsLoading = statsQuery.isLoading || eaStatsQuery.isLoading;

    return (
        <div className="space-y-8">
            <header>
                <p className="microtype mb-2">Admin</p>
                <h1 className="text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Overview
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1.5">
                    Operational health for this tenant.
                </p>
            </header>

            {statsLoading && !stats ? (
                <div className="flex items-center justify-center h-32">
                    <LoadingSpinner />
                </div>
            ) : (
                <section className="grid grid-cols-2 lg:grid-cols-2 xl:grid-cols-4 gap-3">
                    <StatCard
                        label="Total users"
                        value={stats?.total_users ?? 0}
                        icon={FiUsers}
                        hint={
                            stats
                                ? Object.entries(stats.users_by_role)
                                      .map(([r, c]) => `${r}: ${c}`)
                                      .join(", ")
                                : undefined
                        }
                    />
                    <StatCard
                        label="Active users"
                        value={stats?.active_users ?? 0}
                        icon={FiUserCheck}
                    />
                    <StatCard
                        label="Documents"
                        value={stats?.total_documents ?? 0}
                        icon={FiFileText}
                    />
                    <StatCard
                        label="Pending early access"
                        value={ea?.pending ?? 0}
                        icon={FiUserPlus}
                        hint={ea ? `${ea.total} total requests` : undefined}
                    />
                </section>
            )}

            <section>
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]">
                        Quick actions
                    </h2>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 2xl:grid-cols-3 gap-3">
                    {QUICK_ACTIONS.map(({ href, label, description, icon: Icon }) => (
                        <Link
                            key={href}
                            href={href}
                            className="
                                surface-card p-4 group cursor-pointer
                                hover:border-[var(--border-emphasis)]
                                transition-colors duration-150
                                focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]
                            "
                        >
                            <div className="flex items-start gap-3">
                                <span className="w-9 h-9 rounded-md bg-[var(--accent-soft)] text-[var(--accent)] flex items-center justify-center shrink-0">
                                    <Icon className="w-4 h-4" />
                                </span>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5">
                                        <p className="text-[13.5px] font-medium text-[var(--text-primary)] group-hover:text-[var(--accent)] transition-colors">
                                            {label}
                                        </p>
                                        <FiArrowRight className="w-3.5 h-3.5 text-[var(--text-subtle)] opacity-0 group-hover:opacity-100 transition-opacity" />
                                    </div>
                                    <p className="text-[12px] text-[var(--text-muted)] mt-0.5 leading-relaxed">
                                        {description}
                                    </p>
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            </section>

            <section>
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]">
                        Recent activity
                    </h2>
                    <Link
                        href="/dashboard/admin/audit"
                        className="text-[12.5px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors cursor-pointer inline-flex items-center gap-1"
                    >
                        View all
                        <FiArrowRight className="w-3 h-3" />
                    </Link>
                </div>
                <div className="surface-card overflow-hidden">
                    {recentAuditQuery.isLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <LoadingSpinner />
                        </div>
                    ) : recentAuditQuery.isError ? (
                        <p className="px-4 py-8 text-center text-[13px] text-[var(--text-muted)]">
                            Failed to load recent activity.
                        </p>
                    ) : audit && audit.items.length > 0 ? (
                        <ul className="divide-y divide-[var(--border-subtle)]">
                            {audit.items.map((item) => (
                                <li
                                    key={item.id}
                                    className="px-4 py-3 flex items-start gap-3"
                                >
                                    <span className="w-7 h-7 rounded-md bg-[var(--bg-hover)] text-[var(--text-muted)] flex items-center justify-center shrink-0 mt-0.5">
                                        <FiClock className="w-3.5 h-3.5" />
                                    </span>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-baseline gap-2 flex-wrap">
                                            <p className="text-[13px] text-[var(--text-primary)]">
                                                <span className="font-medium capitalize">
                                                    {formatAction(item.action)}
                                                </span>
                                                {item.resource_type && (
                                                    <span className="text-[var(--text-muted)]">
                                                        {" on "}
                                                        {item.resource_type}
                                                        {item.resource_id != null &&
                                                            ` #${item.resource_id}`}
                                                    </span>
                                                )}
                                            </p>
                                            <span className="text-[11px] text-[var(--text-subtle)] tabular-nums">
                                                {formatTimestamp(item.created_at)}
                                            </span>
                                        </div>
                                        {item.user_id != null && (
                                            <Link
                                                href={`/dashboard/admin/users/${item.user_id}`}
                                                className="text-[11.5px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors cursor-pointer"
                                            >
                                                user #{item.user_id}
                                            </Link>
                                        )}
                                        {item.details &&
                                            Object.keys(item.details).length > 0 && (
                                                <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5 font-mono truncate">
                                                    {truncate(JSON.stringify(item.details), 140)}
                                                </p>
                                            )}
                                    </div>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="px-4 py-8 text-center text-[13px] text-[var(--text-muted)]">
                            No recent activity.
                        </p>
                    )}
                </div>
            </section>
        </div>
    );
}
