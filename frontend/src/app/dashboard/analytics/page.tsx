"use client";

import { useEffect, useState } from "react";
import { documentsApi } from "@/lib/api";

const categoryColors: Record<string, string> = {
    bills: "#3b82f6", upi: "#8b5cf6", tickets: "#f59e0b",
    tax: "#10b981", bank: "#06b6d4", invoices: "#f43f5e", unknown: "#71717a",
};

export default function AnalyticsPage() {
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        documentsApi.getStats()
            .then((res) => setStats(res.data))
            .catch(() => setStats(null))
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin" />
            </div>
        );
    }

    const total = stats?.total_documents || 0;
    const catCounts = stats?.category_counts || {};
    const completed = stats?.completed_count || 0;
    const processing = stats?.processing_count || 0;
    const failed = stats?.failed_count || 0;
    const pending = total - completed - processing - failed;
    const maxCat = Math.max(...Object.values(catCounts).map(Number), 1);

    const statuses = [
        { label: "Completed", value: completed, color: "#10b981" },
        { label: "Processing", value: processing, color: "#f59e0b" },
        { label: "Pending", value: pending > 0 ? pending : 0, color: "#71717a" },
        { label: "Failed", value: failed, color: "#ef4444" },
    ];

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold text-white">Analytics</h1>
                <p className="text-sm text-[#52525b] mt-1">Insights into your document library</p>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-5 text-center">
                    <p className="text-2xl font-semibold text-white">{total}</p>
                    <p className="text-xs text-[#71717a] mt-1">Total Documents</p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-5 text-center">
                    <p className="text-2xl font-semibold text-[#10b981]">{completed}</p>
                    <p className="text-xs text-[#71717a] mt-1">Classified</p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-5 text-center">
                    <p className="text-2xl font-semibold text-[#a1a1aa]">{Object.keys(catCounts).length}</p>
                    <p className="text-xs text-[#71717a] mt-1">Categories</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-5">
                    <h2 className="text-sm font-medium text-white mb-4">Category Distribution</h2>
                    {Object.keys(catCounts).length > 0 ? (
                        <div className="space-y-3">
                            {Object.entries(catCounts)
                                .sort(([, a], [, b]) => Number(b) - Number(a))
                                .map(([cat, count]) => (
                                    <div key={cat}>
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-xs text-[#a1a1aa] capitalize">{cat}</span>
                                            <span className="text-xs font-medium text-white">{String(count)}</span>
                                        </div>
                                        <div className="h-1.5 bg-[#1f1f23] rounded-full overflow-hidden">
                                            <div
                                                className="h-full rounded-full transition-all duration-500"
                                                style={{
                                                    width: `${(Number(count) / maxCat) * 100}%`,
                                                    backgroundColor: categoryColors[cat] || "#71717a",
                                                }}
                                            />
                                        </div>
                                    </div>
                                ))}
                        </div>
                    ) : (
                        <p className="text-xs text-[#52525b] text-center py-8">No data</p>
                    )}
                </div>

                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-5">
                    <h2 className="text-sm font-medium text-white mb-4">Processing Status</h2>
                    <div className="space-y-3">
                        {statuses.map((s) => {
                            const pct = total > 0 ? (s.value / total) * 100 : 0;
                            return (
                                <div key={s.label}>
                                    <div className="flex items-center justify-between mb-1">
                                        <div className="flex items-center gap-2">
                                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                                            <span className="text-xs text-[#a1a1aa]">{s.label}</span>
                                        </div>
                                        <span className="text-xs text-white font-medium">{s.value} ({pct.toFixed(0)}%)</span>
                                    </div>
                                    <div className="h-1.5 bg-[#1f1f23] rounded-full overflow-hidden">
                                        <div
                                            className="h-full rounded-full transition-all duration-500"
                                            style={{ width: `${pct}%`, backgroundColor: s.color }}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}
