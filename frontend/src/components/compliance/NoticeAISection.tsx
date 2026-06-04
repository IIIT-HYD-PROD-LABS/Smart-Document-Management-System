"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import toast from "react-hot-toast";
import { FiCpu, FiSettings } from "react-icons/fi";

import { aiApi } from "@/lib/api/ai";
import { useCurrentClient } from "@/stores/currentClientStore";
import type {
    AIActionItem,
    NoticeActionsResponse,
    NoticeSummaryResponse,
} from "@/types/ai";

interface Props {
    noticeId: number;
}

const URGENCY_TINT: Record<AIActionItem["urgency"], string> = {
    high: "var(--danger)",
    medium: "var(--warning)",
    low: "var(--text-muted)",
};

/**
 * AI assistant panel on the notice detail page. Shows two on-demand
 * buttons (Summarize, Suggested actions) and renders the response below.
 *
 * Both buttons are no-ops when the tenant hasn't connected an AI
 * provider yet — instead we render a quiet CTA pointing at /settings/ai.
 */
export default function NoticeAISection({ noticeId }: Props) {
    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const { data: cred, isLoading: credLoading } = useQuery({
        queryKey: ["ai-credential", activeClientId],
        queryFn: () => aiApi.getCredential().then((r) => r.data),
        staleTime: 30_000,
        enabled: activeClientId !== null,
    });

    const [summary, setSummary] = useState<NoticeSummaryResponse | null>(null);
    const [actions, setActions] = useState<NoticeActionsResponse | null>(null);
    const [busy, setBusy] = useState<"summary" | "actions" | null>(null);

    const handleAIError = (e: unknown) => {
        const status = (e as { response?: { status?: number } })?.response?.status;
        const detail =
            (e as { response?: { data?: { detail?: string } } })?.response?.data
                ?.detail || "AI request failed.";
        if (status === 422) toast(detail, { icon: "⚠" });
        else if (status === 412)
            toast.error("Connect an AI provider first (Settings → AI).");
        else toast.error(detail);
    };

    const runSummary = async () => {
        setBusy("summary");
        try {
            const r = await aiApi.noticeSummary(noticeId);
            setSummary(r.data);
        } catch (e) {
            handleAIError(e);
        } finally {
            setBusy(null);
        }
    };

    const runActions = async () => {
        setBusy("actions");
        try {
            const r = await aiApi.noticeActions(noticeId);
            setActions(r.data);
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
                        Connect your Claude or Gemini API key to summarise notices
                        and get suggested next actions.
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
                            onClick={runSummary}
                            disabled={busy !== null}
                            primary
                        />
                        <AIButton
                            label={busy === "actions" ? "Thinking…" : "Suggest actions"}
                            onClick={runActions}
                            disabled={busy !== null}
                        />
                    </div>

                    {summary && (
                        <section className="mb-4">
                            <p className="text-[13px] leading-relaxed text-[var(--text-primary)] whitespace-pre-line">
                                {summary.summary}
                            </p>
                            {summary.key_points.length > 0 && (
                                <ul className="mt-3 space-y-1.5">
                                    {summary.key_points.map((kp, i) => (
                                        <li
                                            key={i}
                                            className="flex gap-2 text-[12.5px] text-[var(--text-secondary)]"
                                        >
                                            <span className="text-[var(--accent)] mt-1 leading-none">·</span>
                                            <span>{kp}</span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                            {summary.deadline_iso && (
                                <p className="mt-3 text-[11.5px] text-[var(--text-muted)] font-mono">
                                    Deadline:{" "}
                                    <span className="text-[var(--text-primary)]">
                                        {summary.deadline_iso}
                                    </span>
                                </p>
                            )}
                        </section>
                    )}

                    {actions && actions.actions.length > 0 && (
                        <section>
                            <h3 className="microtype mb-2">Suggested next steps</h3>
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
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]
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
