"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import type { RowSelectionState } from "@tanstack/react-table";
import { FiUpload, FiChevronLeft, FiChevronRight } from "react-icons/fi";
import { useCurrentClient } from "@/stores/currentClientStore";
import { complianceApi } from "@/lib/api/compliance";
import {
    NoticeFilterSidebar,
    EMPTY_FILTERS,
    type NoticeFilters,
} from "@/components/compliance/NoticeFilterSidebar";
import {
    NoticeTable,
    type NoticeRow,
} from "@/components/compliance/NoticeTable";
import { BulkActionBar } from "@/components/compliance/BulkActionBar";

/**
 * Compliance dashboard — UI-SPEC §1.
 *
 * Composition: 4 stat cards + collapsible filter sidebar + paginated notice
 * table + floating bulk action bar. Tenant scoping is implicit — the
 * `complianceApi.tenantHeaders()` call attaches `X-Client-Id` from the
 * Zustand store on every request.
 */

const PAGE_SIZE = 25;

interface StatCardProps {
    label: string;
    value: string | number;
    color?: string;
    isLoading?: boolean;
}

function StatCard({ label, value, color = "#ffffff", isLoading }: StatCardProps) {
    return (
        <div className="bg-[#111113] border border-[#27272a] rounded-md p-4">
            <p className="text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1">
                {label}
            </p>
            {isLoading ? (
                <div className="h-7 w-16 bg-[#18181b] rounded animate-pulse" />
            ) : (
                <p
                    className="text-2xl font-semibold tabular-nums"
                    style={{ color }}
                >
                    {value}
                </p>
            )}
        </div>
    );
}

function isFiltersDirty(f: NoticeFilters): boolean {
    return (
        f.authority !== "" ||
        f.status !== "" ||
        f.response_deadline_after !== "" ||
        f.response_deadline_before !== "" ||
        f.gstin_or_pan !== ""
    );
}

export default function ComplianceDashboardPage() {
    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const crossClientMode = useCurrentClient((s) => s.crossClientMode);
    const tenantSelected = activeClientId !== null || crossClientMode;

    const [filters, setFilters] = useState<NoticeFilters>(EMPTY_FILTERS);
    const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
    const [page, setPage] = useState(1);

    const dashboardQ = useQuery({
        queryKey: ["client-dashboard", activeClientId],
        queryFn: async () => {
            if (activeClientId === null) return null;
            const { data } = await complianceApi.getClientDashboard(
                activeClientId
            );
            return data;
        },
        enabled: activeClientId !== null,
    });

    const noticesQ = useQuery({
        queryKey: [
            "notices",
            activeClientId,
            crossClientMode,
            filters,
            page,
        ],
        queryFn: async () => {
            const { data } = await complianceApi.listNotices({
                authority: filters.authority || undefined,
                status: filters.status || undefined,
                response_deadline_after:
                    filters.response_deadline_after || undefined,
                response_deadline_before:
                    filters.response_deadline_before || undefined,
                gstin_or_pan: filters.gstin_or_pan || undefined,
                page,
                page_size: PAGE_SIZE,
            });
            return data;
        },
        enabled: tenantSelected,
    });

    const rows: NoticeRow[] = useMemo(
        () => (noticesQ.data?.items ?? []).map((n) => ({ ...n })),
        [noticesQ.data]
    );

    const total = noticesQ.data?.total ?? 0;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    const selectedIds = useMemo(
        () =>
            Object.entries(rowSelection)
                .filter(([, v]) => v)
                .map(([k]) => Number.parseInt(k, 10))
                .filter((n) => Number.isFinite(n)),
        [rowSelection]
    );

    const dashboard = dashboardQ.data;
    const totalNotices = dashboard?.total ?? 0;
    const overdue = dashboard?.overdue ?? 0;
    const distinctAuthorities = dashboard
        ? Object.keys(dashboard.by_authority ?? {}).length
        : 0;
    const unscored = dashboard?.by_risk_tier?.unscored ?? totalNotices;

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
                <div>
                    <h1 className="text-lg font-semibold text-white mb-0.5">
                        Compliance dashboard
                    </h1>
                    <p className="text-[13px] text-[#71717a]">
                        {crossClientMode
                            ? "Viewing notices across all clients you have access to."
                            : "Track notices for the active client through their workflow."}
                    </p>
                </div>
                {tenantSelected && (
                    <Link
                        href="/dashboard/compliance/notices/new"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#3b82f6] text-white text-[12px] font-medium hover:bg-[#2563eb] focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                    >
                        <FiUpload className="w-3.5 h-3.5" />
                        Upload notice
                    </Link>
                )}
            </div>

            {!tenantSelected ? (
                <div className="bg-[#111113] border border-[#27272a] rounded-md p-12 text-center">
                    <h2 className="text-sm font-semibold text-white mb-1">
                        No client selected
                    </h2>
                    <p className="text-[13px] text-[#71717a]">
                        Select a client from the switcher to view notices.
                    </p>
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                        <StatCard
                            label="Total notices"
                            value={totalNotices}
                            isLoading={dashboardQ.isLoading}
                        />
                        <StatCard
                            label="Overdue"
                            value={overdue}
                            color="#ef4444"
                            isLoading={dashboardQ.isLoading}
                        />
                        <StatCard
                            label="By authority"
                            value={distinctAuthorities}
                            color="#3b82f6"
                            isLoading={dashboardQ.isLoading}
                        />
                        <StatCard
                            label="Unscored"
                            value={unscored}
                            color="#71717a"
                            isLoading={dashboardQ.isLoading}
                        />
                    </div>

                    <div className="flex flex-col lg:flex-row gap-6">
                        <NoticeFilterSidebar
                            filters={filters}
                            onChange={(next) => {
                                setFilters(next);
                                setPage(1);
                            }}
                        />

                        <div className="flex-1 min-w-0">
                            {!noticesQ.isLoading &&
                            rows.length === 0 &&
                            !isFiltersDirty(filters) ? (
                                <div className="bg-[#111113] border border-[#27272a] rounded-md p-12 text-center">
                                    <h2 className="text-sm font-semibold text-white mb-1">
                                        No notices yet
                                    </h2>
                                    <p className="text-[13px] text-[#71717a] mb-4">
                                        Upload a compliance notice to start
                                        tracking it through the workflow. Drag a
                                        PDF, JPG, or PNG below — or click
                                        upload.
                                    </p>
                                    <Link
                                        href="/dashboard/compliance/notices/new"
                                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#3b82f6] text-white text-[12px] font-medium hover:bg-[#2563eb] focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                                    >
                                        <FiUpload className="w-3.5 h-3.5" />
                                        Upload first notice
                                    </Link>
                                </div>
                            ) : (
                                <>
                                    <NoticeTable
                                        rows={rows}
                                        isLoading={noticesQ.isLoading}
                                        rowSelection={rowSelection}
                                        onRowSelectionChange={setRowSelection}
                                    />
                                    {total > PAGE_SIZE && (
                                        <div className="mt-3 flex items-center justify-between text-[12px] text-[#a1a1aa]">
                                            <span className="tabular-nums">
                                                Page {page} of {totalPages}
                                            </span>
                                            <div className="flex items-center gap-1.5">
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        setPage((p) =>
                                                            Math.max(1, p - 1)
                                                        )
                                                    }
                                                    disabled={page <= 1}
                                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-[#27272a] text-white hover:bg-[#18181b] disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                                                    aria-label="Previous page"
                                                >
                                                    <FiChevronLeft className="w-3.5 h-3.5" />
                                                    Prev
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        setPage((p) =>
                                                            Math.min(
                                                                totalPages,
                                                                p + 1
                                                            )
                                                        )
                                                    }
                                                    disabled={
                                                        page >= totalPages
                                                    }
                                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-[#27272a] text-white hover:bg-[#18181b] disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                                                    aria-label="Next page"
                                                >
                                                    Next
                                                    <FiChevronRight className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>

                    <BulkActionBar
                        selectedIds={selectedIds}
                        onClear={() => setRowSelection({})}
                        onUpdated={(failedIds) => {
                            // Refresh notices and dashboard stats; clear selection
                            // for non-failed rows, keep red-tinted failures selected
                            // so the user can see what didn't go through.
                            noticesQ.refetch();
                            dashboardQ.refetch();
                            if (!failedIds || failedIds.length === 0) {
                                setRowSelection({});
                            } else {
                                const next: RowSelectionState = {};
                                for (const id of failedIds)
                                    next[String(id)] = true;
                                setRowSelection(next);
                            }
                        }}
                    />
                </>
            )}
        </div>
    );
}
