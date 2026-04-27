"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { FiCheck, FiAlertTriangle, FiX } from "react-icons/fi";
import type { AxiosError } from "axios";
import type { ComplianceNotice, NoticeStatus } from "@/types/compliance";
import { STATUS_CONFIG } from "@/components/compliance/StatusPill";
import { complianceApi } from "@/lib/api/compliance";

/**
 * StatusWorkflow — UI-SPEC §10 horizontal pill chain + advance/dismiss buttons.
 *
 * Mirrors backend NoticeStateMachine (D-03):
 *   received → under_review → response_drafted → submitted → resolved
 *   any non-terminal → dismissed (forks at end)
 *
 * State-machine guards (D-03): only valid transitions surface as buttons. The
 * server is authoritative — on 422 the toast shows the backend's
 * `valid_next_statuses` so the user always sees the truth from the state
 * machine, not a frontend duplicate.
 */

const PROGRESSIVE_CHAIN: NoticeStatus[] = [
    "received",
    "under_review",
    "response_drafted",
    "submitted",
    "resolved",
];

const TERMINAL_FORK: NoticeStatus = "dismissed";

const ALLOWED_TRANSITIONS: Record<NoticeStatus, NoticeStatus[]> = {
    received: ["under_review", "dismissed"],
    under_review: ["response_drafted", "dismissed"],
    response_drafted: ["submitted", "dismissed"],
    submitted: ["resolved", "dismissed"],
    resolved: [],
    dismissed: [],
};

const ADVANCE_VERB: Record<NoticeStatus, string | null> = {
    received: "Mark Under Review",
    under_review: "Mark Response Drafted",
    response_drafted: "Mark Submitted",
    submitted: "Mark Resolved",
    resolved: null,
    dismissed: null,
};

interface InvalidTransitionPayload {
    error?: string;
    valid_next_statuses?: NoticeStatus[];
}

function parseInvalidTransition(
    err: unknown
): { from: NoticeStatus | null; valid: NoticeStatus[] } | null {
    const ax = err as AxiosError<{ detail?: InvalidTransitionPayload | string }>;
    if (!ax?.response || ax.response.status !== 422) return null;
    const detail = ax.response.data?.detail;
    if (!detail || typeof detail === "string") return null;
    if (!Array.isArray(detail.valid_next_statuses)) return null;
    return { from: null, valid: detail.valid_next_statuses };
}

function PillNode({
    status,
    state,
}: {
    status: NoticeStatus;
    state: "past" | "current" | "future";
}) {
    const c = STATUS_CONFIG[status];
    const Icon = c.icon;
    if (state === "current") {
        return (
            <span
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded font-medium"
                style={{ backgroundColor: `${c.color}1a`, color: c.color }}
                aria-current="step"
            >
                <Icon className="w-3.5 h-3.5" />
                {c.label}
            </span>
        );
    }
    if (state === "past") {
        return (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded font-medium border border-[#10b981]/40 text-[#10b981]">
                <FiCheck className="w-3.5 h-3.5" />
                {c.label}
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded font-medium border border-[#27272a] text-[#52525b]">
            <Icon className="w-3.5 h-3.5" />
            {c.label}
        </span>
    );
}

function Connector({ walked }: { walked: boolean }) {
    return (
        <span
            className={`h-px w-4 sm:w-6 ${walked ? "bg-[#10b981]" : "bg-[#27272a]"}`}
            aria-hidden="true"
        />
    );
}

interface Props {
    notice: ComplianceNotice;
}

export function StatusWorkflow({ notice }: Props) {
    const queryClient = useQueryClient();
    const [confirmDismiss, setConfirmDismiss] = useState(false);

    const transition = useMutation({
        mutationFn: async (newStatus: NoticeStatus) => {
            const { data } = await complianceApi.transitionStatus(notice.id, {
                new_status: newStatus,
            });
            return data;
        },
        onSuccess: (_data, newStatus) => {
            toast.success(`Moved to ${STATUS_CONFIG[newStatus].label}`);
            queryClient.invalidateQueries({ queryKey: ["notice", notice.id] });
            queryClient.invalidateQueries({ queryKey: ["notice-activity", notice.id] });
            queryClient.invalidateQueries({ queryKey: ["notices"] });
            queryClient.invalidateQueries({ queryKey: ["client-dashboard"] });
        },
        onError: (err) => {
            const parsed = parseInvalidTransition(err);
            if (parsed) {
                const list = parsed.valid.length
                    ? parsed.valid
                          .map((s) => STATUS_CONFIG[s].label)
                          .join(", ")
                    : "no further transitions";
                toast.error(
                    `That status change isn't allowed. A ${
                        STATUS_CONFIG[notice.status].label
                    } notice can only move to ${list}.`,
                    { duration: 6000 }
                );
            } else {
                toast.error(
                    err instanceof Error ? err.message : "Status change failed"
                );
            }
        },
    });

    const allowed = ALLOWED_TRANSITIONS[notice.status];
    const advanceTarget = allowed.find((s) => s !== "dismissed") ?? null;
    const canDismiss = allowed.includes("dismissed");
    const advanceLabel = advanceTarget ? ADVANCE_VERB[notice.status] : null;
    const currentIdx = PROGRESSIVE_CHAIN.indexOf(notice.status);
    const isTerminal = !advanceTarget && !canDismiss;

    return (
        <section
            aria-label="Status workflow"
            className="bg-[#111113] border border-[#27272a] rounded-md p-5"
        >
            <h3 className="text-[11px] uppercase tracking-wider text-[#a1a1aa] font-medium mb-4">
                Status workflow
            </h3>

            <div className="flex items-center flex-wrap gap-y-2 mb-3" role="list">
                {PROGRESSIVE_CHAIN.map((s, i) => {
                    const state: "past" | "current" | "future" =
                        notice.status === "dismissed"
                            ? "future"
                            : i < currentIdx
                              ? "past"
                              : i === currentIdx
                                ? "current"
                                : "future";
                    return (
                        <span key={s} className="inline-flex items-center" role="listitem">
                            {i > 0 && (
                                <Connector
                                    walked={
                                        notice.status !== "dismissed" && i <= currentIdx
                                    }
                                />
                            )}
                            <PillNode status={s} state={state} />
                        </span>
                    );
                })}
                <span className="ml-2 text-[11px] text-[#52525b]" aria-hidden="true">
                    or
                </span>
                <span className="ml-2">
                    <PillNode
                        status={TERMINAL_FORK}
                        state={
                            notice.status === "dismissed"
                                ? "current"
                                : "future"
                        }
                    />
                </span>
            </div>

            {isTerminal ? (
                <p className="text-[12px] text-[#71717a]">
                    Terminal state. No further transitions.
                </p>
            ) : confirmDismiss ? (
                <div
                    className="border border-[#ef4444]/40 bg-[#ef4444]/5 rounded p-4"
                    role="alertdialog"
                    aria-labelledby="dismiss-heading"
                >
                    <h4
                        id="dismiss-heading"
                        className="text-sm font-semibold text-white mb-1"
                    >
                        Dismiss notice {notice.notice_number}?
                    </h4>
                    <p className="text-[13px] text-[#a1a1aa] mb-3">
                        Dismissing marks the notice as closed without resolution.
                        You can re-open it within 30 days from the audit log.
                    </p>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => transition.mutate("dismissed")}
                            disabled={transition.isPending}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded bg-[#ef4444] text-white font-medium hover:bg-[#dc2626] disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-[#ef4444]/40"
                        >
                            <FiAlertTriangle className="w-3.5 h-3.5" />
                            {transition.isPending ? "Dismissing…" : "Dismiss notice"}
                        </button>
                        <button
                            type="button"
                            onClick={() => setConfirmDismiss(false)}
                            disabled={transition.isPending}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded text-[#a1a1aa] hover:text-white hover:bg-[#18181b] focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                        >
                            <FiX className="w-3.5 h-3.5" />
                            Keep open
                        </button>
                    </div>
                </div>
            ) : (
                <div className="flex items-center gap-2">
                    {advanceTarget && advanceLabel && (
                        <button
                            type="button"
                            onClick={() => transition.mutate(advanceTarget)}
                            disabled={transition.isPending}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded bg-[#3b82f6] text-white font-medium hover:bg-[#2563eb] disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                        >
                            {transition.isPending ? "Updating…" : advanceLabel}
                        </button>
                    )}
                    {canDismiss && (
                        <button
                            type="button"
                            onClick={() => setConfirmDismiss(true)}
                            disabled={transition.isPending}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded text-[#a1a1aa] border border-[#27272a] hover:text-[#ef4444] hover:border-[#ef4444]/60 focus:outline-none focus:ring-2 focus:ring-[#ef4444]/40"
                        >
                            Dismiss
                        </button>
                    )}
                </div>
            )}
        </section>
    );
}
