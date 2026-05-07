"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { FiArrowLeft, FiInfo, FiUserCheck } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { ReviewQueueItem } from "@/types/compliance";

/**
 * Phase 10 Review Queue page — at /dashboard/compliance/review.
 *
 * v2.0: classifier confidences are NULL (BERT deferred to v2.1) so this
 * queue stays empty by design. The page renders an explanatory empty
 * state describing the v2.0/v2.1 split. Once v2.1 ships and BERT
 * predictions populate, this page will surface low-confidence rows for
 * compliance_head / ca_consultant / legal_team to assign correct labels.
 */
export default function ReviewQueuePage() {
    const queueQ = useQuery({
        queryKey: ["compliance-review-pending"],
        queryFn: async () => {
            const { data } = await complianceApi.listPendingReview(1, 50);
            return data;
        },
    });

    const items = queueQ.data?.items ?? [];

    return (
        <div className="px-6 py-8 max-w-6xl mx-auto">
            <Link
                href="/dashboard/compliance"
                className="inline-flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-4 focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded px-1"
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to dashboard
            </Link>

            <header className="mb-6 flex items-center justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-[var(--text-primary)] tracking-tight">
                        Review queue
                    </h1>
                    <p className="text-[13px] text-[var(--text-muted)] mt-1">
                        Notices whose automatic classification fell below
                        the 75% confidence threshold and need a human label.
                    </p>
                </div>
                {queueQ.data && (
                    <span className="text-[12px] text-[var(--text-muted)] tabular-nums">
                        {queueQ.data.total} pending
                    </span>
                )}
            </header>

            {queueQ.isLoading && (
                <div
                    className="surface-card p-6"
                    role="status"
                    aria-live="polite"
                >
                    <div className="h-4 w-40 bg-[var(--bg-hover)] rounded animate-pulse mb-3" />
                    <div className="h-4 w-72 bg-[var(--bg-hover)] rounded animate-pulse mb-3" />
                    <div className="h-4 w-56 bg-[var(--bg-hover)] rounded animate-pulse" />
                </div>
            )}

            {queueQ.error && !queueQ.isLoading && (
                <div className="rounded border border-[color:color-mix(in_srgb,var(--danger)_30%,transparent)] bg-[var(--danger-soft)] px-4 py-3 text-[13px] text-[var(--danger)]">
                    Failed to load review queue. Refresh the page or try again.
                </div>
            )}

            {!queueQ.isLoading && !queueQ.error && items.length === 0 && (
                <EmptyState />
            )}

            {!queueQ.isLoading && items.length > 0 && (
                <ReviewTable items={items} onChanged={() => queueQ.refetch()} />
            )}
        </div>
    );
}

function EmptyState() {
    return (
        <div className="surface-card px-6 py-10 text-center">
            <FiUserCheck
                className="w-8 h-8 text-[var(--accent)] mx-auto mb-3"
                aria-hidden
            />
            <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
                Queue is empty
            </h2>
            <p className="text-[13px] text-[var(--text-muted)] mt-2 max-w-md mx-auto leading-relaxed">
                No notices currently need review.
            </p>
            <div className="mt-6 inline-flex items-start gap-2 rounded border border-[var(--border-default)] bg-[var(--bg-muted)] px-3 py-2 text-left max-w-lg">
                <FiInfo className="w-3.5 h-3.5 text-[var(--text-muted)] mt-0.5 shrink-0" />
                <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
                    The review queue surfaces low-confidence ML predictions
                    when the BERT classifier ships in v2.1. v2.0 ships the
                    rule-based risk scorer and the queue infrastructure;
                    once trained, predictions below 75% confidence will land
                    here for human assignment.
                </p>
            </div>
        </div>
    );
}

function ReviewTable({
    items,
    onChanged,
}: {
    items: ReviewQueueItem[];
    onChanged: () => void;
}) {
    return (
        <div className="surface-card overflow-hidden">
            <table className="w-full text-left">
                <thead className="bg-[var(--bg-muted)] border-b border-[var(--border-default)]">
                    <tr>
                        <Th>Notice</Th>
                        <Th>Predicted authority</Th>
                        <Th>Predicted type</Th>
                        <Th>Reason</Th>
                        <Th>Created</Th>
                        <Th align="right">Action</Th>
                    </tr>
                </thead>
                <tbody>
                    {items.map((row) => (
                        <ReviewRow
                            key={row.id}
                            row={row}
                            onChanged={onChanged}
                        />
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function Th({
    children,
    align = "left",
}: {
    children: React.ReactNode;
    align?: "left" | "right";
}) {
    return (
        <th
            className={`px-4 py-2.5 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-medium ${
                align === "right" ? "text-right" : ""
            }`}
        >
            {children}
        </th>
    );
}

function ReviewRow({
    row,
    onChanged,
}: {
    row: ReviewQueueItem;
    onChanged: () => void;
}) {
    const conf = (s: string | null) =>
        s === null ? "—" : `${Math.round(parseFloat(s) * 100)}%`;

    const reasonLabel = {
        low_authority_confidence: "Low authority",
        low_type_confidence: "Low type",
        both: "Both",
    }[row.reason];

    return (
        <tr className="border-b border-[var(--border-default)] last:border-0 hover:bg-[var(--bg-hover)]">
            <td className="px-4 py-3 align-middle">
                <Link
                    href={`/dashboard/compliance/notices/${row.notice_id}`}
                    className="text-[13px] text-[var(--text-primary)] font-mono hover:underline"
                >
                    #{row.notice_id}
                </Link>
            </td>
            <td className="px-4 py-3 align-middle">
                <span className="text-[13px] text-[var(--text-secondary)]">
                    {row.predicted_authority ?? "—"}
                </span>
                <span className="text-[11px] text-[var(--text-muted)] ml-2 tabular-nums">
                    {conf(row.predicted_authority_confidence)}
                </span>
            </td>
            <td className="px-4 py-3 align-middle">
                <span className="text-[13px] text-[var(--text-secondary)]">
                    {row.predicted_type_id ?? "—"}
                </span>
                <span className="text-[11px] text-[var(--text-muted)] ml-2 tabular-nums">
                    {conf(row.predicted_type_confidence)}
                </span>
            </td>
            <td className="px-4 py-3 align-middle">
                <span className="text-[11px] text-[var(--warning)] uppercase tracking-wider">
                    {reasonLabel}
                </span>
            </td>
            <td className="px-4 py-3 align-middle">
                <span className="text-[12px] text-[var(--text-muted)] tabular-nums">
                    {new Date(row.created_at).toLocaleDateString()}
                </span>
            </td>
            <td className="px-4 py-3 align-middle text-right">
                <AssignButton row={row} onChanged={onChanged} />
            </td>
        </tr>
    );
}

function AssignButton({
    row,
    onChanged,
}: {
    row: ReviewQueueItem;
    onChanged: () => void;
}) {
    const handle = async () => {
        try {
            await complianceApi.assignReviewLabel(row.id, {
                authority: row.predicted_authority ?? undefined,
                notice_type_id: row.predicted_type_id ?? undefined,
            });
            onChanged();
        } catch (e) {
            console.error("assign failed", e);
        }
    };

    return (
        <button
            type="button"
            onClick={handle}
            className="
                inline-flex items-center gap-1.5 px-2.5 py-1
                rounded border border-[var(--accent-edge)]
                text-[11px] text-[var(--accent)] font-medium
                hover:bg-[var(--accent-soft)]
                focus-visible:outline-none focus-visible:ring-2
                focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2
                focus-visible:ring-offset-[var(--bg-page)]
            "
        >
            Assign
        </button>
    );
}
