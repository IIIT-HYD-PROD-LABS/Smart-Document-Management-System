"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { FiLink2 } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { Authority, NoticeStatus } from "@/types/compliance";
import { AuthorityBadge } from "@/components/compliance/AuthorityBadge";
import { StatusPill } from "@/components/compliance/StatusPill";

/**
 * NoticeChainTree — UI-SPEC §11 recursive notice chain.
 *
 * Backend returns a flat list from a recursive CTE walk of
 * `parent_notice_id`. Each entry carries its `depth` so we render with
 * incremental left padding (16px per level). The current notice is
 * highlighted with an accent left-border per UI-SPEC.
 */

interface ChainEntry {
    id: number;
    notice_number: string;
    authority: Authority;
    status: NoticeStatus;
    depth: number;
    parent_notice_id: number | null;
    received_date: string | null;
}

interface ChainResponse {
    items?: ChainEntry[];
}

function fmtDate(iso: string | null): string {
    if (!iso) return "";
    try {
        return format(parseISO(iso), "dd MMM yyyy");
    } catch {
        return "";
    }
}

interface Props {
    noticeId: number;
}

export function NoticeChainTree({ noticeId }: Props) {
    const chainQ = useQuery({
        queryKey: ["notice-chain", noticeId],
        queryFn: async () => {
            const res = await complianceApi.getChain(noticeId, 10);
            const data = res.data as ChainResponse | ChainEntry[];
            const items = Array.isArray(data) ? data : (data.items ?? []);
            return items;
        },
    });

    const items = chainQ.data ?? [];

    return (
        <section
            aria-label="Linked notices"
            className="bg-[#111113] border border-[#27272a] rounded-md p-5"
        >
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-[11px] uppercase tracking-wider text-[#a1a1aa] font-medium">
                    Linked notices
                </h3>
                <FiLink2
                    className="w-3.5 h-3.5 text-[#52525b]"
                    aria-hidden="true"
                />
            </div>

            {chainQ.isLoading ? (
                <div className="h-12 rounded bg-[#18181b] animate-pulse" />
            ) : items.length <= 1 ? (
                <div className="rounded bg-[#18181b]/40 border border-[#27272a] p-4 text-center">
                    <h4 className="text-sm font-semibold text-white mb-1">
                        No linked notices
                    </h4>
                    <p className="text-[12px] text-[#71717a]">
                        Link this notice to a parent (e.g., the original Show
                        Cause) using the link icon above.
                    </p>
                </div>
            ) : (
                <ul role="tree" className="space-y-1.5">
                    {items.map((node) => {
                        const isCurrent = node.id === noticeId;
                        return (
                            <li
                                key={node.id}
                                role="treeitem"
                                aria-current={isCurrent ? "page" : undefined}
                                style={{ paddingLeft: `${node.depth * 16}px` }}
                            >
                                <Link
                                    href={`/dashboard/compliance/notices/${node.id}`}
                                    className={`flex items-center gap-2 px-2 py-1.5 rounded text-[13px] transition-colors hover:bg-[#18181b]/50 focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 ${
                                        isCurrent
                                            ? "border-l-[3px] border-[#3b82f6] bg-[#3b82f6]/5"
                                            : "border-l-[3px] border-transparent"
                                    }`}
                                >
                                    <span
                                        className={`font-mono ${
                                            isCurrent
                                                ? "text-white"
                                                : "text-[#a1a1aa]"
                                        }`}
                                    >
                                        {node.notice_number}
                                    </span>
                                    <AuthorityBadge authority={node.authority} />
                                    <StatusPill status={node.status} />
                                    <span className="ml-auto text-[11px] text-[#52525b] tabular-nums">
                                        {fmtDate(node.received_date)}
                                    </span>
                                </Link>
                            </li>
                        );
                    })}
                </ul>
            )}
        </section>
    );
}
