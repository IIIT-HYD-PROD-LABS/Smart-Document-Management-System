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
                        bg-[#111113] border border-[#27272a] rounded-md
                        text-[#a1a1aa] hover:text-white hover:bg-[#18181b]
                        focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40
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
            <div className="bg-[#111113] border border-[#27272a] rounded-md p-4">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-[11px] uppercase tracking-wider text-[#a1a1aa] font-medium">
                        Filters
                    </h3>
                    <button
                        type="button"
                        onClick={() => setCollapsed(true)}
                        className="text-[#71717a] hover:text-white p-1"
                        aria-label="Collapse filters"
                    >
                        <FiChevronDown className="w-3.5 h-3.5 rotate-90" />
                    </button>
                </div>

                {/* 1. Authority */}
                <div className="mb-4">
                    <label
                        htmlFor="filter-authority"
                        className="block text-[11px] uppercase tracking-wider text-[#71717a] mb-1.5"
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
                            w-full bg-[#18181b] border border-[#27272a] rounded
                            px-2.5 py-1.5 text-[13px] text-white
                            focus:outline-none focus:border-[#3f3f46] focus:ring-1 focus:ring-[#3b82f6]/40
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
                        className="block text-[11px] uppercase tracking-wider text-[#71717a] mb-1.5"
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
                            w-full bg-[#18181b] border border-[#27272a] rounded
                            px-2.5 py-1.5 text-[13px] text-white
                            focus:outline-none focus:border-[#3f3f46] focus:ring-1 focus:ring-[#3b82f6]/40
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
                        className="block text-[11px] uppercase tracking-wider text-[#71717a] mb-1.5"
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
                            w-full bg-[#18181b] border border-[#27272a] rounded
                            px-2.5 py-1.5 text-[13px] text-white
                            focus:outline-none focus:border-[#3f3f46] focus:ring-1 focus:ring-[#3b82f6]/40
                        "
                    />
                </div>

                {/* 4. Deadline to */}
                <div className="mb-4">
                    <label
                        htmlFor="filter-deadline-to"
                        className="block text-[11px] uppercase tracking-wider text-[#71717a] mb-1.5"
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
                            w-full bg-[#18181b] border border-[#27272a] rounded
                            px-2.5 py-1.5 text-[13px] text-white
                            focus:outline-none focus:border-[#3f3f46] focus:ring-1 focus:ring-[#3b82f6]/40
                        "
                    />
                </div>

                {/* 5. GSTIN/PAN search */}
                <div className="mb-4">
                    <label
                        htmlFor="filter-gstin"
                        className="block text-[11px] uppercase tracking-wider text-[#71717a] mb-1.5"
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
                            w-full bg-[#18181b] border border-[#27272a] rounded
                            px-2.5 py-1.5 text-[13px] text-white placeholder:text-[#52525b]
                            focus:outline-none focus:border-[#3f3f46] focus:ring-1 focus:ring-[#3b82f6]/40
                        "
                    />
                </div>

                {isDirty && (
                    <button
                        type="button"
                        onClick={() => onChange(EMPTY_FILTERS)}
                        className="
                            inline-flex items-center gap-1 text-[12px] text-[#3b82f6] hover:text-[#60a5fa]
                            focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 rounded px-1
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
