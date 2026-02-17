"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { documentsApi } from "@/lib/api";
import { FiPieChart, FiBarChart2 } from "react-icons/fi";

const categoryColors: Record<string, string> = {
    bills: "#3b82f6",
    upi: "#8b5cf6",
    tickets: "#f59e0b",
    tax: "#22c55e",
    bank: "#06b6d4",
    invoices: "#f43f5e",
    unknown: "#64748b",
};

export default function AnalyticsPage() {
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStats();
    }, []);

    const loadStats = async () => {
        try {
            const res = await documentsApi.getStats();
            setStats(res.data);
        } catch {
            setStats(null);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="w-8 h-8 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
            </div>
        );
    }

    const totalDocs = stats?.total_documents || 0;
    const catDist = stats?.category_distribution || {};
    const statusDist = stats?.status_distribution || {};
    const maxCatCount = Math.max(...Object.values(catDist).map(Number), 1);

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Analytics</h1>
                <p className="text-slate-400 mt-1">Insights into your document library</p>
            </div>

            {/* Overall Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 text-center">
                    <p className="text-4xl font-bold gradient-text mb-1">{totalDocs}</p>
                    <p className="text-sm text-slate-400">Total Documents</p>
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card p-6 text-center">
                    <p className="text-4xl font-bold text-emerald-400 mb-1">{statusDist.completed || 0}</p>
                    <p className="text-sm text-slate-400">Classified</p>
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-card p-6 text-center">
                    <p className="text-4xl font-bold text-amber-400 mb-1">{Object.keys(catDist).length}</p>
                    <p className="text-sm text-slate-400">Categories Used</p>
                </motion.div>
            </div>

            {/* Category Breakdown */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="glass-card p-6">
                    <div className="flex items-center gap-2 mb-5">
                        <FiBarChart2 className="w-5 h-5 text-primary-400" />
                        <h2 className="text-lg font-semibold text-white">Category Distribution</h2>
                    </div>
                    {Object.keys(catDist).length > 0 ? (
                        <div className="space-y-4">
                            {Object.entries(catDist)
                                .sort(([, a], [, b]) => Number(b) - Number(a))
                                .map(([cat, count], i) => (
                                    <motion.div
                                        key={cat}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: i * 0.05 }}
                                    >
                                        <div className="flex items-center justify-between mb-1.5">
                                            <span className="text-sm text-slate-300 capitalize">{cat}</span>
                                            <span className="text-sm font-medium text-white">{String(count)}</span>
                                        </div>
                                        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${(Number(count) / maxCatCount) * 100}%` }}
                                                transition={{ duration: 0.8, delay: i * 0.1 }}
                                                className="h-full rounded-full"
                                                style={{ backgroundColor: categoryColors[cat] || "#6366f1" }}
                                            />
                                        </div>
                                    </motion.div>
                                ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-500 text-center py-8">No data available</p>
                    )}
                </div>

                {/* Status Breakdown */}
                <div className="glass-card p-6">
                    <div className="flex items-center gap-2 mb-5">
                        <FiPieChart className="w-5 h-5 text-primary-400" />
                        <h2 className="text-lg font-semibold text-white">Processing Status</h2>
                    </div>
                    <div className="space-y-4">
                        {[
                            { key: "completed", label: "Completed", color: "#22c55e" },
                            { key: "processing", label: "Processing", color: "#f59e0b" },
                            { key: "pending", label: "Pending", color: "#64748b" },
                            { key: "failed", label: "Failed", color: "#ef4444" },
                        ].map((s, i) => {
                            const val = statusDist[s.key] || 0;
                            const pct = totalDocs > 0 ? (val / totalDocs) * 100 : 0;
                            return (
                                <motion.div
                                    key={s.key}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: i * 0.1 }}
                                >
                                    <div className="flex items-center justify-between mb-1.5">
                                        <div className="flex items-center gap-2">
                                            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                                            <span className="text-sm text-slate-300">{s.label}</span>
                                        </div>
                                        <span className="text-sm text-white font-medium">{val} ({pct.toFixed(0)}%)</span>
                                    </div>
                                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${pct}%` }}
                                            transition={{ duration: 0.8, delay: i * 0.15 }}
                                            className="h-full rounded-full"
                                            style={{ backgroundColor: s.color }}
                                        />
                                    </div>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}
