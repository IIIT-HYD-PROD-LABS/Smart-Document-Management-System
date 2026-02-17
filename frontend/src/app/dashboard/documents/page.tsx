"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { documentsApi } from "@/lib/api";
import toast from "react-hot-toast";
import { FiFileText, FiTrash2, FiDownload, FiFilter } from "react-icons/fi";

const categories = ["all", "bills", "upi", "tickets", "tax", "bank", "invoices", "unknown"];

const categoryColors: Record<string, string> = {
    bills: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    upi: "bg-violet-500/10 text-violet-400 border-violet-500/20",
    tickets: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    tax: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    bank: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
    invoices: "bg-rose-500/10 text-rose-400 border-rose-500/20",
    unknown: "bg-slate-500/10 text-slate-400 border-slate-500/20",
};

export default function DocumentsPage() {
    const [documents, setDocuments] = useState<any[]>([]);
    const [filteredDocs, setFilteredDocs] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeCategory, setActiveCategory] = useState("all");

    useEffect(() => {
        loadDocuments();
    }, []);

    useEffect(() => {
        if (activeCategory === "all") {
            setFilteredDocs(documents);
        } else {
            setFilteredDocs(documents.filter((d) => d.category === activeCategory));
        }
    }, [activeCategory, documents]);

    const loadDocuments = async () => {
        try {
            const res = await documentsApi.getAll();
            setDocuments(res.data.documents || []);
        } catch {
            toast.error("Failed to load documents");
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm("Delete this document?")) return;
        try {
            await documentsApi.delete(id);
            setDocuments((prev) => prev.filter((d) => d.id !== id));
            toast.success("Document deleted");
        } catch {
            toast.error("Failed to delete");
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="w-8 h-8 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-white">Documents</h1>
                    <p className="text-slate-400 mt-1">{documents.length} documents in your library</p>
                </div>
            </div>

            {/* Category Filter */}
            <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
                <FiFilter className="w-4 h-4 text-slate-500 shrink-0" />
                {categories.map((cat) => (
                    <button
                        key={cat}
                        onClick={() => setActiveCategory(cat)}
                        className={`px-4 py-1.5 rounded-full text-sm font-medium capitalize transition-all whitespace-nowrap ${activeCategory === cat
                                ? "bg-primary-600/20 text-primary-300 border border-primary-500/30"
                                : "text-slate-400 border border-slate-800 hover:border-slate-700 hover:text-white"
                            }`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Document Grid */}
            {filteredDocs.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredDocs.map((doc, i) => (
                        <motion.div
                            key={doc.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.03 }}
                            className="glass-card p-5 group"
                        >
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className="w-10 h-10 rounded-xl bg-primary-600/15 flex items-center justify-center shrink-0">
                                        <FiFileText className="w-5 h-5 text-primary-400" />
                                    </div>
                                    <div className="min-w-0">
                                        <p className="text-sm font-medium text-white truncate">{doc.original_filename}</p>
                                        <p className="text-xs text-slate-500">
                                            {doc.file_size ? `${(doc.file_size / 1024).toFixed(1)} KB` : ""}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button onClick={() => handleDelete(doc.id)} className="p-1.5 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-400">
                                        <FiTrash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 mb-3">
                                <span className={`text-xs px-2.5 py-1 rounded-full border capitalize ${categoryColors[doc.category] || categoryColors.unknown}`}>
                                    {doc.category}
                                </span>
                                {doc.confidence_score && (
                                    <span className="text-xs text-slate-500">
                                        {(doc.confidence_score * 100).toFixed(0)}% confidence
                                    </span>
                                )}
                            </div>

                            {doc.extracted_text && (
                                <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                                    {doc.extracted_text.substring(0, 120)}…
                                </p>
                            )}

                            <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-800/50">
                                <span className={`text-xs px-2 py-0.5 rounded ${doc.status === "completed" ? "bg-emerald-500/10 text-emerald-400" :
                                        doc.status === "processing" ? "bg-amber-500/10 text-amber-400" :
                                            "bg-slate-500/10 text-slate-400"
                                    }`}>
                                    {doc.status}
                                </span>
                                <span className="text-xs text-slate-600">
                                    {new Date(doc.created_at).toLocaleDateString()}
                                </span>
                            </div>
                        </motion.div>
                    ))}
                </div>
            ) : (
                <div className="text-center py-20 glass-card">
                    <FiFileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                    <p className="text-slate-400">No documents found</p>
                </div>
            )}
        </div>
    );
}
