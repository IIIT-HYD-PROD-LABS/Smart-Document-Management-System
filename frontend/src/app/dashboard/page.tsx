"use client";

import { useEffect, useMemo, useState } from "react";
import { documentsApi } from "@/lib/api";
import { StatusBadge, LoadingSpinner } from "@/components";
import { useAuth } from "@/context/AuthContext";
import {
    FiFileText,
    FiCheckCircle,
    FiClock,
    FiArrowRight,
    FiUpload,
    FiTrendingUp,
} from "react-icons/fi";
import Link from "next/link";
import toast from "react-hot-toast";

const CATEGORY_LABELS: Record<string, string> = {
    bills: "Bills",
    upi: "UPI",
    tickets: "Tickets",
    tax: "Tax",
    bank: "Bank",
    invoices: "Invoices",
    unknown: "Unknown",
};

const CATEGORY_ACCENT: Record<string, string> = {
    bills: "#f59e0b",
    upi: "#10b981",
    tickets: "#8b5cf6",
    tax: "#3b82f6",
    bank: "#06b6d4",
    invoices: "#ec4899",
    unknown: "#71717a",
};

interface DashboardStats {
    total_documents: number;
    completed_count: number;
    processing_count: number;
    category_counts: Record<string, number>;
    recent_uploads: Array<{
        id: number;
        original_filename: string;
        category: string;
        confidence_score: number | null;
        status: string;
    }>;
}

export default function DashboardPage() {
    const { user } = useAuth();
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        documentsApi
            .getStats()
            .then((res) => setStats(res.data))
            .catch(() => {
                setStats(null);
                toast.error("Failed to load stats");
            })
            .finally(() => setLoading(false));
    }, []);

    const today = useMemo(() => {
        return new Date().toLocaleDateString("en-IN", {
            weekday: "long",
            day: "numeric",
            month: "short",
            year: "numeric",
        });
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <LoadingSpinner />
            </div>
        );
    }

    const total = stats?.total_documents || 0;
    const completed = stats?.completed_count || 0;
    const processing = stats?.processing_count || 0;
    const catCounts = stats?.category_counts || {};
    const recent = stats?.recent_uploads || [];
    const classifiedRate = total > 0 ? (completed / total) * 100 : 0;

    return (
        <div className="space-y-8">
            {/* ── Header ──────────────────────────────────────────── */}
            <header className="flex items-end justify-between gap-4 flex-wrap">
                <div>
                    <p className="microtype mb-1.5">{today}</p>
                    <h1 className="text-[28px] leading-tight font-semibold text-white tracking-tight">
                        Welcome back,{" "}
                        <span className="text-[var(--accent)]">{user?.username}</span>
                    </h1>
                    <p className="text-[13px] text-[var(--text-subtle)] mt-1.5">
                        Overview of your document library and classification progress.
                    </p>
                </div>
                <Link
                    href="/dashboard/upload"
                    className="
                        inline-flex items-center gap-2 h-9 px-4 rounded-md
                        bg-[var(--accent-soft)] border border-[var(--accent-edge)]
                        text-[13px] font-medium text-[var(--accent)]
                        hover:bg-[var(--accent)] hover:text-white
                        transition-colors duration-150 cursor-pointer
                    "
                >
                    <FiUpload className="w-3.5 h-3.5" />
                    Upload document
                </Link>
            </header>

            {/* ── Stat cards ──────────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <StatCard
                    label="Total"
                    value={total}
                    icon={FiFileText}
                    color="#a1a1aa"
                    hint={
                        total > 0
                            ? `${total} document${total === 1 ? "" : "s"} indexed`
                            : "No documents yet"
                    }
                />
                <StatCard
                    label="Classified"
                    value={completed}
                    icon={FiCheckCircle}
                    color="#10b981"
                    hint={total > 0 ? `${classifiedRate.toFixed(0)}% accuracy` : "—"}
                />
                <StatCard
                    label="Processing"
                    value={processing}
                    icon={FiClock}
                    color="#f59e0b"
                    hint={processing === 0 ? "Queue clear" : "In-flight"}
                    pulse={processing > 0}
                />
            </div>

            {/* ── Categories ──────────────────────────────────────── */}
            {Object.keys(catCounts).length > 0 && (
                <section
                    className="surface-card p-5"
                    aria-labelledby="categories-heading"
                >
                    <header className="flex items-center justify-between mb-4">
                        <h2
                            id="categories-heading"
                            className="text-[13px] font-medium text-white"
                        >
                            Categories
                        </h2>
                        <Link
                            href="/dashboard/documents"
                            className="microtype text-[var(--text-subtle)] hover:text-[var(--text-secondary)] transition-colors flex items-center gap-1"
                        >
                            Filter <FiArrowRight className="w-3 h-3" />
                        </Link>
                    </header>
                    <div className="flex flex-wrap gap-2">
                        {Object.entries(catCounts).map(([cat, count]) => {
                            const color = CATEGORY_ACCENT[cat] ?? "#71717a";
                            return (
                                <Link
                                    key={cat}
                                    href={`/dashboard/documents?category=${cat}`}
                                    className="
                                        group inline-flex items-center gap-2
                                        h-7 pl-2.5 pr-2 rounded-md
                                        bg-[var(--bg-hover)]
                                        border border-[var(--border-emphasis)]
                                        hover:border-[var(--text-subtle)]
                                        transition-all duration-150 cursor-pointer
                                    "
                                >
                                    <span
                                        className="w-1.5 h-1.5 rounded-full"
                                        style={{ backgroundColor: color }}
                                        aria-hidden
                                    />
                                    <span className="text-[12px] text-[var(--text-secondary)] group-hover:text-white transition-colors">
                                        {CATEGORY_LABELS[cat] || cat}
                                    </span>
                                    <span className="font-mono tabular-nums text-[11px] text-[var(--text-subtle)] group-hover:text-[var(--text-muted)] border-l border-[var(--border-emphasis)] pl-2 transition-colors">
                                        {String(count)}
                                    </span>
                                </Link>
                            );
                        })}
                    </div>
                </section>
            )}

            {/* ── Recent documents ────────────────────────────────── */}
            <section
                className="surface-card overflow-hidden"
                aria-labelledby="recent-heading"
            >
                <header className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border-default)]">
                    <h2
                        id="recent-heading"
                        className="text-[13px] font-medium text-white flex items-center gap-2"
                    >
                        Recent documents
                        {recent.length > 0 && (
                            <span className="microtype text-[var(--text-subtle)]">
                                Last {Math.min(recent.length, 5)}
                            </span>
                        )}
                    </h2>
                    <Link
                        href="/dashboard/documents"
                        className="text-[12px] text-[var(--text-subtle)] hover:text-[var(--text-secondary)] flex items-center gap-1 transition-colors"
                    >
                        View all <FiArrowRight className="w-3 h-3" />
                    </Link>
                </header>
                {recent.length > 0 ? (
                    <ul className="divide-y divide-[var(--border-subtle)]">
                        {recent.slice(0, 5).map((doc) => {
                            const color = CATEGORY_ACCENT[doc.category] ?? "#71717a";
                            return (
                                <li key={doc.id}>
                                    <Link
                                        href={`/dashboard/documents/${doc.id}`}
                                        className="list-row flex items-center gap-3 px-5 py-3 cursor-pointer"
                                    >
                                        <div
                                            className="w-7 h-7 rounded-md flex items-center justify-center shrink-0"
                                            style={{ backgroundColor: `${color}1a` }}
                                        >
                                            <FiFileText
                                                className="w-3.5 h-3.5"
                                                style={{ color }}
                                            />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-[13px] text-white truncate">
                                                {doc.original_filename}
                                            </p>
                                            <div className="flex items-center gap-2 mt-0.5">
                                                <span className="text-[11px] text-[var(--text-subtle)] capitalize">
                                                    {CATEGORY_LABELS[doc.category] ||
                                                        doc.category}
                                                </span>
                                                {doc.confidence_score !== null && (
                                                    <>
                                                        <span className="text-[var(--text-disabled)]">·</span>
                                                        <span className="font-mono tabular-nums text-[11px] text-[var(--text-subtle)]">
                                                            {(doc.confidence_score * 100).toFixed(0)}%
                                                        </span>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                        <StatusBadge status={doc.status} />
                                    </Link>
                                </li>
                            );
                        })}
                    </ul>
                ) : (
                    <div className="text-center py-14 px-6">
                        <div className="w-10 h-10 rounded-full bg-[var(--bg-hover)] border border-[var(--border-emphasis)] flex items-center justify-center mx-auto mb-3">
                            <FiFileText className="w-4 h-4 text-[var(--text-disabled)]" />
                        </div>
                        <p className="text-[13px] text-[var(--text-muted)] mb-1">
                            No documents yet
                        </p>
                        <p className="text-[11.5px] text-[var(--text-subtle)] mb-4">
                            Upload your first document to start classifying.
                        </p>
                        <Link
                            href="/dashboard/upload"
                            className="
                                inline-flex items-center gap-1.5 h-8 px-3 rounded-md
                                bg-[var(--accent-soft)] border border-[var(--accent-edge)]
                                text-[12px] font-medium text-[var(--accent)]
                                hover:bg-[var(--accent)] hover:text-white
                                transition-colors duration-150 cursor-pointer
                            "
                        >
                            <FiUpload className="w-3 h-3" />
                            Upload now
                        </Link>
                    </div>
                )}
            </section>
        </div>
    );
}

/** Stat card — Plex Mono numeric, hairline accent strip on top edge,
 *  hover border emphasis. Single source of truth for the 3 cards. */
function StatCard({
    label,
    value,
    icon: Icon,
    color,
    hint,
    pulse = false,
}: {
    label: string;
    value: number;
    icon: React.ComponentType<{ className?: string }>;
    color: string;
    hint?: string;
    pulse?: boolean;
}) {
    return (
        <article
            className="surface-card stat-strip relative p-5 group"
            style={{ color }}
        >
            <header className="flex items-center justify-between mb-3">
                <span className="microtype">{label}</span>
                <Icon
                    className={`w-4 h-4 transition-opacity duration-200 ${
                        pulse ? "motion-safe:animate-pulse" : ""
                    } group-hover:opacity-100 opacity-90`}
                    aria-hidden
                />
            </header>
            <p className="font-mono tabular-nums text-[32px] leading-none font-semibold text-white">
                {value.toLocaleString("en-IN")}
            </p>
            {hint && (
                <p className="text-[11px] text-[var(--text-subtle)] mt-3 flex items-center gap-1">
                    {label === "Classified" && value > 0 && (
                        <FiTrendingUp className="w-3 h-3 text-[var(--success)]" />
                    )}
                    {hint}
                </p>
            )}
        </article>
    );
}
