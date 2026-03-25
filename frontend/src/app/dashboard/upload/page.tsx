"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { AnimatePresence, motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { documentsApi } from "@/lib/api";
import { ConfidenceBadge } from "@/components";
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
    const { user } = useAuth();
    const router = useRouter();
    const [uploads, setUploads] = useState<UploadItem[]>([]);
    const [uploading, setUploading] = useState(false);
    const pollTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

    // Role guard: only editors and admins can upload
    useEffect(() => {
        if (user && user.role === "viewer") router.replace("/dashboard");
    }, [user, router]);

    if (user?.role === "viewer") return null;

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
            } catch (err: any) {
                updateItem(item.file, { status: "error", error: err.response?.data?.detail || "Upload failed" });
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

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold text-white">Upload</h1>
                <p className="text-sm text-[#52525b] mt-1">Drop files to classify them with AI</p>
            </div>

            <div
                {...getRootProps()}
                className={`bg-[#111113] border-2 border-dashed rounded-lg p-16 text-center cursor-pointer transition-colors ${isDragActive ? "border-[#10b981] bg-[#10b981]/[0.03]" : "border-[#27272a] hover:border-[#3f3f46]"}`}
            >
                <input {...getInputProps()} />
                <FiUploadCloud className={`w-8 h-8 mx-auto mb-3 ${isDragActive ? "text-[#10b981]" : "text-[#52525b]"}`} />
                <p className="text-sm text-[#a1a1aa] mb-1">{isDragActive ? "Drop here..." : "Drop files here or click to browse"}</p>
                <p className="text-xs text-[#52525b]">PDF, PNG, JPG, TIFF, DOCX up to 16 MB</p>
            </div>

            {uploads.length > 0 && (
                <div className="mt-6">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-sm text-[#a1a1aa]">{uploads.length} file{uploads.length !== 1 ? "s" : ""}</span>
                        <div className="flex gap-2">
                            <button onClick={clearAll} className="text-xs text-[#52525b] hover:text-[#a1a1aa] transition-colors cursor-pointer">Clear</button>
                            <button onClick={handleUploadAll} disabled={uploading || uploads.every((u) => u.status !== "queued")} className="px-3 py-1 text-xs font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] disabled:opacity-40 transition-colors cursor-pointer">
                                {uploading ? "Uploading..." : "Upload all"}
                            </button>
                        </div>
                    </div>
                    <div className="bg-[#111113] border border-[#27272a] rounded-lg divide-y divide-[#1f1f23]">
                        <AnimatePresence>
                            {uploads.map((item, i) => (
                                <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="px-4 py-3">
                                    <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 rounded bg-[#18181b] flex items-center justify-center">
                                            {item.status === "completed" ? <FiCheckCircle className="w-4 h-4 text-[#10b981]" /> :
                                             ["uploading","uploaded","processing"].includes(item.status) ? <FiLoader className="w-4 h-4 text-[#a1a1aa] animate-spin" /> :
                                             ["error","failed"].includes(item.status) ? <FiX className="w-4 h-4 text-[#ef4444]" /> :
                                             <FiFile className="w-4 h-4 text-[#52525b]" />}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-white truncate">{item.file.name}</p>
                                            <p className="text-xs text-[#52525b]">{formatSize(item.file.size)}</p>
                                        </div>
                                        {item.status === "queued" && <button onClick={() => removeItem(item.file)} className="text-[#52525b] hover:text-[#a1a1aa] cursor-pointer"><FiX className="w-3.5 h-3.5" /></button>}
                                    </div>
                                    {item.status === "uploading" && <div className="w-full bg-[#27272a] rounded-full h-1 mt-2"><div className="bg-[#10b981] h-1 rounded-full transition-all" style={{ width: `${item.uploadProgress}%` }} /></div>}
                                    {item.status === "completed" && item.result && (
                                        <div className="flex items-center gap-2 mt-1">
                                            <span className="text-xs text-[#10b981]">{item.result.category}</span>
                                            <ConfidenceBadge score={item.result.confidence_score} />
                                        </div>
                                    )}
                                    {["error","failed"].includes(item.status) && item.error && <p className="text-xs text-[#ef4444] mt-1">{item.error}</p>}
                                </motion.div>
                            ))}
                        </AnimatePresence>
                    </div>
                </div>
            )}
        </div>
    );
}
