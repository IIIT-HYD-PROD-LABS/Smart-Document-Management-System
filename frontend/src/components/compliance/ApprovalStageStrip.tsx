"use client";

import { FiCheck, FiX, FiClock, FiCircle } from "react-icons/fi";
import type {
    NoticeResponseDetail,
    ApprovalStage,
} from "@/types/compliance";

const STAGES: { stage: ApprovalStage; label: string }[] = [
    { stage: "reviewer", label: "Reviewer" },
    { stage: "legal", label: "Legal" },
    { stage: "cfo", label: "CFO" },
];

/**
 * Visualises the 4-stage Drafter → Reviewer → Legal → CFO chain.
 *
 * Each stage chip shows: filled-success (last decision was approve),
 * danger (last decision was reject), warning + pulse (currently awaiting),
 * or hollow (not yet reached). Tokenized for the enterprise light theme
 * with explicit dark-theme overrides preserved through CSS vars.
 */
interface Props {
    detail: NoticeResponseDetail;
}

export function ApprovalStageStrip({ detail }: Props) {
    const isPending = detail.status.endsWith("_pending");
    const pendingStage: ApprovalStage | null = isPending
        ? (detail.status.replace("_pending", "") as ApprovalStage)
        : null;

    // Latest decision per stage (approvals already chronologically ordered)
    const latestByStage: Record<string, "approved" | "rejected" | undefined> = {};
    for (const a of detail.approvals) {
        latestByStage[a.stage] = a.decision;
    }

    return (
        <div className="flex items-center gap-2 flex-wrap">
            <DrafterChip
                done={detail.status !== "draft"}
            />
            <Connector walked={detail.status !== "draft"} />
            {STAGES.map(({ stage, label }, idx) => {
                const decision = latestByStage[stage];
                const isCurrent = pendingStage === stage;
                const walkedNext = decision === "approved";
                return (
                    <span key={stage} className="flex items-center gap-2">
                        <StageChip
                            label={label}
                            decision={decision}
                            isCurrent={isCurrent}
                        />
                        {idx < STAGES.length - 1 && <Connector walked={walkedNext} />}
                    </span>
                );
            })}
            <Connector walked={detail.status === "approved"} />
            <FinalChip status={detail.status} />
        </div>
    );
}

function DrafterChip({ done }: { done: boolean }) {
    if (done) {
        return (
            <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--success-soft)] text-[var(--success)] border-[color:color-mix(in_srgb,var(--success)_30%,transparent)]"
            >
                <FiCheck className="w-3 h-3" />
                Drafter
            </span>
        );
    }
    return (
        <span
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--bg-muted)] text-[var(--text-muted)] border-[var(--border-default)]"
        >
            <FiCircle className="w-3 h-3" />
            Drafter
        </span>
    );
}

function StageChip({
    label,
    decision,
    isCurrent,
}: {
    label: string;
    decision: "approved" | "rejected" | undefined;
    isCurrent: boolean;
}) {
    if (isCurrent) {
        return (
            <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border motion-safe:animate-pulse bg-[var(--warning-soft)] text-[var(--warning)] border-[color:color-mix(in_srgb,var(--warning)_30%,transparent)] ring-2 ring-[color:color-mix(in_srgb,var(--accent)_30%,transparent)] ring-offset-1 ring-offset-[var(--bg-elevated)]"
            >
                <FiClock className="w-3 h-3" />
                {label}
            </span>
        );
    }
    if (decision === "approved") {
        return (
            <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--success-soft)] text-[var(--success)] border-[color:color-mix(in_srgb,var(--success)_30%,transparent)]"
            >
                <FiCheck className="w-3 h-3" />
                {label}
            </span>
        );
    }
    if (decision === "rejected") {
        return (
            <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--danger-soft)] text-[var(--danger)] border-[color:color-mix(in_srgb,var(--danger)_30%,transparent)]"
            >
                <FiX className="w-3 h-3" />
                {label}
            </span>
        );
    }
    return (
        <span
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--bg-muted)] text-[var(--text-muted)] border-[var(--border-default)]"
        >
            <FiCircle className="w-3 h-3" />
            {label}
        </span>
    );
}

function FinalChip({ status }: { status: string }) {
    if (status === "approved") {
        return (
            <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--success-soft)] text-[var(--success)] border-[color:color-mix(in_srgb,var(--success)_30%,transparent)]"
            >
                <FiCheck className="w-3 h-3" />
                Approved
            </span>
        );
    }
    if (status === "rejected") {
        return (
            <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--danger-soft)] text-[var(--danger)] border-[color:color-mix(in_srgb,var(--danger)_30%,transparent)]"
            >
                <FiX className="w-3 h-3" />
                Rejected
            </span>
        );
    }
    if (status === "withdrawn") {
        return (
            <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--bg-muted)] text-[var(--text-muted)] border-[var(--border-default)]"
            >
                <FiX className="w-3 h-3" />
                Withdrawn
            </span>
        );
    }
    return (
        <span
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border bg-[var(--bg-muted)] text-[var(--text-muted)] border-[var(--border-default)]"
        >
            <FiCircle className="w-3 h-3" />
            Pending
        </span>
    );
}

function Connector({ walked }: { walked: boolean }) {
    return (
        <span
            className={`w-3 h-px ${walked ? "bg-[var(--success)]" : "bg-[var(--border-default)]"}`}
            aria-hidden
        />
    );
}
