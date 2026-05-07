"use client";

import { useState } from "react";
import {
    useQuery,
    useMutation,
    useQueryClient,
} from "@tanstack/react-query";
import { formatDistanceToNow, parseISO, format } from "date-fns";
import toast from "react-hot-toast";
import {
    FiActivity,
    FiEdit3,
    FiPaperclip,
    FiUserCheck,
    FiSend,
} from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { NoticeActivity } from "@/types/compliance";
import { STATUS_CONFIG } from "@/components/compliance/StatusPill";

/**
 * ActivityTimeline — UI-SPEC §9 vertical activity log embedded in notice
 * detail RIGHT column. Distinct from system audit log — shows only
 * user-facing notice activity (D-09).
 */

const TYPE_DOT_COLOR: Record<NoticeActivity["type"], string> = {
    status_change: "var(--accent)",
    note_added: "var(--text-muted)",
    file_attached: "var(--accent)",
    assigned: "#8b5cf6",
};

function typeIcon(type: NoticeActivity["type"]) {
    if (type === "status_change") return FiActivity;
    if (type === "note_added") return FiEdit3;
    if (type === "file_attached") return FiPaperclip;
    return FiUserCheck;
}

function actionLine(a: NoticeActivity): React.ReactNode {
    if (a.type === "status_change") {
        // Backend writes the target status under details["to"] (notice_service
        // transition_notice_status). Older callers used "new_status"; we read
        // both for backward compat and to repair the broken display that
        // showed every status change as "moved status to —".
        const to =
            (a.details?.["to"] as string | undefined) ??
            (a.details?.["new_status"] as string | undefined);
        const label = to && STATUS_CONFIG[to as keyof typeof STATUS_CONFIG]?.label;
        return (
            <>
                moved status to{" "}
                <span className="font-medium text-[var(--text-primary)]">
                    {label ?? to ?? "—"}
                </span>
            </>
        );
    }
    if (a.type === "assigned") {
        // Phase 10 escalation + Phase 10 review_queue both write type='assigned'.
        // Differentiate via details.source.
        const src = a.details?.["source"] as string | undefined;
        if (src === "critical_escalation") {
            const tier = a.details?.["risk_tier"] as string | undefined;
            return (
                <>
                    auto-escalated{tier ? ` (${tier} risk)` : ""}{" "}
                    <span className="text-[var(--danger)]">to compliance head</span>
                </>
            );
        }
        if (src === "review_queue") {
            return <>reviewer assigned authoritative classification</>;
        }
        return <>assignment changed</>;
    }
    if (a.type === "note_added") {
        return <>added a note</>;
    }
    if (a.type === "file_attached") {
        const fn = a.details?.["filename"] as string | undefined;
        return (
            <>
                attached <span className="font-medium text-[var(--text-primary)]">{fn ?? "file"}</span>
            </>
        );
    }
    return (
        <>
            assigned to{" "}
            <span className="font-medium text-[var(--text-primary)]">
                {(a.details?.["to"] as string) ?? "user"}
            </span>
        </>
    );
}

interface Props {
    noticeId: number;
}

export function ActivityTimeline({ noticeId }: Props) {
    const queryClient = useQueryClient();
    const [note, setNote] = useState("");

    const activityQ = useQuery({
        queryKey: ["notice-activity", noticeId],
        queryFn: async () => {
            const { data } = await complianceApi.listActivity(noticeId);
            return data;
        },
    });

    const addNote = useMutation({
        mutationFn: async (n: string) => {
            const { data } = await complianceApi.addNote(noticeId, n);
            return data;
        },
        onSuccess: () => {
            setNote("");
            toast.success("Note added");
            queryClient.invalidateQueries({
                queryKey: ["notice-activity", noticeId],
            });
        },
        onError: (err) =>
            toast.error(
                err instanceof Error ? err.message : "Could not save note"
            ),
    });

    const items = activityQ.data ?? [];

    return (
        <section
            aria-label="Activity timeline"
            className="surface-card p-5"
        >
            <h3 className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-medium mb-3">
                Activity
            </h3>

            <form
                className="mb-5"
                onSubmit={(e) => {
                    e.preventDefault();
                    const trimmed = note.trim();
                    if (trimmed) addNote.mutate(trimmed);
                }}
            >
                <label htmlFor="activity-note" className="sr-only">
                    Add note
                </label>
                <textarea
                    id="activity-note"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Add a note about this notice…"
                    rows={2}
                    className="w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded px-3 py-2 text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--border-emphasis)] focus:ring-1 focus:ring-[var(--accent-edge)] resize-none"
                />
                <div className="mt-2 flex justify-end">
                    <button
                        type="submit"
                        disabled={!note.trim() || addNote.isPending}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[var(--accent)] text-white text-[12px] font-medium hover:bg-[var(--accent-strong)] disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]"
                    >
                        <FiSend className="w-3.5 h-3.5" />
                        {addNote.isPending ? "Saving…" : "Save note"}
                    </button>
                </div>
            </form>

            {activityQ.isLoading ? (
                <ul className="space-y-3" role="status" aria-live="polite">
                    {[0, 1, 2].map((i) => (
                        <li
                            key={i}
                            className="h-12 rounded bg-[var(--bg-hover)] animate-pulse"
                        />
                    ))}
                </ul>
            ) : items.length === 0 ? (
                <div className="rounded bg-[var(--bg-muted)] border border-[var(--border-default)] p-5 text-center">
                    <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                        Activity will appear here
                    </h4>
                    <p className="text-[13px] text-[var(--text-muted)]">
                        Status changes, notes, and attachments will be logged
                        automatically as you work this notice.
                    </p>
                </div>
            ) : (
                <ol className="relative pl-6 border-l border-[var(--border-default)] space-y-5">
                    {items.map((a) => {
                        const dot = TYPE_DOT_COLOR[a.type];
                        const Icon = typeIcon(a.type);
                        const created = parseISO(a.created_at);
                        const rel = formatDistanceToNow(created, {
                            addSuffix: true,
                        });
                        const abs = format(created, "dd MMM yyyy, HH:mm");
                        const noteBody = a.details?.["note"] as string | undefined;
                        return (
                            <li key={a.id} className="relative">
                                <span
                                    className="absolute -left-[27px] top-1.5 w-2 h-2 rounded-full"
                                    style={{ backgroundColor: dot }}
                                    aria-hidden="true"
                                />
                                <div className="flex items-start gap-2">
                                    <Icon
                                        className="w-3.5 h-3.5 text-[var(--text-muted)] mt-0.5 shrink-0"
                                        aria-hidden="true"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-[13px] text-[var(--text-secondary)]">
                                            {actionLine(a)}
                                        </p>
                                        {a.type === "note_added" && noteBody && (
                                            <p className="mt-1 text-[13px] text-[var(--text-primary)] whitespace-pre-wrap">
                                                {noteBody}
                                            </p>
                                        )}
                                        <p
                                            className="mt-0.5 text-[11px] text-[var(--text-subtle)]"
                                            title={abs}
                                        >
                                            {rel}
                                        </p>
                                    </div>
                                </div>
                            </li>
                        );
                    })}
                </ol>
            )}
        </section>
    );
}
