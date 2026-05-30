"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { documentsApi } from "@/lib/api";
import { ConfidenceBadge, StatusBadge, CategoryBadge, Skeleton } from "@/components";
import { FiFileText, FiTrash2, FiFilter, FiCheckSquare, FiSquare, FiX, FiMail, FiUpload, FiShare2, FiSearch } from "react-icons/fi";
import Link from "next/link";
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

const DOCS_QUERY_KEY = ["documents", "all"] as const;

export default function DocumentsPage() {
    const router = useRouter();
    const queryClient = useQueryClient();
    const [filter, setFilter] = useState("all");
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [deleting, setDeleting] = useState(false);

    // React Query (was useState+useEffect): shares the dashboard cache so a
    // revisit inside staleTime is instant, and the sidebar's hover-prefetch
    // (same key + queryFn) lands a warm cache here on arrival.
    const { data: docs = [], isLoading: loading, isError } = useQuery<DocumentListItem[]>({
        queryKey: DOCS_QUERY_KEY,
        queryFn: () => documentsApi.getAll().then((r) => r.data.documents ?? []),
    });

    useEffect(() => {
        if (isError) toast.error("Something went wrong");
    }, [isError]);

    // A background refetch (stale revisit) can drop rows that were deleted
    // elsewhere. Prune `selected` to ids still present so batch-delete never
    // targets a stale selection.
    useEffect(() => {
        setSelected((prev) => {
            const live = new Set(docs.map((d) => d.id));
            const next = new Set([...prev].filter((id) => live.has(id)));
            return next.size === prev.size ? prev : next;
        });
    }, [docs]);

    // Local mutations write through the cache so the list updates instantly
    // without a refetch round-trip to the remote DB.
    const removeFromCache = (ids: Set<number>) =>
        queryClient.setQueryData<DocumentListItem[]>(DOCS_QUERY_KEY, (prev) =>
            (prev ?? []).filter((d) => !ids.has(d.id)),
        );

    const handleDelete = async (id: number) => {
        try {
            await documentsApi.delete(id);
            removeFromCache(new Set([id]));
            setSelected((prev) => { const next = new Set(prev); next.delete(id); return next; });
        } catch { toast.error("Something went wrong"); }
    };

    const handleBatchDelete = async () => {
        if (selected.size === 0) return;
        setDeleting(true);
        try {
            const ids = Array.from(selected);
            await documentsApi.batchDelete(ids);
            removeFromCache(selected);
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
            <div role="status" aria-busy="true" aria-live="polite">
                <span className="sr-only">Loading documents</span>
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <Skeleton className="h-6 w-40" />
                        <Skeleton className="h-4 w-56 mt-2" />
                    </div>
                </div>
                <div className="grid grid-cols-3 gap-3 mb-6">
                    <Skeleton className="h-[60px]" />
                    <Skeleton className="h-[60px]" />
                    <Skeleton className="h-[60px]" />
                </div>
                <div className="space-y-2">
                    {Array.from({ length: 8 }).map((_, i) => (
                        <Skeleton key={i} className="h-14 w-full" />
                    ))}
                </div>
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

            {/* Workspace action row — Upload, Shared, Search consolidated here
                so the document workflows live on one page (Phase 17 IA reset). */}
            <div className="grid grid-cols-3 gap-3 mb-6" role="group" aria-label="Document workspace actions">
                <Link
                    href="/dashboard/upload"
                    className="group flex items-center gap-3 px-4 py-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] hover:border-[var(--accent-edge)] hover:bg-[var(--accent-soft)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-page)]"
                    aria-label="Upload a new document"
                >
                    <span className="w-9 h-9 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0 group-hover:bg-[var(--accent)] transition-colors">
                        <FiUpload className="w-4 h-4 text-[var(--accent)] group-hover:text-white transition-colors" />
                    </span>
                    <div className="min-w-0">
                        <p className="text-[13.5px] font-semibold text-[var(--text-primary)] tracking-tight">Upload</p>
                        <p className="text-[11.5px] text-[var(--text-muted)] truncate">PDF, image, or scan</p>
                    </div>
                </Link>
                <Link
                    href="/dashboard/shared"
                    className="group flex items-center gap-3 px-4 py-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] hover:border-[var(--accent-edge)] hover:bg-[var(--accent-soft)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-page)]"
                    aria-label="Open documents shared with you"
                >
                    <span className="w-9 h-9 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0 group-hover:bg-[var(--accent)] transition-colors">
                        <FiShare2 className="w-4 h-4 text-[var(--accent)] group-hover:text-white transition-colors" />
                    </span>
                    <div className="min-w-0">
                        <p className="text-[13.5px] font-semibold text-[var(--text-primary)] tracking-tight">Shared</p>
                        <p className="text-[11.5px] text-[var(--text-muted)] truncate">Documents shared with you</p>
                    </div>
                </Link>
                <Link
                    href="/dashboard/search"
                    className="group flex items-center gap-3 px-4 py-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] hover:border-[var(--accent-edge)] hover:bg-[var(--accent-soft)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-page)]"
                    aria-label="Search across all documents"
                >
                    <span className="w-9 h-9 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0 group-hover:bg-[var(--accent)] transition-colors">
                        <FiSearch className="w-4 h-4 text-[var(--accent)] group-hover:text-white transition-colors" />
                    </span>
                    <div className="min-w-0">
                        <p className="text-[13.5px] font-semibold text-[var(--text-primary)] tracking-tight">Search</p>
                        <p className="text-[11.5px] text-[var(--text-muted)] truncate">Find by name, content, tag</p>
                    </div>
                </Link>
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
                        disabled={deleting}
                        className="flex items-center gap-2 text-xs transition-colors cursor-pointer touch-target disabled:opacity-50 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
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
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-50 transition-colors cursor-pointer border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
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
                        disabled={deleting}
                        className="transition-colors cursor-pointer touch-target flex items-center justify-center disabled:opacity-50 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
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
