"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import toast from "react-hot-toast";
import {
    FiArrowLeft,
    FiCheck,
    FiCornerUpLeft,
    FiExternalLink,
    FiFlag,
    FiInfo,
} from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { Authority, ReviewQueueItem } from "@/types/compliance";
import { extractErrorMessage } from "@/lib/api";

/**
 * Review queue, triage workbench.
 *
 * 2026-05-21 redesign:
 *   The queue now populates from rule-based heuristics + manual operator
 *   flags (see backend services/review_queue_service.compute_heuristic_confidence
 *   and enqueue_manual). This page is the daily inbox for compliance_head
 *   and ca_consultant to confirm or override the predicted authority +
 *   notice_type on uncertain notices.
 *
 * Layout choices:
 *   1. A reason-bucketed strip at top summarises volume by reason and
 *      doubles as a filter. Click a chip to scope the grid below.
 *   2. Cards (not table rows) so each item has room to show TWO segmented
 *      confidence dots (authority + type) plus a reason chip plus three
 *      actions (confirm, reclassify, open).
 *   3. A "confidence dot strip" replaces a flat percentage; 10 dots with
 *      a marker at the 75 percent threshold makes "below the bar" scan in
 *      under a second.
 *   4. Empty state has its own value: a focused form to manually flag a
 *      notice ID for review, so the page is useful even when the
 *      heuristic queue is dry.
 */

const CONFIDENCE_THRESHOLD = 0.75;

const AUTHORITIES: Authority[] = ["GST", "IT", "MCA", "RBI", "SEBI"];

type ReasonBucket =
    | "low_authority_confidence"
    | "low_type_confidence"
    | "both"
    | "manual_flag";

const REASON_META: Record<
    ReasonBucket,
    { label: string; tint: string; accent: string; soft: string }
> = {
    low_authority_confidence: {
        label: "Low authority",
        tint: "var(--warning)",
        accent: "var(--warning)",
        soft: "var(--warning-soft)",
    },
    low_type_confidence: {
        label: "Low type",
        tint: "var(--info)",
        accent: "var(--info)",
        soft: "var(--info-soft)",
    },
    both: {
        label: "Both unclear",
        tint: "var(--danger)",
        accent: "var(--danger)",
        soft: "var(--danger-soft)",
    },
    manual_flag: {
        label: "Operator flag",
        tint: "var(--accent)",
        accent: "var(--accent)",
        soft: "var(--accent-soft)",
    },
};

function bucketOf(reason: string): ReasonBucket {
    if (reason.startsWith("manual_flag")) return "manual_flag";
    if (reason === "both") return "both";
    if (reason === "low_authority_confidence")
        return "low_authority_confidence";
    if (reason === "low_type_confidence") return "low_type_confidence";
    // Future reason values still render (low_*_confidence catchall)
    return "low_type_confidence";
}

function reasonNote(reason: string): string | null {
    if (!reason.startsWith("manual_flag:")) return null;
    return reason.slice("manual_flag:".length);
}

function modelBadge(model_version: string): {
    label: string;
    dot: string;
} {
    if (model_version === "manual") {
        return { label: "MANUAL", dot: "var(--accent)" };
    }
    if (model_version === "rule_based_heuristic_v1") {
        return { label: "HEURISTIC", dot: "var(--text-muted)" };
    }
    if (model_version.startsWith("bert_") || model_version.includes("bert")) {
        return { label: "BERT", dot: "var(--success)" };
    }
    return { label: model_version.toUpperCase().slice(0, 12), dot: "var(--text-muted)" };
}

function pct(s: string | null): number | null {
    if (s === null) return null;
    const v = parseFloat(s);
    if (Number.isNaN(v)) return null;
    return Math.round(v * 100);
}

function ageLabel(created_at: string): string {
    const now = Date.now();
    const then = new Date(created_at).getTime();
    const hours = (now - then) / 3_600_000;
    if (hours < 1) return "<1h";
    if (hours < 24) return `${Math.round(hours)}h`;
    const days = hours / 24;
    if (days < 7) return `${Math.round(days)}d`;
    if (days < 30) return `${Math.round(days / 7)}w`;
    return `${Math.round(days / 30)}mo`;
}

export default function ReviewQueuePage() {
    const qc = useQueryClient();
    const [filter, setFilter] = useState<ReasonBucket | null>(null);

    const queueQ = useQuery({
        queryKey: ["compliance-review-pending"],
        queryFn: async () => {
            const { data } = await complianceApi.listPendingReview(1, 200);
            return data;
        },
    });

    const items = queueQ.data?.items ?? [];

    const counts = useMemo(() => {
        const m: Record<ReasonBucket, number> = {
            low_authority_confidence: 0,
            low_type_confidence: 0,
            both: 0,
            manual_flag: 0,
        };
        for (const it of items) m[bucketOf(it.reason)] += 1;
        return m;
    }, [items]);

    const visible = useMemo(() => {
        if (!filter) return items;
        return items.filter((it) => bucketOf(it.reason) === filter);
    }, [items, filter]);

    const refresh = () => qc.invalidateQueries({ queryKey: ["compliance-review-pending"] });

    return (
        <div className="px-6 py-8 max-w-6xl mx-auto">
            <Link
                href="/dashboard/compliance"
                className="
                    inline-flex items-center gap-1.5 text-[12px]
                    text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                    mb-4 focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                    rounded px-1
                "
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to dashboard
            </Link>

            <header className="mb-6">
                <div className="flex items-baseline justify-between gap-3 flex-wrap">
                    <h1 className="text-2xl font-semibold text-[var(--text-primary)] tracking-tight">
                        Review queue
                    </h1>
                    <span className="text-[12px] text-[var(--text-muted)] tabular-nums">
                        {queueQ.data
                            ? `${queueQ.data.total} pending`
                            : "loading"}
                    </span>
                </div>
                <p className="text-[13px] text-[var(--text-muted)] mt-1 max-w-2xl leading-relaxed">
                    Notices the classifier is not confident about plus anything
                    a teammate manually flagged. Confirm the prediction if it
                    is right, override it if it is wrong, or open the notice
                    for full context.
                </p>
            </header>

            {/* Bucket strip, doubles as filter */}
            <FilterStrip
                counts={counts}
                active={filter}
                onSelect={setFilter}
            />

            {queueQ.isLoading && <SkeletonGrid />}

            {queueQ.error && !queueQ.isLoading && (
                <div
                    className="
                        rounded-md border px-4 py-3 text-[13px]
                        border-[color:color-mix(in_srgb,var(--danger)_30%,transparent)]
                        bg-[var(--danger-soft)] text-[var(--danger)]
                    "
                    role="alert"
                >
                    Failed to load review queue. Refresh the page or try again.
                </div>
            )}

            {!queueQ.isLoading && !queueQ.error && items.length === 0 && (
                <EmptyState onFlagged={refresh} />
            )}

            {!queueQ.isLoading && visible.length > 0 && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-4">
                    {visible.map((row) => (
                        <TriageCard
                            key={row.id}
                            row={row}
                            onChanged={refresh}
                        />
                    ))}
                </div>
            )}

            {!queueQ.isLoading && items.length > 0 && visible.length === 0 && (
                <div className="mt-6 text-[13px] text-[var(--text-muted)] text-center py-8">
                    No items match the current filter.
                    <button
                        type="button"
                        onClick={() => setFilter(null)}
                        className="
                            ml-2 text-[var(--accent)] hover:underline
                            focus:outline-none focus:ring-2
                            focus:ring-[var(--accent-edge)] rounded
                        "
                    >
                        Clear filter
                    </button>
                </div>
            )}
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  Filter strip                                                            */
/* ──────────────────────────────────────────────────────────────────────── */

function FilterStrip({
    counts,
    active,
    onSelect,
}: {
    counts: Record<ReasonBucket, number>;
    active: ReasonBucket | null;
    onSelect: (b: ReasonBucket | null) => void;
}) {
    const buckets: ReasonBucket[] = [
        "both",
        "low_authority_confidence",
        "low_type_confidence",
        "manual_flag",
    ];
    const totalSelected = buckets.reduce((n, b) => n + counts[b], 0);
    return (
        <div
            className="
                surface-card flex flex-wrap items-center gap-2 px-3 py-2
                sticky top-0 z-10 backdrop-blur
                bg-[color:color-mix(in_srgb,var(--bg-elevated)_92%,transparent)]
            "
            role="toolbar"
            aria-label="Filter by reason"
        >
            <button
                type="button"
                onClick={() => onSelect(null)}
                aria-pressed={active === null}
                className={`
                    px-2.5 py-1 rounded text-[11.5px] font-medium
                    transition-colors
                    ${
                        active === null
                            ? "bg-[var(--bg-hover)] text-[var(--text-primary)] ring-1 ring-[var(--border-emphasis)]"
                            : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                    }
                `}
            >
                All{" "}
                <span className="tabular-nums text-[var(--text-muted)]">
                    {totalSelected}
                </span>
            </button>
            <span className="text-[var(--border-default)]">|</span>
            {buckets.map((b) => {
                const meta = REASON_META[b];
                const c = counts[b];
                const dim = c === 0;
                return (
                    <button
                        key={b}
                        type="button"
                        onClick={() => onSelect(b === active ? null : b)}
                        aria-pressed={active === b}
                        disabled={dim && active !== b}
                        className={`
                            inline-flex items-center gap-1.5
                            px-2.5 py-1 rounded text-[11.5px] font-medium
                            transition-colors
                            ${
                                active === b
                                    ? "ring-1"
                                    : "hover:bg-[var(--bg-hover)]"
                            }
                            ${dim && active !== b ? "opacity-40 cursor-not-allowed" : ""}
                        `}
                        style={
                            active === b
                                ? {
                                      background: meta.soft,
                                      color: meta.accent,
                                  }
                                : { color: "var(--text-secondary)" }
                        }
                    >
                        <span
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ background: meta.tint }}
                            aria-hidden
                        />
                        {meta.label}
                        <span className="tabular-nums text-[var(--text-muted)]">
                            {c}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  Card                                                                    */
/* ──────────────────────────────────────────────────────────────────────── */

function TriageCard({
    row,
    onChanged,
}: {
    row: ReviewQueueItem;
    onChanged: () => void;
}) {
    const [reclassifying, setReclassifying] = useState(false);
    const bucket = bucketOf(row.reason);
    const meta = REASON_META[bucket];
    const noteSuffix = reasonNote(row.reason);
    const badge = modelBadge(row.model_version);

    const auth = pct(row.predicted_authority_confidence);
    const typ = pct(row.predicted_type_confidence);

    const assignMu = useMutation({
        mutationFn: async (payload: {
            authority?: Authority;
            notice_type_id?: number;
        }) => {
            await complianceApi.assignReviewLabel(row.id, payload);
        },
        onSuccess: () => {
            toast.success("Classification confirmed");
            onChanged();
        },
        onError: (e) => toast.error(extractErrorMessage(e, "Assign failed")),
    });

    const confirmPredicted = () => {
        const payload: { authority?: Authority; notice_type_id?: number } = {};
        if (row.predicted_authority) {
            payload.authority = row.predicted_authority;
        }
        if (row.predicted_type_id !== null) {
            payload.notice_type_id = row.predicted_type_id;
        }
        if (!payload.authority && !payload.notice_type_id) {
            toast.error(
                "No prediction to confirm. Use Re-classify to set authority + type.",
            );
            return;
        }
        assignMu.mutate(payload);
    };

    return (
        <article
            className="
                surface-card relative overflow-hidden
                pl-4 pr-3 py-3 flex flex-col gap-3
                hover:shadow-[var(--shadow-md)] transition-shadow
            "
        >
            {/* Reason spine */}
            <div
                aria-hidden
                className="absolute left-0 top-0 bottom-0 w-1"
                style={{ background: meta.tint }}
            />

            {/* Header */}
            <div className="flex items-baseline gap-2 justify-between">
                <div className="flex items-baseline gap-2 min-w-0">
                    <Link
                        href={`/dashboard/compliance/notices/${row.notice_id}`}
                        className="
                            font-mono text-[13px] text-[var(--text-primary)]
                            hover:text-[var(--accent)] truncate
                            focus:outline-none focus:ring-2
                            focus:ring-[var(--accent-edge)] rounded px-0.5
                        "
                    >
                        #{row.notice_id}
                    </Link>
                    <span
                        className="
                            px-1.5 py-0.5 rounded text-[10.5px] font-medium
                            text-[var(--text-secondary)]
                            bg-[var(--bg-muted)]
                            border border-[var(--border-subtle)]
                        "
                    >
                        {row.predicted_authority ?? "·"}
                    </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <span
                        className="
                            inline-flex items-center gap-1
                            text-[10px] font-mono tracking-wider
                            text-[var(--text-muted)]
                        "
                        title={`Source: ${row.model_version}`}
                    >
                        <span
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ background: badge.dot }}
                            aria-hidden
                        />
                        {badge.label}
                    </span>
                    <span className="text-[10.5px] text-[var(--text-muted)] tabular-nums">
                        {ageLabel(row.created_at)}
                    </span>
                </div>
            </div>

            {/* Confidence dot strips */}
            <div className="grid grid-cols-2 gap-3">
                <DotConfidence label="Authority" pct={auth} />
                <DotConfidence label="Type" pct={typ} />
            </div>

            {/* Reason chip */}
            <div className="flex items-center gap-2 flex-wrap">
                <span
                    className="
                        inline-flex items-center gap-1.5
                        px-2 py-0.5 rounded
                        text-[11px] font-medium
                    "
                    style={{
                        background: meta.soft,
                        color: meta.accent,
                    }}
                >
                    <span
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: meta.tint }}
                        aria-hidden
                    />
                    {meta.label}
                </span>
                {noteSuffix && (
                    <span
                        className="
                            text-[11px] text-[var(--text-secondary)]
                            italic
                        "
                        title={`Operator note: ${noteSuffix}`}
                    >
                        “{noteSuffix}”
                    </span>
                )}
                {row.predicted_type_id !== null && (
                    <span className="text-[11px] text-[var(--text-muted)] ml-auto">
                        type id{" "}
                        <span className="font-mono tabular-nums">
                            {row.predicted_type_id}
                        </span>
                    </span>
                )}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 pt-1 border-t border-[var(--border-subtle)] -mx-1 px-1 mt-auto">
                <button
                    type="button"
                    onClick={confirmPredicted}
                    disabled={assignMu.isPending}
                    className="
                        inline-flex items-center gap-1.5
                        px-2.5 py-1 rounded
                        text-[11.5px] font-medium
                        bg-[var(--accent)] text-white
                        hover:bg-[var(--accent-strong)]
                        disabled:opacity-50
                        focus:outline-none focus:ring-2
                        focus:ring-[var(--accent-edge)]
                    "
                >
                    <FiCheck className="w-3.5 h-3.5" />
                    Confirm
                </button>
                <button
                    type="button"
                    onClick={() => setReclassifying(true)}
                    className="
                        inline-flex items-center gap-1.5
                        px-2.5 py-1 rounded
                        text-[11.5px] text-[var(--text-secondary)]
                        hover:text-[var(--text-primary)]
                        hover:bg-[var(--bg-hover)]
                        focus:outline-none focus:ring-2
                        focus:ring-[var(--accent-edge)]
                    "
                >
                    <FiCornerUpLeft className="w-3.5 h-3.5" />
                    Re-classify
                </button>
                <Link
                    href={`/dashboard/compliance/notices/${row.notice_id}`}
                    className="
                        inline-flex items-center gap-1.5
                        px-2.5 py-1 rounded
                        text-[11.5px] text-[var(--text-muted)]
                        hover:text-[var(--text-primary)]
                        hover:bg-[var(--bg-hover)]
                        ml-auto
                        focus:outline-none focus:ring-2
                        focus:ring-[var(--accent-edge)]
                    "
                >
                    Open
                    <FiExternalLink className="w-3.5 h-3.5" />
                </Link>
            </div>

            {reclassifying && (
                <ReclassifyDialog
                    row={row}
                    onClose={() => setReclassifying(false)}
                    onDone={() => {
                        setReclassifying(false);
                        onChanged();
                    }}
                />
            )}
        </article>
    );
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  Confidence visualisation: 10 dots with a threshold marker at the 75%   */
/*  position. Dots fill in proportional to the confidence; the threshold    */
/*  line makes "below the bar" obvious in under a second.                   */
/* ──────────────────────────────────────────────────────────────────────── */

function DotConfidence({
    label,
    pct,
}: {
    label: string;
    pct: number | null;
}) {
    const filled = pct === null ? 0 : Math.round(pct / 10);
    const below = pct !== null && pct / 100 < CONFIDENCE_THRESHOLD;
    const color = below
        ? "var(--danger)"
        : pct === null
          ? "var(--text-disabled)"
          : "var(--success)";
    return (
        <div className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between">
                <span className="text-[10.5px] uppercase tracking-wider text-[var(--text-muted)]">
                    {label}
                </span>
                <span
                    className="text-[12px] font-mono tabular-nums"
                    style={{ color }}
                >
                    {pct === null ? "·" : `${pct}%`}
                </span>
            </div>
            <div className="relative flex items-center gap-[3px] h-3">
                {Array.from({ length: 10 }).map((_, i) => (
                    <span
                        key={i}
                        className="block w-1.5 h-1.5 rounded-full"
                        style={{
                            background:
                                i < filled
                                    ? color
                                    : "var(--border-default)",
                            opacity: i < filled ? 1 : 0.6,
                        }}
                    />
                ))}
                {/* Threshold marker between dot 7 and 8 (75%) */}
                <span
                    aria-hidden
                    className="absolute h-3 border-l border-dashed"
                    style={{
                        left: `calc(${CONFIDENCE_THRESHOLD * 100}% - 1px)`,
                        borderColor: "var(--text-disabled)",
                    }}
                />
            </div>
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  Re-classify modal                                                       */
/* ──────────────────────────────────────────────────────────────────────── */

function ReclassifyDialog({
    row,
    onClose,
    onDone,
}: {
    row: ReviewQueueItem;
    onClose: () => void;
    onDone: () => void;
}) {
    const [authority, setAuthority] = useState<Authority | "">(
        (row.predicted_authority as Authority) || "",
    );
    const [typeId, setTypeId] = useState<string>(
        row.predicted_type_id !== null ? String(row.predicted_type_id) : "",
    );
    const [busy, setBusy] = useState(false);

    const submit = async () => {
        const payload: { authority?: Authority; notice_type_id?: number } = {};
        if (authority) payload.authority = authority;
        const tn = typeId.trim();
        if (tn) {
            const n = parseInt(tn, 10);
            if (!Number.isNaN(n)) payload.notice_type_id = n;
        }
        if (!payload.authority && payload.notice_type_id === undefined) {
            toast.error("Set authority and/or notice type id");
            return;
        }
        setBusy(true);
        try {
            await complianceApi.assignReviewLabel(row.id, payload);
            toast.success("Reviewer classification saved");
            onDone();
        } catch (e) {
            toast.error(extractErrorMessage(e, "Failed to save"));
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            className="
                fixed inset-0 bg-[rgba(15,23,42,0.45)] backdrop-blur-sm
                z-50 flex items-center justify-center p-6
            "
            role="dialog"
            aria-modal="true"
            aria-labelledby={`reclassify-title-${row.id}`}
            onClick={(e) => {
                if (e.target === e.currentTarget && !busy) onClose();
            }}
        >
            <div
                className="
                    bg-[var(--bg-surface)] border border-[var(--border-emphasis)]
                    rounded-[10px] p-5 w-full max-w-md shadow-[var(--shadow-lg)]
                "
            >
                <h2
                    id={`reclassify-title-${row.id}`}
                    className="text-[15px] font-semibold text-[var(--text-primary)]"
                >
                    Re-classify notice #{row.notice_id}
                </h2>
                <p className="text-[12px] text-[var(--text-muted)] mt-1 mb-4">
                    Pick the authoritative classification. Updates the parent
                    notice + writes a timeline activity + an immutable audit
                    log entry.
                </p>
                <div className="space-y-3">
                    <label className="block">
                        <span className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                            Authority
                        </span>
                        <select
                            value={authority}
                            onChange={(e) =>
                                setAuthority(
                                    e.target.value as Authority | "",
                                )
                            }
                            className="
                                w-full px-3 py-2 rounded
                                bg-[var(--bg-elevated)]
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)]
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                            "
                        >
                            <option value="">(leave unchanged)</option>
                            {AUTHORITIES.map((a) => (
                                <option key={a} value={a}>
                                    {a}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="block">
                        <span className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                            Notice type id
                        </span>
                        <input
                            type="number"
                            min={1}
                            value={typeId}
                            onChange={(e) => setTypeId(e.target.value)}
                            placeholder="e.g. 5"
                            className="
                                w-full px-3 py-2 rounded
                                bg-[var(--bg-elevated)]
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)] font-mono
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                            "
                        />
                        <p className="text-[11px] text-[var(--text-muted)] mt-1">
                            Must belong to the chosen authority.
                        </p>
                    </label>
                </div>
                <div className="flex justify-end gap-2 mt-5">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={busy}
                        className="
                            px-3 py-1.5 rounded text-[12.5px]
                            text-[var(--text-secondary)]
                            hover:text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)]
                            disabled:opacity-50
                        "
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onClick={submit}
                        disabled={busy}
                        className="
                            px-3 py-1.5 rounded text-[12.5px] font-medium
                            bg-[var(--accent)] text-white
                            hover:bg-[var(--accent-strong)]
                            disabled:opacity-50
                            focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                        "
                    >
                        {busy ? "Saving…" : "Save classification"}
                    </button>
                </div>
            </div>
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  Empty state with inline manual-flag form                                */
/* ──────────────────────────────────────────────────────────────────────── */

function EmptyState({ onFlagged }: { onFlagged: () => void }) {
    const [open, setOpen] = useState(false);
    const [noticeId, setNoticeId] = useState("");
    const [note, setNote] = useState("");
    const [busy, setBusy] = useState(false);

    const submit = async () => {
        const n = parseInt(noticeId, 10);
        if (Number.isNaN(n) || n <= 0) {
            toast.error("Enter a valid notice id");
            return;
        }
        setBusy(true);
        try {
            await complianceApi.manualEnqueueReview(
                n,
                note.trim() || undefined,
            );
            toast.success(`Notice #${n} flagged for review`);
            setOpen(false);
            setNoticeId("");
            setNote("");
            onFlagged();
        } catch (e) {
            toast.error(extractErrorMessage(e, "Flag failed"));
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="surface-card mt-4 px-6 py-10 text-center">
            <div
                className="
                    w-10 h-10 rounded-full mx-auto mb-3
                    flex items-center justify-center
                    bg-[var(--accent-soft)]
                "
            >
                <FiCheck
                    className="w-5 h-5 text-[var(--accent)]"
                    aria-hidden
                />
            </div>
            <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
                Inbox zero
            </h2>
            <p className="text-[12.5px] text-[var(--text-muted)] mt-2 max-w-md mx-auto leading-relaxed">
                The classifier is confident about every pending notice, and no
                teammate has flagged one for re-classification. Items below the
                75 percent confidence threshold land here automatically once a
                new notice is ingested.
            </p>

            {!open && (
                <button
                    type="button"
                    onClick={() => setOpen(true)}
                    className="
                        mt-5 inline-flex items-center gap-1.5
                        px-3 py-1.5 rounded
                        text-[12.5px] text-[var(--accent)]
                        border border-[var(--accent-edge)]
                        hover:bg-[var(--accent-soft)]
                        focus:outline-none focus:ring-2
                        focus:ring-[var(--accent-edge)]
                    "
                >
                    <FiFlag className="w-3.5 h-3.5" />
                    Flag a notice for review
                </button>
            )}

            {open && (
                <div className="mt-6 mx-auto max-w-sm text-left space-y-3">
                    <label className="block">
                        <span className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                            Notice id
                        </span>
                        <input
                            type="number"
                            min={1}
                            value={noticeId}
                            onChange={(e) => setNoticeId(e.target.value)}
                            placeholder="42"
                            className="
                                w-full px-3 py-2 rounded
                                bg-[var(--bg-elevated)]
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)] font-mono
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                            "
                        />
                    </label>
                    <label className="block">
                        <span className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                            Reason (optional, max 36 chars)
                        </span>
                        <input
                            type="text"
                            value={note}
                            onChange={(e) =>
                                setNote(e.target.value.slice(0, 36))
                            }
                            placeholder="Wrong authority?"
                            maxLength={36}
                            className="
                                w-full px-3 py-2 rounded
                                bg-[var(--bg-elevated)]
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)]
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                            "
                        />
                    </label>
                    <div className="flex items-center justify-between gap-2">
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            disabled={busy}
                            className="
                                text-[12.5px] text-[var(--text-muted)]
                                hover:text-[var(--text-primary)]
                                disabled:opacity-50
                            "
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            onClick={submit}
                            disabled={busy}
                            className="
                                px-3 py-1.5 rounded text-[12.5px] font-medium
                                bg-[var(--accent)] text-white
                                hover:bg-[var(--accent-strong)]
                                disabled:opacity-50
                                focus:outline-none focus:ring-2
                                focus:ring-[var(--accent-edge)]
                            "
                        >
                            {busy ? "Flagging…" : "Flag for review"}
                        </button>
                    </div>
                </div>
            )}

            <div
                className="
                    mt-6 inline-flex items-start gap-2
                    rounded border border-[var(--border-default)]
                    bg-[var(--bg-muted)] px-3 py-2 text-left max-w-lg
                "
            >
                <FiInfo className="w-3.5 h-3.5 text-[var(--text-muted)] mt-0.5 shrink-0" />
                <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
                    The queue surfaces items with classifier confidence below
                    75 percent. The current source is a rule-based heuristic
                    over the ner extractor output (gstins, pans, cins, type
                    assignment). When the BERT classifier ships in v2.1 it
                    takes over automatically.
                </p>
            </div>
        </div>
    );
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  Skeleton                                                                */
/* ──────────────────────────────────────────────────────────────────────── */

function SkeletonGrid() {
    return (
        <div
            className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-4"
            role="status"
            aria-live="polite"
        >
            {Array.from({ length: 4 }).map((_, i) => (
                <div
                    key={i}
                    className="surface-card px-4 py-3 h-[160px] space-y-3"
                >
                    <div className="h-4 w-32 bg-[var(--bg-hover)] rounded animate-pulse" />
                    <div className="h-3 w-24 bg-[var(--bg-hover)] rounded animate-pulse" />
                    <div className="h-3 w-full bg-[var(--bg-hover)] rounded animate-pulse" />
                    <div className="h-3 w-3/4 bg-[var(--bg-hover)] rounded animate-pulse" />
                </div>
            ))}
        </div>
    );
}
