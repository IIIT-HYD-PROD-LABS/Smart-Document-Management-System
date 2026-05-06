"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
    FiArrowLeft,
    FiSave,
    FiSend,
    FiAlertCircle,
    FiCheck,
    FiX,
    FiRotateCcw,
} from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { NoticeResponseDetail, ResponseStatus } from "@/types/compliance";
import { ResponseStatusBadge } from "@/components/compliance/ResponseStatusBadge";
import { ApprovalStageStrip } from "@/components/compliance/ApprovalStageStrip";

/**
 * Phase 12 v2.0 response editor page at
 * /dashboard/compliance/notices/{id}/response.
 *
 * Three-pane layout:
 *   - Header: status badge + ApprovalStageStrip + actions (save / submit /
 *     withdraw / approve / reject)
 *   - Editor: subject + body markdown textarea + recipient + response_date
 *   - Right rail: version timeline + approval log
 *
 * v2.1 will add: rendered Markdown preview, LLM-assisted draft generation,
 * inline evidence attach, response template picker.
 */
export default function ResponseEditorPage() {
    const params = useParams<{ id: string }>();
    const noticeId = Number.parseInt(params.id, 10);
    const valid = Number.isFinite(noticeId);
    const qc = useQueryClient();

    const responseQ = useQuery({
        queryKey: ["notice-response", noticeId],
        queryFn: async () => {
            try {
                const { data } = await complianceApi.getResponse(noticeId);
                return data;
            } catch (err: unknown) {
                if (
                    typeof err === "object" &&
                    err !== null &&
                    "response" in err &&
                    (err as { response?: { status?: number } }).response?.status === 404
                ) {
                    return null;
                }
                throw err;
            }
        },
        enabled: valid,
    });

    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");
    const [recipient, setRecipient] = useState("");
    const [responseDate, setResponseDate] = useState("");
    const [rejectReason, setRejectReason] = useState("");

    // Hydrate form fields from current_version
    useEffect(() => {
        const cv = responseQ.data?.current_version;
        if (cv) {
            setSubject(cv.subject ?? "");
            setBody(cv.body_markdown);
            setRecipient(cv.recipient ?? "");
            setResponseDate(cv.response_date ?? "");
        }
    }, [responseQ.data?.current_version_id]);

    const detail: NoticeResponseDetail | null | undefined = responseQ.data;
    const status: ResponseStatus | "no_response" = detail
        ? detail.status
        : "no_response";
    const isDraftEditable = status === "draft";
    const isPending = (
        ["reviewer_pending", "legal_pending", "cfo_pending"] as ResponseStatus[]
    ).includes(status as ResponseStatus);

    const upsert = useMutation({
        mutationFn: async () => {
            const payload = {
                subject: subject || undefined,
                body_markdown: body,
                recipient: recipient || undefined,
                response_date: responseDate || undefined,
            };
            if (detail) {
                const { data } = await complianceApi.patchResponse(noticeId, payload);
                return data;
            }
            const { data } = await complianceApi.createOrUpdateResponse(noticeId, payload);
            return data;
        },
        onSuccess: () => qc.invalidateQueries({ queryKey: ["notice-response", noticeId] }),
    });
    const submit = useMutation({
        mutationFn: () => complianceApi.submitResponse(noticeId),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["notice-response", noticeId] }),
    });
    const withdraw = useMutation({
        mutationFn: () => complianceApi.withdrawResponse(noticeId),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["notice-response", noticeId] }),
    });
    const approve = useMutation({
        mutationFn: () => complianceApi.approveResponse(noticeId),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["notice-response", noticeId] }),
    });
    const reject = useMutation({
        mutationFn: (reason: string) => complianceApi.rejectResponse(noticeId, reason),
        onSuccess: () => {
            setRejectReason("");
            qc.invalidateQueries({ queryKey: ["notice-response", noticeId] });
        },
    });
    const rollback = useMutation({
        mutationFn: (target_version_id: number) =>
            complianceApi.rollbackResponse(noticeId, target_version_id),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["notice-response", noticeId] }),
    });

    if (!valid) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto">
                <p className="text-[13px] text-[#ef4444]">Invalid notice id.</p>
            </div>
        );
    }
    if (responseQ.isLoading) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto">
                <div className="h-6 w-48 bg-[#18181b] rounded animate-pulse mb-6" />
                <div className="h-64 bg-[#18181b] rounded animate-pulse" />
            </div>
        );
    }

    return (
        <div className="px-6 py-8 max-w-7xl mx-auto">
            <Link
                href={`/dashboard/compliance/notices/${noticeId}`}
                className="inline-flex items-center gap-1.5 text-[12px] text-[#a1a1aa] hover:text-white mb-4"
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to notice
            </Link>

            <header className="mb-6 flex items-start justify-between flex-wrap gap-4">
                <div>
                    <h1 className="text-2xl font-semibold text-white tracking-tight mb-1">
                        Response
                    </h1>
                    <p className="text-[13px] text-[#a1a1aa]">
                        Drafter → Reviewer → Legal → CFO. Notice cannot be marked submitted
                        until the response is approved.
                    </p>
                </div>
                {detail ? (
                    <div className="flex flex-col items-end gap-2">
                        <ResponseStatusBadge status={detail.status} size="md" />
                        <ApprovalStageStrip detail={detail} />
                    </div>
                ) : null}
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-4">
                    <DraftEditor
                        editable={isDraftEditable || !detail}
                        subject={subject}
                        body={body}
                        recipient={recipient}
                        responseDate={responseDate}
                        onChange={(s, b, r, d) => {
                            setSubject(s);
                            setBody(b);
                            setRecipient(r);
                            setResponseDate(d);
                        }}
                    />

                    <ActionBar
                        status={status}
                        canEdit={isDraftEditable || !detail}
                        canSubmit={status === "draft"}
                        canWithdraw={
                            detail !== null &&
                            detail !== undefined &&
                            !["approved", "rejected", "withdrawn"].includes(detail.status)
                        }
                        canApproveReject={isPending}
                        rejectReason={rejectReason}
                        onRejectReasonChange={setRejectReason}
                        onSave={() => upsert.mutate()}
                        onSubmit={() => submit.mutate()}
                        onWithdraw={() => withdraw.mutate()}
                        onApprove={() => approve.mutate()}
                        onReject={() => reject.mutate(rejectReason)}
                        saving={upsert.isPending}
                        submitting={submit.isPending}
                        approving={approve.isPending}
                        rejecting={reject.isPending}
                    />

                    <ErrorBanner mutations={[upsert, submit, withdraw, approve, reject, rollback]} />
                </div>

                <aside className="space-y-6">
                    {detail && (
                        <>
                            <VersionTimeline
                                detail={detail}
                                canRollback={isDraftEditable}
                                onRollback={(vid) => rollback.mutate(vid)}
                            />
                            <ApprovalLog detail={detail} />
                        </>
                    )}
                    {!detail && (
                        <div className="rounded border border-[#1f1f23] bg-[#0c0c0f] px-4 py-3 text-[12px] text-[#71717a]">
                            Save your first draft to begin tracking versions and
                            approvals.
                        </div>
                    )}
                </aside>
            </div>
        </div>
    );
}

function DraftEditor({
    editable,
    subject,
    body,
    recipient,
    responseDate,
    onChange,
}: {
    editable: boolean;
    subject: string;
    body: string;
    recipient: string;
    responseDate: string;
    onChange: (s: string, b: string, r: string, d: string) => void;
}) {
    return (
        <div className="rounded border border-[#1f1f23] bg-[#0c0c0f] p-4 space-y-3">
            <Field label="Subject">
                <input
                    type="text"
                    value={subject}
                    onChange={(e) => onChange(e.target.value, body, recipient, responseDate)}
                    disabled={!editable}
                    className="w-full bg-[#09090b] border border-[#1f1f23] rounded px-3 h-9 text-[13px] text-white focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 disabled:opacity-60"
                    placeholder="Re: Notice DRC-01/2026/A1 — Reply to demand notice"
                />
            </Field>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Field label="Recipient">
                    <input
                        type="text"
                        value={recipient}
                        onChange={(e) => onChange(subject, body, e.target.value, responseDate)}
                        disabled={!editable}
                        className="w-full bg-[#09090b] border border-[#1f1f23] rounded px-3 h-9 text-[13px] text-white focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 disabled:opacity-60"
                        placeholder="Asst. Commissioner, GST Range 5"
                    />
                </Field>
                <Field label="Response date">
                    <input
                        type="date"
                        value={responseDate}
                        onChange={(e) => onChange(subject, body, recipient, e.target.value)}
                        disabled={!editable}
                        className="w-full bg-[#09090b] border border-[#1f1f23] rounded px-3 h-9 text-[13px] text-white focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 disabled:opacity-60"
                    />
                </Field>
            </div>
            <Field label="Body (Markdown)">
                <textarea
                    value={body}
                    onChange={(e) => onChange(subject, e.target.value, recipient, responseDate)}
                    disabled={!editable}
                    rows={18}
                    className="w-full bg-[#09090b] border border-[#1f1f23] rounded px-3 py-2 text-[13px] text-white font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 disabled:opacity-60"
                    placeholder="# Response\n\nWith reference to the above-cited notice..."
                />
            </Field>
            {!editable && (
                <p className="text-[11px] text-[#71717a] flex items-center gap-1">
                    <FiAlertCircle className="w-3 h-3" />
                    Editor is read-only — response is past the draft stage. Withdraw or wait for
                    a rejection to edit again.
                </p>
            )}
        </div>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <label className="block">
            <span className="text-[11px] uppercase tracking-wider text-[#71717a] block mb-1.5">
                {label}
            </span>
            {children}
        </label>
    );
}

function ActionBar(props: {
    status: ResponseStatus | "no_response";
    canEdit: boolean;
    canSubmit: boolean;
    canWithdraw: boolean;
    canApproveReject: boolean;
    rejectReason: string;
    onRejectReasonChange: (s: string) => void;
    onSave: () => void;
    onSubmit: () => void;
    onWithdraw: () => void;
    onApprove: () => void;
    onReject: () => void;
    saving: boolean;
    submitting: boolean;
    approving: boolean;
    rejecting: boolean;
}) {
    return (
        <div className="rounded border border-[#1f1f23] bg-[#0c0c0f] p-4 flex flex-wrap items-center gap-3">
            {props.canEdit && (
                <ActionButton
                    onClick={props.onSave}
                    disabled={props.saving}
                    color="#3b82f6"
                    icon={FiSave}
                    label={props.saving ? "Saving…" : "Save version"}
                />
            )}
            {props.canSubmit && (
                <ActionButton
                    onClick={props.onSubmit}
                    disabled={props.submitting}
                    color="#10b981"
                    icon={FiSend}
                    label={props.submitting ? "Submitting…" : "Submit for review"}
                />
            )}
            {props.canWithdraw && (
                <ActionButton
                    onClick={props.onWithdraw}
                    color="#71717a"
                    icon={FiRotateCcw}
                    label="Withdraw"
                />
            )}
            {props.canApproveReject && (
                <>
                    <ActionButton
                        onClick={props.onApprove}
                        disabled={props.approving}
                        color="#10b981"
                        icon={FiCheck}
                        label={props.approving ? "Approving…" : "Approve current stage"}
                    />
                    <input
                        type="text"
                        value={props.rejectReason}
                        onChange={(e) => props.onRejectReasonChange(e.target.value)}
                        placeholder="Reject reason (required)"
                        className="flex-1 min-w-[160px] bg-[#09090b] border border-[#1f1f23] rounded px-3 h-8 text-[12px] text-white focus:outline-none focus:ring-2 focus:ring-[#ef4444]/40"
                    />
                    <ActionButton
                        onClick={props.onReject}
                        disabled={props.rejecting || !props.rejectReason.trim()}
                        color="#ef4444"
                        icon={FiX}
                        label={props.rejecting ? "Rejecting…" : "Reject"}
                    />
                </>
            )}
        </div>
    );
}

function ActionButton({
    onClick,
    disabled = false,
    color,
    icon: Icon,
    label,
}: {
    onClick: () => void;
    disabled?: boolean;
    color: string;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            className="inline-flex items-center gap-1.5 px-3 h-8 rounded border text-[12px] font-medium disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#09090b]"
            style={{
                backgroundColor: `${color}1a`,
                color,
                borderColor: `${color}40`,
            }}
        >
            <Icon className="w-3.5 h-3.5" />
            {label}
        </button>
    );
}

function VersionTimeline({
    detail,
    canRollback,
    onRollback,
}: {
    detail: NoticeResponseDetail;
    canRollback: boolean;
    onRollback: (vid: number) => void;
}) {
    return (
        <div className="rounded border border-[#1f1f23] bg-[#0c0c0f] p-4">
            <h3 className="text-[12px] uppercase tracking-wider text-[#71717a] mb-3">
                Versions ({detail.versions.length})
            </h3>
            <ul className="space-y-2">
                {detail.versions.map((v) => {
                    const isCurrent = v.id === detail.current_version_id;
                    return (
                        <li
                            key={v.id}
                            className={`flex items-center justify-between gap-2 px-2 py-1.5 rounded ${
                                isCurrent ? "bg-[#3b82f61a]" : ""
                            }`}
                        >
                            <span className="text-[12px] text-[#d4d4d8]">
                                v{v.version_no}
                                {v.rolled_back_from_version_id && (
                                    <span className="text-[10px] text-[#71717a] ml-1">
                                        (← v{v.rolled_back_from_version_id})
                                    </span>
                                )}
                            </span>
                            <span className="text-[10px] text-[#71717a] tabular-nums flex-1 text-right">
                                {new Date(v.created_at).toLocaleString()}
                            </span>
                            {!isCurrent && canRollback && (
                                <button
                                    type="button"
                                    onClick={() => onRollback(v.id)}
                                    className="text-[10px] text-[#3b82f6] hover:underline"
                                >
                                    rollback
                                </button>
                            )}
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}

function ApprovalLog({ detail }: { detail: NoticeResponseDetail }) {
    if (detail.approvals.length === 0) {
        return (
            <div className="rounded border border-[#1f1f23] bg-[#0c0c0f] px-4 py-3">
                <h3 className="text-[12px] uppercase tracking-wider text-[#71717a] mb-2">
                    Approval log
                </h3>
                <p className="text-[11px] text-[#71717a]">
                    No approvals yet. Submit the draft to trigger the workflow.
                </p>
            </div>
        );
    }
    return (
        <div className="rounded border border-[#1f1f23] bg-[#0c0c0f] p-4">
            <h3 className="text-[12px] uppercase tracking-wider text-[#71717a] mb-3">
                Approval log ({detail.approvals.length})
            </h3>
            <ul className="space-y-2">
                {detail.approvals.map((a) => {
                    const color = a.decision === "approved" ? "#10b981" : "#ef4444";
                    return (
                        <li key={a.id} className="text-[12px] flex flex-col gap-0.5">
                            <div className="flex items-center gap-2">
                                <span
                                    className="px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider font-semibold"
                                    style={{
                                        backgroundColor: `${color}1a`,
                                        color,
                                    }}
                                >
                                    {a.stage}
                                </span>
                                <span style={{ color }}>{a.decision}</span>
                                <span className="text-[10px] text-[#71717a] ml-auto tabular-nums">
                                    {new Date(a.created_at).toLocaleString()}
                                </span>
                            </div>
                            {a.reason && (
                                <p className="text-[11px] text-[#a1a1aa] italic ml-1">
                                    “{a.reason}”
                                </p>
                            )}
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}

function ErrorBanner({
    mutations,
}: {
    mutations: { error: unknown; isError: boolean }[];
}) {
    const erroring = mutations.find((m) => m.isError);
    if (!erroring) return null;
    const err = erroring.error as { response?: { data?: { detail?: string } }; message?: string };
    const msg = err.response?.data?.detail ?? err.message ?? "Action failed";
    return (
        <div
            role="alert"
            className="rounded border border-[#7f1d1d] bg-[#1f0b0b] px-3 py-2 text-[12px] text-[#fca5a5]"
        >
            {msg}
        </div>
    );
}
