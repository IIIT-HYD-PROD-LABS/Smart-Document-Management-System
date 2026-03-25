"use client";

import { useEffect, useState } from "react";
import { sharingApi } from "@/lib/api";
import { StatusBadge, LoadingSpinner } from "@/components";
import Link from "next/link";
import toast from "react-hot-toast";
import { FiFile, FiChevronLeft, FiChevronRight } from "react-icons/fi";

interface SharedDocument {
    id: number;
    original_filename: string;
    file_type: string;
    file_size: number;
    category: string;
    status: string;
    created_at: string;
}

export default function SharedWithMePage() {
    const [documents, setDocuments] = useState<SharedDocument[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const perPage = 20;

    useEffect(() => {
        setLoading(true);
        sharingApi.getSharedWithMe(page, perPage)
            .then((res) => {
                setDocuments(res.data.documents);
                setTotal(res.data.total);
            })
            .catch(() => {
                toast.error("Failed to load shared documents");
            })
            .finally(() => setLoading(false));
    }, [page]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <LoadingSpinner />
            </div>
        );
    }

    const totalPages = Math.ceil(total / perPage);

    return (
        <div>
            <h1 className="text-lg font-semibold text-white mb-6">Shared with me</h1>

            {documents.length === 0 ? (
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-12 text-center">
                    <FiFile className="w-8 h-8 text-[#27272a] mx-auto mb-3" />
                    <p className="text-sm text-[#52525b]">No documents have been shared with you yet</p>
                </div>
            ) : (
                <>
                    <div className="bg-[#111113] border border-[#27272a] rounded-lg overflow-x-auto">
                        <table className="w-full min-w-[640px]">
                            <thead>
                                <tr className="border-b border-[#27272a]">
                                    <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Document</th>
                                    <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Type</th>
                                    <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Category</th>
                                    <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Status</th>
                                    <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Shared</th>
                                </tr>
                            </thead>
                            <tbody>
                                {documents.map((doc) => (
                                    <tr key={doc.id} className="border-b border-[#1e1e21] last:border-0 hover:bg-[#18181b]/50">
                                        <td className="px-4 py-3">
                                            <Link href={`/dashboard/documents/${doc.id}`} className="text-sm text-white hover:text-[#a1a1aa] transition-colors">
                                                {doc.original_filename}
                                            </Link>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className="text-xs text-[#71717a] uppercase">{doc.file_type}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className="text-xs text-[#71717a]">{doc.category}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <StatusBadge status={doc.status} />
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className="text-xs text-[#71717a]">
                                                {new Date(doc.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4">
                            <p className="text-xs text-[#52525b]">
                                {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} of {total}
                            </p>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setPage(p => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                    className="p-1.5 rounded border border-[#27272a] text-[#71717a] hover:text-white disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                                >
                                    <FiChevronLeft className="w-4 h-4" />
                                </button>
                                <span className="text-xs text-[#71717a]">{page}/{totalPages}</span>
                                <button
                                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                    className="p-1.5 rounded border border-[#27272a] text-[#71717a] hover:text-white disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                                >
                                    <FiChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
