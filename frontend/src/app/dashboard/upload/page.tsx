"use client";

import { useState, useCallback, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { documentsApi } from "@/lib/api";
import toast from "react-hot-toast";
import { FiUploadCloud, FiFile, FiCheckCircle, FiX, FiLoader } from "react-icons/fi";

interface UploadItem {
    file: File;
    status: "queued" | "uploading" | "uploaded" | "processing" | "completed" | "failed" | "error";
    uploadProgress: number;
    processingProgress?: { stage: string; progress: number };
    documentId?: number;
    taskId?: string;
    result?: any;
    error?: string;
}

export default function UploadPage() {
    const [uploads, setUploads] = useState<UploadItem[]>([]);
    const [uploading, setUploading] = useState(false);
    const pollTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

    const updateItem = useCallback((file: File, updates: Partial<UploadItem>) => {
        setUploads((prev) =>
            prev.map((u) => (u.file === file ? { ...u, ...updates } : u))
        );
    }, []);

    const pollProcessingStatus = useCallback((file: File, documentId: number) => {
        const poll = async () => {
            try {
                const { data } = await documentsApi.getStatus(documentId);
                if (data.status === "completed") {
                    updateItem(file, {
                        status: "completed",
                        result: {
                            category: data.category,
                            confidence_score: data.confidence_score,
                        },
                    });
                    return;
                }
                if (data.status === "failed") {
                    updateItem(file, { status: "failed", error: "Processing failed" });
                    return;
                }
                // Still processing
                updateItem(file, {
                    status: "processing",
                    processingProgress: data.progress,
                });
                const timer = setTimeout(poll, 2500);
                pollTimers.current.set(file.name, timer);
            } catch {
                updateItem(file, { status: "failed", error: "Status check failed" });
            }
        };
        poll();
    }, [updateItem]);

    const onDrop = useCallback((acceptedFiles: File[]) => {
        const newItems: UploadItem[] = acceptedFiles.map((f) => ({
            file: f,
            status: "queued",
            uploadProgress: 0,
        }));
        setUploads((prev) => [...prev, ...newItems]);
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
        const queued = uploads.filter((u) => u.status === "queued");

        for (const item of queued) {
            updateItem(item.file, { status: "uploading", uploadProgress: 0 });

            try {
                const res = await documentsApi.upload(item.file, (percent) => {
                    updateItem(item.file, { uploadProgress: percent });
                });

                const { id, task_id } = res.data;
                updateItem(item.file, {
                    status: "uploaded",
                    uploadProgress: 100,
                    documentId: id,
                    taskId: task_id,
                });

                // Start polling for processing status
                pollProcessingStatus(item.file, id);
            } catch (err: any) {
                updateItem(item.file, {
                    status: "error",
                    error: err.response?.data?.detail || "Upload failed",
                });
            }
        }

        setUploading(false);
    };

    const removeItem = (file: File) => {
        // Clear any active poll timer
        const timer = pollTimers.current.get(file.name);
        if (timer) {
            clearTimeout(timer);
            pollTimers.current.delete(file.name);
        }
        setUploads((prev) => prev.filter((u) => u.file !== file));
    };

    const clearAll = () => {
        // Clear all poll timers
        pollTimers.current.forEach((timer) => clearTimeout(timer));
        pollTimers.current.clear();
        setUploads([]);
    };

    const formatSize = (bytes: number) => {
        const mb = bytes / (1024 * 1024);
        return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
    };

    const getStageLabel = (stage: string) => {
        const labels: Record<string, string> = {
            queued: "Queued",
            reading_file: "Reading file",
            extracting_text: "Extracting text",
            extracting_metadata: "Extracting metadata",
            saving_results: "Saving results",
        };
        return labels[stage] || stage;
    };

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Upload Documents</h1>
                <p className="text-slate-400 mt-1">Drag & drop files to classify them with AI</p>
            </div>

            {/* Dropzone */}
            <div
                {...getRootProps()}
                className={`glass-card p-12 text-center cursor-pointer border-2 border-dashed transition-all duration-300 ${isDragActive
                        ? "border-primary-500 bg-primary-500/5 shadow-lg shadow-primary-500/10"
                        : "border-slate-700/50 hover:border-slate-600"
                    }`}
            >
                <input {...getInputProps()} />
                <FiUploadCloud className={`w-14 h-14 mx-auto mb-4 transition-colors ${isDragActive ? "text-primary-400" : "text-slate-500"}`} />
                <p className="text-lg font-medium text-white mb-2">
                    {isDragActive ? "Drop files here\u2026" : "Drop files here or click to browse"}
                </p>
                <p className="text-sm text-slate-500">
                    Supports PDF, PNG, JPG, TIFF, DOCX — Max 16 MB per file
                </p>
            </div>

            {/* Upload Queue */}
            {uploads.length > 0 && (
                <div className="mt-8">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-white">
                            Upload Queue ({uploads.length})
                        </h2>
                        <div className="flex gap-3">
                            <button
                                onClick={clearAll}
                                className="btn-ghost text-sm text-slate-400"
                            >
                                Clear All
                            </button>
                            <button
                                onClick={handleUploadAll}
                                disabled={uploading || uploads.every((u) => u.status !== "queued")}
                                className="btn-primary text-sm"
                            >
                                {uploading ? "Uploading\u2026" : "Upload All"}
                            </button>
                        </div>
                    </div>

                    <div className="space-y-3">
                        <AnimatePresence>
                            {uploads.map((item, i) => (
                                <motion.div
                                    key={i}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: 10 }}
                                    className="glass-card p-4"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="w-10 h-10 rounded-xl bg-primary-600/20 flex items-center justify-center">
                                            {item.status === "completed" ? (
                                                <FiCheckCircle className="w-5 h-5 text-emerald-400" />
                                            ) : item.status === "uploading" || item.status === "uploaded" || item.status === "processing" ? (
                                                <FiLoader className="w-5 h-5 text-primary-400 animate-spin" />
                                            ) : item.status === "error" || item.status === "failed" ? (
                                                <FiX className="w-5 h-5 text-red-400" />
                                            ) : (
                                                <FiFile className="w-5 h-5 text-slate-400" />
                                            )}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-white truncate">{item.file.name}</p>
                                            <p className="text-xs text-slate-500">
                                                {formatSize(item.file.size)}
                                            </p>
                                        </div>
                                        {item.status === "queued" && (
                                            <button onClick={() => removeItem(item.file)} className="text-slate-500 hover:text-red-400">
                                                <FiX className="w-4 h-4" />
                                            </button>
                                        )}
                                    </div>

                                    {/* Upload progress bar */}
                                    {item.status === "uploading" && (
                                        <div className="w-full bg-slate-700 rounded-full h-1.5 mt-3">
                                            <div
                                                className="bg-primary-500 h-1.5 rounded-full transition-all duration-300"
                                                style={{ width: `${item.uploadProgress}%` }}
                                            />
                                        </div>
                                    )}

                                    {/* Processing status */}
                                    {(item.status === "uploaded" || item.status === "processing") && (
                                        <p className="text-xs text-primary-400 mt-2">
                                            Processing{item.processingProgress ? `: ${getStageLabel(item.processingProgress.stage)}` : "..."}
                                        </p>
                                    )}

                                    {/* Completed result */}
                                    {item.status === "completed" && item.result && (
                                        <p className="text-xs text-emerald-400 mt-2">
                                            {item.result.category} ({(item.result.confidence_score * 100).toFixed(0)}%)
                                        </p>
                                    )}

                                    {/* Error message */}
                                    {(item.status === "error" || item.status === "failed") && item.error && (
                                        <p className="text-xs text-red-400 mt-2">{item.error}</p>
                                    )}
                                </motion.div>
                            ))}
                        </AnimatePresence>
                    </div>
                </div>
            )}
        </div>
    );
}
