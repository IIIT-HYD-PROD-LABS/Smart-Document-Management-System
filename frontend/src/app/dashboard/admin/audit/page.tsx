"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
    FiSearch,
    FiChevronLeft,
    FiChevronRight,
    FiFilter,
    FiX,
} from "react-icons/fi";

import { adminApi } from "@/lib/api";
import { LoadingSpinner } from "@/components";

export const dynamic = "force-dynamic";

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

const PER_PAGE = 50;

function formatTimestamp(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function truncate(s: string, n: number): string {
    return s.length > n ? s.slice(0, n - 1) + "..." : s;
}

export default function AdminAuditPage() {
    const searchParams = useSearchParams();
    const router = useRouter();

    // Seed filter state from the query string so deep-link / linkbacks from
    // /admin/users/:id?user_id=... pre-populate the filters.
    const [userIdFilter, setUserIdFilter] = useState(
        searchParams.get("user_id") || "",
    );
    const [actionFilter, setActionFilter] = useState(searchParams.get("action") || "");
    const [resourceTypeFilter, setResourceTypeFilter] = useState(
        searchParams.get("resource_type") || "",
    );
    const [dateFrom, setDateFrom] = useState(searchParams.get("date_from") || "");
    const [dateTo, setDateTo] = useState(searchParams.get("date_to") || "");
    const [page, setPage] = useState(1);

    // Keep the URL in sync with filters so an admin can share a link.
    useEffect(() => {
        const params = new URLSearchParams();
        if (userIdFilter) params.set("user_id", userIdFilter);
        if (actionFilter) params.set("action", actionFilter);
        if (resourceTypeFilter) params.set("resource_type", resourceTypeFilter);
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        const qs = params.toString();
        router.replace(`/dashboard/admin/audit${qs ? `?${qs}` : ""}`, {
            scroll: false,
        });
    }, [userIdFilter, actionFilter, resourceTypeFilter, dateFrom, dateTo, router]);

    // Resetting filters always sends us back to page 1.
    useEffect(() => {
        setPage(1);
    }, [userIdFilter, actionFilter, resourceTypeFilter, dateFrom, dateTo]);

    const parsedUserId = useMemo(() => {
        if (!userIdFilter) return null;
        const n = Number(userIdFilter);
        return Number.isFinite(n) && n > 0 ? n : null;
    }, [userIdFilter]);

    const auditQuery = useQuery<AuditLogList>({
        queryKey: [
            "admin",
            "audit",
            {
                page,
                userId: parsedUserId,
                action: actionFilter || null,
                resourceType: resourceTypeFilter || null,
                dateFrom: dateFrom || null,
                dateTo: dateTo || null,
            },
        ],
        queryFn: () =>
            adminApi
                .getAuditLogs({
                    page,
                    perPage: PER_PAGE,
                    userId: parsedUserId,
                    action: actionFilter || null,
                    resourceType: resourceTypeFilter || null,
                    dateFrom: dateFrom || null,
                    dateTo: dateTo || null,
                })
                .then((r) => r.data),
    });

    const data = auditQuery.data;
    const items = data?.items ?? [];
    const total = data?.total ?? 0;
    const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

    const hasActiveFilters =
        !!userIdFilter ||
        !!actionFilter ||
        !!resourceTypeFilter ||
        !!dateFrom ||
        !!dateTo;

    const clearFilters = () => {
        setUserIdFilter("");
        setActionFilter("");
        setResourceTypeFilter("");
        setDateFrom("");
        setDateTo("");
    };

    return (
        <div className="space-y-6">
            <header>
                <p className="microtype mb-2">Admin</p>
                <h1 className="text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Audit log
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1.5">
                    Immutable activity trail. {total.toLocaleString()} entries match the current filters.
                </p>
            </header>

            <div className="surface-card p-4 space-y-3">
                <div className="flex items-center gap-2">
                    <FiFilter className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                    <p className="microtype text-[var(--text-muted)]">Filters</p>
                    {hasActiveFilters && (
                        <button
                            type="button"
                            onClick={clearFilters}
                            className="ml-auto inline-flex items-center gap-1 text-[11.5px] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                        >
                            <FiX className="w-3 h-3" />
                            Clear
                        </button>
                    )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                    <label className="block">
                        <span className="microtype block mb-1">User id</span>
                        <div className="relative">
                            <FiSearch className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
                            <input
                                type="number"
                                min={1}
                                value={userIdFilter}
                                onChange={(e) => setUserIdFilter(e.target.value)}
                                placeholder="e.g. 42"
                                className="w-full pl-8 pr-2 py-1.5 bg-[var(--bg-page)] border border-[var(--border-default)] rounded-md text-[12.5px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]"
                            />
                        </div>
                    </label>
                    <label className="block">
                        <span className="microtype block mb-1">Action</span>
                        <input
                            type="text"
                            value={actionFilter}
                            onChange={(e) => setActionFilter(e.target.value)}
                            placeholder="role_change"
                            className="w-full px-2.5 py-1.5 bg-[var(--bg-page)] border border-[var(--border-default)] rounded-md text-[12.5px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]"
                        />
                    </label>
                    <label className="block">
                        <span className="microtype block mb-1">Resource</span>
                        <input
                            type="text"
                            value={resourceTypeFilter}
                            onChange={(e) => setResourceTypeFilter(e.target.value)}
                            placeholder="user"
                            className="w-full px-2.5 py-1.5 bg-[var(--bg-page)] border border-[var(--border-default)] rounded-md text-[12.5px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]"
                        />
                    </label>
                    <label className="block">
                        <span className="microtype block mb-1">Date from</span>
                        <input
                            type="date"
                            value={dateFrom}
                            onChange={(e) => setDateFrom(e.target.value)}
                            className="w-full px-2.5 py-1.5 bg-[var(--bg-page)] border border-[var(--border-default)] rounded-md text-[12.5px] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]"
                        />
                    </label>
                    <label className="block">
                        <span className="microtype block mb-1">Date to</span>
                        <input
                            type="date"
                            value={dateTo}
                            onChange={(e) => setDateTo(e.target.value)}
                            className="w-full px-2.5 py-1.5 bg-[var(--bg-page)] border border-[var(--border-default)] rounded-md text-[12.5px] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]"
                        />
                    </label>
                </div>
            </div>

            {auditQuery.isLoading && !data ? (
                <div className="flex items-center justify-center h-32">
                    <LoadingSpinner />
                </div>
            ) : auditQuery.isError ? (
                <div className="surface-card p-6">
                    <p className="text-[13px] text-[var(--danger)]">
                        Failed to load audit log. Try refreshing the page.
                    </p>
                </div>
            ) : (
                <div className="surface-card overflow-x-auto">
                    <table className="w-full min-w-[820px]">
                        <thead>
                            <tr className="border-b border-[var(--border-default)] bg-[var(--bg-muted)]">
                                <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                    Timestamp
                                </th>
                                <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                    User
                                </th>
                                <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                    Action
                                </th>
                                <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                    Resource
                                </th>
                                <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                    Details
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map((item) => {
                                const detailsStr = item.details
                                    ? JSON.stringify(item.details)
                                    : "";
                                return (
                                    <tr
                                        key={item.id}
                                        className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)] transition-colors"
                                    >
                                        <td className="px-4 py-3 align-top">
                                            <span className="text-[12px] text-[var(--text-muted)] tabular-nums whitespace-nowrap">
                                                {formatTimestamp(item.created_at)}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 align-top">
                                            {item.user_id != null ? (
                                                <Link
                                                    href={`/dashboard/admin/users/${item.user_id}`}
                                                    className="text-[12.5px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors cursor-pointer tabular-nums"
                                                >
                                                    #{item.user_id}
                                                </Link>
                                            ) : (
                                                <span className="text-[12px] text-[var(--text-disabled)]">
                                                    system
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3 align-top">
                                            <span className="text-[12.5px] text-[var(--text-primary)] font-medium capitalize">
                                                {item.action.replace(/_/g, " ")}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 align-top">
                                            <span className="text-[12.5px] text-[var(--text-secondary)]">
                                                {item.resource_type ? (
                                                    <>
                                                        {item.resource_type}
                                                        {item.resource_id != null && (
                                                            <span className="text-[var(--text-muted)] ml-1 tabular-nums">
                                                                #{item.resource_id}
                                                            </span>
                                                        )}
                                                    </>
                                                ) : (
                                                    <span className="text-[var(--text-disabled)]">
                                                        none
                                                    </span>
                                                )}
                                            </span>
                                        </td>
                                        <td
                                            className="px-4 py-3 align-top max-w-[420px]"
                                            title={detailsStr}
                                        >
                                            {detailsStr ? (
                                                <p className="text-[11.5px] text-[var(--text-muted)] font-mono truncate">
                                                    {truncate(detailsStr, 220)}
                                                </p>
                                            ) : (
                                                <span className="text-[12px] text-[var(--text-disabled)]">
                                                    none
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                            {items.length === 0 && (
                                <tr>
                                    <td
                                        colSpan={5}
                                        className="px-4 py-10 text-center text-sm text-[var(--text-muted)]"
                                    >
                                        No audit entries match the current filters.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}

            {totalPages > 1 && (
                <div className="flex items-center justify-between">
                    <p className="text-xs text-[var(--text-muted)]">
                        Showing {(page - 1) * PER_PAGE + 1} to{" "}
                        {Math.min(page * PER_PAGE, total)} of {total.toLocaleString()}
                    </p>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page === 1}
                            className="p-1.5 rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-emphasis)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                            aria-label="Previous page"
                        >
                            <FiChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-xs text-[var(--text-secondary)] tabular-nums">
                            {page} / {totalPages}
                        </span>
                        <button
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page === totalPages}
                            className="p-1.5 rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-emphasis)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                            aria-label="Next page"
                        >
                            <FiChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
