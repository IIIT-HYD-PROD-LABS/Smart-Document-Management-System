"use client";

import { useEffect } from "react";
import toast from "react-hot-toast";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { documentsApi } from "@/lib/api";
import { LoadingSpinner, Skeleton } from "@/components";

const TrendsChart = dynamic(() => import("@/components/analytics/TrendsChart"), {
    ssr: false,
    loading: () => (
        <div className="h-64 flex items-center justify-center">
            <LoadingSpinner />
        </div>
    ),
});

const CategoryDonut = dynamic(
    () => import("@/components/analytics/TrendsChart").then((m) => m.CategoryDonut),
    {
        ssr: false,
        loading: () => (
            <div className="h-56 flex items-center justify-center">
                <LoadingSpinner />
            </div>
        ),
    },
);

interface TrendPoint {
    month: string;
    count: number;
}

interface TrendsResponse {
    trends: TrendPoint[];
}

interface Stats {
    total_documents: number;
    category_counts: Record<string, number>;
    processing_count: number;
    completed_count: number;
    failed_count: number;
}

export default function AnalyticsPage() {
    const statsQ = useQuery<Stats>({
        queryKey: ["docs", "stats"],
        queryFn: () => documentsApi.getStats().then((r) => r.data),
        staleTime: 5 * 60_000,
    });
    const trendsQ = useQuery<TrendsResponse>({
        queryKey: ["docs", "trends", 12],
        queryFn: () => documentsApi.getTrends(12).then((r) => r.data),
        staleTime: 5 * 60_000,
    });

    const loading = statsQ.isLoading || trendsQ.isLoading;
    const isError = statsQ.isError || trendsQ.isError;

    useEffect(() => {
        if (isError) toast.error("Failed to load analytics");
    }, [isError]);

    if (loading) {
        // Mirror the real layout (header + 4 stat cards + trends chart + the
        // two-up donut/status row) so the 2-3s cold fetch against the remote
        // DB reads as "this page is arriving", not a spinner on a blank area.
        return (
            <div role="status" aria-busy="true" aria-live="polite">
                <span className="sr-only">Loading analytics</span>
                <div className="mb-8">
                    <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Analytics</h1>
                    <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>Insights into your document library</p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-[92px]" />
                    ))}
                </div>
                <Skeleton className="h-[268px] mb-4" />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <Skeleton className="h-[248px]" />
                    <Skeleton className="h-[248px]" />
                </div>
            </div>
        );
    }

    const stats = statsQ.data ?? null;
    const trends = trendsQ.data?.trends ?? [];

    const total = stats?.total_documents ?? 0;
    const processing = stats?.processing_count ?? 0;
    const completed = stats?.completed_count ?? 0;
    const failed = stats?.failed_count ?? 0;
    const pending = Math.max(total - completed - processing - failed, 0);
    const catCounts = stats?.category_counts ?? {};

    if (total === 0 && trends.length === 0) {
        return (
            <div>
                <div className="mb-8">
                    <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Analytics</h1>
                    <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>Insights into your document library</p>
                </div>
                <div className="flex flex-col items-center justify-center py-24 text-center">
                    <div
                        className="w-12 h-12 rounded-full flex items-center justify-center mb-4 border"
                        style={{
                            background: "var(--bg-muted)",
                            borderColor: "var(--border-default)",
                        }}
                    >
                        <svg
                            className="w-6 h-6"
                            style={{ color: "var(--text-muted)" }}
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={1.5}
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                        </svg>
                    </div>
                    <h2 className="text-sm font-semibold mb-1" style={{ color: "var(--text-primary)" }}>No documents yet</h2>
                    <p className="text-xs max-w-xs" style={{ color: "var(--text-muted)" }}>
                        Upload some documents to see analytics and trends here.
                    </p>
                </div>
            </div>
        );
    }

    const trendData = trends.map((t) => {
        const [year, mon] = t.month.split("-");
        const d = new Date(Number(year), Number(mon) - 1);
        return {
            month: d.toLocaleString("default", { month: "short" }),
            count: t.count,
        };
    });

    const pieData = Object.entries(catCounts)
        .filter(([, count]) => count > 0)
        .map(([name, value]) => ({ name, value }));

    // Semantic tokens for status segments — track the active theme.
    const statusSegments = [
        { label: "Completed",  value: completed,  color: "var(--success)" },
        { label: "Processing", value: processing, color: "var(--warning)" },
        { label: "Pending",    value: pending,    color: "var(--text-subtle)" },
        { label: "Failed",     value: failed,     color: "var(--danger)" },
    ];

    const statCards = [
        { label: "Total Documents", value: total,      color: "var(--text-primary)" },
        { label: "Processing",      value: processing, color: "var(--warning)" },
        { label: "Completed",       value: completed,  color: "var(--success)" },
        { label: "Failed",          value: failed,     color: "var(--danger)" },
    ];

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Analytics</h1>
                <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>Insights into your document library</p>
            </div>

            {/* Stat Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                {statCards.map((card) => (
                    <div
                        key={card.label}
                        className="rounded-lg p-5 text-center border"
                        style={{
                            background: "var(--bg-elevated)",
                            borderColor: "var(--border-default)",
                            boxShadow: "var(--shadow-sm)",
                        }}
                    >
                        <p className="text-2xl font-semibold tabular-nums" style={{ color: card.color }}>{card.value}</p>
                        <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{card.label}</p>
                    </div>
                ))}
            </div>

            {/* Upload Trends */}
            <div
                className="rounded-lg p-5 mb-4 border"
                style={{
                    background: "var(--bg-elevated)",
                    borderColor: "var(--border-default)",
                    boxShadow: "var(--shadow-sm)",
                }}
            >
                <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Upload Trends</h2>
                <TrendsChart data={trendData} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Category Distribution - Donut Chart */}
                <div
                    className="rounded-lg p-5 border"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Category Distribution</h2>
                    <CategoryDonut data={pieData} />
                </div>

                {/* Processing Status - Horizontal Segmented Bar */}
                <div
                    className="rounded-lg p-5 border"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Processing Status</h2>

                    {total > 0 ? (
                        <>
                            <div
                                className="flex h-4 rounded-full overflow-hidden mb-6 border"
                                style={{
                                    background: "var(--bg-muted)",
                                    borderColor: "var(--border-default)",
                                }}
                            >
                                {statusSegments
                                    .filter((s) => s.value > 0)
                                    .map((s) => (
                                        <div
                                            key={s.label}
                                            className="h-full transition-all duration-500"
                                            style={{
                                                width: `${(s.value / total) * 100}%`,
                                                backgroundColor: s.color,
                                            }}
                                            title={`${s.label}: ${s.value}`}
                                        />
                                    ))}
                            </div>

                            <div className="space-y-3">
                                {statusSegments.map((s) => {
                                    const pct = total > 0 ? (s.value / total) * 100 : 0;
                                    return (
                                        <div key={s.label} className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <div
                                                    className="w-2 h-2 rounded-full"
                                                    style={{ backgroundColor: s.color }}
                                                />
                                                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{s.label}</span>
                                            </div>
                                            <span className="text-xs font-medium tabular-nums" style={{ color: "var(--text-primary)" }}>
                                                {s.value} ({pct.toFixed(0)}%)
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </>
                    ) : (
                        <p className="text-xs text-center py-8" style={{ color: "var(--text-muted)" }}>No data</p>
                    )}
                </div>
            </div>
        </div>
    );
}
