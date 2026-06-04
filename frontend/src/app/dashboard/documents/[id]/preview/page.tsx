"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { documentsApi } from "@/lib/api";
import { LoadingSpinner, Skeleton } from "@/components";
import { FiArrowLeft, FiDownload, FiZoomIn, FiZoomOut, FiChevronLeft, FiChevronRight } from "react-icons/fi";
import toast from "react-hot-toast";
import Cookies from "js-cookie";

interface DocInfo {
    id: number;
    original_filename: string;
    file_type: string;
    extracted_text: string | null;
}

function getAuthHeaders(): Record<string, string> {
    const token = Cookies.get("token");
    return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function PreviewPage() {
    const params = useParams();
    const router = useRouter();
    const docId = Number(params.id);

    const [doc, setDoc] = useState<DocInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [blobUrl, setBlobUrl] = useState<string | null>(null);

    // PDF state
    const [numPages, setNumPages] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [zoom, setZoom] = useState(1);
    const [pdfModule, setPdfModule] = useState<{ Document: React.ComponentType<any>; Page: React.ComponentType<any>; pdfjs: any } | null>(null);

    // Image state
    const [imgZoom, setImgZoom] = useState(1);
    const [imgPosition, setImgPosition] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const dragStart = useRef({ x: 0, y: 0 });
    const imgRef = useRef<HTMLDivElement>(null);
    const imgZoomRef = useRef(imgZoom);
    imgZoomRef.current = imgZoom;

    useEffect(() => {
        documentsApi.getById(docId)
            .then((res) => setDoc(res.data))
            .catch(() => toast.error("Failed to load document"))
            .finally(() => setLoading(false));
    }, [docId]);

    useEffect(() => {
        if (doc?.file_type === "pdf") {
            import("react-pdf").then((mod) => {
                mod.pdfjs.GlobalWorkerOptions.workerSrc = new URL(
                    "pdfjs-dist/build/pdf.worker.min.mjs",
                    import.meta.url
                ).toString();
                setPdfModule(mod);
            });
        }
    }, [doc?.file_type]);

    useEffect(() => {
        if (!doc) return;
        const isPdf = doc.file_type === "pdf";
        const isImage = ["png", "jpg", "jpeg", "tiff", "bmp"].includes(doc.file_type);
        let cancelled = false;
        let currentBlobUrl: string | null = null;

        if (isPdf || isImage) {
            const url = documentsApi.getPreviewUrl(docId);
            fetch(url, { headers: getAuthHeaders() })
                .then(res => {
                    if (!res.ok) throw new Error("Preview fetch failed");
                    return res.blob();
                })
                .then(blob => {
                    if (cancelled) return;
                    currentBlobUrl = URL.createObjectURL(blob);
                    setBlobUrl(currentBlobUrl);
                })
                .catch(() => {
                    if (!cancelled) toast.error("Failed to load preview");
                });
        }

        return () => {
            cancelled = true;
            if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
        };
    }, [doc, docId]);

    useEffect(() => {
        const el = imgRef.current;
        if (!el) return;

        const onWheel = (e: WheelEvent) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            setImgZoom(prev => Math.max(0.25, Math.min(5, prev + delta)));
        };

        el.addEventListener("wheel", onWheel, { passive: false });
        return () => el.removeEventListener("wheel", onWheel);
    }, []);

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        setIsDragging(true);
        dragStart.current = { x: e.clientX - imgPosition.x, y: e.clientY - imgPosition.y };
    }, [imgPosition]);

    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        if (!isDragging) return;
        setImgPosition({
            x: e.clientX - dragStart.current.x,
            y: e.clientY - dragStart.current.y,
        });
    }, [isDragging]);

    const handleMouseUp = useCallback(() => setIsDragging(false), []);

    const handleDownload = useCallback(async () => {
        const url = documentsApi.getPreviewUrl(docId);
        try {
            const res = await fetch(url, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("Download failed");
            const blob = await res.blob();
            const downloadUrl = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = doc?.original_filename ?? "download";
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(downloadUrl);
        } catch {
            toast.error("Failed to download file");
        }
    }, [docId, doc?.original_filename]);

    if (loading) {
        return (
            <div
                role="status"
                aria-busy="true"
                aria-live="polite"
                className="flex flex-col h-[calc(100vh-3.5rem-3rem)] md:h-[calc(100vh-4rem)]"
            >
                <span className="sr-only">Loading document preview</span>
                {/* Top bar */}
                <div
                    className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b"
                    style={{
                        borderColor: "var(--border-default)",
                        background: "var(--bg-elevated)",
                    }}
                >
                    <div className="flex items-center gap-3 min-w-0">
                        <Skeleton className="w-5 h-5 shrink-0" />
                        <Skeleton className="h-4 w-40 sm:w-56" />
                        <Skeleton className="h-3 w-8 hidden sm:block" />
                    </div>
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-7 w-24 mr-1 sm:mr-3" />
                        <Skeleton className="h-7 w-24 rounded" />
                    </div>
                </div>
                {/* Content */}
                <div
                    className="flex-1 overflow-hidden p-4"
                    style={{ background: "var(--bg-page)" }}
                >
                    <Skeleton className="w-full h-full" />
                </div>
            </div>
        );
    }

    if (!doc) {
        return (
            <div className="text-center py-20" style={{ color: "var(--text-secondary)" }}>
                Document not found.
                <button
                    onClick={() => router.back()}
                    className="ml-2 underline cursor-pointer"
                    style={{ color: "var(--accent)" }}
                >
                    Go back
                </button>
            </div>
        );
    }

    const isPdf = doc.file_type === "pdf";
    const isImage = ["png", "jpg", "jpeg", "tiff", "bmp"].includes(doc.file_type);
    const isDocx = doc.file_type === "docx";

    return (
        <div className="flex flex-col h-[calc(100vh-3.5rem-3rem)] md:h-[calc(100vh-4rem)]">
            {/* Top bar */}
            <div
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b"
                style={{
                    borderColor: "var(--border-default)",
                    background: "var(--bg-elevated)",
                }}
            >
                <div className="flex items-center gap-3 min-w-0">
                    <button
                        onClick={() => router.back()}
                        className="transition-colors shrink-0 cursor-pointer touch-target flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    >
                        <FiArrowLeft className="w-5 h-5" />
                    </button>
                    <span className="text-sm font-medium truncate max-w-[200px] sm:max-w-[300px]" style={{ color: "var(--text-primary)" }}>
                        {doc.original_filename}
                    </span>
                    <span className="text-xs uppercase hidden sm:inline" style={{ color: "var(--text-muted)" }}>{doc.file_type}</span>
                </div>
                <div className="flex items-center gap-2">
                    {isPdf && numPages > 0 && (
                        <div className="flex items-center gap-1 mr-1 sm:mr-3">
                            <button
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage <= 1}
                                className="p-1.5 rounded disabled:opacity-30 transition-colors touch-target flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:hover:bg-transparent"
                            >
                                <FiChevronLeft className="w-4 h-4" />
                            </button>
                            <span className="text-xs min-w-[60px] text-center tabular-nums" style={{ color: "var(--text-secondary)" }}>
                                {currentPage} / {numPages}
                            </span>
                            <button
                                onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))}
                                disabled={currentPage >= numPages}
                                className="p-1.5 rounded disabled:opacity-30 transition-colors touch-target flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:hover:bg-transparent"
                            >
                                <FiChevronRight className="w-4 h-4" />
                            </button>
                        </div>
                    )}
                    {(isPdf || isImage) && (
                        <div className="flex items-center gap-1 mr-1 sm:mr-3">
                            <button
                                onClick={() => isPdf ? setZoom(z => Math.max(0.5, z - 0.25)) : setImgZoom(z => Math.max(0.25, z - 0.25))}
                                className="p-1.5 rounded transition-colors touch-target flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                            >
                                <FiZoomOut className="w-4 h-4" />
                            </button>
                            <span className="text-xs min-w-[40px] text-center tabular-nums" style={{ color: "var(--text-secondary)" }}>
                                {Math.round((isPdf ? zoom : imgZoom) * 100)}%
                            </span>
                            <button
                                onClick={() => isPdf ? setZoom(z => Math.min(3, z + 0.25)) : setImgZoom(z => Math.min(5, z + 0.25))}
                                className="p-1.5 rounded transition-colors touch-target flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                            >
                                <FiZoomIn className="w-4 h-4" />
                            </button>
                        </div>
                    )}
                    <button
                        onClick={handleDownload}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors cursor-pointer font-medium text-white bg-[var(--accent)] hover:bg-[var(--accent-strong)]"
                    >
                        <FiDownload className="w-3.5 h-3.5" /> <span className="hidden sm:inline">Download</span>
                    </button>
                </div>
            </div>

            {/* Content */}
            <div
                className="flex-1 overflow-auto flex items-start justify-center p-4"
                style={{ background: "var(--bg-page)" }}
            >
                {isPdf && pdfModule && blobUrl && (
                    <div style={{ transform: `scale(${zoom})`, transformOrigin: "top center" }}>
                        <pdfModule.Document
                            file={blobUrl}
                            onLoadSuccess={({ numPages: n }: { numPages: number }) => setNumPages(n)}
                            loading={
                                <div className="flex items-center justify-center py-20">
                                    <LoadingSpinner size="w-6 h-6" />
                                </div>
                            }
                        >
                            <pdfModule.Page
                                pageNumber={currentPage}
                                renderTextLayer={false}
                                renderAnnotationLayer={false}
                                className="shadow-lg"
                            />
                        </pdfModule.Document>
                    </div>
                )}

                {isImage && blobUrl && (
                    <div
                        ref={imgRef}
                        className="cursor-grab active:cursor-grabbing overflow-hidden w-full h-full flex items-center justify-center"
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        onMouseLeave={handleMouseUp}
                    >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={blobUrl}
                            alt={doc.original_filename}
                            width={1200}
                            height={1600}
                            className="max-w-none select-none"
                            style={{
                                transform: `translate(${imgPosition.x}px, ${imgPosition.y}px) scale(${imgZoom})`,
                                transformOrigin: "center center",
                                width: "auto",
                                height: "auto",
                            }}
                            draggable={false}
                        />
                    </div>
                )}

                {isDocx && (
                    <div className="max-w-3xl w-full">
                        <div
                            className="mb-3 px-4 py-2 rounded text-xs border"
                            style={{
                                background: "var(--bg-elevated)",
                                borderColor: "var(--border-default)",
                                color: "var(--text-secondary)",
                            }}
                        >
                            Showing extracted text. Download the file for full formatting.
                        </div>
                        <pre
                            className="whitespace-pre-wrap text-sm rounded-lg p-6 leading-relaxed border"
                            style={{
                                background: "var(--bg-elevated)",
                                borderColor: "var(--border-default)",
                                color: "var(--text-secondary)",
                                boxShadow: "var(--shadow-sm)",
                            }}
                        >
                            {doc.extracted_text || "No text extracted yet."}
                        </pre>
                    </div>
                )}

                {!isPdf && !isImage && !isDocx && (
                    <div className="text-center py-20" style={{ color: "var(--text-secondary)" }}>
                        Preview not available for this file type. <br />
                        <button
                            onClick={handleDownload}
                            className="underline mt-2 inline-block cursor-pointer"
                            style={{ color: "var(--accent)" }}
                        >
                            Download instead
                        </button>
                    </div>
                )}

                {(isPdf || isImage) && !blobUrl && !loading && (
                    <div className="flex items-center justify-center py-20">
                        <LoadingSpinner size="w-6 h-6" />
                    </div>
                )}
            </div>
        </div>
    );
}
