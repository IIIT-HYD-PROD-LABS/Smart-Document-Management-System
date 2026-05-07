"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { FiArrowLeft, FiSave } from "react-icons/fi";
import { useCurrentClient } from "@/stores/currentClientStore";
import { complianceApi, type CreateNoticePayload } from "@/lib/api/compliance";
import type { Authority } from "@/types/compliance";
import { AUTHORITY_CONFIG } from "@/components/compliance/AuthorityBadge";

/**
 * Notice creation form — UI-SPEC §3 + LIFE-03.
 *
 * Manual metadata entry per CONTEXT D-06 (AI extraction deferred to Phase 10).
 * Authority chosen first; the placeholder for `notice_number` swaps to the
 * regulator-specific format hint per CONTEXT D-07.
 */

const AUTHORITY_HINT: Record<Authority, string> = {
    GST: "DRC-01/2026/001",
    IT: "u/s 143(2)/2026",
    MCA: "MCA-FORM-XXX/2026",
    RBI: "RBI/DBR/2026/001",
    SEBI: "SEBI/HO/2026/001",
};

const todayIso = () => new Date().toISOString().slice(0, 10);

function toDecimal(s: string): string | undefined {
    const t = s.trim();
    if (t === "") return undefined;
    const n = Number(t);
    if (!Number.isFinite(n)) return undefined;
    return n.toFixed(2);
}

export default function NewNoticePage() {
    const router = useRouter();
    const queryClient = useQueryClient();
    const activeClientId = useCurrentClient((s) => s.activeClientId);

    const [authority, setAuthority] = useState<Authority>("GST");
    const [noticeNumber, setNoticeNumber] = useState("");
    const [receivedDate, setReceivedDate] = useState(todayIso);
    const [responseDeadline, setResponseDeadline] = useState("");
    const [taxDemand, setTaxDemand] = useState("");
    const [interest, setInterest] = useState("");
    const [penalty, setPenalty] = useState("");

    const totalLiability = useMemo(() => {
        const sum =
            (Number(taxDemand) || 0) +
            (Number(interest) || 0) +
            (Number(penalty) || 0);
        return sum > 0 ? sum.toFixed(2) : "";
    }, [taxDemand, interest, penalty]);

    const create = useMutation({
        mutationFn: async (payload: CreateNoticePayload) => {
            const { data } = await complianceApi.createNotice(payload);
            return data;
        },
        onSuccess: (notice) => {
            toast.success("Notice saved");
            queryClient.invalidateQueries({ queryKey: ["notices"] });
            queryClient.invalidateQueries({ queryKey: ["client-dashboard"] });
            router.push(`/dashboard/compliance/notices/${notice.id}`);
        },
        onError: (err) => {
            toast.error(
                err instanceof Error ? err.message : "Could not save notice"
            );
        },
    });

    const onSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (activeClientId === null) {
            toast.error("Select a client before creating a notice.");
            return;
        }
        if (!noticeNumber.trim()) {
            toast.error("Notice number is required.");
            return;
        }
        const payload: CreateNoticePayload = {
            client_id: activeClientId,
            notice_number: noticeNumber.trim(),
            authority,
            received_date: receivedDate,
            response_deadline: responseDeadline || null,
            tax_demand: toDecimal(taxDemand) ?? null,
            interest: toDecimal(interest) ?? null,
            penalty: toDecimal(penalty) ?? null,
            total_liability: toDecimal(totalLiability) ?? null,
        };
        create.mutate(payload);
    };

    if (activeClientId === null) {
        return (
            <div className="px-6 py-8 max-w-3xl mx-auto">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
                    Upload notice
                </h1>
                <p className="text-[13px] text-[var(--text-muted)]">
                    Select a client from the switcher first, then return here to
                    upload a notice.
                </p>
            </div>
        );
    }

    const inputClass =
        "w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded px-2.5 py-1.5 text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]";
    const labelClass = "block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5";

    return (
        <div className="px-6 py-8 max-w-3xl mx-auto">
            <Link
                href="/dashboard/compliance"
                className="inline-flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-4 focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded px-1"
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to dashboard
            </Link>

            <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
                Upload notice
            </h1>
            <p className="text-[13px] text-[var(--text-muted)] mb-6">
                Enter the notice metadata. Attach the source PDF or image after
                saving — the upload tools live on the notice detail page.
            </p>

            <form onSubmit={onSubmit} className="space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label htmlFor="authority" className={labelClass}>
                            Authority
                        </label>
                        <select
                            id="authority"
                            value={authority}
                            onChange={(e) =>
                                setAuthority(e.target.value as Authority)
                            }
                            className={inputClass}
                        >
                            {(Object.keys(AUTHORITY_CONFIG) as Authority[]).map(
                                (a) => (
                                    <option key={a} value={a}>
                                        {AUTHORITY_CONFIG[a].label}
                                    </option>
                                )
                            )}
                        </select>
                    </div>

                    <div>
                        <label htmlFor="notice_number" className={labelClass}>
                            Notice number
                        </label>
                        <input
                            id="notice_number"
                            type="text"
                            value={noticeNumber}
                            onChange={(e) => setNoticeNumber(e.target.value)}
                            placeholder={`e.g. ${AUTHORITY_HINT[authority]}`}
                            required
                            className={`${inputClass} font-mono`}
                        />
                    </div>

                    <div>
                        <label htmlFor="received_date" className={labelClass}>
                            Received date
                        </label>
                        <input
                            id="received_date"
                            type="date"
                            value={receivedDate}
                            onChange={(e) => setReceivedDate(e.target.value)}
                            required
                            className={inputClass}
                        />
                    </div>

                    <div>
                        <label htmlFor="response_deadline" className={labelClass}>
                            Response deadline
                        </label>
                        <input
                            id="response_deadline"
                            type="date"
                            value={responseDeadline}
                            onChange={(e) =>
                                setResponseDeadline(e.target.value)
                            }
                            className={inputClass}
                        />
                    </div>
                </div>

                <fieldset className="surface-card p-5">
                    <legend className="px-2 text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                        Financial fields
                    </legend>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-2">
                        <div>
                            <label htmlFor="tax_demand" className={labelClass}>
                                Tax demand
                            </label>
                            <input
                                id="tax_demand"
                                type="number"
                                step="0.01"
                                min="0"
                                value={taxDemand}
                                onChange={(e) => setTaxDemand(e.target.value)}
                                placeholder="0.00"
                                className={`${inputClass} tabular-nums`}
                            />
                        </div>
                        <div>
                            <label htmlFor="interest" className={labelClass}>
                                Interest
                            </label>
                            <input
                                id="interest"
                                type="number"
                                step="0.01"
                                min="0"
                                value={interest}
                                onChange={(e) => setInterest(e.target.value)}
                                placeholder="0.00"
                                className={`${inputClass} tabular-nums`}
                            />
                        </div>
                        <div>
                            <label htmlFor="penalty" className={labelClass}>
                                Penalty
                            </label>
                            <input
                                id="penalty"
                                type="number"
                                step="0.01"
                                min="0"
                                value={penalty}
                                onChange={(e) => setPenalty(e.target.value)}
                                placeholder="0.00"
                                className={`${inputClass} tabular-nums`}
                            />
                        </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-[var(--border-default)] flex items-center justify-between">
                        <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                            Total liability (auto)
                        </span>
                        <span className="text-base font-semibold text-[var(--text-primary)] tabular-nums">
                            {totalLiability
                                ? `₹${Number(totalLiability).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`
                                : "—"}
                        </span>
                    </div>
                </fieldset>

                <div className="flex items-center justify-end gap-2">
                    <Link
                        href="/dashboard/compliance"
                        className="px-3 py-1.5 rounded text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]"
                    >
                        Cancel
                    </Link>
                    <button
                        type="submit"
                        disabled={create.isPending || !noticeNumber.trim()}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[var(--accent)] text-white text-[12px] font-medium hover:bg-[var(--accent-strong)] disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]"
                    >
                        <FiSave className="w-3.5 h-3.5" />
                        {create.isPending ? "Saving…" : "Save notice"}
                    </button>
                </div>
            </form>
        </div>
    );
}
