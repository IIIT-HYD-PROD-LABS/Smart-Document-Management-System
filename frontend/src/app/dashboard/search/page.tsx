"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { documentsApi } from "@/lib/api";
import { FiSearch, FiFileText } from "react-icons/fi";

const categories = ["", "bills", "upi", "tickets", "tax", "bank", "invoices"];

export default function SearchPage() {
    const [query, setQuery] = useState("");
    const [category, setCategory] = useState("");
    const [results, setResults] = useState<any[]>([]);
    const [searched, setSearched] = useState(false);
    const [loading, setLoading] = useState(false);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        setLoading(true);
        try {
            const res = await documentsApi.search(query, category || undefined);
            setResults(res.data.documents || []);
            setSearched(true);
        } catch {
            setResults([]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Search Documents</h1>
                <p className="text-slate-400 mt-1">Find documents by content, keywords, or category</p>
            </div>

            {/* Search Bar */}
            <form onSubmit={handleSearch} className="glass-card p-6 mb-8">
                <div className="flex gap-3">
                    <div className="relative flex-1">
                        <FiSearch className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 w-4 h-4" />
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="input-field !pl-11"
                            placeholder="Search by content, keywords, amount…"
                        />
                    </div>
                    <select
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="input-field !w-40"
                    >
                        <option value="">All Categories</option>
                        {categories.filter(Boolean).map((c) => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                    <button type="submit" disabled={loading} className="btn-primary whitespace-nowrap">
                        {loading ? "Searching…" : "Search"}
                    </button>
                </div>
            </form>

            {/* Results */}
            {searched && (
                <div>
                    <p className="text-sm text-slate-400 mb-4">
                        {results.length} result{results.length !== 1 ? "s" : ""} found
                    </p>
                    {results.length > 0 ? (
                        <div className="space-y-3">
                            {results.map((doc, i) => (
                                <motion.div
                                    key={doc.id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.05 }}
                                    className="glass-card p-5"
                                >
                                    <div className="flex items-start gap-4">
                                        <div className="w-10 h-10 rounded-xl bg-primary-600/15 flex items-center justify-center shrink-0 mt-0.5">
                                            <FiFileText className="w-5 h-5 text-primary-400" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-3 mb-1">
                                                <p className="text-sm font-medium text-white">{doc.original_filename}</p>
                                                <span className="text-xs px-2.5 py-0.5 rounded-full bg-primary-500/10 text-primary-400 capitalize">
                                                    {doc.category}
                                                </span>
                                            </div>
                                            {doc.extracted_text && (
                                                <p className="text-xs text-slate-500 leading-relaxed line-clamp-3">
                                                    {doc.extracted_text.substring(0, 250)}
                                                </p>
                                            )}
                                            <div className="flex items-center gap-4 mt-2 text-xs text-slate-600">
                                                <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                                                {doc.confidence_score && (
                                                    <span>{(doc.confidence_score * 100).toFixed(0)}% confidence</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-16 glass-card">
                            <FiSearch className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                            <p className="text-slate-400">No documents match your search</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
