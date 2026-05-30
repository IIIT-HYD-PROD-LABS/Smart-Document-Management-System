"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import toast from "react-hot-toast";
import { FiAlertTriangle, FiCpu, FiSettings } from "react-icons/fi";

import { aiApi } from "@/lib/api/ai";
import type {
    AIActionItem,
    InvoiceActionsResponse,
    InvoiceSummaryResponse,
    InvoiceTimingResponse,
} from "@/types/ai";

interface Props {
    billId: number;
}

const URGENCY_TINT: Record<AIActionItem["urgency"], string> = {
    high: "var(--danger)",
    medium: "var(--warning)",
    low: "var(--text-muted)",
};

/**
 * AI panel on the vendor invoice detail page. Three on-demand
 * tasks: summary, suggested actions, payment-timing prediction.
 * Same connect-first UX as NoticeAISection.
 */
export default function InvoiceAISection({ billId }: Props) {
    const { data: cred, isLoading: credLoading } = useQuery({
        queryKey: ["ai-credential"],
        queryFn: () => aiApi.getCredential().then((r) => r.data),
        staleTime: 30_000,
    });

    const [summary, setSummary] = useState<InvoiceSummaryResponse | null>(null);
    const [actions, setActions] = useState<InvoiceActionsResponse | null>(null);
    const [timing, setTiming] = useState<InvoiceTimingResponse | null>(null);
    const [busy, setBusy] = useState<
        "summary" | "actions" | "timing" | null
    >(null);

    const handleAIError = (e: unknown) => {
        const status = (e as { response?: { status?: number } })?.response?.status;
        const detail =
            (e as { response?: { data?: { detail?: string } } })?.response?.data
                ?.detail || "AI request failed.";
        if (status === 422)
            toast(detail, {
                icon: (
                    <FiAlertTriangle
                        className="w-4 h-4 text-[var(--warning)]"
                        aria-hidden
                    />
                ),
            });
        else if (status === 412)
            toast.error("Connect an AI provider first (Settings → AI).");
        else toast.error(detail);
    };

    const run = async (kind: "summary" | "actions" | "timing") => {
        setBusy(kind);
        try {
            if (kind === "summary") {
                const r = await aiApi.invoiceSummary(billId);
                setSummary(r.data);
            } else if (kind === "actions") {
                const r = await aiApi.invoiceActions(billId);
                setActions(r.data);
            } else {
                const r = await aiApi.invoiceTiming(billId);
                setTiming(r.data);
            }
        } catch (e) {
            handleAIError(e);
        } finally {
            setBusy(null);
        }
    };

    if (credLoading) {
        return (
            <div className="surface-card p-5">
                <div className="h-4 w-32 bg-[var(--bg-hover)] animate-pulse rounded" />
            </div>
        );
    }

    return (
        <div className="surface-card p-5">
            <header className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <FiCpu className="w-3.5 h-3.5 text-[var(--accent)]" />
                    <h2 className="microtype">AI assistant</h2>
                </div>
                {cred && (
                    <span className="text-[11px] text-[var(--text-subtle)] font-mono">
                        {cred.provider} · {cred.model}
                    </span>
                )}
            </header>

            {!cred ? (
                <div className="py-3">
                    <p className="text-[12.5px] text-[var(--text-muted)] mb-2">
                        Connect your Claude or Gemini API key for invoice
                        summaries, anomaly detection, and payment-timing
                        suggestions.
                    </p>
                    <Link
                        href="/dashboard/settings/ai"
                        className="
                            inline-flex items-center gap-1.5 text-[12.5px]
                            text-[var(--accent)] hover:text-[var(--accent-strong)]
                            font-medium
                        "
                    >
                        <FiSettings className="w-3 h-3" />
                        Connect AI
                    </Link>
                </div>
            ) : (
                <>
                    <div className="flex flex-wrap gap-2 mb-4">
                        <AIButton
                            label={busy === "summary" ? "Summarising…" : "Summarize"}
                            onClick={() => run("summary")}
                            disabled={busy !== null}
                            primary
                        />
                        <AIButton
                            label={busy === "actions" ? "Thinking…" : "Suggest actions"}
                            onClick={() => run("actions")}
                            disabled={busy !== null}
                        />
                        <AIButton
                            label={busy === "timing" ? "Reasoning…" : "Payment timing"}
                            onClick={() => run("timing")}
                            disabled={busy !== null}
                        />
                    </div>

                    {summary && (
                        <section className="mb-4">
                            <p className="text-[13px] leading-relaxed text-[var(--text-primary)] whitespace-pre-line">
                                {summary.summary}
                            </p>
                            {summary.anomalies.length > 0 && (
                                <ul className="mt-3 space-y-1.5">
                                    {summary.anomalies.map((a, i) => (
                                        <li
                                            key={i}
                                            className="flex gap-2 text-[12px] text-[var(--warning)]"
                                        >
                                            <FiAlertTriangle className="w-3 h-3 mt-0.5 shrink-0" aria-hidden />
                                            <span>{a}</span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </section>
                    )}

                    {actions && actions.actions.length > 0 && (
                        <section className="mb-4">
                            <h3 className="microtype mb-2">Suggested actions</h3>
                            <ul className="space-y-2">
                                {actions.actions.map((a, i) => (
                                    <li
                                        key={i}
                                        className="rounded-md border border-[var(--border-default)] p-3 bg-[var(--bg-page)]"
                                        style={{
                                            borderLeftColor: URGENCY_TINT[a.urgency],
                                            borderLeftWidth: "3px",
                                        }}
                                    >
                                        <p className="text-[13px] font-medium text-[var(--text-primary)]">
                                            {a.label}
                                        </p>
                                        <p className="text-[12px] text-[var(--text-muted)] mt-0.5">
                                            {a.rationale}
                                        </p>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    )}

                    {timing && (
                        <section className="rounded-md p-3 bg-[var(--accent-soft)] border border-[var(--accent-edge)]">
                            <h3 className="microtype mb-1 text-[var(--accent)]">
                                Payment timing
                            </h3>
                            <p className="text-[13px] font-medium text-[var(--text-primary)]">
                                {timing.recommendation}
                            </p>
                            <p className="text-[12px] text-[var(--text-muted)] mt-1">
                                {timing.rationale}
                            </p>
                            {timing.suggested_payment_date && (
                                <p className="mt-2 text-[11.5px] text-[var(--text-muted)] font-mono">
                                    Suggested:{" "}
                                    <span className="text-[var(--text-primary)]">
                                        {timing.suggested_payment_date}
                                    </span>
                                </p>
                            )}
                        </section>
                    )}
                </>
            )}
        </div>
    );
}

function AIButton({
    label,
    onClick,
    disabled,
    primary,
}: {
    label: string;
    onClick: () => void;
    disabled: boolean;
    primary?: boolean;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            className={`
                inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md
                text-[12.5px] font-medium transition-colors duration-150
                cursor-pointer
                disabled:opacity-50 disabled:cursor-not-allowed
                ${
                    primary
                        ? "bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)]"
                        : "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]"
                }
            `}
        >
            {label}
        </button>
    );
}
