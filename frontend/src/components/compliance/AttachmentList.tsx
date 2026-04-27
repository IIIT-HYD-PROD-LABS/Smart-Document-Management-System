"use client";

import { useQuery } from "@tanstack/react-query";
import { FiFile } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";

/**
 * AttachmentList — UI-SPEC §2 RIGHT column file list.
 *
 * Phase 9 sources attachments from the notice activity feed (`file_attached`
 * entries). The primary `notice.document_id` is set on first upload (Plan 05
 * "first-upload-wins"); subsequent uploads append `file_attached` activity
 * rows but do not replace the primary FK. Both surface the same way here.
 */

function fmtSize(bytes: number | null | undefined): string {
    if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
    noticeId: number;
}

export function AttachmentList({ noticeId }: Props) {
    const activityQ = useQuery({
        queryKey: ["notice-activity", noticeId],
        queryFn: async () => {
            const { data } = await complianceApi.listActivity(noticeId);
            return data;
        },
    });

    const attachments = (activityQ.data ?? [])
        .filter((a) => a.type === "file_attached")
        .map((a) => ({
            id: a.id,
            filename:
                (a.details?.["filename"] as string | undefined) ??
                "attachment",
            size: a.details?.["size"] as number | undefined,
        }));

    return (
        <section
            aria-label="Attachments"
            className="bg-[#111113] border border-[#27272a] rounded-md p-5"
        >
            <h3 className="text-[11px] uppercase tracking-wider text-[#a1a1aa] font-medium mb-3">
                Attachments
            </h3>

            {activityQ.isLoading ? (
                <div className="h-10 rounded bg-[#18181b] animate-pulse" />
            ) : attachments.length === 0 ? (
                <p className="text-[13px] text-[#71717a]">
                    No attachments yet. Drop a PDF, JPG, or PNG below to attach
                    one.
                </p>
            ) : (
                <ul className="space-y-1.5">
                    {attachments.map((att) => (
                        <li
                            key={att.id}
                            className="flex items-center gap-2.5 px-3 py-2 rounded bg-[#18181b]/40 border border-[#27272a]"
                        >
                            <FiFile
                                className="w-3.5 h-3.5 text-[#3b82f6] shrink-0"
                                aria-hidden="true"
                            />
                            <span className="text-[13px] text-white truncate flex-1">
                                {att.filename}
                            </span>
                            <span className="text-[11px] text-[#71717a] tabular-nums shrink-0">
                                {fmtSize(att.size)}
                            </span>
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
}
