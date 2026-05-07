"use client";

import { useState } from "react";
import { FiX, FiChevronDown, FiUserPlus, FiDownload, FiMoreHorizontal } from "react-icons/fi";
import toast from "react-hot-toast";
import { complianceApi } from "@/lib/api/compliance";
import type { NoticeStatus } from "@/types/compliance";
import { STATUS_CONFIG } from "@/components/compliance/StatusPill";

/**
 * BulkActionBar — UI-SPEC §4.
 *
 * Floating bottom-anchored bar that mounts when selectedIds.length > 0.
 * Slides up from below (200ms) on entrance.
 *
 * Slots:
 *  1. Selection count badge ("N selected")
 *  2. Update status dropdown (5 forward statuses)
 *  3. Assign (disabled in Phase 9)
 *  4. Export (disabled in Phase 9)
 *  5. "•••" overflow menu (placeholder)
 *  6. Clear selection
 *
 * Bulk update calls complianceApi.bulkUpdate which returns
 * { results: [{id, success, error}], summary: {ok, failed} } per RESEARCH
 * Pattern 8. Toast UX:
 *  - Full success → success toast "Updated N notice(s)"
 *  - All-fail     → error toast "All N updates failed"
 *  - Partial      → warning toast "Updated X of N. Y failed."
 * On partial failure, the parent's onUpdated callback is still invoked so
 * the table refetches and the now-stale rows clear their _pending.
 */
const FORWARD_STATUSES: NoticeStatus[] = [
    "received",
    "under_review",
    "response_drafted",
    "submitted",
    "resolved",
    "dismissed",
];

interface Props {
    selectedIds: number[];
    onClear: () => void;
    /** Called after a bulk action completes (success, partial, or all-fail). */
    onUpdated: (failedIds?: number[]) => void;
}

export function BulkActionBar({ selectedIds, onClear, onUpdated }: Props) {
    const [statusMenuOpen, setStatusMenuOpen] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    if (selectedIds.length === 0) return null;

    const handleBulkStatus = async (newStatus: NoticeStatus) => {
        setStatusMenuOpen(false);
        setSubmitting(true);
        try {
            const { data } = await complianceApi.bulkUpdate({
                notice_ids: selectedIds,
                new_status: newStatus,
            });
            const total = selectedIds.length;
            const ok = data.summary.ok;
            const failed = data.summary.failed;
            const failedIds = data.results
                .filter((r) => !r.success)
                .map((r) => r.id);

            if (failed === 0) {
                toast.success(
                    `Updated ${ok} notice${ok === 1 ? "" : "s"}`,
                    { duration: 4000 }
                );
            } else if (ok === 0) {
                toast.error(`All ${total} updates failed`, { duration: 6000 });
            } else {
                toast(`Updated ${ok} of ${total}. ${failed} failed.`, {
                    icon: "⚠",
                    duration: 6000,
                    style: {
                        background: "var(--warning-soft)",
                        color: "var(--warning)",
                        border: "1px solid var(--warning)",
                    },
                });
            }
            onUpdated(failedIds);
        } catch (err) {
            const msg =
                err instanceof Error ? err.message : "Bulk update request failed";
            toast.error(msg);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div
            className="
                fixed bottom-6 left-1/2 -translate-x-1/2 z-40
                flex items-center gap-2 px-3 py-2
                bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-md shadow-[var(--shadow-lg)]
                animate-in slide-in-from-bottom duration-200
            "
            role="toolbar"
            aria-label="Bulk actions"
        >
            <span
                className="
                    inline-flex items-center px-2.5 py-1 rounded
                    bg-[var(--accent-soft)] text-[var(--accent)] text-[12px] font-medium
                "
                aria-live="polite"
            >
                {selectedIds.length} selected
            </span>

            <div className="relative">
                <button
                    type="button"
                    onClick={() => setStatusMenuOpen((v) => !v)}
                    disabled={submitting}
                    className="
                        inline-flex items-center gap-1 px-3 py-1.5 rounded
                        bg-[var(--accent)] text-white text-[12px] font-medium
                        hover:bg-[var(--accent-strong)] disabled:opacity-60 disabled:cursor-not-allowed
                        focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                    "
                    aria-haspopup="menu"
                    aria-expanded={statusMenuOpen}
                >
                    {submitting ? `Updating ${selectedIds.length}…` : "Update status"}
                    <FiChevronDown className="w-3.5 h-3.5" />
                </button>
                {statusMenuOpen && !submitting && (
                    <div
                        role="menu"
                        className="
                            absolute bottom-full left-0 mb-2 w-56
                            bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-md shadow-[var(--shadow-lg)]
                            py-1
                        "
                    >
                        {FORWARD_STATUSES.map((s) => (
                            <button
                                key={s}
                                type="button"
                                role="menuitem"
                                onClick={() => handleBulkStatus(s)}
                                className="
                                    w-full text-left px-3 py-1.5 text-[13px] text-[var(--text-primary)]
                                    hover:bg-[var(--bg-hover)] flex items-center gap-2
                                "
                            >
                                <span
                                    className="w-2 h-2 rounded-full"
                                    style={{ backgroundColor: STATUS_CONFIG[s].color }}
                                />
                                Mark {STATUS_CONFIG[s].label}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <button
                type="button"
                disabled
                className="
                    inline-flex items-center gap-1 px-3 py-1.5 rounded
                    text-[12px] text-[var(--text-disabled)] bg-[var(--bg-muted)] border border-[var(--border-default)]
                    cursor-not-allowed
                "
                title="Coming after Phase 9"
            >
                <FiUserPlus className="w-3.5 h-3.5" />
                Assign
            </button>

            <button
                type="button"
                disabled
                className="
                    inline-flex items-center gap-1 px-3 py-1.5 rounded
                    text-[12px] text-[var(--text-disabled)] bg-[var(--bg-muted)] border border-[var(--border-default)]
                    cursor-not-allowed
                "
                title="Coming after Phase 9"
            >
                <FiDownload className="w-3.5 h-3.5" />
                Export
            </button>

            <button
                type="button"
                disabled
                className="
                    p-1.5 rounded text-[var(--text-disabled)] bg-[var(--bg-muted)] border border-[var(--border-default)]
                    cursor-not-allowed
                "
                title="More — coming after Phase 9"
                aria-label="More actions"
            >
                <FiMoreHorizontal className="w-3.5 h-3.5" />
            </button>

            <button
                type="button"
                onClick={onClear}
                className="
                    ml-1 inline-flex items-center gap-1 px-2 py-1.5 rounded
                    text-[12px] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]
                    focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                "
                aria-label="Clear selection"
            >
                <FiX className="w-3.5 h-3.5" />
                Clear
            </button>
        </div>
    );
}
