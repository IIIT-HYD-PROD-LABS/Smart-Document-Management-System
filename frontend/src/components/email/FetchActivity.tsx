"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
    emailApi,
    FetchStatus,
    GmailFetchLog,
} from "@/lib/email-api";

interface Props {
    credentialId: number;
}

const STATUS_BADGE: Record<
    FetchStatus,
    { label: string; bg: string; text: string }
> = {
    SUCCESS_WITH_RESULTS: {
        label: "SUCCESS",
        bg: "var(--success-soft)",
        text: "var(--success)",
    },
    SUCCESS_EMPTY: {
        label: "EMPTY",
        bg: "var(--warning-soft)",
        text: "var(--warning)",
    },
    FETCH_FAILED: {
        label: "FAILED",
        bg: "var(--danger-soft)",
        text: "var(--danger)",
    },
};

/**
 * FetchActivity — EMAIL-07 read-only GmailFetchLog viewer.
 *
 * Three-state badge (green / amber / red) per Plan 02 CHECK constraint.
 * Detects 2x consecutive FETCH_FAILED at the head of the list and
 * surfaces a reconnect prompt (mirrors D-15: two consecutive failures
 * trigger a Phase 11 alert; UI surfaces it inline).
 */
export default function FetchActivity({ credentialId }: Props) {
    const [logs, setLogs] = useState<GmailFetchLog[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        emailApi
            .listActivity(credentialId, 50)
            .then((r) => {
                if (!cancelled) setLogs(r.data);
            })
            .catch((e: unknown) => {
                const msg =
                    (e as { response?: { data?: { detail?: string } } })
                        ?.response?.data?.detail ||
                    "Failed to load fetch activity";
                if (!cancelled) toast.error(msg);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [credentialId]);

    if (loading) {
        return (
            <div className="text-[13px] text-[var(--text-muted)]">
                Loading fetch activity…
            </div>
        );
    }

    if (logs.length === 0) {
        return (
            <div
                className="
                    text-[13px] text-[var(--text-muted)]
                    bg-[var(--bg-elevated)] border border-[var(--border-default)]
                    rounded-md p-4
                "
            >
                No scan runs yet. Once the scheduler runs, recent fetch
                attempts will appear here.
            </div>
        );
    }

    // Detect consecutive failures at the head of the (newest-first) list.
    const consecutiveFailures =
        logs[0]?.status === "FETCH_FAILED" &&
        logs[1]?.status === "FETCH_FAILED";

    return (
        <div className="space-y-4">
            {consecutiveFailures && (
                <div
                    className="
                        flex items-start gap-3 p-3 rounded-md
                        bg-[var(--danger-soft)] border border-[var(--danger)]/30
                        text-[12.5px] text-[var(--danger)]
                    "
                    role="alert"
                >
                    <div>
                        <div className="font-medium text-[var(--danger)]">
                            Two consecutive scans failed
                        </div>
                        <div className="mt-0.5 text-[var(--text-secondary)]">
                            Verify the Gmail connection on /dashboard/email/connect.
                            If the credential was revoked, click Reconnect.
                        </div>
                    </div>
                </div>
            )}

            <div className="overflow-x-auto">
                <table className="w-full text-[12.5px]">
                    <thead>
                        <tr className="text-left text-[var(--text-muted)] border-b border-[var(--border-default)]">
                            <th className="py-2 pr-3 font-medium">Started</th>
                            <th className="py-2 pr-3 font-medium">Status</th>
                            <th className="py-2 pr-3 font-medium">Messages</th>
                            <th className="py-2 font-medium">Error</th>
                        </tr>
                    </thead>
                    <tbody>
                        {logs.map((l) => {
                            const cfg = STATUS_BADGE[l.status];
                            return (
                                <tr
                                    key={l.id}
                                    className="border-b border-[var(--border-subtle)]"
                                    data-status={l.status}
                                >
                                    <td className="py-2 pr-3 align-middle font-mono text-[var(--text-secondary)]">
                                        {new Date(l.started_at).toLocaleString()}
                                    </td>
                                    <td className="py-2 pr-3 align-middle">
                                        <span
                                            className="
                                                inline-flex items-center px-2 py-0.5
                                                rounded text-[11px] font-medium font-mono
                                            "
                                            style={{
                                                backgroundColor: cfg.bg,
                                                color: cfg.text,
                                            }}
                                        >
                                            {cfg.label}
                                        </span>
                                    </td>
                                    <td className="py-2 pr-3 align-middle font-mono tabular-nums text-[var(--text-secondary)]">
                                        {l.messages_processed}
                                    </td>
                                    <td className="py-2 align-middle text-[var(--text-subtle)] text-[11.5px]">
                                        {l.error_message ? (
                                            <span title={l.error_message}>
                                                {l.error_message.length > 80
                                                    ? `${l.error_message.slice(0, 80)}…`
                                                    : l.error_message}
                                            </span>
                                        ) : (
                                            "—"
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
