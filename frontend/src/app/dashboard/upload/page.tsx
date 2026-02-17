"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { documentsApi } from "@/lib/api";
import toast from "react-hot-toast";
import { FiUploadCloud, FiFile, FiCheckCircle, FiX, FiLoader } from "react-icons/fi";

interface UploadItem {
    file: File;
    status: "queued" | "uploading" | "done" | "error";
    result?: any;
    error?: string;
}

export default function UploadPage() {
    const [uploads, setUploads] = useState<UploadItem[]>([]);
    const [uploading, setUploading] = useState(false);

    const onDrop = useCallback((acceptedFiles: File[]) => {
        const newItems: UploadItem[] = acceptedFiles.map((f) => ({ file: f, status: "queued" }));
        setUploads((prev) => [...prev, ...newItems]);
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "application/pdf": [".pdf"],
            "image/png": [".png"],
            "image/jpeg": [".jpg", ".jpeg"],
            "image/tiff": [".tiff", ".tif"],
        },
        maxSize: 16 * 1024 * 1024,
    });

    const handleUploadAll = async () => {
        setUploading(true);
        const queued = uploads.filter((u) => u.status === "queued");

        for (let i = 0; i < queued.length; i++) {
            const item = queued[i];
            setUploads((prev) =>
                prev.map((u) => (u.file === item.file ? { ...u, status: "uploading" } : u))
            );
            try {
                const res = await documentsApi.upload(item.file);
                setUploads((prev) =>
                    prev.map((u) =>
                        u.file === item.file ? { ...u, status: "done", result: res.data } : u
                    )
                );
            } catch (err: any) {
                setUploads((prev) =>
                    prev.map((u) =>
                        u.file === item.file
                            ? { ...u, status: "error", error: err.response?.data?.detail || "Upload failed" }
                            : u
                    )
                );
            }
        }

        setUploading(false);
        const doneCount = uploads.filter((u) => u.status === "done").length + queued.length;
        toast.success(`Uploaded ${doneCount} document(s)`);
    };

    const removeItem = (file: File) => {
        setUploads((prev) => prev.filter((u) => u.file !== file));
    };

    const formatSize = (bytes: number) => {
        const mb = bytes / (1024 * 1024);
        return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
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
                    {isDragActive ? "Drop files here…" : "Drop files here or click to browse"}
                </p>
                <p className="text-sm text-slate-500">
                    Supports PDF, PNG, JPG, TIFF — Max 16 MB per file
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
                                onClick={() => setUploads([])}
                                className="btn-ghost text-sm text-slate-400"
                            >
                                Clear All
                            </button>
                            <button
                                onClick={handleUploadAll}
                                disabled={uploading || uploads.every((u) => u.status !== "queued")}
                                className="btn-primary text-sm"
                            >
                                {uploading ? "Uploading…" : "Upload All"}
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
                                    className="glass-card p-4 flex items-center gap-4"
                                >
                                    <div className="w-10 h-10 rounded-xl bg-primary-600/20 flex items-center justify-center">
                                        {item.status === "done" ? (
                                            <FiCheckCircle className="w-5 h-5 text-emerald-400" />
                                        ) : item.status === "uploading" ? (
                                            <FiLoader className="w-5 h-5 text-primary-400 animate-spin" />
                                        ) : item.status === "error" ? (
                                            <FiX className="w-5 h-5 text-red-400" />
                                        ) : (
                                            <FiFile className="w-5 h-5 text-slate-400" />
                                        )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate">{item.file.name}</p>
                                        <p className="text-xs text-slate-500">
                                            {formatSize(item.file.size)}
                                            {item.result && (
                                                <span className="ml-2 text-emerald-400">
                                                    → {item.result.category} ({(item.result.confidence_score * 100).toFixed(0)}%)
                                                </span>
                                            )}
                                            {item.error && <span className="ml-2 text-red-400">{item.error}</span>}
                                        </p>
                                    </div>
                                    {item.status === "queued" && (
                                        <button onClick={() => removeItem(item.file)} className="text-slate-500 hover:text-red-400">
                                            <FiX className="w-4 h-4" />
                                        </button>
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
