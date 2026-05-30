"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useDropzone } from "react-dropzone";
import { AnimatePresence, motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { documentsApi, extractErrorMessage } from "@/lib/api";
import { ConfidenceBadge } from "@/components";
import { FiUploadCloud, FiFile, FiCheckCircle, FiX, FiLoader, FiLock } from "react-icons/fi";

interface UploadItem {
    file: File;
    status: "queued" | "uploading" | "uploaded" | "processing" | "completed" | "failed" | "error";
    uploadProgress: number;
    processingProgress?: { stage: string; progress: number };
    documentId?: number;
    taskId?: string;
    result?: { category: string; confidence_score: number | null };
    error?: string;
}

export default function UploadPage() {
    const { user } = useAuth();
    const router = useRouter();
    const [uploads, setUploads] = useState<UploadItem[]>([]);
    const [uploading, setUploading] = useState(false);
    const pollTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

    // Role guard: only editors and admins can upload.
    // The early return MUST live below all hooks (see render-time guard
    // at the bottom of this function) — placing it here would change
    // hook count between renders during auth hydration and crash React.
    useEffect(() => {
        if (user && user.role === "viewer") router.replace("/dashboard");
    }, [user, router]);

    const updateItem = useCallback((file: File, updates: Partial<UploadItem>) => {
        setUploads((prev) => prev.map((u) => (u.file === file ? { ...u, ...updates } : u)));
    }, []);

    const pollProcessingStatus = useCallback((file: File, documentId: number) => {
        let attempts = 0;
        const MAX_ATTEMPTS = 120;
        const poll = async () => {
            attempts++;
            if (attempts > MAX_ATTEMPTS) {
                updateItem(file, { status: "failed", error: "Processing timed out" });
                pollTimers.current.delete(file.name);
                return;
            }
            try {
                const { data } = await documentsApi.getStatus(documentId);
                if (data.status === "completed") {
                    updateItem(file, { status: "completed", result: { category: data.category, confidence_score: data.confidence_score } });
                    return;
                }
                if (data.status === "failed") { updateItem(file, { status: "failed", error: "Processing failed" }); return; }
                updateItem(file, { status: "processing", processingProgress: data.progress });
                const timer = setTimeout(poll, 2500);
                pollTimers.current.set(file.name, timer);
            } catch { updateItem(file, { status: "failed", error: "Status check failed" }); }
        };
        poll();
    }, [updateItem]);

    useEffect(() => {
        return () => {
            pollTimers.current.forEach((t) => clearTimeout(t));
            pollTimers.current.clear();
        };
    }, []);

    const onDrop = useCallback((acceptedFiles: File[]) => {
        setUploads((prev) => [...prev, ...acceptedFiles.map((f) => ({ file: f, status: "queued" as const, uploadProgress: 0 }))]);
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "application/pdf": [".pdf"],
            "image/png": [".png"],
            "image/jpeg": [".jpg", ".jpeg"],
            "image/tiff": [".tiff", ".tif"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
        },
        maxSize: 16 * 1024 * 1024,
    });

    const handleUploadAll = async () => {
        setUploading(true);
        for (const item of uploads.filter((u) => u.status === "queued")) {
            updateItem(item.file, { status: "uploading", uploadProgress: 0 });
            try {
                const res = await documentsApi.upload(item.file, (p) => updateItem(item.file, { uploadProgress: p }));
                const { id, task_id } = res.data;
                updateItem(item.file, { status: "uploaded", uploadProgress: 100, documentId: id, taskId: task_id });
                pollProcessingStatus(item.file, id);
            } catch (err: unknown) {
                updateItem(item.file, { status: "error", error: extractErrorMessage(err, "Upload failed") });
            }
        }
        setUploading(false);
    };

    const removeItem = (file: File) => {
        const timer = pollTimers.current.get(file.name);
        if (timer) { clearTimeout(timer); pollTimers.current.delete(file.name); }
        setUploads((prev) => prev.filter((u) => u.file !== file));
    };

    const clearAll = () => {
        pollTimers.current.forEach((t) => clearTimeout(t));
        pollTimers.current.clear();
        setUploads([]);
    };

    const formatSize = (bytes: number) => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;

    // Render-time role guard (replaces the pre-hooks early return that
    // violated Rules of Hooks). All hooks above unconditionally execute.
    // Render an explanatory notice instead of a blank frame during the
    // async redirect (the effect above routes viewers back to /dashboard).
    if (user?.role === "viewer") {
        return (
            <div className="surface-card py-14 px-6 text-center max-w-md mx-auto">
                <div className="w-12 h-12 rounded-full bg-[var(--bg-hover)] border border-[var(--border-default)] flex items-center justify-center mx-auto mb-4">
                    <FiLock className="w-5 h-5 text-[var(--text-subtle)]" />
                </div>
                <p className="text-[14px] font-medium text-[var(--text-primary)] mb-1">
                    Uploading requires editor access
                </p>
                <p className="text-[13px] text-[var(--text-muted)] mb-5">
                    Your account has view-only access. Ask an admin to upgrade your role to upload documents.
                </p>
                <Link
                    href="/dashboard"
                    className="
                        inline-flex items-center gap-1.5 h-9 px-3.5 rounded-md
                        border border-[var(--border-default)]
                        bg-[var(--bg-surface)]
                        text-[13px] font-medium text-[var(--text-primary)]
                        hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                        transition-colors duration-150 cursor-pointer
                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
                    "
                >
                    Back to overview
                </Link>
            </div>
        );
    }

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-2xl font-semibold text-[var(--text-primary)] tracking-tight">Upload</h1>
                <p className="text-sm mt-1 text-[var(--text-muted)]">Drop files to classify them with AI</p>
            </div>

            <div
                {...getRootProps()}
                className={`
                    rounded-xl p-16 text-center cursor-pointer border-2 group
                    transition-all duration-200 hover:shadow-sm
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
                    ${
                        isDragActive
                            ? "border-solid border-[var(--accent)] bg-[var(--accent-soft)]"
                            : "border-dashed border-[var(--border-default)] bg-[color-mix(in_srgb,var(--bg-elevated)_60%,transparent)] hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
                    }
                `}
            >
                <input {...getInputProps()} />
                <div
                    className={`
                        w-14 h-14 mx-auto mb-4 rounded-full flex items-center justify-center transition-colors
                        ${isDragActive ? "bg-[var(--accent-soft)]" : "bg-[var(--bg-muted)] group-hover:bg-[var(--accent-soft)]"}
                    `}
                >
                    <FiUploadCloud
                        className={`w-7 h-7 transition-colors ${isDragActive ? "text-[var(--accent)]" : "text-[var(--text-secondary)] group-hover:text-[var(--accent)]"}`}
                    />
                </div>
                <p className="text-base font-medium mb-1 text-[var(--text-primary)]">
                    {isDragActive ? "Release to upload" : "Drop files here or click to browse"}
                </p>
                <p className="text-xs text-[var(--text-muted)]">
                    PDF, PNG, JPG, TIFF, DOCX &middot; up to 16 MB each
                </p>
            </div>

            {uploads.length > 0 && (
                <div className="mt-6">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-sm text-[var(--text-secondary)]">
                            {uploads.length} file{uploads.length !== 1 ? "s" : ""}
                        </span>
                        <div className="flex gap-2">
                            <button
                                onClick={clearAll}
                                className="
                                    text-xs px-2 py-1 rounded-md transition-colors cursor-pointer
                                    text-[var(--text-muted)] hover:text-[var(--text-primary)]
                                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
                                "
                            >
                                Clear
                            </button>
                            <button
                                onClick={handleUploadAll}
                                disabled={uploading || uploads.every((u) => u.status !== "queued")}
                                className="
                                    px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer
                                    bg-[var(--accent)] text-white
                                    hover:bg-[var(--accent-strong)]
                                    disabled:opacity-40 transition-colors
                                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
                                "
                            >
                                {uploading ? "Uploading..." : "Upload all"}
                            </button>
                        </div>
                    </div>
                    <div
                        className="rounded-lg overflow-hidden border"
                        style={{
                            background: "var(--bg-elevated)",
                            borderColor: "var(--border-default)",
                            boxShadow: "var(--shadow-sm)",
                        }}
                    >
                        <AnimatePresence>
                            {uploads.map((item, idx) => {
                                const isComplete = item.status === "completed";
                                const isProgressing = ["uploading", "uploaded", "processing"].includes(item.status);
                                const isErrored = ["error", "failed"].includes(item.status);
                                return (
                                    <motion.div
                                        key={`${item.file.name}-${item.file.size}-${item.file.lastModified}`}
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        exit={{ opacity: 0 }}
                                        className="px-4 py-3"
                                        style={{
                                            borderTop: idx === 0 ? "none" : `1px solid var(--border-subtle)`,
                                        }}
                                    >
                                        <div className="flex items-center gap-3">
                                            <div
                                                className="w-8 h-8 rounded flex items-center justify-center shrink-0"
                                                style={{ background: "var(--bg-muted)" }}
                                            >
                                                {isComplete ? (
                                                    <FiCheckCircle className="w-4 h-4" style={{ color: "var(--success)" }} />
                                                ) : isProgressing ? (
                                                    <FiLoader className="w-4 h-4 animate-spin" style={{ color: "var(--text-secondary)" }} />
                                                ) : isErrored ? (
                                                    <FiX className="w-4 h-4" style={{ color: "var(--danger)" }} />
                                                ) : (
                                                    <FiFile className="w-4 h-4" style={{ color: "var(--text-muted)" }} />
                                                )}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm truncate" style={{ color: "var(--text-primary)" }}>{item.file.name}</p>
                                                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{formatSize(item.file.size)}</p>
                                            </div>
                                            {item.status === "queued" && (
                                                <button
                                                    onClick={() => removeItem(item.file)}
                                                    aria-label={`Remove ${item.file.name}`}
                                                    className="
                                                        cursor-pointer transition-colors touch-target flex items-center justify-center rounded-md
                                                        text-[var(--text-muted)] hover:text-[var(--danger)]
                                                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
                                                    "
                                                >
                                                    <FiX className="w-3.5 h-3.5" />
                                                </button>
                                            )}
                                        </div>
                                        {item.status === "uploading" && (
                                            <div
                                                className="w-full rounded-full h-1 mt-2 overflow-hidden"
                                                style={{ background: "var(--bg-muted)" }}
                                            >
                                                <div
                                                    className="h-1 rounded-full transition-all"
                                                    style={{
                                                        width: `${item.uploadProgress}%`,
                                                        background: "var(--success)",
                                                    }}
                                                />
                                            </div>
                                        )}
                                        {isComplete && item.result && (
                                            <div className="flex items-center gap-2 mt-1.5">
                                                <span className="text-xs font-medium" style={{ color: "var(--success)" }}>{item.result.category}</span>
                                                <ConfidenceBadge score={item.result.confidence_score ?? 0} />
                                            </div>
                                        )}
                                        {isErrored && item.error && (
                                            <p className="text-xs mt-1" style={{ color: "var(--danger)" }}>{item.error}</p>
                                        )}
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                    </div>
                </div>
            )}
        </div>
    );
}
