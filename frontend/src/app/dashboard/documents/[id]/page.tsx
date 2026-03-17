"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { documentsApi } from "@/lib/api";
import { FiArrowLeft, FiFile, FiCalendar, FiTag, FiHash, FiCopy, FiCheck } from "react-icons/fi";

interface ExtractedFieldItem {
    value: string;
    confidence: number;
}

interface AIExtractedData {
    dates?: ExtractedFieldItem[];
    amounts?: ExtractedFieldItem[];
    parties?: ExtractedFieldItem[];
    key_terms?: ExtractedFieldItem[];
    [key: string]: ExtractedFieldItem[] | undefined;
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
    ai_extracted_data: AIExtractedData | null;
    extraction_status: string | null;
    status: string;
    s3_url: string | null;
    created_at: string;
    updated_at: string | null;
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

function ExtractionStatusBadge({ status }: { status: string | null }) {
    if (!status) return null;
    const config: Record<string, { bg: string; text: string; label: string }> = {
        completed: { bg: "bg-[#10b981]/10", text: "text-[#10b981]", label: "AI Extracted" },
        processing: { bg: "bg-[#f59e0b]/10", text: "text-[#f59e0b]", label: "AI Processing" },
        pending: { bg: "bg-[#3b82f6]/10", text: "text-[#3b82f6]", label: "AI Pending" },
        failed: { bg: "bg-[#ef4444]/10", text: "text-[#ef4444]", label: "AI Failed" },
    };
    const c = config[status];
    if (!c) return null;
    return (
        <span className={`text-xs px-2.5 py-1 rounded-md ${c.bg} ${c.text}`}>
            {c.label}
        </span>
    );
}

function ExtractionConfidenceBadge({ confidence }: { confidence: number }) {
    const pct = Math.round(confidence * 100);
    let color: string;
    if (confidence >= 0.8) color = "bg-[#10b981]/10 text-[#10b981]";
    else if (confidence >= 0.5) color = "bg-[#f59e0b]/10 text-[#f59e0b]";
    else color = "bg-[#ef4444]/10 text-[#ef4444]";
    return (
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${color} font-medium`}>
            {pct}%
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

const FIELD_GROUP_LABELS: Record<string, string> = {
    dates: "Dates",
    amounts: "Amounts",
    parties: "Parties",
    key_terms: "Key Terms",
};

function renderFieldGroup(groupKey: string, items: ExtractedFieldItem[]) {
    if (!items || items.length === 0) return null;
    const label = FIELD_GROUP_LABELS[groupKey] || groupKey;
    return (
        <div key={groupKey}>
            <p className="text-[11px] text-[#52525b] uppercase tracking-wider mb-2">{label}</p>
            <div className="flex flex-wrap gap-2">
                {items.map((item, idx) => (
                    <span
                        key={`${groupKey}-${idx}`}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-[#18181b] border border-[#27272a] rounded-md text-sm text-white"
                    >
                        {item.value}
                        <ExtractionConfidenceBadge confidence={item.confidence} />
                    </span>
                ))}
            </div>
        </div>
    );
}

export default function DocumentDetailPage() {
    const params = useParams();
    const router = useRouter();
    const [doc, setDoc] = useState<DocumentDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        const id = Number(params.id);
        if (!id) return;
        documentsApi.getById(id)
            .then((res) => setDoc(res.data))
            .catch(() => setError("Document not found"))
            .finally(() => setLoading(false));
    }, [params.id]);

    const copyText = () => {
        if (!doc?.extracted_text) return;
        navigator.clipboard.writeText(doc.extracted_text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
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

    const hasAIData = doc.ai_summary || (doc.ai_extracted_data && Object.keys(doc.ai_extracted_data).length > 0);

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
                <div className="flex items-center gap-2">
                    <ExtractionStatusBadge status={doc.extraction_status} />
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

            {/* AI Summary section -- only if ai_summary exists */}
            {doc.ai_summary && (
                <div className="p-5 bg-[#111113] border border-[#27272a] rounded-lg mb-6">
                    <h2 className="text-sm font-medium text-white mb-3">AI Summary</h2>
                    <p className="text-sm text-[#a1a1aa] leading-relaxed whitespace-pre-wrap">
                        {doc.ai_summary}
                    </p>
                </div>
            )}

            {/* AI Extracted Fields section -- only if ai_extracted_data has content */}
            {doc.ai_extracted_data && Object.keys(doc.ai_extracted_data).length > 0 && (
                <div className="p-5 bg-[#111113] border border-[#27272a] rounded-lg mb-6">
                    <h2 className="text-sm font-medium text-white mb-4">AI Extracted Fields</h2>
                    <div className="space-y-4">
                        {(["dates", "amounts", "parties", "key_terms"] as const).map((groupKey) => {
                            const items = doc.ai_extracted_data?.[groupKey];
                            if (!items || items.length === 0) return null;
                            return renderFieldGroup(groupKey, items);
                        })}
                        {/* Render any additional field groups not in the standard set */}
                        {Object.keys(doc.ai_extracted_data)
                            .filter((k) => !["dates", "amounts", "parties", "key_terms"].includes(k))
                            .map((groupKey) => {
                                const items = doc.ai_extracted_data?.[groupKey];
                                if (!items || items.length === 0) return null;
                                return renderFieldGroup(groupKey, items);
                            })}
                    </div>
                </div>
            )}

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

            {/* Extracted text */}
            <div className="bg-[#111113] border border-[#27272a] rounded-lg">
                <div className="flex items-center justify-between px-5 py-3 border-b border-[#27272a]">
                    <h2 className="text-sm font-medium text-white">Extracted Text</h2>
                    {doc.extracted_text && (
                        <button
                            onClick={copyText}
                            className="flex items-center gap-1.5 text-xs text-[#71717a] hover:text-white transition-colors cursor-pointer"
                        >
                            {copied ? <FiCheck className="w-3.5 h-3.5 text-[#10b981]" /> : <FiCopy className="w-3.5 h-3.5" />}
                            {copied ? "Copied" : "Copy"}
                        </button>
                    )}
                </div>
                <div className="p-5">
                    {doc.extracted_text ? (
                        <pre className="text-sm text-[#a1a1aa] leading-relaxed whitespace-pre-wrap font-mono break-words max-h-[500px] overflow-y-auto">
                            {doc.extracted_text}
                        </pre>
                    ) : (
                        <p className="text-sm text-[#52525b] italic">No text extracted from this document.</p>
                    )}
                </div>
            </div>
        </div>
    );
}
