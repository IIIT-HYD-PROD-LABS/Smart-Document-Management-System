"use client";

import { useState } from "react";
import { documentsApi } from "@/lib/api";
import { FiSearch, FiFileText } from "react-icons/fi";

const categories = ["", "bills", "upi", "tickets", "tax", "bank", "invoices"];

function ConfidenceBadge({ score }: { score: number }) {
    if (score <= 0) return null;
    const pct = Math.round(score * 100);
    let colorClass: string;
    let label: string;
    if (score >= 0.8) {
        colorClass = "bg-[#10b981]/10 text-[#10b981]";
        label = "High";
    } else if (score >= 0.5) {
        colorClass = "bg-[#f59e0b]/10 text-[#f59e0b]";
        label = "Medium";
    } else {
        colorClass = "bg-[#ef4444]/10 text-[#ef4444]";
        label = "Low";
    }
    return (
        <span className={`text-[11px] px-2 py-0.5 rounded ${colorClass}`} title={`${label} confidence`}>
            {pct}%
        </span>
    );
}

export default function SearchPage() {
    const [query, setQuery] = useState("");
    const [category, setCategory] = useState("");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [amountMin, setAmountMin] = useState("");
    const [amountMax, setAmountMax] = useState("");
    const [results, setResults] = useState<any[]>([]);
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
        } finally {
            setLoading(false);
        }
    };

    const inputClass =
        "w-full px-3 py-2 bg-[#111113] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors";
    const labelClass = "block text-xs text-[#71717a] mb-1";

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold text-white">Search</h1>
                <p className="text-sm text-[#52525b] mt-1">Find documents by content or keywords</p>
            </div>

            <form onSubmit={handleSearch} className="mb-8 space-y-4">
                {/* Main search bar */}
                <div className="flex gap-2">
                    <div className="relative flex-1">
                        <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[#52525b] w-4 h-4" />
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="w-full pl-9 pr-3 py-2 bg-[#111113] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors"
                            placeholder="Search by content, keywords..."
                        />
                    </div>
                    <select
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="px-3 py-2 bg-[#111113] border border-[#27272a] rounded-md text-sm text-[#a1a1aa] focus:outline-none focus:border-[#3f3f46] transition-colors cursor-pointer"
                    >
                        <option value="">All</option>
                        {categories.filter(Boolean).map((c) => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                    <button
                        type="submit"
                        disabled={loading}
                        className="px-4 py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] disabled:opacity-50 transition-colors cursor-pointer"
                    >
                        {loading ? "..." : "Search"}
                    </button>
                </div>

                {/* Filter panel */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-4 bg-[#0d0d0f] border border-[#27272a] rounded-lg">
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
                    <p className="text-xs text-[#52525b] mb-4">
                        {results.length} result{results.length !== 1 ? "s" : ""}
                    </p>
                    {results.length > 0 ? (
                        <div className="bg-[#111113] border border-[#27272a] rounded-lg divide-y divide-[#1f1f23]">
                            {results.map((doc) => (
                                <div key={doc.id} className="px-5 py-4">
                                    <div className="flex items-center gap-3 mb-2">
                                        <FiFileText className="w-4 h-4 text-[#52525b]" />
                                        <span className="text-sm text-white">{doc.original_filename}</span>
                                        <span className="text-[11px] px-2 py-0.5 rounded bg-[#10b981]/10 text-[#10b981]">{doc.category}</span>
                                        <ConfidenceBadge score={doc.confidence_score} />
                                    </div>
                                    {doc.extracted_text && (
                                        <p className="text-xs text-[#71717a] leading-relaxed line-clamp-2 ml-7">
                                            {doc.extracted_text.substring(0, 200)}
                                        </p>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="bg-[#111113] border border-[#27272a] rounded-lg py-16 text-center">
                            <p className="text-sm text-[#52525b]">No documents match your search</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
