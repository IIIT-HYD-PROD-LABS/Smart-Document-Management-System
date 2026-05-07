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
                    <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
                        Notice
                    </span>
                ),
                cell: ({ row }) => (
                    <Link
                        href={`/dashboard/compliance/notices/${row.original.id}`}
                        className="text-[13.5px] font-medium text-[var(--text-primary)] hover:text-[var(--accent)] focus:outline-none focus:underline"
                    >
                        {row.original.notice_number}
                    </Link>
                ),
            },
            {
                accessorKey: "authority",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
                        Authority
                    </span>
                ),
                cell: ({ row }) => <AuthorityBadge authority={row.original.authority} />,
            },
            {
                accessorKey: "status",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
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
                    <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
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
                    <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
                        Deadline
                    </span>
                ),
                cell: ({ row }) => (
                    <span className="text-[13px] text-[var(--text-secondary)] tabular-nums">
                        {formatDate(row.original.response_deadline)}
                    </span>
                ),
            },
            {
                accessorKey: "received_date",
                header: () => (
                    <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
                        Received
                    </span>
                ),
                cell: ({ row }) => (
                    <span className="text-[13px] text-[var(--text-muted)] tabular-nums">
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
            <div className="bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-lg overflow-hidden shadow-[var(--shadow-sm)]">
                <div className="px-4 py-3 border-b border-[var(--border-default)] flex items-center gap-4">
                    <div className="w-3.5 h-3.5 bg-[var(--bg-hover)] rounded animate-pulse" />
                    <div className="h-3 w-24 bg-[var(--bg-hover)] rounded animate-pulse" />
                </div>
                {[0, 1, 2, 3, 4].map((i) => (
                    <div
                        key={i}
                        className="px-4 py-3 border-b border-[var(--border-default)] last:border-0 flex items-center gap-4"
                    >
                        <div className="w-3.5 h-3.5 bg-[var(--bg-hover)] rounded animate-pulse" />
                        <div className="h-3 w-32 bg-[var(--bg-hover)] rounded animate-pulse" />
                        <div className="h-3 w-20 bg-[var(--bg-hover)] rounded animate-pulse" />
                        <div className="h-3 w-24 bg-[var(--bg-hover)] rounded animate-pulse" />
                        <div className="h-3 w-12 bg-[var(--bg-hover)] rounded animate-pulse" />
                        <div className="h-3 w-20 bg-[var(--bg-hover)] rounded animate-pulse ml-auto" />
                    </div>
                ))}
            </div>
        );
    }

    if (rows.length === 0) {
        return (
            <div className="surface-card p-10 text-center">
                <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-1.5">
                    No notices match these filters
                </h3>
                <p className="text-[13px] text-[var(--text-muted)]">
                    Try clearing one or more filters, or reset all filters.
                </p>
            </div>
        );
    }

    return (
        <div className="surface-card overflow-x-auto p-0">
            <table className="w-full" role="table">
                <thead className="bg-[var(--bg-muted)]">
                    {table.getHeaderGroups().map((hg) => (
                        <tr key={hg.id} className="border-b border-[var(--border-default)]">
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
                            ? "bg-[var(--danger-soft)]"
                            : pending
                              ? "bg-[var(--warning-soft)]"
                              : row.getIsSelected()
                                ? "bg-[var(--accent-soft)]"
                                : "hover:bg-[var(--bg-hover)]";
                        return (
                            <tr
                                key={row.id}
                                className={`border-b border-[var(--border-subtle)] last:border-0 transition-colors ${rowClass}`}
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
                    className="px-4 py-2 border-t border-[var(--border-default)] bg-[var(--danger-soft)] text-[12px] text-[var(--danger)]"
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
