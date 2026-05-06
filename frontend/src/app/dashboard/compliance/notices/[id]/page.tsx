"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { parseISO } from "date-fns";
import { FiArrowLeft, FiEdit3 } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { ComplianceNotice } from "@/types/compliance";
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

/**
 * Notice detail — UI-SPEC §2 two-column 40/60 layout.
 *
 * lg+: lg:grid-cols-5 with LEFT (lg:col-span-2 = 40%) holding metadata,
 * workflow, and chain; RIGHT (lg:col-span-3 = 60%) holding activity,
 * attachments, and the upload dropzone. Below lg the columns stack with LEFT
 * first per CONTEXT D-31.
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
                <p className="text-[13px] text-[#ef4444]">Invalid notice id.</p>
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
                <div className="h-6 w-48 bg-[#18181b] rounded animate-pulse mb-6" />
                <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                    <div className="lg:col-span-2 h-72 bg-[#18181b] rounded animate-pulse" />
                    <div className="lg:col-span-3 h-72 bg-[#18181b] rounded animate-pulse" />
                </div>
            </div>
        );
    }

    if (noticeQ.error || !noticeQ.data) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto">
                <Link
                    href="/dashboard/compliance"
                    className="inline-flex items-center gap-1.5 text-[12px] text-[#a1a1aa] hover:text-white mb-4"
                >
                    <FiArrowLeft className="w-3.5 h-3.5" />
                    Back to dashboard
                </Link>
                <h1 className="text-lg font-semibold text-white mb-1">
                    Notice not found
                </h1>
                <p className="text-[13px] text-[#71717a]">
                    The notice may have been deleted, or you don&apos;t have
                    access to its client.
                </p>
            </div>
        );
    }

    const notice = noticeQ.data;
    const overdue = isOverdue(notice);

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <Link
                href="/dashboard/compliance"
                className="inline-flex items-center gap-1.5 text-[12px] text-[#a1a1aa] hover:text-white mb-4 focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 rounded px-1"
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to dashboard
            </Link>

            <header className="mb-6 flex items-center gap-3 flex-wrap">
                <h1
                    className="text-2xl font-semibold text-white tracking-tight"
                    aria-label={`Notice ${notice.notice_number}`}
                >
                    {notice.notice_number}
                </h1>
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
                <Link
                    href={`/dashboard/compliance/notices/${notice.id}/response`}
                    className="ml-auto inline-flex items-center gap-1.5 px-3 h-8 rounded border border-[#3b82f6]/40 bg-[#3b82f61a] text-[12px] text-[#3b82f6] font-medium hover:bg-[#3b82f626] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-2 focus-visible:ring-offset-[#09090b]"
                >
                    <FiEdit3 className="w-3.5 h-3.5" />
                    Draft response
                </Link>
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
