"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { FiBarChart2, FiPlay, FiClock, FiPieChart, FiDownload } from "react-icons/fi";
import { useCurrentClient } from "@/stores/currentClientStore";
import { complianceApi } from "@/lib/api/compliance";
import { AUTHORITY_CONFIG } from "@/components/compliance/AuthorityBadge";
import { STATUS_CONFIG } from "@/components/compliance/StatusPill";
import type {
    PenaltyByAuthorityRow,
    NoticeVolumeByStatusRow,
    ResponseTimeStats,
    Authority,
    NoticeStatus,
} from "@/types/compliance";

/**
 * Trigger a browser download for a Blob response. Common helper used by
 * every CSV export button on this page so we don't repeat the
 * createObjectURL → anchor.click → revoke ritual five times.
 */
function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

function todayStamp(): string {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}${mm}${dd}`;
}

const downloadButtonClass =
    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium bg-[#18181b] border border-[#27272a] text-[#a1a1aa] hover:text-white hover:border-[#3f3f46] disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6]/40";

/**
 * Reports — UI-SPEC §reports + CLIENT-07.
 *
 * Renders monthly health summary metrics structurally as React JSX. The
 * backend's `summary_html` string is shown inside a `<details><pre>` block
 * with `whitespace-pre-wrap` — never injected via React's raw-HTML prop.
 * This eliminates the XSS surface for backend-generated HTML even though
 * the source is currently trusted.
 */

interface HealthSummary {
    metrics: Record<string, number | string>;
    summary_html: string;
}

function currentMonth(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function ReportsPage() {
    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const [month, setMonth] = useState<string>(currentMonth());
    const [summary, setSummary] = useState<HealthSummary | null>(null);

    const generate = useMutation({
        mutationFn: async (): Promise<HealthSummary> => {
            if (activeClientId === null)
                throw new Error("Select a client first.");
            const res = await complianceApi.healthSummary({
                client_id: activeClientId,
                month: `${month}-01`,
            });
            return res.data as HealthSummary;
        },
        onSuccess: (data) => {
            setSummary(data);
            toast.success("Report generated");
        },
        onError: (err) =>
            toast.error(
                err instanceof Error ? err.message : "Could not generate report"
            ),
    });

    const downloadHealthSummary = useMutation({
        mutationFn: async () => {
            if (activeClientId === null)
                throw new Error("Select a client first.");
            const res = await complianceApi.exportHealthSummary({
                client_id: activeClientId,
                month: `${month}-01`,
            });
            const filename = `health_summary_${month.replace("-", "")}.csv`;
            downloadBlob(res.data, filename);
        },
        onSuccess: () => toast.success("CSV downloaded"),
        onError: (err) =>
            toast.error(
                err instanceof Error ? err.message : "Could not export report"
            ),
    });

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <header className="mb-6 flex items-start gap-3">
                <FiBarChart2
                    className="w-5 h-5 text-[#3b82f6] mt-0.5 shrink-0"
                    aria-hidden="true"
                />
                <div>
                    <h1 className="text-lg font-semibold text-white mb-0.5">
                        Reports
                    </h1>
                    <p className="text-[13px] text-[#71717a]">
                        Generate a monthly compliance health summary on demand.
                    </p>
                </div>
            </header>

            {activeClientId === null ? (
                <div className="bg-[#111113] border border-[#27272a] rounded-md p-12 text-center">
                    <h2 className="text-sm font-semibold text-white mb-1">
                        No client selected
                    </h2>
                    <p className="text-[13px] text-[#71717a]">
                        Select a client from the switcher to generate reports.
                    </p>
                </div>
            ) : (
                <>
                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            generate.mutate();
                        }}
                        className="bg-[#111113] border border-[#27272a] rounded-md p-4 mb-6 flex items-end gap-3 flex-wrap"
                    >
                        <div className="flex-1 min-w-[180px]">
                            <label
                                htmlFor="report-month"
                                className="block text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1.5"
                            >
                                Month
                            </label>
                            <input
                                id="report-month"
                                type="month"
                                value={month}
                                onChange={(e) => setMonth(e.target.value)}
                                required
                                className="w-full bg-[#18181b] border border-[#27272a] rounded px-2.5 py-1.5 text-[13px] text-white focus:outline-none focus:border-[#3f3f46] focus:ring-1 focus:ring-[#3b82f6]/40"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={generate.isPending}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#3b82f6] text-white text-[12px] font-medium hover:bg-[#2563eb] disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                        >
                            <FiPlay className="w-3.5 h-3.5" />
                            {generate.isPending ? "Generating…" : "Generate"}
                        </button>
                        <button
                            type="button"
                            onClick={() => downloadHealthSummary.mutate()}
                            disabled={downloadHealthSummary.isPending}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#18181b] border border-[#27272a] text-white text-[12px] font-medium hover:border-[#3f3f46] disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                            title="Download monthly summary as CSV"
                        >
                            <FiDownload className="w-3.5 h-3.5" />
                            {downloadHealthSummary.isPending ? "Downloading…" : "Download CSV"}
                        </button>
                    </form>

                    {summary && (
                        <div className="bg-[#111113] border border-[#27272a] rounded-md p-6">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                                {Object.entries(summary.metrics).map(
                                    ([k, v]) => (
                                        <div
                                            key={k}
                                            className="bg-[#18181b] rounded p-4"
                                        >
                                            <div className="text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1">
                                                {k.replace(/_/g, " ")}
                                            </div>
                                            <div className="text-2xl font-semibold text-white tabular-nums">
                                                {v}
                                            </div>
                                        </div>
                                    )
                                )}
                            </div>
                            <details className="border-t border-[#27272a] pt-4">
                                <summary className="text-[11px] uppercase tracking-wider text-[#a1a1aa] cursor-pointer hover:text-white focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 rounded">
                                    Raw HTML (debug)
                                </summary>
                                <pre className="mt-2 text-xs text-[#71717a] font-mono whitespace-pre-wrap bg-[#18181b] rounded p-3 overflow-x-auto">
                                    {summary.summary_html}
                                </pre>
                            </details>
                        </div>
                    )}

                    {/* Phase 13 — analytics aggregations */}
                    <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <PenaltyByAuthorityCard />
                        <ResponseTimeCard />
                        <NoticeVolumeCard />
                    </div>
                </>
            )}
        </div>
    );
}

function PenaltyByAuthorityCard() {
    const q = useQuery({
        queryKey: ["report-penalty-by-authority"],
        queryFn: async () => {
            const { data } = await complianceApi.penaltyByAuthority(90);
            return data;
        },
    });
    const rows = q.data ?? [];
    const total = rows.reduce((sum, r) => sum + r.total_penalty, 0);

    const onDownload = async () => {
        try {
            const res = await complianceApi.exportPenaltyByAuthority(90);
            downloadBlob(res.data, `penalty_by_authority_${todayStamp()}.csv`);
            toast.success("CSV downloaded");
        } catch {
            toast.error("Download failed");
        }
    };

    return (
        <div className="bg-[#111113] border border-[#27272a] rounded-md p-5">
            <div className="flex items-center justify-between mb-3 gap-2">
                <div className="flex items-center gap-2">
                    <FiPieChart className="w-4 h-4 text-[#ec4899]" />
                    <h2 className="text-[13px] font-semibold text-white">
                        Penalty by authority — last 90 days
                    </h2>
                </div>
                <button
                    type="button"
                    onClick={onDownload}
                    disabled={rows.length === 0}
                    className={downloadButtonClass}
                    title="Download as CSV"
                >
                    <FiDownload className="w-3 h-3" />
                    CSV
                </button>
            </div>
            {q.isLoading && <div className="h-24 bg-[#18181b] rounded animate-pulse" />}
            {!q.isLoading && rows.length === 0 && (
                <p className="text-[12px] text-[#71717a]">No notices in window.</p>
            )}
            {rows.length > 0 && (
                <div className="space-y-2">
                    {rows.map((r: PenaltyByAuthorityRow) => {
                        const auth = r.authority as Authority;
                        const cfg = AUTHORITY_CONFIG[auth];
                        const pct = total > 0 ? (r.total_penalty / total) * 100 : 0;
                        return (
                            <div key={r.authority} className="space-y-1">
                                <div className="flex items-center justify-between text-[12px]">
                                    <span style={{ color: cfg?.color }}>
                                        {cfg?.label ?? r.authority}
                                    </span>
                                    <span className="text-[#a1a1aa] tabular-nums">
                                        ₹{r.total_penalty.toLocaleString("en-IN")} ({r.count})
                                    </span>
                                </div>
                                <div className="h-1.5 rounded bg-[#18181b] overflow-hidden">
                                    <div
                                        className="h-full"
                                        style={{
                                            width: `${pct}%`,
                                            backgroundColor: cfg?.color ?? "#3b82f6",
                                        }}
                                    />
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

function NoticeVolumeCard() {
    const q = useQuery({
        queryKey: ["report-notice-volume"],
        queryFn: async () => {
            const { data } = await complianceApi.noticeVolumeByStatus(90);
            return data;
        },
    });
    const rows = q.data ?? [];
    const total = rows.reduce((sum, r) => sum + r.count, 0);

    const onDownload = async () => {
        try {
            const res = await complianceApi.exportNoticeVolumeByStatus(90);
            downloadBlob(res.data, `notice_volume_by_status_${todayStamp()}.csv`);
            toast.success("CSV downloaded");
        } catch {
            toast.error("Download failed");
        }
    };

    return (
        <div className="bg-[#111113] border border-[#27272a] rounded-md p-5">
            <div className="flex items-center justify-between mb-3 gap-2">
                <div className="flex items-center gap-2">
                    <FiBarChart2 className="w-4 h-4 text-[#3b82f6]" />
                    <h2 className="text-[13px] font-semibold text-white">
                        Notice volume by status — last 90 days
                    </h2>
                </div>
                <button
                    type="button"
                    onClick={onDownload}
                    disabled={total === 0}
                    className={downloadButtonClass}
                    title="Download as CSV"
                >
                    <FiDownload className="w-3 h-3" />
                    CSV
                </button>
            </div>
            {q.isLoading && <div className="h-24 bg-[#18181b] rounded animate-pulse" />}
            {!q.isLoading && total === 0 && (
                <p className="text-[12px] text-[#71717a]">No notices in window.</p>
            )}
            {total > 0 && (
                <div className="space-y-2">
                    {rows.map((r: NoticeVolumeByStatusRow) => {
                        const cfg = STATUS_CONFIG[r.status as NoticeStatus];
                        const pct = (r.count / total) * 100;
                        return (
                            <div key={r.status} className="space-y-1">
                                <div className="flex items-center justify-between text-[12px]">
                                    <span style={{ color: cfg?.color }}>
                                        {cfg?.label ?? r.status}
                                    </span>
                                    <span className="text-[#a1a1aa] tabular-nums">
                                        {r.count} ({pct.toFixed(0)}%)
                                    </span>
                                </div>
                                <div className="h-1.5 rounded bg-[#18181b] overflow-hidden">
                                    <div
                                        className="h-full"
                                        style={{
                                            width: `${pct}%`,
                                            backgroundColor: cfg?.color ?? "#71717a",
                                        }}
                                    />
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

function ResponseTimeCard() {
    const q = useQuery<ResponseTimeStats>({
        queryKey: ["report-response-time"],
        queryFn: async () => {
            const { data } = await complianceApi.responseTimeDistribution(90);
            return data;
        },
    });

    const stats = q.data;

    const onDownload = async () => {
        try {
            const res = await complianceApi.exportResponseTime(90);
            downloadBlob(res.data, `response_time_distribution_${todayStamp()}.csv`);
            toast.success("CSV downloaded");
        } catch {
            toast.error("Download failed");
        }
    };

    return (
        <div className="bg-[#111113] border border-[#27272a] rounded-md p-5">
            <div className="flex items-center justify-between mb-3 gap-2">
                <div className="flex items-center gap-2">
                    <FiClock className="w-4 h-4 text-[#10b981]" />
                    <h2 className="text-[13px] font-semibold text-white">
                        Response time — last 90 days
                    </h2>
                </div>
                <button
                    type="button"
                    onClick={onDownload}
                    disabled={!stats || stats.count === 0}
                    className={downloadButtonClass}
                    title="Download as CSV"
                >
                    <FiDownload className="w-3 h-3" />
                    CSV
                </button>
            </div>
            {q.isLoading && <div className="h-24 bg-[#18181b] rounded animate-pulse" />}
            {stats && stats.count === 0 && (
                <p className="text-[12px] text-[#71717a]">
                    No resolved/submitted notices in window.
                </p>
            )}
            {stats && stats.count > 0 && (
                <div className="grid grid-cols-2 gap-3">
                    {[
                        { label: "p50 (median)", value: stats.p50 },
                        { label: "p90", value: stats.p90 },
                        { label: "p95", value: stats.p95 },
                        { label: "mean", value: stats.mean },
                    ].map((m) => (
                        <div key={m.label} className="bg-[#18181b] rounded p-3">
                            <div className="text-[10px] uppercase tracking-wider text-[#a1a1aa] mb-1">
                                {m.label}
                            </div>
                            <div className="text-lg font-semibold text-white tabular-nums">
                                {m.value.toFixed(1)}
                                <span className="text-[11px] text-[#71717a] ml-1">days</span>
                            </div>
                        </div>
                    ))}
                    <div className="col-span-2 text-[11px] text-[#71717a] text-right">
                        based on {stats.count} resolved/submitted notices
                    </div>
                </div>
            )}
        </div>
    );
}
