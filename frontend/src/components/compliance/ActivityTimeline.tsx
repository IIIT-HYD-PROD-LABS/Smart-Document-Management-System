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
    status_change: "#3b82f6",
    note_added: "#71717a",
    file_attached: "#3b82f6",
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
                <span className="font-medium text-white">
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
                    <span className="text-[#ef4444]">to compliance head</span>
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
                attached <span className="font-medium text-white">{fn ?? "file"}</span>
            </>
        );
    }
    return (
        <>
            assigned to{" "}
            <span className="font-medium text-white">
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
            className="bg-[#111113] border border-[#27272a] rounded-md p-5"
        >
            <h3 className="text-[11px] uppercase tracking-wider text-[#a1a1aa] font-medium mb-3">
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
                    className="w-full bg-[#18181b] border border-[#27272a] rounded px-3 py-2 text-[13px] text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] focus:ring-1 focus:ring-[#3b82f6]/40 resize-none"
                />
                <div className="mt-2 flex justify-end">
                    <button
                        type="submit"
                        disabled={!note.trim() || addNote.isPending}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#3b82f6] text-white text-[12px] font-medium hover:bg-[#2563eb] disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
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
                            className="h-12 rounded bg-[#18181b] animate-pulse"
                        />
                    ))}
                </ul>
            ) : items.length === 0 ? (
                <div className="rounded bg-[#18181b]/40 border border-[#27272a] p-5 text-center">
                    <h4 className="text-sm font-semibold text-white mb-1">
                        Activity will appear here
                    </h4>
                    <p className="text-[13px] text-[#71717a]">
                        Status changes, notes, and attachments will be logged
                        automatically as you work this notice.
                    </p>
                </div>
            ) : (
                <ol className="relative pl-6 border-l border-[#27272a] space-y-5">
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
                                        className="w-3.5 h-3.5 text-[#71717a] mt-0.5 shrink-0"
                                        aria-hidden="true"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-[13px] text-[#a1a1aa]">
                                            {actionLine(a)}
                                        </p>
                                        {a.type === "note_added" && noteBody && (
                                            <p className="mt-1 text-[13px] text-white whitespace-pre-wrap">
                                                {noteBody}
                                            </p>
                                        )}
                                        <p
                                            className="mt-0.5 text-[11px] text-[#52525b]"
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
