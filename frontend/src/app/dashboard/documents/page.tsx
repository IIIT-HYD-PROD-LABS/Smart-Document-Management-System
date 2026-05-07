"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { documentsApi } from "@/lib/api";
import { ConfidenceBadge, StatusBadge, CategoryBadge, LoadingSpinner } from "@/components";
import { FiFileText, FiTrash2, FiFilter, FiCheckSquare, FiSquare, FiX, FiMail } from "react-icons/fi";
import toast from "react-hot-toast";

const categories = ["all", "bills", "upi", "tickets", "tax", "bank", "invoices", "unknown"];

interface DocumentListItem {
    id: number;
    original_filename: string;
    file_size: number | null;
    file_type: string;
    category: string;
    confidence_score: number | null;
    status: string;
    created_at: string;
    source?: string;
}

export default function DocumentsPage() {
    const router = useRouter();
    const [docs, setDocs] = useState<DocumentListItem[]>([]);
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
                <LoadingSpinner />
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Documents</h1>
                    <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                        {docs.length} document{docs.length !== 1 ? "s" : ""} in your library
                    </p>
                </div>
            </div>

            {/* Bulk action bar */}
            {isSelectMode && (
                <div
                    className="flex items-center gap-3 mb-4 px-4 py-3 rounded-lg border"
                    style={{
                        background: "var(--accent-soft)",
                        borderColor: "var(--accent-edge)",
                    }}
                >
                    <button
                        onClick={toggleSelectAll}
                        className="flex items-center gap-2 text-xs transition-colors cursor-pointer"
                        style={{ color: "var(--text-secondary)" }}
                    >
                        {selected.size === filtered.length
                            ? <FiCheckSquare className="w-4 h-4" style={{ color: "var(--accent)" }} />
                            : <FiSquare className="w-4 h-4" />}
                        {selected.size === filtered.length ? "Deselect all" : "Select all"}
                    </button>
                    <span className="text-xs" style={{ color: "var(--text-disabled)" }}>|</span>
                    <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>{selected.size} selected</span>
                    <div className="flex-1" />
                    <button
                        onClick={handleBatchDelete}
                        disabled={deleting}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-50 transition-colors cursor-pointer border"
                        style={{
                            background: "var(--danger-soft)",
                            color: "var(--danger)",
                            borderColor: "color-mix(in srgb, var(--danger) 25%, transparent)",
                        }}
                    >
                        <FiTrash2 className="w-3.5 h-3.5" />
                        {deleting ? "Deleting..." : `Delete ${selected.size}`}
                    </button>
                    <button
                        onClick={() => setSelected(new Set())}
                        className="transition-colors cursor-pointer touch-target flex items-center justify-center"
                        style={{ color: "var(--text-muted)" }}
                    >
                        <FiX className="w-4 h-4" />
                    </button>
                </div>
            )}

            <div className="flex flex-wrap items-center gap-1.5 mb-6">
                <FiFilter className="w-3.5 h-3.5 mr-1 shrink-0" style={{ color: "var(--text-muted)" }} />
                {categories.map((cat) => {
                    const isActive = filter === cat;
                    return (
                        <button
                            key={cat}
                            onClick={() => setFilter(cat)}
                            className="px-2.5 py-1 text-xs rounded-md transition-colors cursor-pointer border"
                            style={{
                                background: isActive ? "var(--bg-elevated)" : "transparent",
                                color: isActive ? "var(--text-primary)" : "var(--text-muted)",
                                borderColor: isActive ? "var(--border-emphasis)" : "transparent",
                                fontWeight: isActive ? 500 : 400,
                            }}
                        >
                            {cat.charAt(0).toUpperCase() + cat.slice(1)}
                        </button>
                    );
                })}
            </div>

            {filtered.length > 0 ? (
                <div
                    className="rounded-lg overflow-hidden border"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    {filtered.map((doc, idx) => {
                        const isSelected = selected.has(doc.id);
                        return (
                            <div
                                key={doc.id}
                                onClick={() => isSelectMode ? toggleSelect(doc.id, { stopPropagation: () => {} } as React.MouseEvent) : router.push(`/dashboard/documents/${doc.id}`)}
                                className="flex items-center gap-4 px-5 py-4 transition-colors group cursor-pointer"
                                style={{
                                    background: isSelected ? "var(--accent-soft)" : "transparent",
                                    borderTop: idx === 0 ? "none" : "1px solid var(--border-subtle)",
                                }}
                                onMouseEnter={(e) => {
                                    if (!isSelected) e.currentTarget.style.background = "var(--bg-hover)";
                                }}
                                onMouseLeave={(e) => {
                                    if (!isSelected) e.currentTarget.style.background = "transparent";
                                }}
                            >
                                <div
                                    onClick={(e) => toggleSelect(doc.id, e)}
                                    className="shrink-0 touch-target flex items-center justify-center"
                                >
                                    {isSelected
                                        ? <FiCheckSquare className="w-4 h-4" style={{ color: "var(--accent)" }} />
                                        : <FiSquare
                                            className="w-4 h-4 transition-colors"
                                            style={{
                                                color: isSelectMode ? "var(--text-muted)" : "var(--border-emphasis)",
                                            }}
                                        />}
                                </div>

                                <FiFileText className="w-4 h-4 shrink-0" style={{ color: "var(--text-muted)" }} />
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5">
                                        {(doc.source === "gmail" || doc.source === "gmail_body") && (
                                            <FiMail
                                                className="w-3.5 h-3.5 shrink-0"
                                                style={{ color: "var(--accent)" }}
                                                title={doc.source === "gmail_body" ? "Ingested from Gmail body" : "Ingested from Gmail attachment"}
                                            />
                                        )}
                                        <p className="text-sm truncate" style={{ color: "var(--text-primary)" }}>{doc.original_filename}</p>
                                    </div>
                                    <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                                        {doc.file_size != null ? `${(doc.file_size / 1024).toFixed(1)} KB` : "Unknown size"} &middot; {new Date(doc.created_at).toLocaleDateString()}
                                    </p>
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                    <span className="hidden sm:inline-flex">
                                        {doc.category && (
                                            <CategoryBadge category={doc.category} />
                                        )}
                                    </span>
                                    <span className="hidden md:inline-flex">
                                        <ConfidenceBadge score={doc.confidence_score ?? 0} />
                                    </span>
                                    <StatusBadge status={doc.status} />
                                    <button
                                        onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }}
                                        className="opacity-0 group-hover:opacity-100 transition-all cursor-pointer touch-target flex items-center justify-center"
                                        style={{ color: "var(--text-muted)" }}
                                        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--danger)"; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
                                    >
                                        <FiTrash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <div
                    className="rounded-lg py-16 text-center border"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                    }}
                >
                    <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                        {filter === "all" ? "No documents yet" : `No ${filter} documents`}
                    </p>
                </div>
            )}
        </div>
    );
}
