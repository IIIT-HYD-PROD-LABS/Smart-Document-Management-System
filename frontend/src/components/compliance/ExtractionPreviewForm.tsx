"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { FiAlertCircle, FiFileText, FiSave, FiUploadCloud, FiX } from "react-icons/fi";

import { useCurrentClient } from "@/stores/currentClientStore";
import { AUTHORITY_CONFIG } from "@/components/compliance/AuthorityBadge";
import { ExtractedFieldRow } from "@/components/compliance/ExtractedFieldRow";
import {
    complianceApi,
    type AcceptExtractionItem,
    type CreateNoticePayload,
    type ExtractPreviewResponse,
    type ExtractedFieldDto,
} from "@/lib/api/compliance";
import type { Authority } from "@/types/compliance";

/**
 * Upload-first notice creation form — Phase 17 D-26..D-28.
 *
 * Three states on one page:
 *   1. empty       : dropzone hero, form mostly hidden (only authority + notice_number visible)
 *   2. extracting  : indeterminate progress strip while extract-preview runs
 *   3. extracted   : form populated with extracted values + per-field confidence badges,
 *                    each row has accept/edit/discard, manual fallback link in the header
 *
 * The fallback "Fill manually" path is always one click away (link in the
 * upload zone) so tenants without AI credential or who prefer typing keep
 * the existing v1.0 flow.
 */

type Mode = "upload" | "manual";

interface FieldState {
    value: string;
    discarded: boolean;
}

const EMPTY_FIELD: FieldState = { value: "", discarded: false };

function fieldValue(extracted: ExtractedFieldDto | undefined): string {
    if (!extracted || extracted.value === null || extracted.value === undefined) return "";
    if (Array.isArray(extracted.value)) return extracted.value.join(", ");
    return String(extracted.value);
}

function decimalOrNull(s: string): string | null {
    const t = s.trim();
    if (!t) return null;
    const n = Number(t);
    return Number.isFinite(n) ? n.toFixed(2) : null;
}

function authorityFromExtracted(value: string | null): Authority {
    const allowed: Authority[] = ["GST", "IT", "MCA", "RBI", "SEBI"];
    if (value && (allowed as string[]).includes(value)) return value as Authority;
    return "GST";
}

export function ExtractionPreviewForm({
    activeClientId,
    initialMode = "upload",
}: {
    activeClientId: number;
    initialMode?: Mode;
}) {
    const router = useRouter();
    const queryClient = useQueryClient();

    const [mode, setMode] = useState<Mode>(initialMode);
    const [filename, setFilename] = useState<string | null>(null);
    const [fileObj, setFileObj] = useState<File | null>(null);
    const [envelope, setEnvelope] = useState<ExtractPreviewResponse | null>(null);
    const [credentialMissing, setCredentialMissing] = useState(false);

    const [authority, setAuthority] = useState<Authority>("GST");
    const [authorityEdited, setAuthorityEdited] = useState(false);
    const [fields, setFields] = useState<Record<string, FieldState>>({
        notice_number: EMPTY_FIELD,
        issued_date: EMPTY_FIELD,
        response_deadline: EMPTY_FIELD,
        tax_demand: EMPTY_FIELD,
        interest: EMPTY_FIELD,
        penalty: EMPTY_FIELD,
    });

    const extracted = envelope?.envelope.fields ?? {};
    const decisionLabel =
        envelope?.decision.action === "review_queue"
            ? "Queued for review"
            : envelope?.decision.action === "apply"
              ? "Ready to save"
              : null;

    const totalLiability = useMemo(() => {
        const t = Number(fields.tax_demand.value) || 0;
        const i = Number(fields.interest.value) || 0;
        const p = Number(fields.penalty.value) || 0;
        const sum = t + i + p;
        return sum > 0 ? sum.toFixed(2) : "";
    }, [fields.tax_demand.value, fields.interest.value, fields.penalty.value]);

    const extract = useMutation({
        mutationFn: async (file: File) => {
            const { data } = await complianceApi.extractPreview(file);
            return data;
        },
        onSuccess: (data) => {
            setEnvelope(data);
            setCredentialMissing(false);
            const f = data.envelope.fields;
            const ext_auth = f.authority?.value;
            const inferred = authorityFromExtracted(
                typeof ext_auth === "string" ? ext_auth : null,
            );
            setAuthority(inferred);
            setAuthorityEdited(false);
            setFields({
                notice_number: { value: fieldValue(f.notice_number), discarded: false },
                issued_date: { value: fieldValue(f.issued_date), discarded: false },
                response_deadline: { value: fieldValue(f.response_deadline), discarded: false },
                tax_demand: { value: fieldValue(f.tax_demand), discarded: false },
                interest: { value: fieldValue(f.interest), discarded: false },
                penalty: { value: fieldValue(f.penalty), discarded: false },
            });
            if (data.decision.action === "review_queue") {
                toast(
                    `Routing to review queue (${data.decision.reason ?? "low confidence"})`,
                    { icon: "ℹ️" },
                );
            } else if (data.decision.action === "apply") {
                toast.success(
                    `Extracted ${Object.keys(f).length} fields at ${Math.round(
                        data.decision.average_confidence * 100,
                    )}% confidence`,
                );
            }
        },
        onError: (err: unknown) => {
            const e = err as { response?: { status?: number; data?: { detail?: { code?: string } } } };
            if (e.response?.status === 412 && e.response?.data?.detail?.code === "no_ai_credential") {
                setCredentialMissing(true);
                toast.error("Connect an AI provider in settings to enable extraction");
                setMode("manual");
                return;
            }
            const msg = err instanceof Error ? err.message : "Extraction failed";
            toast.error(`${msg} — fill in manually`);
            setMode("manual");
        },
    });

    const onDrop = useCallback(
        (accepted: File[]) => {
            const file = accepted[0];
            if (!file) return;
            setFilename(file.name);
            setFileObj(file);
            extract.mutate(file);
        },
        [extract],
    );

    const dropzone = useDropzone({
        onDrop,
        accept: {
            "application/pdf": [],
            "image/jpeg": [],
            "image/png": [],
        },
        multiple: false,
        disabled: extract.isPending,
    });

    const save = useMutation({
        mutationFn: async () => {
            const payload: CreateNoticePayload = {
                client_id: activeClientId,
                notice_number: fields.notice_number.value.trim(),
                authority,
                received_date: fields.issued_date.value || new Date().toISOString().slice(0, 10),
                response_deadline: fields.response_deadline.value || null,
                tax_demand: decimalOrNull(fields.tax_demand.value),
                interest: decimalOrNull(fields.interest.value),
                penalty: decimalOrNull(fields.penalty.value),
                total_liability: decimalOrNull(totalLiability),
            };
            const { data: notice } = await complianceApi.createNotice(payload);

            // When the user dropped a file, persist it AND accept extraction
            // so the user-edited values are recorded against the canonical
            // notice with full per-field audit (D-17).
            if (fileObj) {
                try {
                    await complianceApi.uploadNoticeFile(notice.id, fileObj);
                } catch (uploadErr) {
                    toast.error("Notice saved, but file upload failed; re-upload from the detail page");
                }
            }
            if (envelope && fileObj) {
                const items: AcceptExtractionItem[] = [];
                const ACCEPT_FIELDS: Array<keyof typeof fields> = [
                    "notice_number",
                    "issued_date",
                    "response_deadline",
                    "tax_demand",
                    "interest",
                    "penalty",
                ];
                for (const key of ACCEPT_FIELDS) {
                    const state = fields[key];
                    if (state.discarded || !state.value.trim()) continue;
                    const ext = extracted[key];
                    if (!ext) continue;
                    items.push({
                        field: key,
                        value: state.value,
                        accept_as_is: String(ext.value ?? "") === state.value,
                    });
                }
                if (extracted.authority && !authorityEdited) {
                    items.push({
                        field: "authority",
                        value: authority,
                        accept_as_is: true,
                    });
                } else if (extracted.authority && authorityEdited) {
                    items.push({
                        field: "authority",
                        value: authority,
                        accept_as_is: false,
                    });
                }
                if (items.length) {
                    try {
                        await complianceApi.acceptExtraction(notice.id, items);
                    } catch (acceptErr) {
                        // Non-fatal: notice exists; user can revisit and accept later.
                        toast(
                            "Notice saved; AI fields will sync on the detail page shortly",
                            { icon: "ℹ️" },
                        );
                    }
                }
            }
            return notice;
        },
        onSuccess: (notice) => {
            toast.success("Notice saved");
            queryClient.invalidateQueries({ queryKey: ["notices"] });
            queryClient.invalidateQueries({ queryKey: ["client-dashboard"] });
            router.push(`/dashboard/compliance/notices/${notice.id}`);
        },
        onError: (err) => {
            toast.error(err instanceof Error ? err.message : "Could not save notice");
        },
    });

    const onSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!fields.notice_number.value.trim()) {
            toast.error("Notice number is required.");
            return;
        }
        save.mutate();
    };

    const setField = (key: keyof typeof fields, value: string) =>
        setFields((prev) => ({ ...prev, [key]: { ...prev[key], value, discarded: false } }));

    const discardField = (key: keyof typeof fields) =>
        setFields((prev) => ({ ...prev, [key]: { value: "", discarded: true } }));

    const restoreField = (key: keyof typeof fields) => {
        const ext = extracted[key];
        if (!ext) return;
        setFields((prev) => ({
            ...prev,
            [key]: { value: fieldValue(ext), discarded: false },
        }));
    };

    const inputClass =
        "w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded px-2.5 py-1.5 text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]";

    const dropzoneState = dropzone.isDragActive
        ? "border-[var(--accent)] bg-[var(--accent-soft)]"
        : "border-[var(--border-default)] bg-[var(--bg-elevated)] hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)]";

    const showEnvelopeUI = mode === "upload";

    return (
        <form onSubmit={onSubmit} className="space-y-5">
            {showEnvelopeUI ? (
                <div>
                    {envelope || filename ? (
                        <div className="flex items-center justify-between gap-3 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-2.5">
                            <div className="flex items-center gap-2 min-w-0">
                                <FiFileText className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
                                <div className="min-w-0">
                                    <div className="text-[13px] text-[var(--text-primary)] truncate">
                                        {filename}
                                    </div>
                                    {decisionLabel ? (
                                        <div className="text-[11px] text-[var(--text-muted)]">
                                            {decisionLabel} ·{" "}
                                            {envelope
                                                ? `${Math.round(
                                                      envelope.decision.average_confidence * 100,
                                                  )}% average confidence`
                                                : "Processing"}
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                            <button
                                type="button"
                                onClick={() => {
                                    setEnvelope(null);
                                    setFilename(null);
                                    setFileObj(null);
                                }}
                                className="inline-flex items-center gap-1 text-[12px] text-[var(--text-muted)] hover:text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded px-1 cursor-pointer"
                                aria-label="Replace file"
                            >
                                <FiX className="w-3.5 h-3.5" />
                                Replace
                            </button>
                        </div>
                    ) : (
                        <div
                            {...dropzone.getRootProps()}
                            className={`rounded-md border-2 border-dashed p-10 text-center cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)] ${dropzoneState} ${
                                extract.isPending ? "opacity-70 cursor-wait" : ""
                            }`}
                            role="button"
                            aria-label="Upload notice for AI extraction"
                        >
                            <input {...dropzone.getInputProps()} />
                            <FiUploadCloud className="w-7 h-7 text-[var(--text-muted)] mx-auto mb-3" />
                            <div className="text-[14px] text-[var(--text-primary)] mb-1">
                                Drop a notice PDF, JPG, or PNG to auto-fill the form
                            </div>
                            <div className="text-[12px] text-[var(--text-muted)] mb-3">
                                Uses your connected AI provider. PDF/JPG/PNG only.
                            </div>
                            <button
                                type="button"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setMode("manual");
                                }}
                                className="text-[12px] text-[var(--accent)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded px-1 cursor-pointer"
                            >
                                Fill manually instead
                            </button>
                        </div>
                    )}
                    {extract.isPending ? (
                        <div className="mt-2 h-0.5 w-full overflow-hidden rounded bg-[var(--bg-hover)]">
                            <div className="h-full w-1/3 animate-pulse bg-[var(--accent)]" />
                        </div>
                    ) : null}
                </div>
            ) : null}

            {credentialMissing ? (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-[12px] text-amber-800 dark:text-amber-200 flex items-start gap-2">
                    <FiAlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
                    <div>
                        Connect an AI provider in{" "}
                        <Link
                            href="/dashboard/settings/ai-credentials"
                            className="underline hover:no-underline"
                        >
                            settings
                        </Link>{" "}
                        to enable extraction. You can still upload and fill the form
                        manually.
                    </div>
                </div>
            ) : null}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <ExtractedFieldRow
                    label="Authority"
                    inputId="authority"
                    extracted={extracted.authority}
                    edited={
                        authorityEdited ||
                        (extracted.authority?.value !== undefined &&
                            String(extracted.authority.value) !== authority)
                    }
                >
                    <select
                        id="authority"
                        value={authority}
                        onChange={(e) => {
                            setAuthority(e.target.value as Authority);
                            setAuthorityEdited(true);
                        }}
                        className={inputClass}
                    >
                        {(Object.keys(AUTHORITY_CONFIG) as Authority[]).map((a) => (
                            <option key={a} value={a}>
                                {AUTHORITY_CONFIG[a].label}
                            </option>
                        ))}
                    </select>
                </ExtractedFieldRow>

                <ExtractedFieldRow
                    label="Notice number"
                    inputId="notice_number"
                    extracted={extracted.notice_number}
                    edited={
                        extracted.notice_number !== undefined &&
                        String(extracted.notice_number.value ?? "") !==
                            fields.notice_number.value
                    }
                    discarded={fields.notice_number.discarded}
                    onDiscard={() => discardField("notice_number")}
                    onRestore={() => restoreField("notice_number")}
                >
                    <input
                        id="notice_number"
                        type="text"
                        value={fields.notice_number.value}
                        onChange={(e) => setField("notice_number", e.target.value)}
                        required
                        className={`${inputClass} font-mono`}
                        placeholder="DRC-01/2026/4456"
                    />
                </ExtractedFieldRow>

                <ExtractedFieldRow
                    label="Received / Issued date"
                    inputId="issued_date"
                    extracted={extracted.issued_date}
                    edited={
                        extracted.issued_date !== undefined &&
                        String(extracted.issued_date.value ?? "") !== fields.issued_date.value
                    }
                    discarded={fields.issued_date.discarded}
                    onDiscard={() => discardField("issued_date")}
                    onRestore={() => restoreField("issued_date")}
                >
                    <input
                        id="issued_date"
                        type="date"
                        value={fields.issued_date.value}
                        onChange={(e) => setField("issued_date", e.target.value)}
                        className={inputClass}
                    />
                </ExtractedFieldRow>

                <ExtractedFieldRow
                    label="Response deadline"
                    inputId="response_deadline"
                    extracted={extracted.response_deadline}
                    edited={
                        extracted.response_deadline !== undefined &&
                        String(extracted.response_deadline.value ?? "") !==
                            fields.response_deadline.value
                    }
                    discarded={fields.response_deadline.discarded}
                    onDiscard={() => discardField("response_deadline")}
                    onRestore={() => restoreField("response_deadline")}
                >
                    <input
                        id="response_deadline"
                        type="date"
                        value={fields.response_deadline.value}
                        onChange={(e) => setField("response_deadline", e.target.value)}
                        className={inputClass}
                    />
                </ExtractedFieldRow>
            </div>

            <fieldset className="surface-card p-5">
                <legend className="px-2 text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                    Financial fields
                </legend>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-2">
                    {(["tax_demand", "interest", "penalty"] as const).map((key) => (
                        <ExtractedFieldRow
                            key={key}
                            label={key === "tax_demand" ? "Tax demand" : key === "interest" ? "Interest" : "Penalty"}
                            inputId={key}
                            extracted={extracted[key]}
                            edited={
                                extracted[key] !== undefined &&
                                String(extracted[key]?.value ?? "") !== fields[key].value
                            }
                            discarded={fields[key].discarded}
                            onDiscard={() => discardField(key)}
                            onRestore={() => restoreField(key)}
                        >
                            <input
                                id={key}
                                type="number"
                                step="0.01"
                                min="0"
                                value={fields[key].value}
                                onChange={(e) => setField(key, e.target.value)}
                                placeholder="0.00"
                                className={`${inputClass} tabular-nums`}
                            />
                        </ExtractedFieldRow>
                    ))}
                </div>

                <div className="mt-4 pt-4 border-t border-[var(--border-default)] flex items-center justify-between">
                    <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                        Total liability (auto)
                    </span>
                    <span className="text-base font-semibold text-[var(--text-primary)] tabular-nums">
                        {totalLiability
                            ? `₹${Number(totalLiability).toLocaleString("en-IN", {
                                  maximumFractionDigits: 2,
                              })}`
                            : "—"}
                    </span>
                </div>
            </fieldset>

            <div className="flex items-center justify-end gap-2">
                <Link
                    href="/dashboard/compliance"
                    className="px-3 py-1.5 rounded text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] cursor-pointer"
                >
                    Cancel
                </Link>
                <button
                    type="submit"
                    disabled={save.isPending || !fields.notice_number.value.trim()}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[var(--accent)] text-white text-[12px] font-medium hover:bg-[var(--accent-strong)] disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] cursor-pointer transition-colors"
                >
                    <FiSave className="w-3.5 h-3.5" />
                    {save.isPending ? "Saving…" : "Save notice"}
                </button>
            </div>
        </form>
    );
}
