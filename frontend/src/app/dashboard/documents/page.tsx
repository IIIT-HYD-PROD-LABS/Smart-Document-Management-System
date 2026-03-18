"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { documentsApi } from "@/lib/api";
import { FiFileText, FiTrash2, FiFilter, FiCheckSquare, FiSquare, FiX } from "react-icons/fi";
import toast from "react-hot-toast";

const categories = ["all", "bills", "upi", "tickets", "tax", "bank", "invoices", "unknown"];

function ConfidenceBadge({ score }: { score: number }) {
    if (score <= 0) return null;
    const pct = Math.round(score * 100);
    let colorClass: string;
    let label: string;
    if (score >= 0.8) {
        colorClass = "bg-[#10b981]/10 text-[#10b981]";
        label = "High";
    } else if (score >= 0.5) {
        colorClass = "bg-[#f59e0b]/10 text-[#f59e0b]";
        label = "Medium";
    } else {
        colorClass = "bg-[#ef4444]/10 text-[#ef4444]";
        label = "Low";
    }
    return (
        <span className={`text-[11px] px-2 py-0.5 rounded ${colorClass}`} title={`${label} confidence`}>
            {pct}%
        </span>
    );
}

export default function DocumentsPage() {
    const router = useRouter();
    const [docs, setDocs] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [deleting, setDeleting] = useState(false);

    useEffect(() => {
        loadDocs();
    }, []);

    const loadDocs = async () => {
        try {
            const res = await documentsApi.getAll();
            setDocs(res.data.documents || []);
        } catch {
            setDocs([]);
            toast.error("Something went wrong");
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        try {
            await documentsApi.delete(id);
            setDocs((prev) => prev.filter((d) => d.id !== id));
            setSelected((prev) => { const next = new Set(prev); next.delete(id); return next; });
        } catch { toast.error("Something went wrong"); }
    };

    const handleBatchDelete = async () => {
        if (selected.size === 0) return;
        setDeleting(true);
        try {
            const ids = Array.from(selected);
            await documentsApi.batchDelete(ids);
            setDocs((prev) => prev.filter((d) => !selected.has(d.id)));
            setSelected(new Set());
        } catch { toast.error("Something went wrong"); }
        setDeleting(false);
    };

    const toggleSelect = (id: number, e: React.MouseEvent) => {
        e.stopPropagation();
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const filtered = filter === "all" ? docs : docs.filter((d) => d.category === filter);

    const toggleSelectAll = () => {
        if (selected.size === filtered.length) {
            setSelected(new Set());
        } else {
            setSelected(new Set(filtered.map((d) => d.id)));
        }
    };

    const isSelectMode = selected.size > 0;

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-lg font-semibold text-white">Documents</h1>
                    <p className="text-sm text-[#52525b] mt-1">{docs.length} document{docs.length !== 1 ? "s" : ""} in your library</p>
                </div>
            </div>

            {/* Bulk action bar */}
            {isSelectMode && (
                <div className="flex items-center gap-3 mb-4 px-4 py-3 bg-[#18181b] border border-[#3f3f46] rounded-lg">
                    <button
                        onClick={toggleSelectAll}
                        className="flex items-center gap-2 text-xs text-[#a1a1aa] hover:text-white transition-colors cursor-pointer"
                    >
                        {selected.size === filtered.length
                            ? <FiCheckSquare className="w-4 h-4 text-[#3b82f6]" />
                            : <FiSquare className="w-4 h-4" />}
                        {selected.size === filtered.length ? "Deselect all" : "Select all"}
                    </button>
                    <span className="text-xs text-[#52525b]">|</span>
                    <span className="text-xs text-white">{selected.size} selected</span>
                    <div className="flex-1" />
                    <button
                        onClick={handleBatchDelete}
                        disabled={deleting}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#ef4444]/10 text-[#ef4444] rounded-md hover:bg-[#ef4444]/20 disabled:opacity-50 transition-colors cursor-pointer"
                    >
                        <FiTrash2 className="w-3.5 h-3.5" />
                        {deleting ? "Deleting..." : `Delete ${selected.size}`}
                    </button>
                    <button
                        onClick={() => setSelected(new Set())}
                        className="text-[#52525b] hover:text-white transition-colors cursor-pointer"
                    >
                        <FiX className="w-4 h-4" />
                    </button>
                </div>
            )}

            <div className="flex items-center gap-1.5 mb-6">
                <FiFilter className="w-3.5 h-3.5 text-[#52525b] mr-1" />
                {categories.map((cat) => (
                    <button
                        key={cat}
                        onClick={() => setFilter(cat)}
                        className={`px-2.5 py-1 text-xs rounded-md transition-colors cursor-pointer ${
                            filter === cat
                                ? "bg-[#18181b] text-white border border-[#3f3f46]"
                                : "text-[#71717a] hover:text-[#a1a1aa] border border-transparent"
                        }`}
                    >
                        {cat.charAt(0).toUpperCase() + cat.slice(1)}
                    </button>
                ))}
            </div>

            {filtered.length > 0 ? (
                <div className="bg-[#111113] border border-[#27272a] rounded-lg divide-y divide-[#1f1f23]">
                    {filtered.map((doc) => (
                        <div
                            key={doc.id}
                            onClick={() => isSelectMode ? toggleSelect(doc.id, { stopPropagation: () => {} } as React.MouseEvent) : router.push(`/dashboard/documents/${doc.id}`)}
                            className={`flex items-center gap-4 px-5 py-4 hover:bg-[#18181b] transition-colors group cursor-pointer ${
                                selected.has(doc.id) ? "bg-[#3b82f6]/5" : ""
                            }`}
                        >
                            {/* Checkbox */}
                            <div
                                onClick={(e) => toggleSelect(doc.id, e)}
                                className="shrink-0"
                            >
                                {selected.has(doc.id)
                                    ? <FiCheckSquare className="w-4 h-4 text-[#3b82f6]" />
                                    : <FiSquare className={`w-4 h-4 ${isSelectMode ? "text-[#52525b]" : "text-[#27272a] group-hover:text-[#52525b]"} transition-colors`} />}
                            </div>

                            <FiFileText className="w-4 h-4 text-[#52525b] shrink-0" />
                            <div className="flex-1 min-w-0">
                                <p className="text-sm text-white truncate">{doc.original_filename}</p>
                                <p className="text-xs text-[#52525b] mt-0.5">
                                    {(doc.file_size / 1024).toFixed(1)} KB · {new Date(doc.created_at).toLocaleDateString()}
                                </p>
                            </div>
                            <div className="flex items-center gap-3">
                                {doc.category && doc.category !== "unknown" && (
                                    <span className="text-[11px] px-2 py-0.5 rounded bg-[#10b981]/10 text-[#10b981]">
                                        {doc.category}
                                    </span>
                                )}
                                {doc.category === "unknown" && (
                                    <span className="text-[11px] px-2 py-0.5 rounded bg-[#27272a] text-[#71717a]">
                                        unknown
                                    </span>
                                )}
                                <ConfidenceBadge score={doc.confidence_score} />
                                <span className={`text-[11px] px-2 py-0.5 rounded ${
                                    doc.status === "completed" ? "bg-[#10b981]/10 text-[#10b981]" :
                                    doc.status === "processing" ? "bg-[#f59e0b]/10 text-[#f59e0b]" :
                                    "bg-[#27272a] text-[#71717a]"
                                }`}>
                                    {doc.status}
                                </span>
                                <button
                                    onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }}
                                    className="opacity-0 group-hover:opacity-100 text-[#52525b] hover:text-[#ef4444] transition-all cursor-pointer"
                                >
                                    <FiTrash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="bg-[#111113] border border-[#27272a] rounded-lg py-16 text-center">
                    <p className="text-sm text-[#52525b]">{filter === "all" ? "No documents yet" : `No ${filter} documents`}</p>
                </div>
            )}
        </div>
    );
}
