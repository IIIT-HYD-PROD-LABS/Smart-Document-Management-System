"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { parseISO, formatDistanceToNow } from "date-fns";
import { FiArrowLeft, FiEdit3, FiCalendar, FiAlertOctagon } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { ComplianceNotice, RiskTier } from "@/types/compliance";
import { AuthorityBadge } from "@/components/compliance/AuthorityBadge";
import { StatusPill } from "@/components/compliance/StatusPill";
import { ConfidenceBadge } from "@/components/compliance/ConfidenceBadge";
import { WhyThisRiskScore } from "@/components/compliance/WhyThisRiskScore";
import { MetadataPanel } from "@/components/compliance/MetadataPanel";
import { StatusWorkflow } from "@/components/compliance/StatusWorkflow";
import { NoticeChainTree } from "@/components/compliance/NoticeChainTree";
import { ActivityTimeline } from "@/components/compliance/ActivityTimeline";
import { AttachmentList } from "@/components/compliance/AttachmentList";
import { FileDropzone } from "@/components/compliance/FileDropzone";
import { TIER_CONFIG } from "@/components/compliance/RiskTierDot";

/**
 * Notice detail — enterprise hero + UI-SPEC §2 two-column 40/60 body.
 *
 * Hero (top): risk-tier color stripe on the left, large notice number,
 * authority + status + risk pills, deadline countdown chip, "Draft response"
 * action. Body: lg:grid-cols-5 — LEFT 40% metadata/workflow/chain,
 * RIGHT 60% activity/attachments/upload (stacks below lg, LEFT first).
 */

function isOverdue(n: ComplianceNotice): boolean {
    if (!n.response_deadline) return false;
    if (
        n.status === "resolved" ||
        n.status === "dismissed" ||
        n.status === "submitted"
    )
        return false;
    try {
        return parseISO(n.response_deadline).getTime() < Date.now();
    } catch {
        return false;
    }
}

function deadlineCountdown(
    n: ComplianceNotice
): { label: string; tone: "info" | "warning" | "danger" } | null {
    if (!n.response_deadline) return null;
    try {
        const dt = parseISO(n.response_deadline);
        const ms = dt.getTime() - Date.now();
        const days = Math.round(ms / (1000 * 60 * 60 * 24));
        if (days < 0) {
            return {
                label: `Overdue · ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"}`,
                tone: "danger",
            };
        }
        if (days <= 3) {
            return {
                label: days === 0
                    ? "Due today"
                    : `Due in ${days} day${days === 1 ? "" : "s"}`,
                tone: "warning",
            };
        }
        return {
            label: `Due ${formatDistanceToNow(dt, { addSuffix: true })}`,
            tone: "info",
        };
    } catch {
        return null;
    }
}

export default function NoticeDetailPage() {
    const params = useParams<{ id: string }>();
    const noticeId = Number.parseInt(params.id, 10);
    const valid = Number.isFinite(noticeId);

    const noticeQ = useQuery({
        queryKey: ["notice", noticeId],
        queryFn: async () => {
            const { data } = await complianceApi.getNotice(noticeId);
            return data;
        },
        enabled: valid,
    });

    if (!valid) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto">
                <p className="text-[13px] text-[var(--danger)]">Invalid notice id.</p>
            </div>
        );
    }

    if (noticeQ.isLoading) {
        return (
            <div
                className="px-6 py-8 max-w-5xl mx-auto"
                role="status"
                aria-live="polite"
            >
                <div className="h-6 w-48 bg-[var(--bg-hover)] rounded animate-pulse mb-6" />
                <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                    <div className="lg:col-span-2 h-72 bg-[var(--bg-hover)] rounded animate-pulse" />
                    <div className="lg:col-span-3 h-72 bg-[var(--bg-hover)] rounded animate-pulse" />
                </div>
            </div>
        );
    }

    if (noticeQ.error || !noticeQ.data) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto">
                <Link
                    href="/dashboard/compliance"
                    className="inline-flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-4"
                >
                    <FiArrowLeft className="w-3.5 h-3.5" />
                    Back to dashboard
                </Link>
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
                    Notice not found
                </h1>
                <p className="text-[13px] text-[var(--text-muted)]">
                    The notice may have been deleted, or you don&apos;t have
                    access to its client.
                </p>
            </div>
        );
    }

    const notice = noticeQ.data;
    const overdue = isOverdue(notice);
    const tier = notice.risk_tier as RiskTier | null;
    const stripeColor = tier ? TIER_CONFIG[tier]?.color ?? "var(--border-default)" : "var(--border-default)";
    const countdown = deadlineCountdown(notice);

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <Link
                href="/dashboard/compliance"
                className="inline-flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-4 focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded px-1"
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to dashboard
            </Link>

            {/* ── Hero header ─────────────────────────────────────── */}
            <header
                className="surface-card relative overflow-hidden mb-6"
                aria-label={`Notice ${notice.notice_number}`}
            >
                {/* Risk-tier color stripe on left edge */}
                <span
                    className="absolute top-0 left-0 bottom-0 w-1"
                    style={{ backgroundColor: stripeColor }}
                    aria-hidden
                />
                <div className="pl-5 pr-5 py-5">
                    <p className="microtype text-[var(--text-muted)] mb-1">
                        {notice.authority} · Notice
                    </p>
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div className="min-w-0">
                            <h1 className="text-[24px] leading-[1.2] font-semibold text-[var(--text-primary)] tracking-tight font-mono break-all">
                                {notice.notice_number}
                            </h1>
                            <div className="mt-3 flex items-center gap-2 flex-wrap">
                                <AuthorityBadge authority={notice.authority} size="md" />
                                <StatusPill
                                    status={notice.status}
                                    overdue={overdue}
                                    size="md"
                                />
                                <ConfidenceBadge
                                    authorityConfidence={
                                        notice.classifier_authority_confidence !== null
                                            ? Number(notice.classifier_authority_confidence)
                                            : null
                                    }
                                    typeConfidence={
                                        notice.classifier_type_confidence !== null
                                            ? Number(notice.classifier_type_confidence)
                                            : null
                                    }
                                    size="md"
                                />
                                {countdown && (
                                    <span
                                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[11.5px] font-medium border"
                                        style={
                                            countdown.tone === "danger"
                                                ? {
                                                      backgroundColor: "var(--danger-soft)",
                                                      color: "var(--danger)",
                                                      borderColor:
                                                          "color-mix(in srgb, var(--danger) 30%, transparent)",
                                                  }
                                                : countdown.tone === "warning"
                                                ? {
                                                      backgroundColor: "var(--warning-soft)",
                                                      color: "var(--warning)",
                                                      borderColor:
                                                          "color-mix(in srgb, var(--warning) 30%, transparent)",
                                                  }
                                                : {
                                                      backgroundColor: "var(--info-soft)",
                                                      color: "var(--info)",
                                                      borderColor:
                                                          "color-mix(in srgb, var(--info) 30%, transparent)",
                                                  }
                                        }
                                    >
                                        {countdown.tone === "danger" ? (
                                            <FiAlertOctagon className="w-3.5 h-3.5" />
                                        ) : (
                                            <FiCalendar className="w-3.5 h-3.5" />
                                        )}
                                        {countdown.label}
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                            <Link
                                href={`/dashboard/compliance/notices/${notice.id}/response`}
                                className="inline-flex items-center gap-1.5 px-3 h-9 rounded-md bg-[var(--accent)] hover:bg-[var(--accent-strong)] text-[13px] text-white font-medium transition-colors shadow-[var(--shadow-sm)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]"
                            >
                                <FiEdit3 className="w-3.5 h-3.5" />
                                Draft response
                            </Link>
                        </div>
                    </div>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                <div className="lg:col-span-2 space-y-6">
                    <MetadataPanel notice={notice} />
                    <WhyThisRiskScore
                        score={
                            notice.risk_score !== null
                                ? Number(notice.risk_score)
                                : null
                        }
                        tier={notice.risk_tier}
                        factors={
                            notice.ner_extracted_fields?.risk_top_factors ?? null
                        }
                        modelVersion={notice.model_version}
                        scoredAt={notice.risk_scored_at}
                    />
                    <StatusWorkflow notice={notice} />
                    <NoticeChainTree noticeId={notice.id} />
                </div>

                <div className="lg:col-span-3 space-y-6">
                    <ActivityTimeline noticeId={notice.id} />
                    <AttachmentList noticeId={notice.id} />
                    <FileDropzone noticeId={notice.id} />
                </div>
            </div>
        </div>
    );
}
