"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { documentsApi } from "@/lib/api";
import { LoadingSpinner } from "@/components";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
} from "recharts";

// Light-theme calibrated category palette — deeper saturations for AA on white.
const CATEGORY_COLORS: Record<string, string> = {
    bills:    "#047857",
    upi:      "#6d28d9",
    tickets:  "#b45309",
    tax:      "#1d4ed8",
    bank:     "#0e7490",
    invoices: "#be185d",
    unknown:  "#71717a",
};

interface TrendPoint {
    month: string;
    count: number;
}

interface Stats {
    total_documents: number;
    category_counts: Record<string, number>;
    processing_count: number;
    completed_count: number;
    failed_count: number;
}

export default function AnalyticsPage() {
    const [stats, setStats] = useState<Stats | null>(null);
    const [trends, setTrends] = useState<TrendPoint[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            documentsApi.getStats(),
            documentsApi.getTrends(12),
        ])
            .then(([statsRes, trendsRes]) => {
                setStats(statsRes.data);
                setTrends(trendsRes.data.trends ?? []);
            })
            .catch(() => {
                setStats(null);
                setTrends([]);
                toast.error("Failed to load analytics");
            })
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <LoadingSpinner />
            </div>
        );
    }

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

    // Light-theme semantic colors for status segments
    const statusSegments = [
        { label: "Completed",  value: completed,  color: "#047857" },
        { label: "Processing", value: processing, color: "#b45309" },
        { label: "Pending",    value: pending,    color: "#71717a" },
        { label: "Failed",     value: failed,     color: "#b91c1c" },
    ];

    const statCards = [
        { label: "Total Documents", value: total,      color: "var(--text-primary)" },
        { label: "Processing",      value: processing, color: "var(--warning)" },
        { label: "Completed",       value: completed,  color: "var(--success)" },
        { label: "Failed",          value: failed,     color: "var(--danger)" },
    ];

    // Recharts tooltip uses a div with inline style; pull tokens at runtime.
    const tooltipStyle = {
        backgroundColor: "var(--bg-elevated)",
        border: "1px solid var(--border-default)",
        borderRadius: "8px",
        color: "var(--text-primary)",
        fontSize: 12,
        boxShadow: "var(--shadow-md)",
    };

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
                {trendData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={260}>
                        <AreaChart data={trendData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                            <defs>
                                <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#2563eb" stopOpacity={0.18} />
                                    <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                            <XAxis
                                dataKey="month"
                                tick={{ fill: "#71717a", fontSize: 12 }}
                                axisLine={{ stroke: "#e4e4e7" }}
                                tickLine={false}
                            />
                            <YAxis
                                allowDecimals={false}
                                tick={{ fill: "#71717a", fontSize: 12 }}
                                axisLine={{ stroke: "#e4e4e7" }}
                                tickLine={false}
                            />
                            <Tooltip
                                contentStyle={tooltipStyle}
                                labelStyle={{ color: "#52525b" }}
                                cursor={{ stroke: "#d4d4d8", strokeDasharray: "3 3" }}
                            />
                            <Area
                                type="monotone"
                                dataKey="count"
                                stroke="#2563eb"
                                strokeWidth={2}
                                fill="url(#trendGradient)"
                                name="Uploads"
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                ) : (
                    <p className="text-xs text-center py-8" style={{ color: "var(--text-muted)" }}>No trend data available</p>
                )}
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
                    {pieData.length > 0 ? (
                        <div className="flex flex-col items-center">
                            <ResponsiveContainer width="100%" height={220}>
                                <PieChart>
                                    <Pie
                                        data={pieData}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={60}
                                        outerRadius={90}
                                        dataKey="value"
                                        paddingAngle={2}
                                    >
                                        {pieData.map((entry) => (
                                            <Cell
                                                key={entry.name}
                                                fill={CATEGORY_COLORS[entry.name] ?? "#71717a"}
                                                stroke="#ffffff"
                                                strokeWidth={2}
                                            />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={tooltipStyle}
                                        formatter={(value: number, name: string) => [value, name]}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
                                {pieData.map((entry) => (
                                    <div key={entry.name} className="flex items-center gap-1.5">
                                        <div
                                            className="w-2 h-2 rounded-full"
                                            style={{ backgroundColor: CATEGORY_COLORS[entry.name] ?? "#71717a" }}
                                        />
                                        <span className="text-xs capitalize" style={{ color: "var(--text-secondary)" }}>{entry.name}</span>
                                        <span className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>{entry.value}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <p className="text-xs text-center py-8" style={{ color: "var(--text-muted)" }}>No data</p>
                    )}
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
