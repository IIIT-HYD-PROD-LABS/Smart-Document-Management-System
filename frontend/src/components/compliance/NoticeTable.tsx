"use client";

import { useMemo } from "react";
import Link from "next/link";
import { format, parseISO } from "date-fns";
import {
    useReactTable,
    getCoreRowModel,
    flexRender,
    type ColumnDef,
    type RowSelectionState,
} from "@tanstack/react-table";
import type { ComplianceNotice } from "@/types/compliance";
import { StatusPill } from "@/components/compliance/StatusPill";
import { AuthorityBadge } from "@/components/compliance/AuthorityBadge";
import { RiskTierDot } from "@/components/compliance/RiskTierDot";

/**
 * Per-row UX extensions for partial-failure feedback during bulk actions
 * (UI-SPEC §4 Bulk Action Bar / RESEARCH Pattern 8).
 *
 *  _pending — true while the row's mutation is in flight (renders amber tint)
 *  _error   — non-null sets a red row-tint and exposes a tooltip-able message
 */
export interface NoticeRow extends ComplianceNotice {
    _pending?: boolean;
    _error?: string | null;
}

interface Props {
    rows: NoticeRow[];
    isLoading: boolean;
    rowSelection: RowSelectionState;
    onRowSelectionChange: (
        updaterOrValue:
            | RowSelectionState
            | ((old: RowSelectionState) => RowSelectionState)
    ) => void;
}

/** Compute overdue from response_deadline + current date. */
function isOverdue(notice: ComplianceNotice): boolean {
    if (!notice.response_deadline) return false;
    if (
        notice.status === "resolved" ||
        notice.status === "dismissed" ||
        notice.status === "submitted"
    ) {
        return false;
    }
    try {
        return parseISO(notice.response_deadline).getTime() < Date.now();
    } catch {
        return false;
    }
}

function formatDate(iso: string | null): string {
    if (!iso) return "—";
    try {
        return format(parseISO(iso), "dd MMM yyyy");
    } catch {
        return iso;
    }
}

export function NoticeTable({
    rows,
    isLoading,
    rowSelection,
    onRowSelectionChange,
}: Props) {
    const columns = useMemo<ColumnDef<NoticeRow>[]>(
        () => [
            {
                id: "select",
                header: ({ table }) => {
                    const allSelected = table.getIsAllPageRowsSelected();
                    const someSelected = table.getIsSomePageRowsSelected();
                    return (
                        <input
                            type="checkbox"
                            className="accent-[#3b82f6] w-3.5 h-3.5"
                            checked={allSelected}
                            ref={(el) => {
                                if (el) el.indeterminate = !allSelected && someSelected;
                            }}
                            onChange={(e) =>
                                table.toggleAllPageRowsSelected(e.target.checked)
                            }
                            aria-label="Select all rows"
                        />
                    );
                },
                cell: ({ row }) => (
                    <input
                        type="checkbox"
                        className="accent-[#3b82f6] w-3.5 h-3.5"
                        checked={row.getIsSelected()}
                        onChange={(e) => row.toggleSelected(e.target.checked)}
                        aria-label={`Select notice ${row.original.notice_number}`}
                    />
                ),
                size: 32,
            },
            {
                accessorKey: "notice_number",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[#a1a1aa]">
                        Notice
                    </span>
                ),
                cell: ({ row }) => (
                    <Link
                        href={`/dashboard/compliance/notices/${row.original.id}`}
                        className="text-[13px] text-white hover:text-[#3b82f6] focus:outline-none focus:underline"
                    >
                        {row.original.notice_number}
                    </Link>
                ),
            },
            {
                accessorKey: "authority",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[#a1a1aa]">
                        Authority
                    </span>
                ),
                cell: ({ row }) => <AuthorityBadge authority={row.original.authority} />,
            },
            {
                accessorKey: "status",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[#a1a1aa]">
                        Status
                    </span>
                ),
                cell: ({ row }) => (
                    <StatusPill
                        status={row.original.status}
                        overdue={isOverdue(row.original)}
                    />
                ),
            },
            {
                id: "risk",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[#a1a1aa]">
                        Risk
                    </span>
                ),
                cell: ({ row }) => (
                    <RiskTierDot tier={row.original.risk_tier} showLabel />
                ),
                size: 100,
            },
            {
                accessorKey: "response_deadline",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[#a1a1aa]">
                        Deadline
                    </span>
                ),
                cell: ({ row }) => (
                    <span className="text-[13px] text-[#a1a1aa] tabular-nums">
                        {formatDate(row.original.response_deadline)}
                    </span>
                ),
            },
            {
                accessorKey: "received_date",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[#a1a1aa]">
                        Received
                    </span>
                ),
                cell: ({ row }) => (
                    <span className="text-[13px] text-[#71717a] tabular-nums">
                        {formatDate(row.original.received_date)}
                    </span>
                ),
            },
        ],
        []
    );

    const table = useReactTable({
        data: rows,
        columns,
        state: { rowSelection },
        enableRowSelection: true,
        onRowSelectionChange,
        getRowId: (row) => String(row.id),
        getCoreRowModel: getCoreRowModel(),
    });

    if (isLoading) {
        return (
            <div className="bg-[#111113] border border-[#27272a] rounded-md overflow-hidden">
                <div className="px-4 py-3 border-b border-[#27272a] flex items-center gap-4">
                    <div className="w-3.5 h-3.5 bg-[#18181b] rounded animate-pulse" />
                    <div className="h-3 w-24 bg-[#18181b] rounded animate-pulse" />
                </div>
                {[0, 1, 2, 3, 4].map((i) => (
                    <div
                        key={i}
                        className="px-4 py-3 border-b border-[#27272a] last:border-0 flex items-center gap-4"
                    >
                        <div className="w-3.5 h-3.5 bg-[#18181b] rounded animate-pulse" />
                        <div className="h-3 w-32 bg-[#18181b] rounded animate-pulse" />
                        <div className="h-3 w-20 bg-[#18181b] rounded animate-pulse" />
                        <div className="h-3 w-24 bg-[#18181b] rounded animate-pulse" />
                        <div className="h-3 w-12 bg-[#18181b] rounded animate-pulse" />
                        <div className="h-3 w-20 bg-[#18181b] rounded animate-pulse ml-auto" />
                    </div>
                ))}
            </div>
        );
    }

    if (rows.length === 0) {
        return (
            <div className="bg-[#111113] border border-[#27272a] rounded-md p-8 text-center">
                <h3 className="text-sm font-semibold text-white mb-1">
                    No notices match these filters
                </h3>
                <p className="text-[13px] text-[#71717a]">
                    Try clearing one or more filters, or reset all filters.
                </p>
            </div>
        );
    }

    return (
        <div className="bg-[#111113] border border-[#27272a] rounded-md overflow-x-auto">
            <table className="w-full" role="table">
                <thead>
                    {table.getHeaderGroups().map((hg) => (
                        <tr key={hg.id} className="border-b border-[#27272a]">
                            {hg.headers.map((h) => (
                                <th
                                    key={h.id}
                                    className="text-left px-4 py-3 font-medium"
                                    style={
                                        h.column.columnDef.size
                                            ? { width: h.column.columnDef.size }
                                            : undefined
                                    }
                                >
                                    {h.isPlaceholder
                                        ? null
                                        : flexRender(
                                              h.column.columnDef.header,
                                              h.getContext()
                                          )}
                                </th>
                            ))}
                        </tr>
                    ))}
                </thead>
                <tbody>
                    {table.getRowModel().rows.map((row) => {
                        const pending = row.original._pending;
                        const error = row.original._error;
                        const rowClass = error
                            ? "bg-[#ef4444]/5 hover:bg-[#ef4444]/10"
                            : pending
                              ? "bg-[#f59e0b]/5"
                              : row.getIsSelected()
                                ? "bg-[#3b82f6]/5"
                                : "hover:bg-[#18181b]/50";
                        return (
                            <tr
                                key={row.id}
                                className={`border-b border-[#27272a] last:border-0 transition-colors ${rowClass}`}
                                title={error ?? undefined}
                            >
                                {row.getVisibleCells().map((cell) => (
                                    <td key={cell.id} className="px-4 py-3 align-middle">
                                        {flexRender(
                                            cell.column.columnDef.cell,
                                            cell.getContext()
                                        )}
                                    </td>
                                ))}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
            {/* Per-row error indicators (bottom marker, complements row-tint above) */}
            {rows.some((r) => r._error) && (
                <div
                    className="px-4 py-2 border-t border-[#ef4444]/20 bg-[#ef4444]/5 text-[12px] text-[#ef4444]"
                    role="alert"
                >
                    {rows.filter((r) => r._error).length} row
                    {rows.filter((r) => r._error).length === 1 ? "" : "s"} failed —
                    hover the row to see the reason.
                </div>
            )}
        </div>
    );
}
