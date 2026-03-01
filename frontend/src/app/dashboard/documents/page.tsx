"use client";

import { useEffect, useState } from "react";
import { documentsApi } from "@/lib/api";
import { FiFileText, FiTrash2, FiFilter } from "react-icons/fi";

const categories = ["all", "bills", "upi", "tickets", "tax", "bank", "invoices", "unknown"];

export default function DocumentsPage() {
    const [docs, setDocs] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");

    useEffect(() => {
        loadDocs();
    }, []);

    const loadDocs = async () => {
        try {
            const res = await documentsApi.getAll();
            setDocs(res.data.documents || []);
        } catch {
            setDocs([]);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        try {
            await documentsApi.delete(id);
            setDocs((prev) => prev.filter((d) => d.id !== id));
        } catch {}
    };

    const filtered = filter === "all" ? docs : docs.filter((d) => d.category === filter);

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
                        <div key={doc.id} className="flex items-center gap-4 px-5 py-4 hover:bg-[#18181b] transition-colors group">
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
                                {doc.confidence_score > 0 && (
                                    <span className="text-[11px] text-[#52525b]">
                                        {(doc.confidence_score * 100).toFixed(0)}%
                                    </span>
                                )}
                                <span className={`text-[11px] px-2 py-0.5 rounded ${
                                    doc.status === "completed" ? "bg-[#10b981]/10 text-[#10b981]" :
                                    doc.status === "processing" ? "bg-[#f59e0b]/10 text-[#f59e0b]" :
                                    "bg-[#27272a] text-[#71717a]"
                                }`}>
                                    {doc.status}
                                </span>
                                <button
                                    onClick={() => handleDelete(doc.id)}
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
