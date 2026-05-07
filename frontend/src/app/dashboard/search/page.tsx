"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { documentsApi } from "@/lib/api";
import { ConfidenceBadge, CategoryBadge } from "@/components";
import { FiSearch, FiFileText } from "react-icons/fi";
import toast from "react-hot-toast";

const categories = ["", "bills", "upi", "tickets", "tax", "bank", "invoices"];

interface SearchResult {
    id: number;
    original_filename: string;
    category: string;
    confidence_score: number | null;
    extracted_text: string | null;
    status: string;
}

export default function SearchPage() {
    const router = useRouter();
    const [query, setQuery] = useState("");
    const [category, setCategory] = useState("");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [amountMin, setAmountMin] = useState("");
    const [amountMax, setAmountMax] = useState("");
    const [results, setResults] = useState<SearchResult[]>([]);
    const [searched, setSearched] = useState(false);
    const [loading, setLoading] = useState(false);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        setLoading(true);
        try {
            const res = await documentsApi.search(
                query,
                category || undefined,
                dateFrom || undefined,
                dateTo || undefined,
                amountMin !== "" ? Number(amountMin) : undefined,
                amountMax !== "" ? Number(amountMax) : undefined,
            );
            setResults(res.data.documents || []);
            setSearched(true);
        } catch {
            setResults([]);
            setSearched(true);
            toast.error("Search failed");
        } finally {
            setLoading(false);
        }
    };

    const inputClass =
        "w-full px-3 py-2 bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-md text-sm text-[var(--text-primary)] placeholder:text-[var(--text-subtle)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)] transition-colors";
    const labelClass = "block text-xs text-[var(--text-muted)] mb-1";

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold text-[var(--text-primary)]">Search</h1>
                <p className="text-sm text-[var(--text-muted)] mt-1">Find documents by content or keywords</p>
            </div>

            <form onSubmit={handleSearch} className="mb-8 space-y-4">
                {/* Main search bar */}
                <div className="flex flex-col sm:flex-row gap-2">
                    <div className="relative flex-1">
                        <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-subtle)] w-4 h-4" />
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="w-full pl-9 pr-3 py-2 bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-md text-sm text-[var(--text-primary)] placeholder:text-[var(--text-subtle)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)] transition-colors"
                            placeholder="Search by content, keywords..."
                        />
                    </div>
                    <select
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="px-3 py-2 bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-md text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)] transition-colors cursor-pointer"
                    >
                        <option value="">All</option>
                        {categories.filter(Boolean).map((c) => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                    <button
                        type="submit"
                        disabled={loading}
                        className="px-4 py-2 text-sm font-medium bg-[var(--accent)] text-white rounded-md hover:bg-[var(--accent-strong)] disabled:opacity-50 transition-colors cursor-pointer"
                    >
                        {loading ? "..." : "Search"}
                    </button>
                </div>

                {/* Filter panel */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-4 bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-lg">
                    <div>
                        <label className={labelClass}>Date from</label>
                        <input
                            type="date"
                            value={dateFrom}
                            onChange={(e) => setDateFrom(e.target.value)}
                            className={inputClass}
                        />
                    </div>
                    <div>
                        <label className={labelClass}>Date to</label>
                        <input
                            type="date"
                            value={dateTo}
                            onChange={(e) => setDateTo(e.target.value)}
                            className={inputClass}
                        />
                    </div>
                    <div>
                        <label className={labelClass}>Min amount</label>
                        <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={amountMin}
                            onChange={(e) => setAmountMin(e.target.value)}
                            placeholder="0.00"
                            className={inputClass}
                        />
                    </div>
                    <div>
                        <label className={labelClass}>Max amount</label>
                        <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={amountMax}
                            onChange={(e) => setAmountMax(e.target.value)}
                            placeholder="Any"
                            className={inputClass}
                        />
                    </div>
                </div>
            </form>

            {searched && (
                <div>
                    <p className="text-xs text-[var(--text-muted)] mb-4">
                        {results.length} result{results.length !== 1 ? "s" : ""}
                    </p>
                    {results.length > 0 ? (
                        <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg divide-y divide-[var(--border-default)]">
                            {results.map((doc) => (
                                <div
                                    key={doc.id}
                                    onClick={() => router.push(`/dashboard/documents/${doc.id}`)}
                                    className="px-5 py-4 hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
                                >
                                    <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-2">
                                        <FiFileText className="w-4 h-4 text-[var(--text-subtle)] shrink-0" />
                                        <span className="text-sm font-medium text-[var(--text-primary)] truncate max-w-[60vw] sm:max-w-none">{doc.original_filename}</span>
                                        <CategoryBadge category={doc.category} />
                                        <span className="hidden sm:inline-flex"><ConfidenceBadge score={doc.confidence_score ?? 0} /></span>
                                    </div>
                                    {doc.extracted_text && (
                                        <p className="text-xs text-[var(--text-muted)] leading-relaxed line-clamp-2 ml-7">
                                            {doc.extracted_text.substring(0, 200)}
                                        </p>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-lg py-16 text-center">
                            <p className="text-sm text-[var(--text-muted)]">No documents match your search</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
