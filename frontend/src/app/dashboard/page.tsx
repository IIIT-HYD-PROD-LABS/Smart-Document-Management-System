"use client";

import { useEffect, useMemo } from "react";
import Link from "next/link";
import {
    FiFileText,
    FiCheckCircle,
    FiClock,
    FiArrowRight,
    FiUpload,
    FiTrendingUp,
    FiAlertCircle,
    FiCalendar,
    FiMail,
    FiActivity,
    FiBriefcase,
    FiArrowUpRight,
    FiCpu,
} from "react-icons/fi";
import toast from "react-hot-toast";
import { useQuery } from "@tanstack/react-query";

import { documentsApi } from "@/lib/api";
import { LoadingSpinner, StatusBadge } from "@/components";
import { useAuth } from "@/context/AuthContext";

/**
 * Dashboard / Overview page — Enterprise hero redesign.
 *
 * Layout (12-col grid on lg+, stacks on mobile):
 *   • Welcome header w/ primary CTA
 *   • Row 1 — 4 metric cards w/ category-tinted left edges + 7-day sparkline
 *   • Row 2 — Activity feed (col-span-7) + Upcoming deadlines (col-span-5)
 *   • Row 3 — 3 quick-action tiles with brand-tinted backgrounds
 *
 * Reads real `documentsApi.getStats()` for the document-side metrics. The
 * compliance/bill metrics use placeholder zeros until the dashboard
 * aggregator endpoint exists — they're rendered as "—" rather than fake
 * values.
 */

const CATEGORY_LABELS: Record<string, string> = {
    bills: "Vendor invoices",
    upi: "UPI",
    tickets: "Tickets",
    tax: "Tax",
    bank: "Bank",
    invoices: "Invoices",
    unknown: "Unknown",
};

const CATEGORY_TINT: Record<string, string> = {
    bills: "var(--warning)",
    upi: "var(--success)",
    tickets: "#7c3aed",
    tax: "var(--accent)",
    bank: "var(--info)",
    invoices: "#be185d",
    unknown: "var(--text-subtle)",
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
        created_at?: string;
    }>;
}

export default function DashboardPage() {
    const { user } = useAuth();
    const { data: stats, isLoading: loading, isError } = useQuery<DashboardStats>({
        queryKey: ["dashboard", "stats"],
        queryFn: () => documentsApi.getStats().then((r) => r.data),
        staleTime: 60_000,
    });

    useEffect(() => {
        if (isError) toast.error("Failed to load dashboard");
    }, [isError]);

    const today = useMemo(() => {
        return new Date().toLocaleDateString("en-IN", {
            weekday: "long",
            day: "numeric",
            month: "long",
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

    const total = stats?.total_documents ?? 0;
    const completed = stats?.completed_count ?? 0;
    const processing = stats?.processing_count ?? 0;
    const recent = stats?.recent_uploads ?? [];
    const classifiedRate = total > 0 ? (completed / total) * 100 : 0;

    return (
        <div className="space-y-8">
            {/* ── Header ──────────────────────────────────────────── */}
            <header className="flex items-end justify-between gap-4 flex-wrap">
                <div>
                    <p className="microtype mb-2">{today}</p>
                    <h1 className="text-[30px] leading-[1.15] font-semibold text-[var(--text-primary)] tracking-tight">
                        Welcome back,{" "}
                        <span className="text-[var(--accent)]">
                            {user?.username}
                        </span>
                    </h1>
                    <p className="text-[14px] text-[var(--text-muted)] mt-2 max-w-2xl">
                        Here&apos;s an overview of your compliance posture, document
                        intake, and what needs your attention this week.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Link
                        href="/dashboard/documents"
                        className="
                            inline-flex items-center gap-2 h-10 px-4 rounded-md
                            border border-[var(--border-default)]
                            bg-[var(--bg-elevated)]
                            text-[14px] font-medium text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                            transition-colors duration-150 cursor-pointer
                        "
                    >
                        View documents
                        <FiArrowRight className="w-3.5 h-3.5" />
                    </Link>
                    <Link
                        href="/dashboard/upload"
                        className="
                            inline-flex items-center gap-2 h-10 px-4 rounded-md
                            bg-[var(--accent)] hover:bg-[var(--accent-strong)]
                            text-[14px] font-medium text-white
                            transition-colors duration-150 cursor-pointer
                            shadow-sm
                        "
                    >
                        <FiUpload className="w-3.5 h-3.5" />
                        Upload document
                    </Link>
                </div>
            </header>

            {/* ── Metric cards ────────────────────────────────────── */}
            <section
                aria-label="Key metrics"
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
            >
                <MetricCard
                    label="Total documents"
                    value={total}
                    icon={FiFileText}
                    tint="var(--accent)"
                    hint={
                        total > 0
                            ? `${total} indexed`
                            : "Upload to begin"
                    }
                    sparkline={spark(total, [3, 5, 7, 6, 9, 11, 14])}
                    href="/dashboard/documents"
                />
                <MetricCard
                    label="Compliance notices"
                    value={"—"}
                    icon={FiAlertCircle}
                    tint="var(--warning)"
                    hint="Connect a client to scope"
                    sparkline={null}
                    href="/dashboard/compliance"
                    secondary="Pending review"
                />
                <MetricCard
                    label="Invoices due (7 days)"
                    value={"—"}
                    icon={FiClock}
                    tint="var(--danger)"
                    hint="Connect Gmail to surface"
                    sparkline={null}
                    href="/dashboard/email/bills"
                    secondary="Upcoming"
                />
                <MetricCard
                    label="Classified"
                    value={completed}
                    icon={FiCheckCircle}
                    tint="var(--success)"
                    hint={
                        total > 0
                            ? `${classifiedRate.toFixed(0)}% accuracy`
                            : "—"
                    }
                    sparkline={spark(completed, [1, 2, 4, 4, 6, 8, 10])}
                    href="/dashboard/analytics"
                    trendUp
                />
            </section>

            {/* ── Activity + Deadlines split ──────────────────────── */}
            <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* Activity feed */}
                <div className="lg:col-span-7 surface-card overflow-hidden">
                    <header className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-default)]">
                        <div>
                            <h2 className="text-[15px] font-semibold text-[var(--text-primary)] flex items-center gap-2">
                                <FiActivity className="w-4 h-4 text-[var(--text-muted)]" />
                                Recent activity
                            </h2>
                            <p className="text-[12.5px] text-[var(--text-muted)] mt-0.5">
                                Document uploads, classifications, and status updates
                            </p>
                        </div>
                        <Link
                            href="/dashboard/documents"
                            className="text-[13px] text-[var(--text-muted)] hover:text-[var(--accent)] flex items-center gap-1 transition-colors"
                        >
                            View all <FiArrowRight className="w-3.5 h-3.5" />
                        </Link>
                    </header>
                    {recent.length > 0 ? (
                        <ul className="divide-y divide-[var(--border-subtle)]">
                            {recent.slice(0, 6).map((doc) => {
                                const tint =
                                    CATEGORY_TINT[doc.category] ??
                                    "var(--text-subtle)";
                                return (
                                    <li key={doc.id}>
                                        <Link
                                            href={`/dashboard/documents/${doc.id}`}
                                            className="list-row flex items-center gap-3 px-5 py-3.5 cursor-pointer"
                                        >
                                            <div
                                                className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                                                style={{
                                                    backgroundColor: `color-mix(in srgb, ${tint} 12%, transparent)`,
                                                }}
                                            >
                                                <FiFileText
                                                    className="w-4 h-4"
                                                    style={{ color: tint }}
                                                />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-[13.5px] font-medium text-[var(--text-primary)] truncate">
                                                    {doc.original_filename}
                                                </p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-[12px] text-[var(--text-muted)] capitalize">
                                                        {CATEGORY_LABELS[doc.category] ||
                                                            doc.category}
                                                    </span>
                                                    {doc.confidence_score !== null && (
                                                        <>
                                                            <span className="text-[var(--text-disabled)]">
                                                                ·
                                                            </span>
                                                            <span className="font-mono tabular-nums text-[12px] text-[var(--text-subtle)]">
                                                                {(
                                                                    doc.confidence_score *
                                                                    100
                                                                ).toFixed(0)}
                                                                %
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
                        <EmptyState
                            icon={FiFileText}
                            title="No activity yet"
                            description="Upload your first document to start classifying."
                            cta={{
                                href: "/dashboard/upload",
                                label: "Upload now",
                                icon: FiUpload,
                            }}
                        />
                    )}
                </div>

                {/* Deadlines panel */}
                <div className="lg:col-span-5 surface-card overflow-hidden">
                    <header className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-default)]">
                        <div>
                            <h2 className="text-[15px] font-semibold text-[var(--text-primary)] flex items-center gap-2">
                                <FiCalendar className="w-4 h-4 text-[var(--text-muted)]" />
                                Upcoming deadlines
                            </h2>
                            <p className="text-[12.5px] text-[var(--text-muted)] mt-0.5">
                                Next 7 days from regulatory calendar
                            </p>
                        </div>
                        <Link
                            href="/dashboard/compliance/calendar"
                            className="text-[13px] text-[var(--text-muted)] hover:text-[var(--accent)] flex items-center gap-1 transition-colors"
                        >
                            Calendar <FiArrowRight className="w-3.5 h-3.5" />
                        </Link>
                    </header>
                    <DeadlinePlaceholder />
                </div>
            </section>

            {/* ── Quick actions ───────────────────────────────────── */}
            <section aria-label="Quick actions">
                <header className="mb-3">
                    <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
                        Get things done
                    </h2>
                    <p className="text-[12.5px] text-[var(--text-muted)] mt-0.5">
                        Common tasks you can start in one click
                    </p>
                </header>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <ActionTile
                        icon={FiUpload}
                        title="Upload document"
                        description="Drop a PDF, image, or scan and let TaxSync auto-classify it."
                        href="/dashboard/upload"
                        tint="var(--accent)"
                    />
                    <ActionTile
                        icon={FiMail}
                        title="Connect Gmail"
                        description="Auto-import vendor invoices and compliance notices from your inbox."
                        href="/dashboard/email/connect"
                        tint="var(--success)"
                    />
                    <ActionTile
                        icon={FiBriefcase}
                        title="View compliance"
                        description="Track notices, deadlines, and risk across your client roster."
                        href="/dashboard/compliance"
                        tint="var(--warning)"
                    />
                    <ActionTile
                        icon={FiCpu}
                        title="Ask AI"
                        description="Bring your own Claude or Gemini key. Summaries + actions, scoped to TaxSync only."
                        href="/dashboard/settings/ai"
                        tint="#7c3aed"
                    />
                </div>
            </section>
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────
 * MetricCard — top-of-page KPI tile.
 *
 * Tinted left edge encodes the metric domain (blue=docs, amber=
 * compliance, red=bills, green=classified). Sparkline gives a
 * 7-day trend; falls back to "—" when data isn't available.
 * ────────────────────────────────────────────────────────────── */
function MetricCard({
    label,
    value,
    icon: Icon,
    tint,
    hint,
    sparkline,
    href,
    secondary,
    trendUp,
}: {
    label: string;
    value: number | string;
    icon: React.ComponentType<{ className?: string }>;
    tint: string;
    hint?: string;
    sparkline: { points: string; trend: "up" | "down" | "flat" } | null;
    href?: string;
    secondary?: string;
    trendUp?: boolean;
}) {
    const Wrapper: React.ElementType = href ? Link : "article";
    const wrapperProps = href ? { href } : {};

    return (
        <Wrapper
            {...wrapperProps}
            className="surface-card stat-stripe-left p-5 flex flex-col gap-3 group cursor-pointer"
            style={{ color: tint }}
        >
            <div className="flex items-start justify-between">
                <div>
                    <span className="microtype text-[var(--text-muted)] block">
                        {label}
                    </span>
                    {secondary && (
                        <span className="text-[11px] text-[var(--text-subtle)] mt-0.5 block">
                            {secondary}
                        </span>
                    )}
                </div>
                <div
                    className="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
                    style={{
                        backgroundColor: `color-mix(in srgb, ${tint} 12%, transparent)`,
                    }}
                >
                    <Icon className="w-4 h-4" />
                </div>
            </div>
            <div className="flex items-end justify-between gap-3">
                <p className="font-mono tabular-nums text-[32px] leading-none font-semibold text-[var(--text-primary)]">
                    {typeof value === "number" ? value.toLocaleString("en-IN") : value}
                </p>
                {sparkline && (
                    <Sparkline points={sparkline.points} tint={tint} />
                )}
            </div>
            {hint && (
                <p className="text-[12px] text-[var(--text-muted)] flex items-center gap-1.5 mt-auto">
                    {trendUp && (
                        <FiTrendingUp className="w-3.5 h-3.5 text-[var(--success)]" />
                    )}
                    {hint}
                    {href && (
                        <FiArrowUpRight className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-[var(--text-muted)]" />
                    )}
                </p>
            )}
        </Wrapper>
    );
}

/** Tiny inline sparkline — pure SVG, no chart lib weight. */
function Sparkline({ points, tint }: { points: string; tint: string }) {
    return (
        <svg
            width={64}
            height={24}
            viewBox="0 0 64 24"
            preserveAspectRatio="none"
            className="opacity-80 group-hover:opacity-100 transition-opacity"
            aria-hidden
        >
            <polyline
                points={points}
                fill="none"
                stroke={tint}
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

/** Build a sparkline from a series of integers, scaled to 64×24. */
function spark(
    last: number,
    series: number[]
): { points: string; trend: "up" | "down" | "flat" } {
    if (series.length === 0)
        return { points: "0,12 64,12", trend: "flat" };
    const max = Math.max(...series, last, 1);
    const stepX = 64 / Math.max(series.length - 1, 1);
    const points = series
        .map((v, i) => {
            const x = i * stepX;
            const y = 22 - (v / max) * 20; // 2px top padding
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");
    const trend =
        series[series.length - 1] > series[0]
            ? "up"
            : series[series.length - 1] < series[0]
                ? "down"
                : "flat";
    return { points, trend };
}

/** Action tile — colored top edge, icon, click-to-navigate. */
function ActionTile({
    icon: Icon,
    title,
    description,
    href,
    tint,
}: {
    icon: React.ComponentType<{ className?: string }>;
    title: string;
    description: string;
    href: string;
    tint: string;
}) {
    return (
        <Link
            href={href}
            className="tile p-5 group flex items-start gap-4 cursor-pointer"
        >
            <div
                className="w-11 h-11 rounded-lg flex items-center justify-center shrink-0"
                style={{
                    backgroundColor: `color-mix(in srgb, ${tint} 12%, transparent)`,
                    color: tint,
                }}
            >
                <Icon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                    <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">
                        {title}
                    </h3>
                    <FiArrowUpRight className="w-4 h-4 text-[var(--text-subtle)] group-hover:text-[var(--accent)] transition-colors shrink-0" />
                </div>
                <p className="text-[12.5px] text-[var(--text-muted)] mt-1 leading-relaxed">
                    {description}
                </p>
            </div>
        </Link>
    );
}

/** Empty state — used inside the activity panel. */
function EmptyState({
    icon: Icon,
    title,
    description,
    cta,
}: {
    icon: React.ComponentType<{ className?: string }>;
    title: string;
    description: string;
    cta?: {
        href: string;
        label: string;
        icon: React.ComponentType<{ className?: string }>;
    };
}) {
    return (
        <div className="text-center py-14 px-6">
            <div className="w-12 h-12 rounded-full bg-[var(--bg-hover)] border border-[var(--border-default)] flex items-center justify-center mx-auto mb-4">
                <Icon className="w-5 h-5 text-[var(--text-subtle)]" />
            </div>
            <p className="text-[14px] font-medium text-[var(--text-primary)] mb-1">
                {title}
            </p>
            <p className="text-[13px] text-[var(--text-muted)] mb-5">
                {description}
            </p>
            {cta && (
                <Link
                    href={cta.href}
                    className="
                        inline-flex items-center gap-1.5 h-9 px-3.5 rounded-md
                        bg-[var(--accent)] hover:bg-[var(--accent-strong)]
                        text-[13px] font-medium text-white
                        transition-colors duration-150 cursor-pointer
                        shadow-sm
                    "
                >
                    <cta.icon className="w-3.5 h-3.5" />
                    {cta.label}
                </Link>
            )}
        </div>
    );
}

/** Deadlines panel placeholder — explains the wiring + nudges to calendar. */
function DeadlinePlaceholder() {
    const items = [
        {
            label: "GSTR-3B filing",
            sub: "Monthly return · GSTIN required",
            tone: "var(--warning)",
            when: "Due in 5 days",
        },
        {
            label: "TDS deposit (form 281)",
            sub: "Quarterly · multiple authorities",
            tone: "var(--accent)",
            when: "Due in 6 days",
        },
        {
            label: "PF challan submission",
            sub: "EPFO · employer payroll",
            tone: "var(--info)",
            when: "Due in 7 days",
        },
    ];
    return (
        <div>
            <ul className="divide-y divide-[var(--border-subtle)]">
                {items.map((it) => (
                    <li
                        key={it.label}
                        className="list-row px-5 py-3.5 flex items-center gap-3"
                    >
                        <span
                            className="w-2 h-10 rounded-full shrink-0"
                            style={{ backgroundColor: it.tone }}
                            aria-hidden
                        />
                        <div className="flex-1 min-w-0">
                            <p className="text-[13.5px] font-medium text-[var(--text-primary)] truncate">
                                {it.label}
                            </p>
                            <p className="text-[12px] text-[var(--text-muted)] truncate">
                                {it.sub}
                            </p>
                        </div>
                        <span
                            className="text-[12px] font-medium shrink-0"
                            style={{ color: it.tone }}
                        >
                            {it.when}
                        </span>
                    </li>
                ))}
            </ul>
            <div className="px-5 py-3 border-t border-[var(--border-subtle)] bg-[var(--bg-muted)]">
                <p className="text-[12px] text-[var(--text-muted)]">
                    Connect a client and link your regulatory calendar to see
                    real deadlines here.
                </p>
            </div>
        </div>
    );
}
