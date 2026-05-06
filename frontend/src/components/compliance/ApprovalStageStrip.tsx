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
 * Each stage chip shows: filled-green (last decision was approve),
 * red (last decision was reject), amber + pulse (currently awaiting),
 * or hollow (not yet reached).
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
        <div className="flex items-center gap-2">
            <DrafterChip
                done={detail.status !== "draft"}
            />
            <Connector />
            {STAGES.map(({ stage, label }, idx) => {
                const decision = latestByStage[stage];
                const isCurrent = pendingStage === stage;
                return (
                    <span key={stage} className="flex items-center gap-2">
                        <StageChip
                            label={label}
                            decision={decision}
                            isCurrent={isCurrent}
                        />
                        {idx < STAGES.length - 1 && <Connector />}
                    </span>
                );
            })}
            <Connector />
            <FinalChip status={detail.status} />
        </div>
    );
}

function DrafterChip({ done }: { done: boolean }) {
    const color = done ? "#10b981" : "#71717a";
    const Icon = done ? FiCheck : FiCircle;
    return (
        <span
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium"
            style={{ backgroundColor: `${color}1a`, color }}
        >
            <Icon className="w-3 h-3" />
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
    let color = "#71717a";
    let Icon: React.ComponentType<{ className?: string }> = FiCircle;
    let pulse = "";
    if (decision === "approved") {
        color = "#10b981";
        Icon = FiCheck;
    } else if (decision === "rejected") {
        color = "#ef4444";
        Icon = FiX;
    }
    if (isCurrent) {
        color = "#f59e0b";
        Icon = FiClock;
        pulse = "motion-safe:animate-pulse";
    }
    return (
        <span
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium ${pulse}`}
            style={{ backgroundColor: `${color}1a`, color }}
        >
            <Icon className="w-3 h-3" />
            {label}
        </span>
    );
}

function FinalChip({ status }: { status: string }) {
    let color = "#71717a";
    let Icon: React.ComponentType<{ className?: string }> = FiCircle;
    let label = "Pending";
    if (status === "approved") {
        color = "#10b981";
        Icon = FiCheck;
        label = "Approved";
    } else if (status === "rejected") {
        color = "#ef4444";
        Icon = FiX;
        label = "Rejected";
    } else if (status === "withdrawn") {
        color = "#71717a";
        Icon = FiX;
        label = "Withdrawn";
    }
    return (
        <span
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium"
            style={{ backgroundColor: `${color}1a`, color }}
        >
            <Icon className="w-3 h-3" />
            {label}
        </span>
    );
}

function Connector() {
    return <span className="w-3 h-px bg-[#1f1f23]" aria-hidden />;
}
