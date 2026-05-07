"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
    FiSearch,
    FiArrowLeft,
    FiFile,
    FiBookOpen,
    FiInfo,
} from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { UnifiedSearchHit } from "@/types/compliance";
import { AuthorityBadge } from "@/components/compliance/AuthorityBadge";
import { RiskTierDot } from "@/components/compliance/RiskTierDot";

/**
 * Phase 13 v2.0 unified search page — at /dashboard/compliance/search.
 *
 * Searches compliance_notices + documents in a single query, ranked by
 * ts_rank_cd. Currently backed by PostgreSQL FTS; v2.1 will swap the
 * backend to Elasticsearch with no API contract change.
 *
 * Snippets from `ts_headline` contain server-inserted <b> tags around
 * matches but the source text may also contain user-controlled HTML.
 * v2.0 strips ALL tags client-side to neutralize any XSS surface; v2.1
 * will server-side sanitize + restore highlighting.
 */
type EntityFilter = "all" | "notice" | "document";

function stripHtml(s: string): string {
    return s.replace(/<[^>]*>/g, "");
}

export default function UnifiedSearchPage() {
    const [input, setInput] = useState("");
    const [query, setQuery] = useState("");
    const [filter, setFilter] = useState<EntityFilter>("all");

    useEffect(() => {
        const t = setTimeout(() => setQuery(input.trim()), 300);
        return () => clearTimeout(t);
    }, [input]);

    const types = filter === "all" ? "notice,document" : filter;

    const searchQ = useQuery({
        queryKey: ["unified-search", query, types],
        queryFn: async () => {
            if (!query) return null;
            const { data } = await complianceApi.unifiedSearch({
                q: query,
                entity_types: types,
                page: 1,
                page_size: 25,
            });
            return data;
        },
        enabled: query.length > 0,
    });

    const hits: UnifiedSearchHit[] = searchQ.data?.items ?? [];

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <Link
                href="/dashboard/compliance"
                className="inline-flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-4"
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to dashboard
            </Link>

            <header className="mb-6">
                <h1 className="text-2xl font-semibold text-[var(--text-primary)] tracking-tight mb-2">
                    Search
                </h1>
                <p className="text-[13px] text-[var(--text-muted)]">
                    Cross-entity search across compliance notices and DMS
                    documents.
                </p>
            </header>

            <div className="mb-4 flex flex-wrap items-center gap-3">
                <div className="relative flex-1 min-w-[280px]">
                    <FiSearch
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] w-4 h-4"
                        aria-hidden
                    />
                    <input
                        type="search"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Search notices and documents…"
                        className="w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded pl-10 pr-3 h-10 text-[14px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]"
                        autoFocus
                    />
                </div>
                <FilterTabs value={filter} onChange={setFilter} />
            </div>

            <ResultArea
                isLoading={searchQ.isLoading}
                isError={searchQ.isError}
                hasQuery={query.length > 0}
                hits={hits}
                backend={searchQ.data?.backend ?? "postgres-fts"}
            />
        </div>
    );
}

function FilterTabs({
    value,
    onChange,
}: {
    value: EntityFilter;
    onChange: (v: EntityFilter) => void;
}) {
    const tabs: { id: EntityFilter; label: string }[] = [
        { id: "all", label: "All" },
        { id: "notice", label: "Notices" },
        { id: "document", label: "Documents" },
    ];
    return (
        <div className="inline-flex items-center gap-1 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded p-1">
            {tabs.map((t) => (
                <button
                    key={t.id}
                    type="button"
                    onClick={() => onChange(t.id)}
                    className={`px-3 h-7 text-[12px] rounded ${
                        value === t.id
                            ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                            : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                    }`}
                >
                    {t.label}
                </button>
            ))}
        </div>
    );
}

function ResultArea({
    isLoading,
    isError,
    hasQuery,
    hits,
    backend,
}: {
    isLoading: boolean;
    isError: boolean;
    hasQuery: boolean;
    hits: UnifiedSearchHit[];
    backend: string;
}) {
    if (!hasQuery) {
        return (
            <div className="surface-card px-5 py-8 text-center">
                <FiSearch className="w-6 h-6 text-[var(--text-muted)] mx-auto mb-2" />
                <p className="text-[13px] text-[var(--text-secondary)]">
                    Type a query to search.
                </p>
            </div>
        );
    }
    if (isLoading) {
        return (
            <ul className="space-y-2">
                {[0, 1, 2, 3].map((i) => (
                    <li
                        key={i}
                        className="h-16 bg-[var(--bg-hover)] rounded animate-pulse"
                    />
                ))}
            </ul>
        );
    }
    if (isError) {
        return (
            <div className="rounded border border-[color:color-mix(in_srgb,var(--danger)_30%,transparent)] bg-[var(--danger-soft)] px-3 py-2 text-[13px] text-[var(--danger)]">
                Search failed. Refresh the page or try a different query.
            </div>
        );
    }
    if (hits.length === 0) {
        return (
            <div className="surface-card px-5 py-8 text-center">
                <p className="text-[13px] text-[var(--text-secondary)]">No results.</p>
            </div>
        );
    }
    return (
        <>
            <ul className="space-y-2 mb-3">
                {hits.map((hit) => (
                    <SearchHitRow key={`${hit.entity_type}-${hit.entity_id}`} hit={hit} />
                ))}
            </ul>
            <BackendNote backend={backend} count={hits.length} />
        </>
    );
}

function SearchHitRow({ hit }: { hit: UnifiedSearchHit }) {
    const isNotice = hit.entity_type === "notice";
    const href = isNotice
        ? `/dashboard/compliance/notices/${hit.entity_id}`
        : `/dashboard/documents/${hit.entity_id}`;
    const Icon = isNotice ? FiBookOpen : FiFile;
    const md = hit.metadata;
    const snippetText = stripHtml(hit.snippet);

    return (
        <li>
            <Link
                href={href}
                className="block rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] px-4 py-3 hover:border-[var(--accent-edge)] hover:bg-[var(--bg-hover)] shadow-[var(--shadow-sm)] transition-colors"
            >
                <div className="flex items-start gap-3">
                    <Icon
                        className={`w-4 h-4 mt-0.5 shrink-0 ${
                            isNotice ? "text-[var(--accent)]" : "text-[var(--text-muted)]"
                        }`}
                    />
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[13px] text-[var(--text-primary)] font-mono truncate">
                                {hit.title}
                            </span>
                            <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                                {hit.entity_type}
                            </span>
                            {isNotice && typeof md.authority === "string" && (
                                <AuthorityBadge
                                    authority={md.authority as "GST" | "IT" | "MCA" | "RBI" | "SEBI"}
                                />
                            )}
                            {isNotice && typeof md.risk_tier === "string" && (
                                <RiskTierDot
                                    tier={md.risk_tier as "critical" | "high" | "medium" | "low"}
                                    showLabel
                                />
                            )}
                        </div>
                        {snippetText && (
                            <p className="text-[12px] text-[var(--text-secondary)] mt-1 leading-relaxed line-clamp-2">
                                {snippetText}
                            </p>
                        )}
                    </div>
                    <span className="text-[10px] text-[var(--text-muted)] tabular-nums shrink-0 ml-2">
                        {hit.rank.toFixed(3)}
                    </span>
                </div>
            </Link>
        </li>
    );
}

function BackendNote({ backend, count }: { backend: string; count: number }) {
    return (
        <div className="flex items-center gap-2 px-3 py-2 text-[11px] text-[var(--text-muted)] bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded">
            <FiInfo className="w-3 h-3 shrink-0" />
            <span>
                {count} result{count === 1 ? "" : "s"} via{" "}
                <span className="font-mono text-[var(--text-secondary)]">{backend}</span>
                {backend === "postgres-fts" &&
                    " — Elasticsearch swap-in deferred to v2.1"}
            </span>
        </div>
    );
}
