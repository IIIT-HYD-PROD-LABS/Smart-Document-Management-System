"use client";

import { format, parseISO } from "date-fns";
import type { ComplianceNotice } from "@/types/compliance";

/**
 * MetadataPanel — UI-SPEC §2 LEFT column metadata grid.
 *
 * 9 fields per CONTEXT D-05 (5 dates) + D-08 (4 financials) + legal_sections
 * chips per D-12. INR formatted with `tabular-nums`. Date format `dd MMM yyyy`
 * matches v1.0 admin pattern.
 */

function fmtDate(iso: string | null | undefined): string {
    if (!iso) return "—";
    try {
        return format(parseISO(iso), "dd MMM yyyy");
    } catch {
        return iso;
    }
}

function fmtInr(val: string | null | undefined): string {
    if (val === null || val === undefined || val === "") return "—";
    const n = Number(val);
    if (Number.isNaN(n)) return val;
    return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function Row({
    label,
    value,
    mono = false,
}: {
    label: string;
    value: React.ReactNode;
    mono?: boolean;
}) {
    return (
        <div>
            <dt className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                {label}
            </dt>
            <dd
                className={`text-[13px] text-[var(--text-primary)] ${mono ? "tabular-nums" : ""}`}
            >
                {value}
            </dd>
        </div>
    );
}

interface Props {
    notice: ComplianceNotice;
}

export function MetadataPanel({ notice }: Props) {
    return (
        <section
            aria-label="Notice metadata"
            className="surface-card p-5"
        >
            <h3 className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-medium mb-4">
                Metadata
            </h3>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
                <Row label="Received" value={fmtDate(notice.received_date)} />
                <Row
                    label="Response deadline"
                    value={fmtDate(notice.response_deadline)}
                />
                <Row label="Hearing date" value={fmtDate(notice.hearing_date)} />
                <Row
                    label="Compliance date"
                    value={fmtDate(notice.compliance_date)}
                />
                <Row
                    label="Appeal deadline"
                    value={fmtDate(notice.appeal_deadline)}
                />
                <Row label="Tax demand" value={fmtInr(notice.tax_demand)} mono />
                <Row label="Interest" value={fmtInr(notice.interest)} mono />
                <Row label="Penalty" value={fmtInr(notice.penalty)} mono />
                <Row
                    label="Total liability"
                    value={fmtInr(notice.total_liability)}
                    mono
                />
            </dl>

            {notice.legal_sections && notice.legal_sections.length > 0 && (
                <div className="mt-5 pt-4 border-t border-[var(--border-default)]">
                    <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-2">
                        Legal sections
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                        {notice.legal_sections.map((sec) => (
                            <span
                                key={sec}
                                className="inline-flex items-center px-2 py-1 text-[11px] rounded bg-[var(--bg-muted)] border border-[var(--border-default)] text-[var(--text-secondary)] font-mono"
                            >
                                {sec}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </section>
    );
}
