"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
    FiArrowLeft,
    FiCalendar,
    FiAlertTriangle,
    FiInfo,
} from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { CalendarEntry, Authority } from "@/types/compliance";
import { AUTHORITY_CONFIG } from "@/components/compliance/AuthorityBadge";

const MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * Compliance calendar page — Phase 11 D-13.
 *
 * Month-grid view of statutory deadlines + gazetted holidays for the
 * selected year. Authority + category filters. Click a date cell to
 * see the deadline detail.
 *
 * The grid uses CSS grid, not a third-party calendar lib, to keep the
 * frontend bundle lean. Each cell is one day; deadlines render as small
 * authority-color pills inside the cell.
 */
export default function CalendarPage() {
    const today = new Date();
    const [year, setYear] = useState(today.getFullYear());
    const [month, setMonth] = useState(today.getMonth() + 1);
    const [authorityFilter, setAuthorityFilter] = useState<string>("");
    const [categoryFilter, setCategoryFilter] = useState<string>("");

    const entriesQ = useQuery({
        queryKey: ["calendar-entries", year, month, authorityFilter, categoryFilter],
        queryFn: async () => {
            const { data } = await complianceApi.listCalendarEntriesV2({
                year,
                month,
                authority: authorityFilter || undefined,
                category: categoryFilter || undefined,
            });
            return data;
        },
    });

    const entries = entriesQ.data ?? [];
    const entriesByDate = useMemo(() => {
        const m = new Map<string, CalendarEntry[]>();
        for (const e of entries) {
            const list = m.get(e.date) ?? [];
            list.push(e);
            m.set(e.date, list);
        }
        return m;
    }, [entries]);

    return (
        <div className="px-6 py-8 max-w-7xl mx-auto">
            <Link
                href="/dashboard/compliance"
                className="inline-flex items-center gap-1.5 text-[12px] text-[#a1a1aa] hover:text-white mb-4"
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to dashboard
            </Link>

            <header className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <FiCalendar className="w-5 h-5 text-[#3b82f6]" />
                    <h1 className="text-2xl font-semibold text-white tracking-tight">
                        Compliance calendar
                    </h1>
                </div>
                <p className="text-[13px] text-[#a1a1aa]">
                    Indian statutory filing deadlines + gazetted holidays for FY {year - 1}-{String(year).slice(2)}.
                </p>
            </header>

            {/* Filters */}
            <div className="mb-6 flex flex-wrap items-center gap-3">
                <YearMonthPicker
                    year={year} month={month}
                    onYear={setYear} onMonth={setMonth}
                />
                <AuthoritySelect value={authorityFilter} onChange={setAuthorityFilter} />
                <CategorySelect value={categoryFilter} onChange={setCategoryFilter} />
                <span className="ml-auto text-[12px] text-[#71717a] tabular-nums">
                    {entries.length} {entries.length === 1 ? "entry" : "entries"}
                </span>
            </div>

            <MonthGrid year={year} month={month} entriesByDate={entriesByDate} />

            <Legend />
        </div>
    );
}

function YearMonthPicker({
    year,
    month,
    onYear,
    onMonth,
}: {
    year: number;
    month: number;
    onYear: (y: number) => void;
    onMonth: (m: number) => void;
}) {
    const goPrev = () => {
        if (month === 1) {
            onYear(year - 1);
            onMonth(12);
        } else onMonth(month - 1);
    };
    const goNext = () => {
        if (month === 12) {
            onYear(year + 1);
            onMonth(1);
        } else onMonth(month + 1);
    };
    return (
        <div className="inline-flex items-center gap-2 px-3 h-9 rounded bg-[#0c0c0f] border border-[#1f1f23]">
            <button
                type="button"
                onClick={goPrev}
                className="text-[#a1a1aa] hover:text-white px-1"
                aria-label="Previous month"
            >
                ‹
            </button>
            <span className="text-[13px] text-white font-medium min-w-[80px] text-center">
                {MONTH_NAMES[month - 1]} {year}
            </span>
            <button
                type="button"
                onClick={goNext}
                className="text-[#a1a1aa] hover:text-white px-1"
                aria-label="Next month"
            >
                ›
            </button>
        </div>
    );
}

function AuthoritySelect({
    value,
    onChange,
}: {
    value: string;
    onChange: (v: string) => void;
}) {
    return (
        <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="
                h-9 px-3 rounded bg-[#0c0c0f] border border-[#1f1f23]
                text-[13px] text-white
                focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40
            "
            aria-label="Filter by authority"
        >
            <option value="">All authorities</option>
            <option value="GST">GST</option>
            <option value="IT">Income Tax</option>
            <option value="MCA">MCA</option>
            <option value="RBI">RBI</option>
            <option value="SEBI">SEBI</option>
        </select>
    );
}

function CategorySelect({
    value,
    onChange,
}: {
    value: string;
    onChange: (v: string) => void;
}) {
    return (
        <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="
                h-9 px-3 rounded bg-[#0c0c0f] border border-[#1f1f23]
                text-[13px] text-white
                focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40
            "
            aria-label="Filter by category"
        >
            <option value="">All entries</option>
            <option value="filing_deadline">Filing deadlines</option>
            <option value="holiday">Holidays</option>
            <option value="circular_extension">Circular extensions</option>
        </select>
    );
}

function MonthGrid({
    year,
    month,
    entriesByDate,
}: {
    year: number;
    month: number;
    entriesByDate: Map<string, CalendarEntry[]>;
}) {
    // Build the grid (Sun-Sat, padded for first week's offset)
    const firstOfMonth = new Date(year, month - 1, 1);
    const firstWeekday = firstOfMonth.getDay(); // 0 = Sunday
    const daysInMonth = new Date(year, month, 0).getDate();
    const cells: ({ day: number; iso: string } | null)[] = [];
    for (let i = 0; i < firstWeekday; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) {
        const iso = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
        cells.push({ day: d, iso });
    }
    while (cells.length % 7 !== 0) cells.push(null);

    const todayIso = new Date().toISOString().slice(0, 10);

    return (
        <div className="rounded border border-[#1f1f23] overflow-hidden">
            <div className="grid grid-cols-7 bg-[#0a0a0c] border-b border-[#1f1f23]">
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
                    <div
                        key={d}
                        className="px-2 py-2 text-[10px] uppercase tracking-wider text-[#71717a] text-center"
                    >
                        {d}
                    </div>
                ))}
            </div>
            <div className="grid grid-cols-7">
                {cells.map((c, idx) => {
                    if (c === null)
                        return (
                            <div
                                key={`empty-${idx}`}
                                className="bg-[#0a0a0c] min-h-[96px]"
                            />
                        );
                    const dateEntries = entriesByDate.get(c.iso) ?? [];
                    const isWeekend = idx % 7 === 0; // Sundays only
                    const isToday = c.iso === todayIso;
                    return (
                        <div
                            key={c.iso}
                            className={`
                                relative border-r border-b border-[#1f1f23] p-2 min-h-[96px]
                                ${isWeekend ? "bg-[#080809]" : "bg-[#0c0c0f]"}
                                ${isToday ? "ring-1 ring-inset ring-[#3b82f6]" : ""}
                            `}
                        >
                            <span
                                className={`
                                    text-[11px] font-mono tabular-nums
                                    ${isToday ? "text-[#3b82f6] font-semibold" : "text-[#a1a1aa]"}
                                `}
                            >
                                {c.day}
                            </span>
                            <div className="mt-1 space-y-1">
                                {dateEntries.slice(0, 3).map((e) => (
                                    <DayEntry key={e.id} entry={e} />
                                ))}
                                {dateEntries.length > 3 && (
                                    <span className="text-[10px] text-[#71717a]">
                                        +{dateEntries.length - 3} more
                                    </span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function DayEntry({ entry }: { entry: CalendarEntry }) {
    if (entry.category === "holiday") {
        return (
            <div
                className="
                    text-[10px] px-1.5 py-0.5 rounded
                    bg-[#71717a1a] text-[#a1a1aa]
                    truncate
                "
                title={entry.label}
            >
                {entry.label}
            </div>
        );
    }
    const auth = entry.authority as Authority | null;
    const color = auth ? AUTHORITY_CONFIG[auth]?.color ?? "#3b82f6" : "#3b82f6";
    return (
        <div
            className="text-[10px] px-1.5 py-0.5 rounded truncate font-medium"
            style={{ backgroundColor: `${color}1a`, color }}
            title={entry.label}
        >
            {entry.label}
        </div>
    );
}

function Legend() {
    return (
        <div className="mt-6 flex items-start gap-2 rounded border border-[#1f1f23] bg-[#0c0c0f] px-3 py-2">
            <FiInfo className="w-3.5 h-3.5 text-[#71717a] mt-0.5 shrink-0" />
            <p className="text-[11px] text-[#71717a] leading-relaxed">
                Indian statutory deadlines (GSTR, TDS, Advance Tax, ITR, MCA AOC-4 / MGT-7) are
                color-coded by authority. Gazetted holidays are gray. Today is highlighted in blue.
                If a deadline falls on a Sunday or gazetted holiday, the system auto-shifts to
                the next working day.
            </p>
        </div>
    );
}
