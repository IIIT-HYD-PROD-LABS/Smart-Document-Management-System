"use client";

import { useState } from "react";
import { FiChevronDown, FiChevronRight, FiX } from "react-icons/fi";
import type {
    Authority,
    NoticeStatus,
} from "@/types/compliance";
import { AUTHORITY_CONFIG } from "@/components/compliance/AuthorityBadge";
import { STATUS_CONFIG } from "@/components/compliance/StatusPill";

/**
 * NoticeFilterSidebar — UI-SPEC §1 dashboard filter panel.
 *
 * 280px wide collapsible panel with 5 filter dropdowns:
 *  1. Authority (single-select; "All authorities" clears)
 *  2. Status (single-select)
 *  3. Deadline from (date-string yyyy-mm-dd)
 *  4. Deadline to (date-string yyyy-mm-dd)
 *  5. GSTIN/PAN search (text)
 *
 * Per CONTEXT D-30 the sidebar is collapsible. State lifts to the parent
 * dashboard page so URL/query-string-state can be added later (RESEARCH
 * Pattern 7 hybrid recommendation).
 */
export interface NoticeFilters {
    authority: Authority | "";
    status: NoticeStatus | "";
    response_deadline_after: string;
    response_deadline_before: string;
    gstin_or_pan: string;
}

export const EMPTY_FILTERS: NoticeFilters = {
    authority: "",
    status: "",
    response_deadline_after: "",
    response_deadline_before: "",
    gstin_or_pan: "",
};

interface Props {
    filters: NoticeFilters;
    onChange: (next: NoticeFilters) => void;
    /** Optional: render the sidebar collapsed initially. */
    initialCollapsed?: boolean;
}

export function NoticeFilterSidebar({
    filters,
    onChange,
    initialCollapsed = false,
}: Props) {
    const [collapsed, setCollapsed] = useState(initialCollapsed);

    const set = (patch: Partial<NoticeFilters>) =>
        onChange({ ...filters, ...patch });

    const isDirty =
        filters.authority !== "" ||
        filters.status !== "" ||
        filters.response_deadline_after !== "" ||
        filters.response_deadline_before !== "" ||
        filters.gstin_or_pan !== "";

    if (collapsed) {
        return (
            <aside className="w-12 shrink-0">
                <button
                    type="button"
                    onClick={() => setCollapsed(false)}
                    className="
                        w-10 h-10 flex items-center justify-center
                        bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md
                        text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]
                        focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                        shadow-[var(--shadow-sm)]
                    "
                    aria-label="Open filters"
                >
                    <FiChevronRight className="w-4 h-4" />
                </button>
            </aside>
        );
    }

    return (
        <aside className="w-[280px] shrink-0">
            <div className="surface-card p-4">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-[12px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
                        Filters
                    </h3>
                    <button
                        type="button"
                        onClick={() => setCollapsed(true)}
                        className="text-[var(--text-subtle)] hover:text-[var(--text-primary)] p-1"
                        aria-label="Collapse filters"
                    >
                        <FiChevronDown className="w-3.5 h-3.5 rotate-90" />
                    </button>
                </div>

                {/* 1. Authority */}
                <div className="mb-4">
                    <label
                        htmlFor="filter-authority"
                        className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5 font-semibold"
                    >
                        Authority
                    </label>
                    <select
                        id="filter-authority"
                        value={filters.authority}
                        onChange={(e) =>
                            set({ authority: e.target.value as Authority | "" })
                        }
                        className="
                            w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md
                            px-2.5 py-2 text-[13.5px] text-[var(--text-primary)]
                            focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]
                        "
                    >
                        <option value="">All authorities</option>
                        {(Object.keys(AUTHORITY_CONFIG) as Authority[]).map((a) => (
                            <option key={a} value={a}>
                                {AUTHORITY_CONFIG[a].label}
                            </option>
                        ))}
                    </select>
                </div>

                {/* 2. Status */}
                <div className="mb-4">
                    <label
                        htmlFor="filter-status"
                        className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5 font-semibold"
                    >
                        Status
                    </label>
                    <select
                        id="filter-status"
                        value={filters.status}
                        onChange={(e) =>
                            set({ status: e.target.value as NoticeStatus | "" })
                        }
                        className="
                            w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md
                            px-2.5 py-2 text-[13.5px] text-[var(--text-primary)]
                            focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]
                        "
                    >
                        <option value="">All statuses</option>
                        {(Object.keys(STATUS_CONFIG) as NoticeStatus[]).map((s) => (
                            <option key={s} value={s}>
                                {STATUS_CONFIG[s].label}
                            </option>
                        ))}
                    </select>
                </div>

                {/* 3. Deadline from */}
                <div className="mb-4">
                    <label
                        htmlFor="filter-deadline-from"
                        className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5 font-semibold"
                    >
                        Deadline from
                    </label>
                    <input
                        id="filter-deadline-from"
                        type="date"
                        value={filters.response_deadline_after}
                        onChange={(e) =>
                            set({ response_deadline_after: e.target.value })
                        }
                        className="
                            w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md
                            px-2.5 py-2 text-[13.5px] text-[var(--text-primary)]
                            focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]
                        "
                    />
                </div>

                {/* 4. Deadline to */}
                <div className="mb-4">
                    <label
                        htmlFor="filter-deadline-to"
                        className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5 font-semibold"
                    >
                        Deadline to
                    </label>
                    <input
                        id="filter-deadline-to"
                        type="date"
                        value={filters.response_deadline_before}
                        onChange={(e) =>
                            set({ response_deadline_before: e.target.value })
                        }
                        className="
                            w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md
                            px-2.5 py-2 text-[13.5px] text-[var(--text-primary)]
                            focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]
                        "
                    />
                </div>

                {/* 5. GSTIN/PAN search */}
                <div className="mb-4">
                    <label
                        htmlFor="filter-gstin"
                        className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5 font-semibold"
                    >
                        GSTIN / PAN
                    </label>
                    <input
                        id="filter-gstin"
                        type="text"
                        value={filters.gstin_or_pan}
                        placeholder="e.g. 27AAAAA0000A1Z5"
                        onChange={(e) =>
                            set({ gstin_or_pan: e.target.value.toUpperCase() })
                        }
                        className="
                            w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md
                            px-2.5 py-2 text-[13.5px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)]
                            focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]
                        "
                    />
                </div>

                {isDirty && (
                    <button
                        type="button"
                        onClick={() => onChange(EMPTY_FILTERS)}
                        className="
                            inline-flex items-center gap-1 text-[12.5px] text-[var(--accent)] hover:text-[var(--accent-strong)]
                            focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded px-1
                        "
                    >
                        <FiX className="w-3 h-3" />
                        Reset filters
                    </button>
                )}
            </div>
        </aside>
    );
}
