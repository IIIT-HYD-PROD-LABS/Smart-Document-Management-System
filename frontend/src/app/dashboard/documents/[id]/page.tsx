"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { documentsApi, sharingApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import toast from "react-hot-toast";
import { FiArrowLeft, FiFile, FiCalendar, FiTag, FiHash, FiCopy, FiCheck, FiEdit3, FiX, FiSave, FiShare2, FiTrash2 } from "react-icons/fi";

interface AIField {
    value: unknown;
    confidence: number;
}

interface Highlight {
    text: string;
    start: number;
    end: number;
}

interface DocumentDetail {
    id: number;
    filename: string;
    original_filename: string;
    file_type: string;
    file_size: number;
    category: string;
    confidence_score: number;
    extracted_text: string | null;
    extracted_metadata: Record<string, unknown> | null;
    ai_summary: string | null;
    ai_extracted_fields: Record<string, AIField> | null;
    ai_extraction_status: string | null;
    ai_provider: string | null;
    ai_error: string | null;
    highlighted_text: Highlight[] | null;
    status: string;
    s3_url: string | null;
    created_at: string;
    updated_at: string | null;
}

interface SharePermission {
    id: number;
    document_id: number;
    user_id: number;
    user_email: string;
    user_name: string;
    permission: string;
    granted_by: number;
    created_at: string;
}

function StatusBadge({ status }: { status: string }) {
    const styles: Record<string, string> = {
        completed: "bg-[#10b981]/10 text-[#10b981]",
        processing: "bg-[#f59e0b]/10 text-[#f59e0b]",
        pending: "bg-[#3b82f6]/10 text-[#3b82f6]",
        failed: "bg-[#ef4444]/10 text-[#ef4444]",
    };
    return (
        <span className={`text-xs px-2.5 py-1 rounded-md ${styles[status] || "bg-[#27272a] text-[#71717a]"}`}>
            {status}
        </span>
    );
}

function ConfidenceBadge({ score }: { score: number }) {
    if (score <= 0) return null;
    const pct = Math.round(score * 100);
    let color: string;
    if (score >= 0.8) color = "text-[#10b981]";
    else if (score >= 0.5) color = "text-[#f59e0b]";
    else color = "text-[#ef4444]";
    return <span className={`text-2xl font-semibold ${color}`}>{pct}%</span>;
}

function MetadataItem({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="text-[11px] text-[#52525b] uppercase tracking-wider mb-1">{label}</p>
            <p className="text-sm text-white">{value}</p>
        </div>
    );
}

/** Render text with highlighted portions shown in yellow */
function HighlightedText({ text, highlights }: { text: string; highlights: Highlight[] }) {
    if (!highlights.length) return <>{text}</>;

    const sorted = [...highlights].sort((a, b) => a.start - b.start);
    const parts: React.ReactNode[] = [];
    let lastEnd = 0;

    sorted.forEach((h, i) => {
        if (h.start > lastEnd) {
            parts.push(<span key={`t-${i}`}>{text.slice(lastEnd, h.start)}</span>);
        }
        parts.push(
            <mark key={`h-${i}`} className="bg-[#f59e0b]/20 text-[#f59e0b] rounded-sm px-0.5">
                {text.slice(h.start, h.end)}
            </mark>
        );
        lastEnd = h.end;
    });

    if (lastEnd < text.length) {
        parts.push(<span key="tail">{text.slice(lastEnd)}</span>);
    }

    return <>{parts}</>;
}

export default function DocumentDetailPage() {
    const params = useParams();
    const router = useRouter();
    const { user } = useAuth();
    const [doc, setDoc] = useState<DocumentDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    // Highlighting state
    const [highlightMode, setHighlightMode] = useState(false);
    const [highlights, setHighlights] = useState<Highlight[]>([]);
    const [saving, setSaving] = useState(false);
    const [hasChanges, setHasChanges] = useState(false);

    // Sharing state
    const [showShareModal, setShowShareModal] = useState(false);
    const [shareEmail, setShareEmail] = useState("");
    const [sharePermission, setSharePermission] = useState("view");
    const [permissions, setPermissions] = useState<SharePermission[]>([]);
    const [sharingLoading, setSharingLoading] = useState(false);

    const canShare = user?.role === "admin" || user?.role === "editor";

    useEffect(() => {
        const id = Number(params.id);
        if (!id) return;
        documentsApi.getById(id)
            .then((res) => {
                setDoc(res.data);
                setHighlights(res.data.highlighted_text || []);
            })
            .catch((err) => {
                if (err?.response?.status === 404) {
                    setError("Document not found");
                } else if (err?.response?.status === 403) {
                    setError("Access denied");
                } else {
                    setError("Failed to load document");
                }
            })
            .finally(() => setLoading(false));
    }, [params.id]);

    const docId = doc?.id;

    const loadPermissions = useCallback(async () => {
        if (!docId) return;
        try {
            const res = await sharingApi.getPermissions(docId);
            setPermissions(res.data);
        } catch {
            // Silently fail if not owner
        }
    }, [docId]);

    useEffect(() => {
        if (doc && canShare) loadPermissions();
    }, [doc, canShare, loadPermissions]);

    const handleShare = async () => {
        if (!doc || !shareEmail) return;
        setSharingLoading(true);
        try {
            await sharingApi.share(doc.id, shareEmail, sharePermission);
            toast.success("Document shared");
            setShareEmail("");
            loadPermissions();
        } catch (err: unknown) {
            const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            toast.error(message || "Failed to share");
        } finally {
            setSharingLoading(false);
        }
    };

    const handleRevoke = async (permId: number) => {
        if (!doc) return;
        try {
            await sharingApi.revoke(doc.id, permId);
            toast.success("Access revoked");
            loadPermissions();
        } catch {
            toast.error("Failed to revoke");
        }
    };

    const copyText = () => {
        if (!doc?.extracted_text) return;
        // If highlights exist, copy only highlighted text
        if (highlights.length > 0) {
            const sorted = [...highlights].sort((a, b) => a.start - b.start);
            const text = sorted.map(h => h.text).join("\n\n");
            navigator.clipboard.writeText(text);
        } else {
            navigator.clipboard.writeText(doc.extracted_text);
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleTextSelect = useCallback(() => {
        if (!highlightMode || !doc?.extracted_text) return;
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed) return;

        const selectedText = selection.toString().trim();
        if (!selectedText) return;

        // Find the position in the extracted text
        const fullText = doc.extracted_text;
        const range = selection.getRangeAt(0);
        const container = range.startContainer;

        // Walk up to find the pre element
        let preEl = container instanceof HTMLElement ? container : container.parentElement;
        while (preEl && preEl.tagName !== "PRE") preEl = preEl.parentElement;
        if (!preEl) return;

        // Get text offset within the pre element
        const preText = preEl.textContent || "";
        const beforeRange = document.createRange();
        beforeRange.setStart(preEl, 0);
        beforeRange.setEnd(range.startContainer, range.startOffset);
        const start = beforeRange.toString().length;
        const end = start + selectedText.length;

        // Validate bounds
        if (start < 0 || end > fullText.length) return;

        // Check for overlaps with existing highlights
        const overlaps = highlights.some(h =>
            (start < h.end && end > h.start)
        );
        if (overlaps) {
            toast.error("Selection overlaps an existing highlight");
            selection.removeAllRanges();
            return;
        }

        setHighlights(prev => [...prev, { text: selectedText, start, end }]);
        setHasChanges(true);
        selection.removeAllRanges();
        toast.success("Text highlighted");
    }, [highlightMode, doc?.id, doc?.extracted_text, highlights]);

    const removeHighlight = (index: number) => {
        setHighlights(prev => prev.filter((_, i) => i !== index));
        setHasChanges(true);
    };

    const saveHighlights = async () => {
        if (!doc) return;
        setSaving(true);
        try {
            await documentsApi.saveHighlights(doc.id, highlights);
            setHasChanges(false);
            toast.success("Highlights saved");
        } catch {
            toast.error("Failed to save highlights");
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin" />
            </div>
        );
    }

    if (error || !doc) {
        return (
            <div className="text-center py-16">
                <p className="text-sm text-[#ef4444]">{error || "Document not found"}</p>
                <button onClick={() => router.back()} className="mt-4 text-sm text-[#71717a] hover:text-white transition-colors cursor-pointer">
                    Go back
                </button>
            </div>
        );
    }

    const fileSize = doc.file_size >= 1024 * 1024
        ? `${(doc.file_size / (1024 * 1024)).toFixed(1)} MB`
        : `${(doc.file_size / 1024).toFixed(1)} KB`;

    return (
        <div className="max-w-4xl">
            {/* Back button */}
            <button
                onClick={() => router.back()}
                className="flex items-center gap-2 text-sm text-[#71717a] hover:text-white transition-colors mb-6 cursor-pointer"
            >
                <FiArrowLeft className="w-4 h-4" />
                Back
            </button>

            {/* Header */}
            <div className="flex items-start justify-between mb-8">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-[#18181b] border border-[#27272a] rounded-lg flex items-center justify-center">
                        <FiFile className="w-5 h-5 text-[#52525b]" />
                    </div>
                    <div>
                        <h1 className="text-lg font-semibold text-white">{doc.original_filename}</h1>
                        <p className="text-xs text-[#52525b] mt-1">{fileSize} &middot; {doc.file_type.toUpperCase()}</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {canShare && (
                        <button
                            onClick={() => setShowShareModal(true)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#71717a] hover:text-white border border-[#27272a] rounded-md hover:border-[#3f3f46] transition-colors cursor-pointer"
                        >
                            <FiShare2 className="w-3.5 h-3.5" />
                            Share
                        </button>
                    )}
                    <StatusBadge status={doc.status} />
                </div>
            </div>

            {/* Info grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 p-5 bg-[#111113] border border-[#27272a] rounded-lg mb-6">
                <div className="flex items-start gap-3">
                    <FiTag className="w-4 h-4 text-[#52525b] mt-0.5 shrink-0" />
                    <MetadataItem label="Category" value={doc.category || "Unknown"} />
                </div>
                <div className="flex items-start gap-3">
                    <FiHash className="w-4 h-4 text-[#52525b] mt-0.5 shrink-0" />
                    <div>
                        <p className="text-[11px] text-[#52525b] uppercase tracking-wider mb-1">Confidence</p>
                        <ConfidenceBadge score={doc.confidence_score} />
                    </div>
                </div>
                <div className="flex items-start gap-3">
                    <FiCalendar className="w-4 h-4 text-[#52525b] mt-0.5 shrink-0" />
                    <MetadataItem label="Uploaded" value={new Date(doc.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })} />
                </div>
                <div className="flex items-start gap-3">
                    <FiFile className="w-4 h-4 text-[#52525b] mt-0.5 shrink-0" />
                    <MetadataItem label="File ID" value={`#${doc.id}`} />
                </div>
            </div>

            {/* Extracted metadata */}
            {doc.extracted_metadata && Object.keys(doc.extracted_metadata).length > 0 && (
                <div className="p-5 bg-[#111113] border border-[#27272a] rounded-lg mb-6">
                    <h2 className="text-sm font-medium text-white mb-4">Extracted Metadata</h2>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                        {Object.entries(doc.extracted_metadata).map(([key, value]) => (
                            <MetadataItem key={key} label={key} value={String(value ?? "-")} />
                        ))}
                    </div>
                </div>
            )}

            {/* AI Summary */}
            {doc.ai_summary && (
                <div className="p-5 bg-[#111113] border border-[#27272a] rounded-lg mb-6">
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-medium text-white">AI Summary</h2>
                        {doc.ai_provider && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-[#27272a] text-[#71717a] uppercase tracking-wider">
                                {doc.ai_provider}
                            </span>
                        )}
                    </div>
                    <p className="text-sm text-[#a1a1aa] leading-relaxed">{doc.ai_summary}</p>
                </div>
            )}

            {/* AI Extracted Fields */}
            {doc.ai_extracted_fields && Object.keys(doc.ai_extracted_fields).length > 0 && (
                <div className="p-5 bg-[#111113] border border-[#27272a] rounded-lg mb-6">
                    <h2 className="text-sm font-medium text-white mb-4">AI Extracted Fields</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(doc.ai_extracted_fields).map(([key, field]) => {
                            const conf = typeof field === "object" && field && "confidence" in field
                                ? (field as AIField).confidence
                                : null;
                            const val = typeof field === "object" && field && "value" in field
                                ? (field as AIField).value
                                : field;
                            const displayVal = Array.isArray(val) ? val.join(", ") : String(val ?? "-");
                            const confPct = conf !== null ? Math.round(conf * 100) : null;
                            const confColor = conf !== null
                                ? conf >= 0.8 ? "text-[#10b981]" : conf >= 0.5 ? "text-[#f59e0b]" : "text-[#ef4444]"
                                : "";
                            return (
                                <div key={key} className="flex items-start justify-between p-3 bg-[#09090b] rounded-md border border-[#1e1e21]">
                                    <div className="min-w-0 flex-1">
                                        <p className="text-[11px] text-[#52525b] uppercase tracking-wider mb-1">
                                            {key.replace(/_/g, " ")}
                                        </p>
                                        <p className="text-sm text-white break-words">{displayVal}</p>
                                    </div>
                                    {confPct !== null && (
                                        <span className={`text-xs font-medium ml-3 shrink-0 ${confColor}`}>
                                            {confPct}%
                                        </span>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* AI Error */}
            {doc.ai_error && (
                <div className="p-4 bg-[#ef4444]/5 border border-[#ef4444]/20 rounded-lg mb-6">
                    <p className="text-xs text-[#ef4444]">AI extraction failed: {doc.ai_error}</p>
                </div>
            )}

            {/* Saved highlights summary */}
            {highlights.length > 0 && !highlightMode && (
                <div className="p-5 bg-[#111113] border border-[#f59e0b]/20 rounded-lg mb-6">
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-medium text-white">Highlighted Text ({highlights.length} selections)</h2>
                        <button
                            onClick={copyText}
                            className="flex items-center gap-1.5 text-xs text-[#71717a] hover:text-white transition-colors cursor-pointer"
                        >
                            <FiCopy className="w-3.5 h-3.5" />
                            Copy highlights
                        </button>
                    </div>
                    <div className="space-y-2">
                        {[...highlights].sort((a, b) => a.start - b.start).map((h, i) => (
                            <div key={i} className="p-2.5 bg-[#f59e0b]/5 border border-[#f59e0b]/10 rounded text-sm text-[#a1a1aa]">
                                {h.text.length > 150 ? h.text.slice(0, 150) + "..." : h.text}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Extracted text with highlighting */}
            <div className={`bg-[#111113] border rounded-lg mb-6 ${highlightMode ? "border-[#f59e0b]/40" : "border-[#27272a]"}`}>
                <div className="flex items-center justify-between px-5 py-3 border-b border-[#27272a]">
                    <div className="flex items-center gap-3">
                        <h2 className="text-sm font-medium text-white">Extracted Text</h2>
                        {highlightMode && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-[#f59e0b]/10 text-[#f59e0b] uppercase tracking-wider animate-pulse">
                                Select text to highlight
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        {doc.extracted_text && (
                            <>
                                <button
                                    onClick={() => setHighlightMode(!highlightMode)}
                                    className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded transition-colors cursor-pointer ${
                                        highlightMode
                                            ? "bg-[#f59e0b]/10 text-[#f59e0b]"
                                            : "text-[#71717a] hover:text-white"
                                    }`}
                                >
                                    <FiEdit3 className="w-3.5 h-3.5" />
                                    {highlightMode ? "Done" : "Highlight"}
                                </button>
                                {hasChanges && (
                                    <button
                                        onClick={saveHighlights}
                                        disabled={saving}
                                        className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded bg-[#10b981]/10 text-[#10b981] hover:bg-[#10b981]/20 transition-colors cursor-pointer disabled:opacity-50"
                                    >
                                        <FiSave className="w-3.5 h-3.5" />
                                        {saving ? "Saving..." : "Save"}
                                    </button>
                                )}
                                {!highlightMode && (
                                    <button
                                        onClick={copyText}
                                        className="flex items-center gap-1.5 text-xs text-[#71717a] hover:text-white transition-colors cursor-pointer"
                                    >
                                        {copied ? <FiCheck className="w-3.5 h-3.5 text-[#10b981]" /> : <FiCopy className="w-3.5 h-3.5" />}
                                        {copied ? "Copied" : "Copy"}
                                    </button>
                                )}
                            </>
                        )}
                    </div>
                </div>

                {/* Highlight chips in edit mode */}
                {highlightMode && highlights.length > 0 && (
                    <div className="px-5 py-3 border-b border-[#27272a] flex flex-wrap gap-2">
                        {[...highlights].sort((a, b) => a.start - b.start).map((h, i) => (
                            <span key={i} className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#f59e0b]/10 text-[#f59e0b] text-xs">
                                {h.text.length > 30 ? h.text.slice(0, 30) + "..." : h.text}
                                <button onClick={() => removeHighlight(i)} className="hover:text-white cursor-pointer">
                                    <FiX className="w-3 h-3" />
                                </button>
                            </span>
                        ))}
                    </div>
                )}

                <div className="p-5">
                    {doc.extracted_text ? (
                        <pre
                            className={`text-sm text-[#a1a1aa] leading-relaxed whitespace-pre-wrap font-mono break-words max-h-[500px] overflow-y-auto ${
                                highlightMode ? "cursor-text select-text" : ""
                            }`}
                            onMouseUp={handleTextSelect}
                        >
                            <HighlightedText text={doc.extracted_text} highlights={highlights} />
                        </pre>
                    ) : (
                        <p className="text-sm text-[#52525b] italic">No text extracted from this document.</p>
                    )}
                </div>
            </div>

            {/* Share Modal */}
            {showShareModal && (
                <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowShareModal(false)}>
                    <div className="bg-[#111113] border border-[#27272a] rounded-lg w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-sm font-medium text-white">Share document</h3>
                            <button onClick={() => setShowShareModal(false)} className="text-[#52525b] hover:text-white cursor-pointer">
                                <FiX className="w-4 h-4" />
                            </button>
                        </div>

                        <div className="flex gap-2 mb-4">
                            <input
                                type="email"
                                value={shareEmail}
                                onChange={(e) => setShareEmail(e.target.value)}
                                placeholder="Enter email address"
                                className="flex-1 px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors"
                            />
                            <select
                                value={sharePermission}
                                onChange={(e) => setSharePermission(e.target.value)}
                                className="px-2 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white focus:outline-none cursor-pointer"
                            >
                                <option value="view">View</option>
                                <option value="edit">Edit</option>
                            </select>
                            <button
                                onClick={handleShare}
                                disabled={sharingLoading || !shareEmail}
                                className="px-4 py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors disabled:opacity-50 cursor-pointer"
                            >
                                {sharingLoading ? "..." : "Share"}
                            </button>
                        </div>

                        {permissions.length > 0 && (
                            <div>
                                <p className="text-[11px] text-[#52525b] uppercase tracking-wider mb-2">People with access</p>
                                <div className="space-y-2 max-h-48 overflow-y-auto">
                                    {permissions.map((p) => (
                                        <div key={p.id} className="flex items-center justify-between p-2.5 bg-[#09090b] rounded-md border border-[#1e1e21]">
                                            <div className="min-w-0 flex-1">
                                                <p className="text-sm text-white truncate">{p.user_name || p.user_email}</p>
                                                <p className="text-xs text-[#52525b] truncate">{p.user_email}</p>
                                            </div>
                                            <div className="flex items-center gap-2 ml-3">
                                                <span className="text-xs text-[#71717a] px-2 py-0.5 bg-[#27272a] rounded">{p.permission}</span>
                                                <button
                                                    onClick={() => handleRevoke(p.id)}
                                                    className="text-[#52525b] hover:text-[#ef4444] transition-colors cursor-pointer"
                                                >
                                                    <FiTrash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
