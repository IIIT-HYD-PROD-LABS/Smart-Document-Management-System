"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import type { RowSelectionState } from "@tanstack/react-table";
import {
    FiUpload,
    FiChevronLeft,
    FiChevronRight,
    FiAlertTriangle,
    FiShield,
    FiMail,
    FiInfo,
} from "react-icons/fi";
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
 * Compliance dashboard — Enterprise hero redesign.
 *
 * Hero header:
 *   • Total notice count + risk-distribution stacked bar (low / medium /
 *     high / critical) with semantic color pills.
 *   • Quick stats row: Total · Overdue · Authorities · Unscored.
 *
 * Body:
 *   • Filter sidebar (existing component, retokenized).
 *   • NoticeTable (existing component, retokenized).
 *
 * Empty state (no notices for tenant):
 *   • Friendly illustration + "Connect Gmail to auto-import" + "Upload first
 *     notice" CTAs.
 */

const PAGE_SIZE = 25;

const RISK_CONFIG: Array<{
    key: "low" | "medium" | "high" | "critical";
    label: string;
    color: string;
}> = [
    { key: "low", label: "Low", color: "var(--success)" },
    { key: "medium", label: "Medium", color: "var(--warning)" },
    { key: "high", label: "High", color: "#f97316" },
    { key: "critical", label: "Critical", color: "var(--danger)" },
];

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
    const byStatus = dashboard?.by_status ?? {};
    const byRiskTier = dashboard?.by_risk_tier ?? {};
    const unscored = byRiskTier.unscored ?? totalNotices;
    const scoredTotal = RISK_CONFIG.reduce(
        (sum, r) => sum + (byRiskTier[r.key] ?? 0),
        0
    );

    // Workflow funnel: turns the by_status map into action-oriented buckets
    // so the page reads as "what needs attention" rather than just "list of
    // notices". Each interactive card is a filter shortcut into the table
    // below. statusFilter is typed against NoticeFilters["status"] (a
    // NoticeStatus enum union) so a typo here is a build-time error.
    const workflowStages: Array<{
        key: string;
        label: string;
        sub: string;
        count: number;
        tone: "neutral" | "info" | "warn" | "danger";
        statusFilter?: NoticeFilters["status"];
    }> = [
        {
            key: "new",
            label: "New",
            sub: "Just arrived — needs triage",
            count: byStatus.received ?? 0,
            tone: "info",
            statusFilter: "received",
        },
        {
            key: "in_review",
            label: "In review",
            sub: "Being worked right now",
            count: byStatus.under_review ?? 0,
            tone: "neutral",
            statusFilter: "under_review",
        },
        {
            key: "drafted",
            label: "Awaiting submission",
            sub: "Response drafted, not filed",
            count: byStatus.response_drafted ?? 0,
            tone: "warn",
            statusFilter: "response_drafted",
        },
        {
            key: "overdue",
            label: "Overdue",
            sub: "Past response deadline",
            count: overdue,
            tone: "danger",
            // statusFilter intentionally omitted — there is no derived
            // "overdue" predicate in NoticeFilters, so this card renders
            // as a non-interactive presentational tile, not a button.
        },
    ];

    const setStatusFilter = (status: NoticeFilters["status"] | undefined) => {
        setFilters((prev) => ({ ...prev, status: status ?? "" }));
        setPage(1);
    };

    return (
        <div className="space-y-6">
            {/* ── Hero header ─────────────────────────────────────── */}
            <header className="space-y-2">
                <p className="microtype">Compliance · Notice workflow</p>
                <div className="flex items-end justify-between gap-4 flex-wrap">
                    <div>
                        <h1 className="text-[28px] leading-[1.15] font-semibold text-[var(--text-primary)] tracking-tight">
                            Compliance notices
                        </h1>
                        <p className="text-[14px] text-[var(--text-muted)] mt-1.5 max-w-2xl">
                            {crossClientMode
                                ? "Every regulator notice across the clients you have access to. Triage, draft a response, and track the audit chain end-to-end."
                                : "Every regulator notice for this organization, end-to-end: receive, triage, draft a response, file it, and keep the audit trail. The cards below show what needs attention next."}
                        </p>
                    </div>
                    {tenantSelected && (
                        <Link
                            href="/dashboard/compliance/notices/new"
                            className="
                                inline-flex items-center gap-2 h-10 px-4 rounded-md
                                bg-[var(--accent)] hover:bg-[var(--accent-strong)]
                                text-[14px] font-medium text-white
                                transition-colors duration-150 cursor-pointer
                                shadow-sm
                            "
                        >
                            <FiUpload className="w-3.5 h-3.5" />
                            Upload notice
                        </Link>
                    )}
                </div>
            </header>

            {!tenantSelected ? (
                <NoTenantSelected />
            ) : (
                <>
                    {/* ── Workflow funnel — what needs attention next ─── */}
                    <section
                        aria-label="Notice workflow status"
                        className="grid grid-cols-2 lg:grid-cols-4 gap-3"
                    >
                        {workflowStages.map((stage) => {
                            const toneRing = {
                                neutral: "border-[var(--border-default)]",
                                info: "border-[color:color-mix(in_srgb,var(--accent)_35%,transparent)]",
                                warn: "border-[color:color-mix(in_srgb,var(--warning)_40%,transparent)]",
                                danger: "border-[color:color-mix(in_srgb,var(--danger)_40%,transparent)]",
                            }[stage.tone];
                            const toneLabel = {
                                neutral: "text-[var(--text-secondary)]",
                                info: "text-[var(--accent)]",
                                warn: "text-[var(--warning)]",
                                danger: "text-[var(--danger)]",
                            }[stage.tone];
                            const isInteractive = stage.statusFilter !== undefined;
                            const filterActive =
                                isInteractive && filters.status === stage.statusFilter;

                            // Card content (shared between button + div renderers
                            // so the visual is identical).
                            const inner = (
                                <>
                                    <div className="flex items-center justify-between">
                                        <span className={`text-[11px] font-medium uppercase tracking-wider ${toneLabel}`}>
                                            {stage.label}
                                        </span>
                                        <span className="font-mono tabular-nums text-[22px] font-semibold text-[var(--text-primary)] leading-none">
                                            {dashboardQ.isLoading ? "—" : stage.count.toLocaleString("en-IN")}
                                        </span>
                                    </div>
                                    <p className="text-[11.5px] text-[var(--text-muted)] mt-2 leading-snug">
                                        {stage.sub}
                                    </p>
                                    {isInteractive && (
                                        <p className="text-[10.5px] text-[var(--text-subtle)] mt-2 uppercase tracking-wider">
                                            {filterActive ? "Filter active — click to clear" : "Click to filter"}
                                        </p>
                                    )}
                                </>
                            );

                            const baseClasses = `
                                text-left p-4 rounded-lg border bg-[var(--bg-surface)]
                                ${toneRing}
                                transition-colors duration-150
                            `;

                            // Non-interactive cards (Overdue) render as plain
                            // divs — no disabled <button>, no fake hover. The
                            // count + tone communicate severity on their own.
                            if (!isInteractive) {
                                return (
                                    <div key={stage.key} className={baseClasses}>
                                        {inner}
                                    </div>
                                );
                            }

                            return (
                                <button
                                    key={stage.key}
                                    type="button"
                                    onClick={() =>
                                        setStatusFilter(
                                            filterActive ? undefined : stage.statusFilter
                                        )
                                    }
                                    aria-pressed={filterActive}
                                    className={`
                                        ${baseClasses}
                                        cursor-pointer hover:bg-[var(--bg-hover)]
                                        ${filterActive ? "ring-2 ring-[var(--accent)] ring-offset-1 ring-offset-[var(--bg-page)]" : ""}
                                        focus-visible:outline-none focus-visible:ring-2
                                        focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2
                                        focus-visible:ring-offset-[var(--bg-page)]
                                    `}
                                >
                                    {inner}
                                </button>
                            );
                        })}
                    </section>

                    {/* ── Risk distribution + quick stats ─────────────── */}
                    <section
                        className="surface-card p-5"
                        aria-label="Risk distribution and counts"
                    >
                        <div className="grid grid-cols-1 md:grid-cols-12 gap-5">
                            <div className="md:col-span-7">
                                <div className="flex items-center justify-between mb-3">
                                    <div>
                                        <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
                                            Risk distribution
                                        </h2>
                                        <p className="text-[12.5px] text-[var(--text-muted)] mt-0.5">
                                            {scoredTotal > 0
                                                ? `${scoredTotal} scored notice${scoredTotal === 1 ? "" : "s"}`
                                                : "No notices have been risk-scored yet"}
                                        </p>
                                    </div>
                                    <span className="font-mono tabular-nums text-[26px] font-semibold text-[var(--text-primary)]">
                                        {totalNotices.toLocaleString("en-IN")}
                                    </span>
                                </div>
                                <RiskDistributionBar
                                    counts={byRiskTier}
                                    isLoading={dashboardQ.isLoading}
                                />
                                <div className="flex flex-wrap gap-2 mt-3">
                                    {RISK_CONFIG.map((r) => {
                                        const count = byRiskTier[r.key] ?? 0;
                                        return (
                                            <span
                                                key={r.key}
                                                className="pill"
                                                style={{
                                                    backgroundColor: `color-mix(in srgb, ${r.color} 12%, transparent)`,
                                                    borderColor: `color-mix(in srgb, ${r.color} 30%, transparent)`,
                                                    color: r.color,
                                                }}
                                            >
                                                <span
                                                    className="w-1.5 h-1.5 rounded-full"
                                                    style={{
                                                        backgroundColor: r.color,
                                                    }}
                                                    aria-hidden
                                                />
                                                <span>{r.label}</span>
                                                <span className="font-mono tabular-nums opacity-90 ml-1">
                                                    {count}
                                                </span>
                                            </span>
                                        );
                                    })}
                                    {unscored > 0 && (
                                        <span
                                            className="pill"
                                            style={{
                                                backgroundColor: "var(--bg-hover)",
                                                borderColor: "var(--border-emphasis)",
                                                color: "var(--text-muted)",
                                            }}
                                        >
                                            <span
                                                className="w-1.5 h-1.5 rounded-full border border-[var(--text-disabled)]"
                                                aria-hidden
                                            />
                                            <span>Unscored</span>
                                            <span className="font-mono tabular-nums opacity-90 ml-1">
                                                {unscored}
                                            </span>
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div className="md:col-span-5 grid grid-cols-2 gap-3">
                                <QuickStat
                                    label="Total"
                                    value={totalNotices}
                                    tint="var(--accent)"
                                    icon={FiShield}
                                    isLoading={dashboardQ.isLoading}
                                />
                                <QuickStat
                                    label="Overdue"
                                    value={overdue}
                                    tint="var(--danger)"
                                    icon={FiAlertTriangle}
                                    isLoading={dashboardQ.isLoading}
                                />
                                <QuickStat
                                    label="Authorities"
                                    value={distinctAuthorities}
                                    tint="var(--info)"
                                    icon={FiShield}
                                    isLoading={dashboardQ.isLoading}
                                />
                                <QuickStat
                                    label="Unscored"
                                    value={unscored}
                                    tint="var(--text-muted)"
                                    icon={FiInfo}
                                    isLoading={dashboardQ.isLoading}
                                />
                            </div>
                        </div>
                    </section>

                    {/* ── Filters + table ─────────────────────────────── */}
                    <div className="flex flex-col lg:flex-row gap-5">
                        <NoticeFilterSidebar
                            filters={filters}
                            onChange={(next) => {
                                setFilters(next);
                                setPage(1);
                            }}
                        />

                        <div className="flex-1 min-w-0">
                            {noticesQ.isError ? (
                                <NoticesErrorState
                                    onRetry={() => noticesQ.refetch()}
                                />
                            ) : !noticesQ.isLoading &&
                            rows.length === 0 &&
                            !isFiltersDirty(filters) ? (
                                <EmptyNoticesState />
                            ) : (
                                <>
                                    <NoticeTable
                                        rows={rows}
                                        isLoading={noticesQ.isLoading}
                                        rowSelection={rowSelection}
                                        onRowSelectionChange={setRowSelection}
                                        onResetFilters={
                                            isFiltersDirty(filters)
                                                ? () => {
                                                      setFilters(EMPTY_FILTERS);
                                                      setPage(1);
                                                  }
                                                : undefined
                                        }
                                    />
                                    {total > PAGE_SIZE && (
                                        <div className="mt-4 flex items-center justify-between text-[13px] text-[var(--text-muted)]">
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
                                                    className="
                                                        inline-flex items-center gap-1 px-3 py-1.5 rounded-md
                                                        border border-[var(--border-default)]
                                                        bg-[var(--bg-elevated)] text-[var(--text-primary)]
                                                        hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                                                        disabled:opacity-40 disabled:cursor-not-allowed
                                                        focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                                                    "
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
                                                    className="
                                                        inline-flex items-center gap-1 px-3 py-1.5 rounded-md
                                                        border border-[var(--border-default)]
                                                        bg-[var(--bg-elevated)] text-[var(--text-primary)]
                                                        hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                                                        disabled:opacity-40 disabled:cursor-not-allowed
                                                        focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                                                    "
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

/* ── Risk distribution stacked bar ─────────────────────────── */
function RiskDistributionBar({
    counts,
    isLoading,
}: {
    counts: Record<string, number>;
    isLoading: boolean;
}) {
    if (isLoading) {
        return (
            <div className="h-3 rounded-full bg-[var(--bg-hover)] animate-pulse" />
        );
    }
    const total = RISK_CONFIG.reduce(
        (sum, r) => sum + (counts[r.key] ?? 0),
        0
    );
    if (total === 0) {
        return (
            <div
                className="h-3 rounded-full border border-dashed border-[var(--border-emphasis)]"
                aria-label="No risk data yet"
            />
        );
    }
    return (
        <div
            className="h-3 rounded-full overflow-hidden flex bg-[var(--bg-hover)]"
            role="img"
            aria-label={`Risk distribution: ${RISK_CONFIG.map(
                (r) => `${counts[r.key] ?? 0} ${r.label}`
            ).join(", ")}`}
        >
            {RISK_CONFIG.map((r) => {
                const count = counts[r.key] ?? 0;
                if (count === 0) return null;
                const pct = (count / total) * 100;
                return (
                    <span
                        key={r.key}
                        className="h-full transition-all"
                        style={{
                            width: `${pct}%`,
                            backgroundColor: r.color,
                        }}
                        title={`${r.label}: ${count}`}
                    />
                );
            })}
        </div>
    );
}

/* ── Quick stat tile ───────────────────────────────────────── */
function QuickStat({
    label,
    value,
    tint,
    icon: Icon,
    isLoading,
}: {
    label: string;
    value: number;
    tint: string;
    icon: React.ComponentType<{ className?: string }>;
    isLoading: boolean;
}) {
    return (
        <div
            className="rounded-lg border border-[var(--border-default)] p-3 flex items-center gap-3"
            style={{
                backgroundColor: `color-mix(in srgb, ${tint} 6%, var(--bg-elevated))`,
            }}
        >
            <div
                className="w-9 h-9 rounded-md flex items-center justify-center shrink-0"
                style={{
                    backgroundColor: `color-mix(in srgb, ${tint} 14%, transparent)`,
                    color: tint,
                }}
            >
                <Icon className="w-4 h-4" />
            </div>
            <div className="min-w-0">
                <p className="microtype text-[var(--text-muted)]">{label}</p>
                {isLoading ? (
                    <div className="h-5 w-12 mt-1 bg-[var(--bg-hover)] rounded animate-pulse" />
                ) : (
                    <p
                        className="font-mono tabular-nums text-[20px] leading-none font-semibold mt-0.5"
                        style={{ color: "var(--text-primary)" }}
                    >
                        {value.toLocaleString("en-IN")}
                    </p>
                )}
            </div>
        </div>
    );
}

/* ── Empty / error states ──────────────────────────────────── */
function NoTenantSelected() {
    return (
        <div className="surface-card p-12 text-center">
            <div className="w-14 h-14 rounded-full bg-[var(--accent-soft)] border border-[var(--accent-edge)] flex items-center justify-center mx-auto mb-4">
                <FiShield className="w-6 h-6 text-[var(--accent)]" />
            </div>
            <h2 className="text-[16px] font-semibold text-[var(--text-primary)] mb-1.5">
                Select a client to begin
            </h2>
            <p className="text-[13.5px] text-[var(--text-muted)] max-w-md mx-auto">
                Choose a client from the switcher above to view notices, track
                deadlines, and manage compliance workflows. Or enable
                cross-client mode to see everything you have access to.
            </p>
        </div>
    );
}

function EmptyNoticesState() {
    return (
        <div className="surface-card p-10 text-center">
            <div className="relative w-20 h-20 mx-auto mb-5">
                <div className="absolute inset-0 rounded-full bg-[var(--accent-soft)] blur-xl opacity-60" />
                <div className="relative w-full h-full rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center shadow-[var(--shadow-md)]">
                    <FiShield className="w-8 h-8 text-[var(--accent)]" />
                </div>
            </div>
            <h2 className="text-[18px] font-semibold text-[var(--text-primary)] mb-1.5">
                No notices yet
            </h2>
            <p className="text-[13.5px] text-[var(--text-muted)] mb-6 max-w-md mx-auto">
                Connect Gmail to auto-import compliance notices, or upload a
                PDF / image directly to start tracking it through the workflow.
            </p>
            <div className="flex items-center justify-center gap-2 flex-wrap">
                <Link
                    href="/dashboard/email/connect"
                    className="
                        inline-flex items-center gap-2 h-10 px-4 rounded-md
                        bg-[var(--accent)] hover:bg-[var(--accent-strong)]
                        text-[14px] font-medium text-white
                        transition-colors duration-150 cursor-pointer
                        shadow-sm
                    "
                >
                    <FiMail className="w-3.5 h-3.5" />
                    Connect Gmail
                </Link>
                <Link
                    href="/dashboard/compliance/notices/new"
                    className="
                        inline-flex items-center gap-2 h-10 px-4 rounded-md
                        border border-[var(--border-default)]
                        bg-[var(--bg-elevated)]
                        text-[14px] font-medium text-[var(--text-primary)]
                        hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                        transition-colors duration-150 cursor-pointer
                    "
                >
                    <FiUpload className="w-3.5 h-3.5" />
                    Upload first notice
                </Link>
            </div>
        </div>
    );
}

function NoticesErrorState({ onRetry }: { onRetry: () => void }) {
    return (
        <div className="surface-card p-10 text-center" role="alert">
            <div className="relative w-20 h-20 mx-auto mb-5">
                <div className="absolute inset-0 rounded-full bg-[var(--danger-soft)] blur-xl opacity-60" />
                <div className="relative w-full h-full rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center shadow-[var(--shadow-md)]">
                    <FiAlertTriangle className="w-8 h-8 text-[var(--danger)]" />
                </div>
            </div>
            <h2 className="text-[18px] font-semibold text-[var(--text-primary)] mb-1.5">
                Couldn&apos;t load notices
            </h2>
            <p className="text-[13.5px] text-[var(--text-muted)] mb-6 max-w-md mx-auto">
                Something went wrong fetching your notices. Your data is safe,
                this is likely a temporary connection issue.
            </p>
            <button
                type="button"
                onClick={onRetry}
                className="
                    inline-flex items-center gap-2 h-10 px-4 rounded-md
                    border border-[var(--border-default)]
                    bg-[var(--bg-elevated)]
                    text-[14px] font-medium text-[var(--text-primary)]
                    hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                    focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                    transition-colors duration-150 cursor-pointer
                "
            >
                Retry
            </button>
        </div>
    );
}
