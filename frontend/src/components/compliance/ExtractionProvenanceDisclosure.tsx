"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FiChevronDown, FiCpu, FiInfo } from "react-icons/fi";

import { complianceApi, type ExtractionResponseDto } from "@/lib/api/compliance";

/**
 * Extraction provenance disclosure — Phase 17 D-28.
 *
 * Collapsed by default; on expand it fetches `GET /notices/{id}/extraction`
 * and lists the provider, model, average confidence, and each extracted
 * field with its post-validation confidence. Lives on the notice detail
 * page alongside the existing NoticeAISection (Phase 16 summary).
 *
 * Renders nothing when the notice has no extraction artefact yet —
 * keeps manually-created notices uncluttered.
 */

interface Props {
    noticeId: number;
    hasExtraction: boolean;
}

const STATUS_LABEL: Record<string, string> = {
    pending: "Pending",
    completed: "Extracted, awaiting acceptance",
    accepted: "Accepted",
    failed: "Failed",
    superseded: "Superseded",
};

function confidenceTone(c: number): string {
    if (c >= 0.85) return "text-emerald-700 dark:text-emerald-300";
    if (c >= 0.75) return "text-emerald-700 dark:text-emerald-300";
    if (c >= 0.55) return "text-amber-700 dark:text-amber-300";
    return "text-rose-700 dark:text-rose-300";
}

export function ExtractionProvenanceDisclosure({ noticeId, hasExtraction }: Props) {
    const [open, setOpen] = useState(false);

    const query = useQuery({
        queryKey: ["notice-extraction", noticeId],
        queryFn: async (): Promise<ExtractionResponseDto> => {
            const { data } = await complianceApi.getExtraction(noticeId);
            return data;
        },
        enabled: open && hasExtraction,
        staleTime: 60_000,
    });

    if (!hasExtraction) return null;

    return (
        <section className="rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)]">
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="w-full flex items-center justify-between gap-3 px-3 py-2.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)] rounded-md cursor-pointer transition-colors hover:bg-[var(--bg-hover)]"
                aria-expanded={open}
                aria-controls={`extraction-disclosure-${noticeId}`}
            >
                <div className="flex items-center gap-2 min-w-0">
                    <FiCpu className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
                    <div className="text-[13px] text-[var(--text-primary)] truncate">
                        AI extraction provenance
                    </div>
                </div>
                <FiChevronDown
                    className={`w-4 h-4 text-[var(--text-muted)] transition-transform ${open ? "rotate-180" : ""}`}
                />
            </button>

            {open ? (
                <div
                    id={`extraction-disclosure-${noticeId}`}
                    className="border-t border-[var(--border-default)] px-3 py-3 text-[12px]"
                >
                    {query.isPending ? (
                        <div className="text-[var(--text-muted)]">Loading provenance…</div>
                    ) : query.isError ? (
                        <div className="text-rose-600 dark:text-rose-400">
                            Could not load extraction provenance.
                        </div>
                    ) : query.data ? (
                        <ProvenanceBody data={query.data} />
                    ) : null}
                </div>
            ) : null}
        </section>
    );
}

function ProvenanceBody({ data }: { data: ExtractionResponseDto }) {
    const fields = data.envelope?.fields ?? {};
    const fieldEntries = Object.entries(fields);
    const status = data.extraction_status ?? "pending";

    return (
        <div className="space-y-3">
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-[12px]">
                <DetailRow label="Status" value={STATUS_LABEL[status] ?? status} />
                <DetailRow
                    label="Provider"
                    value={data.extracted_by_provider ?? "—"}
                    mono
                />
                <DetailRow
                    label="Average confidence"
                    value={
                        data.extraction_confidence !== null && data.extraction_confidence !== undefined
                            ? `${Math.round(Number(data.extraction_confidence) * 100)}%`
                            : "—"
                    }
                />
                <DetailRow
                    label="Extracted at"
                    value={
                        data.extracted_at
                            ? new Date(data.extracted_at).toLocaleString("en-IN")
                            : "—"
                    }
                />
            </dl>

            {fieldEntries.length ? (
                <div>
                    <div className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                        Fields ({fieldEntries.length})
                    </div>
                    <ul className="rounded border border-[var(--border-default)] divide-y divide-[var(--border-default)]">
                        {fieldEntries.map(([name, payload]) => (
                            <li
                                key={name}
                                className="flex items-center justify-between gap-3 px-2.5 py-1.5"
                            >
                                <div className="flex items-center gap-1.5 min-w-0">
                                    <span className="font-mono text-[11px] text-[var(--text-secondary)]">
                                        {name}
                                    </span>
                                    {payload.validation_failure ? (
                                        <FiInfo
                                            className="w-3 h-3 text-amber-600 dark:text-amber-400"
                                            title={payload.validation_failure}
                                            aria-label={payload.validation_failure}
                                        />
                                    ) : null}
                                </div>
                                <span className={`tabular-nums text-[12px] ${confidenceTone(payload.confidence)}`}>
                                    {Math.round(payload.confidence * 100)}%
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            ) : (
                <div className="text-[var(--text-muted)]">No fields returned.</div>
            )}
        </div>
    );
}

function DetailRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
    return (
        <>
            <dt className="text-[var(--text-muted)]">{label}</dt>
            <dd className={`text-[var(--text-primary)] ${mono ? "font-mono text-[11px]" : ""}`}>
                {value}
            </dd>
        </>
    );
}
