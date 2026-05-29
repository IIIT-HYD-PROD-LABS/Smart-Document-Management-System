"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { documentsApi, sharingApi, extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import toast from "react-hot-toast";
import { ConfidenceBadge, StatusBadge, Skeleton } from "@/components";
import { FiArrowLeft, FiFile, FiCalendar, FiTag, FiHash, FiCopy, FiCheck, FiEdit3, FiX, FiSave, FiShare2, FiTrash2, FiEye, FiClock, FiRotateCcw } from "react-icons/fi";
import Link from "next/link";

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
    current_version: number;
    total_versions: number;
    created_at: string;
    updated_at: string | null;
}

interface DocumentVersionEntry {
    id: number;
    version_number: number;
    original_filename: string;
    file_type: string;
    file_size: number;
    category: string | null;
    created_by: number | null;
    created_at: string;
    change_reason: string | null;
    is_current: boolean;
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

function MetadataItem({ label, value }: { label: string; value: string }) {
    return (
        <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-wider mb-1 font-semibold" style={{ color: "var(--text-muted)" }}>{label}</p>
            <p className="text-sm break-words" style={{ color: "var(--text-primary)" }}>{value}</p>
        </div>
    );
}

/**
 * Hero stat tile for the top metadata row.
 * Tinted left edge by metric type via the .stat-stripe-left utility from globals.css.
 */
function StatTile({
    label,
    value,
    icon,
    tint,
    children,
}: {
    label: string;
    value?: string;
    icon: React.ReactNode;
    tint: string;
    children?: React.ReactNode;
}) {
    return (
        <div
            className="surface-card stat-stripe-left p-4 flex items-start gap-3 min-h-[80px]"
            style={{ color: tint }}
        >
            <div
                className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 mt-0.5"
                style={{ background: `color-mix(in srgb, ${tint} 10%, transparent)`, color: tint }}
            >
                {icon}
            </div>
            <div className="min-w-0 flex-1">
                <p className="text-[11px] uppercase tracking-wider mb-1 font-semibold" style={{ color: "var(--text-muted)" }}>
                    {label}
                </p>
                {children ?? (
                    <p className="text-base font-medium truncate" style={{ color: "var(--text-primary)" }}>
                        {value}
                    </p>
                )}
            </div>
        </div>
    );
}

/** Render text with highlighted portions shown in warning yellow */
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
            <mark
                key={`h-${i}`}
                className="rounded-sm px-0.5"
                style={{ background: "var(--warning-soft)", color: "var(--warning)" }}
            >
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
    const copiedTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

    // Highlighting state
    const [highlightMode, setHighlightMode] = useState(false);
    const [highlights, setHighlights] = useState<Highlight[]>([]);
    const [saving, setSaving] = useState(false);
    const [hasChanges, setHasChanges] = useState(false);

    // Version history state
    const [versions, setVersions] = useState<DocumentVersionEntry[]>([]);
    const [showVersions, setShowVersions] = useState(false);
    const [versionsLoading, setVersionsLoading] = useState(false);
    const [rollingBack, setRollingBack] = useState(false);

    // Sharing state
    const [showShareModal, setShowShareModal] = useState(false);
    const [shareEmail, setShareEmail] = useState("");
    const [sharePermission, setSharePermission] = useState("view");
    const [permissions, setPermissions] = useState<SharePermission[]>([]);
    const [sharingLoading, setSharingLoading] = useState(false);

    const canShare = user?.role === "admin" || user?.role === "editor";
    const canEdit = user?.role === "admin" || user?.role === "editor";

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
            toast.error(extractErrorMessage(err, "Failed to share"));
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

    const loadVersions = useCallback(async () => {
        if (!docId) return;
        setVersionsLoading(true);
        try {
            const res = await documentsApi.getVersions(docId);
            setVersions(res.data.versions || []);
        } catch {
            toast.error("Failed to load version history");
        } finally {
            setVersionsLoading(false);
        }
    }, [docId]);

    const handleRollback = async (versionNumber: number) => {
        if (!doc) return;
        if (!confirm(`Restore version ${versionNumber}? The current state will be saved as a new version.`)) return;
        setRollingBack(true);
        try {
            await documentsApi.rollback(doc.id, versionNumber);
            toast.success(`Restored to version ${versionNumber}`);
            const res = await documentsApi.getById(doc.id);
            setDoc(res.data);
            setHighlights(res.data.highlighted_text || []);
            loadVersions();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Rollback failed"));
        } finally {
            setRollingBack(false);
        }
    };

    useEffect(() => {
        if (showVersions && docId) loadVersions();
    }, [showVersions, docId, loadVersions]);

    const copyText = () => {
        if (!doc?.extracted_text) return;
        if (highlights.length > 0) {
            const sorted = [...highlights].sort((a, b) => a.start - b.start);
            const text = sorted.map(h => h.text).join("\n\n");
            navigator.clipboard.writeText(text);
        } else {
            navigator.clipboard.writeText(doc.extracted_text);
        }
        setCopied(true);
        clearTimeout(copiedTimerRef.current);
        copiedTimerRef.current = setTimeout(() => setCopied(false), 2000);
    };

    useEffect(() => {
        return () => clearTimeout(copiedTimerRef.current);
    }, []);

    const handleTextSelect = useCallback(() => {
        if (!highlightMode || !doc?.extracted_text) return;
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed) return;

        const selectedText = selection.toString().trim();
        if (!selectedText) return;

        const fullText = doc.extracted_text;
        const range = selection.getRangeAt(0);
        const container = range.startContainer;

        let preEl = container instanceof HTMLElement ? container : container.parentElement;
        while (preEl && preEl.tagName !== "PRE") preEl = preEl.parentElement;
        if (!preEl) return;

        const beforeRange = document.createRange();
        beforeRange.setStart(preEl, 0);
        beforeRange.setEnd(range.startContainer, range.startOffset);
        const start = beforeRange.toString().length;
        const end = start + selectedText.length;

        if (start < 0 || end > fullText.length) return;

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
            <div
                className="max-w-4xl"
                role="status"
                aria-busy="true"
                aria-live="polite"
            >
                <span className="sr-only">Loading document</span>

                {/* Back button */}
                <Skeleton className="h-5 w-16 mb-6" />

                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
                    <div className="flex items-center gap-4 min-w-0">
                        <Skeleton className="w-12 h-12 rounded-lg shrink-0" />
                        <div className="min-w-0 space-y-2">
                            <Skeleton className="h-5 w-56" />
                            <Skeleton className="h-3 w-28" />
                        </div>
                    </div>
                    <div className="flex items-center gap-3 flex-wrap shrink-0">
                        <Skeleton className="h-7 w-20 rounded-md" />
                        <Skeleton className="h-7 w-16 rounded-md" />
                        <Skeleton className="h-6 w-20 rounded-full" />
                    </div>
                </div>

                {/* Hero metadata tile row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <div
                            key={i}
                            className="surface-card stat-stripe-left p-4 flex items-start gap-3 min-h-[80px]"
                            style={{ color: "var(--text-muted)" }}
                        >
                            <Skeleton className="w-8 h-8 rounded-md shrink-0 mt-0.5" />
                            <div className="min-w-0 flex-1 space-y-2">
                                <Skeleton className="h-2.5 w-16" />
                                <Skeleton className="h-4 w-24" />
                            </div>
                        </div>
                    ))}
                </div>

                {/* Extracted text card */}
                <div
                    className="rounded-lg border mb-6"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    <div
                        className="flex items-center justify-between px-5 py-3 border-b"
                        style={{ borderColor: "var(--border-default)" }}
                    >
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-4 w-16" />
                    </div>
                    <div className="p-5 space-y-3">
                        <Skeleton className="h-3 w-full" />
                        <Skeleton className="h-3 w-11/12" />
                        <Skeleton className="h-3 w-full" />
                        <Skeleton className="h-3 w-4/5" />
                        <Skeleton className="h-3 w-full" />
                        <Skeleton className="h-3 w-3/4" />
                    </div>
                </div>
            </div>
        );
    }

    if (error || !doc) {
        return (
            <div className="text-center py-16">
                <p className="text-sm" style={{ color: "var(--danger)" }}>{error || "Document not found"}</p>
                <button
                    onClick={() => router.back()}
                    className="mt-4 text-sm transition-colors cursor-pointer"
                    style={{ color: "var(--text-muted)" }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
                >
                    Go back
                </button>
            </div>
        );
    }

    const fileSize = doc.file_size >= 1024 * 1024
        ? `${(doc.file_size / (1024 * 1024)).toFixed(1)} MB`
        : `${(doc.file_size / 1024).toFixed(1)} KB`;

    // Confidence band → tint color for the StatTile stripe
    const confidenceTint = doc.confidence_score >= 0.8
        ? "var(--success)"
        : doc.confidence_score >= 0.5
            ? "var(--warning)"
            : "var(--danger)";

    return (
        <div className="max-w-4xl">
            {/* Back button */}
            <button
                onClick={() => router.back()}
                className="flex items-center gap-2 text-sm transition-colors mb-6 cursor-pointer"
                style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
            >
                <FiArrowLeft className="w-4 h-4" />
                Back
            </button>

            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
                <div className="flex items-center gap-4 min-w-0">
                    <div
                        className="w-12 h-12 rounded-lg flex items-center justify-center shrink-0 border"
                        style={{
                            background: "var(--bg-muted)",
                            borderColor: "var(--border-default)",
                        }}
                    >
                        <FiFile className="w-5 h-5" style={{ color: "var(--text-secondary)" }} />
                    </div>
                    <div className="min-w-0">
                        <h1 className="text-lg font-semibold truncate" style={{ color: "var(--text-primary)" }}>{doc.original_filename}</h1>
                        <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{fileSize} &middot; {doc.file_type.toUpperCase()}</p>
                    </div>
                </div>
                <div className="flex items-center gap-3 flex-wrap shrink-0">
                    <Link
                        href={`/dashboard/documents/${doc.id}/preview`}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border transition-colors"
                        style={{
                            color: "var(--text-secondary)",
                            borderColor: "var(--border-default)",
                            background: "var(--bg-elevated)",
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.borderColor = "var(--border-emphasis)";
                            e.currentTarget.style.color = "var(--text-primary)";
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.borderColor = "var(--border-default)";
                            e.currentTarget.style.color = "var(--text-secondary)";
                        }}
                    >
                        <FiEye className="w-3.5 h-3.5" /> Preview
                    </Link>
                    {canShare && (
                        <button
                            onClick={() => setShowShareModal(true)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border transition-colors cursor-pointer"
                            style={{
                                color: "var(--text-secondary)",
                                borderColor: "var(--border-default)",
                                background: "var(--bg-elevated)",
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.borderColor = "var(--border-emphasis)";
                                e.currentTarget.style.color = "var(--text-primary)";
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.borderColor = "var(--border-default)";
                                e.currentTarget.style.color = "var(--text-secondary)";
                            }}
                        >
                            <FiShare2 className="w-3.5 h-3.5" />
                            Share
                        </button>
                    )}
                    <StatusBadge status={doc.status} />
                </div>
            </div>

            {/* Hero metadata tile row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                <StatTile
                    label="Category"
                    value={doc.category || "Unknown"}
                    icon={<FiTag className="w-4 h-4" />}
                    tint="var(--accent)"
                />
                <StatTile
                    label="Confidence"
                    icon={<FiHash className="w-4 h-4" />}
                    tint={confidenceTint}
                >
                    <ConfidenceBadge score={doc.confidence_score ?? 0} variant="display" />
                </StatTile>
                <StatTile
                    label="Uploaded"
                    value={new Date(doc.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                    icon={<FiCalendar className="w-4 h-4" />}
                    tint="var(--info)"
                />
                <StatTile
                    label="File ID"
                    value={`#${doc.id}`}
                    icon={<FiFile className="w-4 h-4" />}
                    tint="var(--text-muted)"
                />
            </div>

            {/* Version history */}
            {doc.total_versions > 1 && (
                <div
                    className="p-5 rounded-lg border mb-6"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                            <FiClock className="w-4 h-4" style={{ color: "var(--text-muted)" }} />
                            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                                Version History
                            </h2>
                            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                                (v{doc.current_version} &middot; {doc.total_versions} total)
                            </span>
                        </div>
                        <button
                            onClick={() => setShowVersions(!showVersions)}
                            className="text-xs transition-colors cursor-pointer"
                            style={{ color: "var(--text-secondary)" }}
                            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
                        >
                            {showVersions ? "Hide" : "Show"}
                        </button>
                    </div>

                    {showVersions && (
                        <div className="mt-4">
                            {versionsLoading ? (
                                <div className="flex justify-center py-4">
                                    <div
                                        className="w-4 h-4 border-2 rounded-full animate-spin"
                                        style={{
                                            borderColor: "var(--border-default)",
                                            borderTopColor: "var(--accent)",
                                        }}
                                    />
                                </div>
                            ) : versions.length === 0 ? (
                                <p className="text-xs italic" style={{ color: "var(--text-muted)" }}>No previous versions found.</p>
                            ) : (
                                <div className="space-y-2">
                                    {versions.map((v) => {
                                        const vSize = v.file_size >= 1024 * 1024
                                            ? `${(v.file_size / (1024 * 1024)).toFixed(1)} MB`
                                            : `${(v.file_size / 1024).toFixed(1)} KB`;
                                        return (
                                            <div
                                                key={v.id}
                                                className="flex items-center justify-between p-3 rounded-md border"
                                                style={{
                                                    background: v.is_current ? "var(--success-soft)" : "var(--bg-muted)",
                                                    borderColor: v.is_current
                                                        ? "color-mix(in srgb, var(--success) 25%, transparent)"
                                                        : "var(--border-default)",
                                                }}
                                            >
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                                                            v{v.version_number}
                                                        </span>
                                                        {v.is_current && (
                                                            <span
                                                                className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                                                                style={{ background: "var(--success-soft)", color: "var(--success)" }}
                                                            >
                                                                previous
                                                            </span>
                                                        )}
                                                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                                                            {vSize} &middot; {v.file_type.toUpperCase()}
                                                        </span>
                                                    </div>
                                                    {v.change_reason && (
                                                        <p className="text-xs mt-1 truncate" style={{ color: "var(--text-secondary)" }}>
                                                            {v.change_reason}
                                                        </p>
                                                    )}
                                                    <p className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                                                        {new Date(v.created_at).toLocaleDateString("en-IN", {
                                                            day: "numeric", month: "short", year: "numeric",
                                                            hour: "2-digit", minute: "2-digit",
                                                        })}
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-2 ml-3 shrink-0">
                                                    {canEdit && (
                                                        <button
                                                            onClick={() => handleRollback(v.version_number)}
                                                            disabled={rollingBack}
                                                            className="flex items-center gap-1 text-xs transition-colors cursor-pointer disabled:opacity-50"
                                                            style={{ color: "var(--text-secondary)" }}
                                                            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--warning)"; }}
                                                            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
                                                            title={`Restore version ${v.version_number}`}
                                                        >
                                                            <FiRotateCcw className="w-3.5 h-3.5" />
                                                            Restore
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Extracted metadata */}
            {doc.extracted_metadata && Object.keys(doc.extracted_metadata).length > 0 && (
                <div
                    className="p-5 rounded-lg border mb-6"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Extracted Metadata</h2>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                        {Object.entries(doc.extracted_metadata).map(([key, value]) => (
                            <MetadataItem key={key} label={key} value={String(value ?? "-")} />
                        ))}
                    </div>
                </div>
            )}

            {/* AI Summary */}
            {doc.ai_summary && (
                <div
                    className="p-5 rounded-lg border mb-6"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>AI Summary</h2>
                        {doc.ai_provider && (
                            <span
                                className="text-[10px] px-2 py-0.5 rounded uppercase tracking-wider font-medium border"
                                style={{
                                    background: "var(--bg-muted)",
                                    color: "var(--text-muted)",
                                    borderColor: "var(--border-default)",
                                }}
                            >
                                {doc.ai_provider}
                            </span>
                        )}
                    </div>
                    <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{doc.ai_summary}</p>
                </div>
            )}

            {/* AI Extracted Fields */}
            {doc.ai_extracted_fields && Object.keys(doc.ai_extracted_fields).length > 0 && (
                <div
                    className="p-5 rounded-lg border mb-6"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "var(--border-default)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>AI Extracted Fields</h2>
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
                                ? conf >= 0.8 ? "var(--success)" : conf >= 0.5 ? "var(--warning)" : "var(--danger)"
                                : "var(--text-muted)";
                            return (
                                <div
                                    key={key}
                                    className="flex items-start justify-between p-3 rounded-md border"
                                    style={{
                                        background: "var(--bg-muted)",
                                        borderColor: "var(--border-default)",
                                    }}
                                >
                                    <div className="min-w-0 flex-1">
                                        <p className="text-[11px] uppercase tracking-wider mb-1 font-semibold" style={{ color: "var(--text-muted)" }}>
                                            {key.replace(/_/g, " ")}
                                        </p>
                                        <p className="text-sm break-words" style={{ color: "var(--text-primary)" }}>{displayVal}</p>
                                    </div>
                                    {confPct !== null && (
                                        <span
                                            className="text-xs font-medium ml-3 shrink-0 tabular-nums"
                                            style={{ color: confColor }}
                                        >
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
                <div
                    className="p-4 rounded-lg border mb-6"
                    style={{
                        background: "var(--danger-soft)",
                        borderColor: "color-mix(in srgb, var(--danger) 25%, transparent)",
                    }}
                >
                    <p className="text-xs" style={{ color: "var(--danger)" }}>AI extraction failed: {doc.ai_error}</p>
                </div>
            )}

            {/* Saved highlights summary */}
            {highlights.length > 0 && !highlightMode && (
                <div
                    className="p-5 rounded-lg border mb-6"
                    style={{
                        background: "var(--bg-elevated)",
                        borderColor: "color-mix(in srgb, var(--warning) 25%, transparent)",
                        boxShadow: "var(--shadow-sm)",
                    }}
                >
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Highlighted Text ({highlights.length} selections)</h2>
                        <button
                            onClick={copyText}
                            className="flex items-center gap-1.5 text-xs transition-colors cursor-pointer"
                            style={{ color: "var(--text-secondary)" }}
                            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
                            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
                        >
                            <FiCopy className="w-3.5 h-3.5" />
                            Copy highlights
                        </button>
                    </div>
                    <div className="space-y-2">
                        {[...highlights].sort((a, b) => a.start - b.start).map((h, i) => (
                            <div
                                key={i}
                                className="p-2.5 rounded text-sm border"
                                style={{
                                    background: "var(--warning-soft)",
                                    borderColor: "color-mix(in srgb, var(--warning) 20%, transparent)",
                                    color: "var(--text-secondary)",
                                }}
                            >
                                {h.text.length > 150 ? h.text.slice(0, 150) + "..." : h.text}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Extracted text with highlighting */}
            <div
                className="rounded-lg border mb-6"
                style={{
                    background: "var(--bg-elevated)",
                    borderColor: highlightMode
                        ? "color-mix(in srgb, var(--warning) 40%, transparent)"
                        : "var(--border-default)",
                    boxShadow: "var(--shadow-sm)",
                }}
            >
                <div
                    className="flex items-center justify-between px-5 py-3 border-b"
                    style={{ borderColor: "var(--border-default)" }}
                >
                    <div className="flex items-center gap-3">
                        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Extracted Text</h2>
                        {highlightMode && (
                            <span
                                className="text-[10px] px-2 py-0.5 rounded uppercase tracking-wider animate-pulse font-medium"
                                style={{ background: "var(--warning-soft)", color: "var(--warning)" }}
                            >
                                Select text to highlight
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        {doc.extracted_text && (
                            <>
                                <button
                                    onClick={() => setHighlightMode(!highlightMode)}
                                    className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded transition-colors cursor-pointer"
                                    style={
                                        highlightMode
                                            ? { background: "var(--warning-soft)", color: "var(--warning)" }
                                            : { color: "var(--text-secondary)" }
                                    }
                                    onMouseEnter={(e) => {
                                        if (!highlightMode) e.currentTarget.style.color = "var(--text-primary)";
                                    }}
                                    onMouseLeave={(e) => {
                                        if (!highlightMode) e.currentTarget.style.color = "var(--text-secondary)";
                                    }}
                                >
                                    <FiEdit3 className="w-3.5 h-3.5" />
                                    {highlightMode ? "Done" : "Highlight"}
                                </button>
                                {hasChanges && (
                                    <button
                                        onClick={saveHighlights}
                                        disabled={saving}
                                        className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded transition-colors cursor-pointer disabled:opacity-50"
                                        style={{ background: "var(--success-soft)", color: "var(--success)" }}
                                    >
                                        <FiSave className="w-3.5 h-3.5" />
                                        {saving ? "Saving..." : "Save"}
                                    </button>
                                )}
                                {!highlightMode && (
                                    <button
                                        onClick={copyText}
                                        className="flex items-center gap-1.5 text-xs transition-colors cursor-pointer"
                                        style={{ color: "var(--text-secondary)" }}
                                        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
                                    >
                                        {copied
                                            ? <FiCheck className="w-3.5 h-3.5" style={{ color: "var(--success)" }} />
                                            : <FiCopy className="w-3.5 h-3.5" />}
                                        {copied ? "Copied" : "Copy"}
                                    </button>
                                )}
                            </>
                        )}
                    </div>
                </div>

                {/* Highlight chips in edit mode */}
                {highlightMode && highlights.length > 0 && (
                    <div
                        className="px-5 py-3 border-b flex flex-wrap gap-2"
                        style={{ borderColor: "var(--border-default)" }}
                    >
                        {[...highlights].sort((a, b) => a.start - b.start).map((h, i) => (
                            <span
                                key={i}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium"
                                style={{ background: "var(--warning-soft)", color: "var(--warning)" }}
                            >
                                {h.text.length > 30 ? h.text.slice(0, 30) + "..." : h.text}
                                <button
                                    onClick={() => removeHighlight(i)}
                                    className="cursor-pointer transition-colors"
                                    onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.color = "var(--warning)"; }}
                                >
                                    <FiX className="w-3 h-3" />
                                </button>
                            </span>
                        ))}
                    </div>
                )}

                <div className="p-5">
                    {doc.extracted_text ? (
                        <pre
                            className={`text-sm leading-relaxed whitespace-pre-wrap font-mono break-words max-h-[500px] overflow-y-auto ${
                                highlightMode ? "cursor-text select-text" : ""
                            }`}
                            style={{ color: "var(--text-secondary)" }}
                            onMouseUp={handleTextSelect}
                        >
                            <HighlightedText text={doc.extracted_text} highlights={highlights} />
                        </pre>
                    ) : (
                        <p className="text-sm italic" style={{ color: "var(--text-muted)" }}>No text extracted from this document.</p>
                    )}
                </div>
            </div>

            {/* Share Modal */}
            {showShareModal && (
                <div
                    className="fixed inset-0 flex items-center justify-center z-50 p-4"
                    style={{ background: "rgba(15, 23, 42, 0.55)" }}
                    onClick={() => setShowShareModal(false)}
                >
                    <div
                        className="rounded-lg w-full max-w-md p-6 border"
                        style={{
                            background: "var(--bg-elevated)",
                            borderColor: "var(--border-default)",
                            boxShadow: "var(--shadow-lg)",
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Share document</h3>
                            <button
                                onClick={() => setShowShareModal(false)}
                                className="cursor-pointer transition-colors touch-target flex items-center justify-center"
                                style={{ color: "var(--text-muted)" }}
                                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
                            >
                                <FiX className="w-4 h-4" />
                            </button>
                        </div>

                        <div className="flex gap-2 mb-4">
                            <input
                                type="email"
                                value={shareEmail}
                                onChange={(e) => setShareEmail(e.target.value)}
                                placeholder="Enter email address"
                                className="flex-1 px-3 py-2 rounded-md text-sm focus:outline-none transition-colors border"
                                style={{
                                    background: "var(--bg-page)",
                                    borderColor: "var(--border-default)",
                                    color: "var(--text-primary)",
                                }}
                                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-default)"; }}
                            />
                            <select
                                value={sharePermission}
                                onChange={(e) => setSharePermission(e.target.value)}
                                className="px-2 py-2 rounded-md text-sm focus:outline-none cursor-pointer border"
                                style={{
                                    background: "var(--bg-page)",
                                    borderColor: "var(--border-default)",
                                    color: "var(--text-primary)",
                                }}
                            >
                                <option value="view">View</option>
                                <option value="edit">Edit</option>
                            </select>
                            <button
                                onClick={handleShare}
                                disabled={sharingLoading || !shareEmail}
                                className="px-4 py-2 text-sm font-medium rounded-md transition-colors disabled:opacity-50 cursor-pointer"
                                style={{ background: "var(--accent)", color: "#ffffff" }}
                                onMouseEnter={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.background = "var(--accent-strong)"; }}
                                onMouseLeave={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.background = "var(--accent)"; }}
                            >
                                {sharingLoading ? "..." : "Share"}
                            </button>
                        </div>

                        {permissions.length > 0 && (
                            <div>
                                <p className="text-[11px] uppercase tracking-wider mb-2 font-semibold" style={{ color: "var(--text-muted)" }}>People with access</p>
                                <div className="space-y-2 max-h-48 overflow-y-auto">
                                    {permissions.map((p) => (
                                        <div
                                            key={p.id}
                                            className="flex items-center justify-between p-2.5 rounded-md border"
                                            style={{
                                                background: "var(--bg-muted)",
                                                borderColor: "var(--border-default)",
                                            }}
                                        >
                                            <div className="min-w-0 flex-1">
                                                <p className="text-sm truncate" style={{ color: "var(--text-primary)" }}>{p.user_name || p.user_email}</p>
                                                <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{p.user_email}</p>
                                            </div>
                                            <div className="flex items-center gap-2 ml-3">
                                                <span
                                                    className="text-xs px-2 py-0.5 rounded font-medium border"
                                                    style={{
                                                        background: "var(--bg-elevated)",
                                                        color: "var(--text-secondary)",
                                                        borderColor: "var(--border-default)",
                                                    }}
                                                >
                                                    {p.permission}
                                                </span>
                                                <button
                                                    onClick={() => handleRevoke(p.id)}
                                                    className="transition-colors cursor-pointer touch-target flex items-center justify-center"
                                                    style={{ color: "var(--text-muted)" }}
                                                    onMouseEnter={(e) => { e.currentTarget.style.color = "var(--danger)"; }}
                                                    onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
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
