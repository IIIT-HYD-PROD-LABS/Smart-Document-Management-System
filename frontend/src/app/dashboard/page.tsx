"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { documentsApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FiFileText, FiCheckCircle, FiClock, FiTrendingUp, FiUpload } from "react-icons/fi";
import Link from "next/link";

interface Stats {
    total_documents: number;
    category_distribution: Record<string, number>;
    status_distribution: Record<string, number>;
    recent_documents: any[];
}

const categoryColors: Record<string, string> = {
    bills: "from-blue-500 to-blue-700",
    upi: "from-violet-500 to-violet-700",
    tickets: "from-amber-500 to-amber-700",
    tax: "from-emerald-500 to-emerald-700",
    bank: "from-cyan-500 to-cyan-700",
    invoices: "from-rose-500 to-rose-700",
    unknown: "from-slate-500 to-slate-700",
};

const categoryEmoji: Record<string, string> = {
    bills: "🧾",
    upi: "💳",
    tickets: "🎫",
    tax: "📋",
    bank: "🏦",
    invoices: "📄",
    unknown: "❓",
};

export default function DashboardPage() {
    const { user } = useAuth();
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStats();
    }, []);

    const loadStats = async () => {
        try {
            const res = await documentsApi.getStats();
            setStats(res.data);
        } catch {
            setStats({ total_documents: 0, category_distribution: {}, status_distribution: {}, recent_documents: [] });
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

    const completed = stats?.status_distribution?.completed || 0;
    const pending = stats?.status_distribution?.pending || 0;
    const processing = stats?.status_distribution?.processing || 0;

    const summaryCards = [
        { label: "Total Documents", value: stats?.total_documents || 0, icon: FiFileText, color: "text-primary-400" },
        { label: "Classified", value: completed, icon: FiCheckCircle, color: "text-emerald-400" },
        { label: "Processing", value: processing + pending, icon: FiClock, color: "text-amber-400" },
        { label: "Categories", value: Object.keys(stats?.category_distribution || {}).length, icon: FiTrendingUp, color: "text-cyan-400" },
    ];

    return (
        <div>
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">
                    Welcome back, <span className="gradient-text">{user?.username}</span>
                </h1>
                <p className="text-slate-400 mt-1">Here&apos;s an overview of your document library</p>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
                {summaryCards.map((card, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 15 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.08 }}
                        className="glass-card p-5"
                    >
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-sm text-slate-400">{card.label}</span>
                            <card.icon className={`w-5 h-5 ${card.color}`} />
                        </div>
                        <p className="text-3xl font-bold text-white">{card.value}</p>
                    </motion.div>
                ))}
            </div>

            {/* Category Distribution */}
            <div className="glass-card p-6 mb-8">
                <h2 className="text-lg font-semibold text-white mb-5">Category Distribution</h2>
                {Object.keys(stats?.category_distribution || {}).length > 0 ? (
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
                        {Object.entries(stats?.category_distribution || {}).map(([cat, count]) => (
                            <div key={cat} className="text-center p-4 rounded-xl bg-white/[0.03] border border-slate-800 hover:border-primary-500/30 transition-all">
                                <div className="text-2xl mb-2">{categoryEmoji[cat] || "📄"}</div>
                                <p className="text-sm font-medium text-white capitalize">{cat}</p>
                                <p className="text-xl font-bold text-primary-400 mt-1">{count}</p>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-12">
                        <FiUpload className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                        <p className="text-slate-400">No documents yet</p>
                        <Link href="/dashboard/upload" className="btn-primary inline-flex items-center gap-2 mt-4 text-sm">
                            Upload Your First Document
                        </Link>
                    </div>
                )}
            </div>

            {/* Recent Documents */}
            <div className="glass-card p-6">
                <div className="flex items-center justify-between mb-5">
                    <h2 className="text-lg font-semibold text-white">Recent Documents</h2>
                    <Link href="/dashboard/documents" className="text-sm text-primary-400 hover:text-primary-300">
                        View All →
                    </Link>
                </div>
                {stats?.recent_documents && stats.recent_documents.length > 0 ? (
                    <div className="space-y-3">
                        {stats.recent_documents.slice(0, 5).map((doc: any) => (
                            <div
                                key={doc.id}
                                className="flex items-center gap-4 p-3 rounded-xl hover:bg-white/[0.02] transition-all"
                            >
                                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${categoryColors[doc.category] || categoryColors.unknown} flex items-center justify-center text-white text-lg`}>
                                    {categoryEmoji[doc.category] || "📄"}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-white truncate">{doc.original_filename}</p>
                                    <p className="text-xs text-slate-500 capitalize">{doc.category} • {doc.file_size ? `${(doc.file_size / 1024).toFixed(1)} KB` : ""}</p>
                                </div>
                                <span className={`text-xs px-2.5 py-1 rounded-full ${doc.status === "completed" ? "bg-emerald-500/10 text-emerald-400" :
                                        doc.status === "processing" ? "bg-amber-500/10 text-amber-400" :
                                            "bg-slate-500/10 text-slate-400"
                                    }`}>
                                    {doc.status}
                                </span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-sm text-slate-500 text-center py-6">No documents to show</p>
                )}
            </div>
        </div>
    );
}
