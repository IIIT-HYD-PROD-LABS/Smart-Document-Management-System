"use client";

import { useEffect, useState } from "react";
import { documentsApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FiFileText, FiCheckCircle, FiClock, FiArrowRight } from "react-icons/fi";
import Link from "next/link";

const categoryLabels: Record<string, string> = {
    bills: "Bills", upi: "UPI", tickets: "Tickets",
    tax: "Tax", bank: "Bank", invoices: "Invoices", unknown: "Unknown",
};

export default function DashboardPage() {
    const { user } = useAuth();
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
    const completed = stats?.completed_count || 0;
    const processing = (stats?.processing_count || 0);
    const catCounts = stats?.category_counts || {};
    const recent = stats?.recent_uploads || [];

    const cards = [
        { label: "Total", value: total, icon: FiFileText, color: "text-[#a1a1aa]" },
        { label: "Classified", value: completed, icon: FiCheckCircle, color: "text-[#10b981]" },
        { label: "Processing", value: processing, icon: FiClock, color: "text-[#f59e0b]" },
    ];

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold text-white">Welcome back, {user?.username}</h1>
                <p className="text-sm text-[#52525b] mt-1">Overview of your document library</p>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-8">
                {cards.map((c, i) => (
                    <div key={i} className="bg-[#111113] border border-[#27272a] rounded-lg p-5">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs text-[#71717a] uppercase tracking-wider">{c.label}</span>
                            <c.icon className={`w-4 h-4 ${c.color}`} />
                        </div>
                        <p className="text-2xl font-semibold text-white">{c.value}</p>
                    </div>
                ))}
            </div>

            {/* Category breakdown */}
            {Object.keys(catCounts).length > 0 && (
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-5 mb-8">
                    <h2 className="text-sm font-medium text-white mb-4">Categories</h2>
                    <div className="flex flex-wrap gap-3">
                        {Object.entries(catCounts).map(([cat, count]) => (
                            <div key={cat} className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#18181b] border border-[#27272a]">
                                <span className="text-xs text-[#a1a1aa]">{categoryLabels[cat] || cat}</span>
                                <span className="text-xs font-medium text-white">{String(count)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Recent documents */}
            <div className="bg-[#111113] border border-[#27272a] rounded-lg">
                <div className="flex items-center justify-between px-5 py-4 border-b border-[#1f1f23]">
                    <h2 className="text-sm font-medium text-white">Recent documents</h2>
                    <Link href="/dashboard/documents" className="text-xs text-[#71717a] hover:text-[#a1a1aa] flex items-center gap-1 transition-colors">
                        View all <FiArrowRight className="w-3 h-3" />
                    </Link>
                </div>
                {recent.length > 0 ? (
                    <div className="divide-y divide-[#1f1f23]">
                        {recent.slice(0, 5).map((doc: any) => (
                            <div key={doc.id} className="flex items-center gap-4 px-5 py-3">
                                <FiFileText className="w-4 h-4 text-[#52525b] shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-white truncate">{doc.original_filename}</p>
                                    <p className="text-xs text-[#52525b]">
                                        {doc.category} {doc.confidence_score ? `· ${(doc.confidence_score * 100).toFixed(0)}%` : ""}
                                    </p>
                                </div>
                                <span className={`text-[11px] px-2 py-0.5 rounded ${
                                    doc.status === "completed" ? "bg-[#10b981]/10 text-[#10b981]" :
                                    doc.status === "processing" ? "bg-[#f59e0b]/10 text-[#f59e0b]" :
                                    "bg-[#27272a] text-[#71717a]"
                                }`}>
                                    {doc.status}
                                </span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-12">
                        <p className="text-sm text-[#52525b] mb-3">No documents yet</p>
                        <Link href="/dashboard/upload" className="text-xs text-[#10b981] hover:text-[#34d399] transition-colors">
                            Upload your first document
                        </Link>
                    </div>
                )}
            </div>
        </div>
    );
}
