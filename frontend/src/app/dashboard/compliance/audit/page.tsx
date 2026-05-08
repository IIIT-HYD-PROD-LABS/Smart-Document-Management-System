"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { FiShield, FiInfo } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { AuditLogEntry } from "@/types/compliance";

/**
 * Audit log viewer — UI-SPEC §8 + AUDIT-01.
 *
 * Read-only by construction: there are no mutation handlers in this page.
 * The DB-level enforcement (Plan 04 trigger + REVOKE on app_runtime) is the
 * authoritative defense; the UI's omission of write controls is the
 * principle-of-least-surprise complement (CONTEXT D-33).
 */

const ACTION_OPTIONS = [
    "",
    "notice_create",
    "notice_update",
    "notice_status_changed",
    "client_onboarded",
    "membership_added",
    "membership_removed",
    "login",
    "logout",
];

function fmtTs(iso: string): { abs: string; rel: string } {
    try {
        const d = parseISO(iso);
        return {
            abs: format(d, "dd MMM yyyy, HH:mm:ss"),
            rel: format(d, "yyyy-MM-dd"),
        };
    } catch {
        return { abs: iso, rel: iso };
    }
}

export default function AuditPage() {
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [actor, setActor] = useState("");
    const [actionFilter, setActionFilter] = useState("");

    const auditQ = useQuery({
        queryKey: ["audit", dateFrom, dateTo, actor, actionFilter],
        queryFn: async () => {
            const actorId = actor.trim()
                ? Number.parseInt(actor.trim(), 10)
                : undefined;
            const { data } = await complianceApi.listAudit({
                date_from: dateFrom || undefined,
                date_to: dateTo || undefined,
                actor_user_id: Number.isFinite(actorId)
                    ? (actorId as number)
                    : undefined,
                action: actionFilter || undefined,
                page: 1,
                page_size: 100,
            });
            return data;
        },
    });

    const entries: AuditLogEntry[] = auditQ.data ?? [];

    const fieldClass =
        "w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded px-2.5 py-1.5 text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]";

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <header className="mb-6 flex items-start gap-3">
                <FiShield
                    className="w-5 h-5 text-[var(--accent)] mt-0.5 shrink-0"
                    aria-hidden="true"
                />
                <div>
                    <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-0.5">
                        Audit log
                    </h1>
                    <p className="text-[13px] text-[var(--text-muted)]">
                        System-of-record for compliance actions. Immutable at
                        the database level.
                    </p>
                </div>
            </header>

            <div
                className="rounded-md p-4 mb-6 bg-[var(--accent-soft)] border border-[var(--accent-edge)] flex items-start gap-3"
                role="note"
            >
                <FiInfo
                    className="w-4 h-4 text-[var(--accent)] mt-0.5 shrink-0"
                    aria-hidden="true"
                />
                <p className="text-[13px] text-[var(--text-secondary)]">
                    Records here are immutable — enforced at the database
                    level. This is your auditor-grade trail.
                </p>
            </div>

            <div className="surface-card p-4 mb-4">
                <h2 className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-3">
                    Filters
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <div>
                        <label
                            htmlFor="audit-date-from"
                            className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5"
                        >
                            From date
                        </label>
                        <input
                            id="audit-date-from"
                            type="date"
                            value={dateFrom}
                            onChange={(e) => setDateFrom(e.target.value)}
                            className={fieldClass}
                        />
                    </div>
                    <div>
                        <label
                            htmlFor="audit-date-to"
                            className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5"
                        >
                            To date
                        </label>
                        <input
                            id="audit-date-to"
                            type="date"
                            value={dateTo}
                            onChange={(e) => setDateTo(e.target.value)}
                            className={fieldClass}
                        />
                    </div>
                    <div>
                        <label
                            htmlFor="audit-actor"
                            className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5"
                        >
                            Actor (user id)
                        </label>
                        <input
                            id="audit-actor"
                            type="text"
                            inputMode="numeric"
                            value={actor}
                            onChange={(e) => setActor(e.target.value)}
                            placeholder="e.g. 12"
                            className={fieldClass}
                        />
                    </div>
                    <div>
                        <label
                            htmlFor="audit-action"
                            className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1.5"
                        >
                            Action
                        </label>
                        <select
                            id="audit-action"
                            value={actionFilter}
                            onChange={(e) => setActionFilter(e.target.value)}
                            className={fieldClass}
                        >
                            {ACTION_OPTIONS.map((a) => (
                                <option key={a || "_all"} value={a}>
                                    {a === "" ? "All actions" : a}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            <div className="surface-card overflow-hidden">
                {auditQ.isLoading ? (
                    <ul role="status" aria-live="polite">
                        {[0, 1, 2, 3].map((i) => (
                            <li
                                key={i}
                                className="px-4 py-4 border-b border-[var(--border-default)] last:border-0"
                            >
                                <div className="h-3 w-2/3 bg-[var(--bg-hover)] rounded animate-pulse mb-2" />
                                <div className="h-3 w-1/3 bg-[var(--bg-hover)] rounded animate-pulse" />
                            </li>
                        ))}
                    </ul>
                ) : auditQ.isError ? (
                    // Distinguish "no rows" from "you can't see them" — 403
                    // is the common case (only `auditor`, `compliance_head`,
                    // and `ca_consultant` have AUDIT_VIEW). Anything else
                    // surfaces as a generic load-failure block.
                    (() => {
                        const status = (
                            auditQ.error as { response?: { status?: number } }
                        )?.response?.status;
                        if (status === 403) {
                            return (
                                <div className="p-12 text-center">
                                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                                        You don&apos;t have access to the audit log
                                    </h3>
                                    <p className="text-[13px] text-[var(--text-muted)] max-w-md mx-auto">
                                        Audit visibility is restricted to{" "}
                                        <code className="font-mono text-[12px] bg-[var(--bg-hover)] px-1 py-0.5 rounded">
                                            auditor
                                        </code>
                                        ,{" "}
                                        <code className="font-mono text-[12px] bg-[var(--bg-hover)] px-1 py-0.5 rounded">
                                            compliance_head
                                        </code>
                                        , and{" "}
                                        <code className="font-mono text-[12px] bg-[var(--bg-hover)] px-1 py-0.5 rounded">
                                            ca_consultant
                                        </code>{" "}
                                        roles. Ask your tenant admin to upgrade
                                        your membership if you need to see this.
                                    </p>
                                </div>
                            );
                        }
                        return (
                            <div className="p-12 text-center">
                                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                                    Couldn&apos;t load audit log
                                </h3>
                                <p className="text-[13px] text-[var(--text-muted)]">
                                    {(auditQ.error as Error)?.message ||
                                        "Try refreshing the page."}
                                </p>
                            </div>
                        );
                    })()
                ) : entries.length === 0 ? (
                    <div className="p-12 text-center">
                        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
                            No audit records in this range
                        </h3>
                        <p className="text-[13px] text-[var(--text-muted)]">
                            Adjust the date range or actor filter to see audit
                            history.
                        </p>
                    </div>
                ) : (
                    <ul>
                        {entries.map((e) => {
                            const ts = fmtTs(e.created_at);
                            return (
                                <li
                                    key={e.id}
                                    className="px-4 py-4 border-b border-[var(--border-default)] last:border-0"
                                >
                                    <div className="flex items-baseline gap-2 flex-wrap">
                                        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                                            {e.action}
                                        </span>
                                        {e.resource_type && (
                                            <span className="text-[12px] text-[var(--text-secondary)]">
                                                on {e.resource_type}
                                                {e.resource_id !== null
                                                    ? ` #${e.resource_id}`
                                                    : ""}
                                            </span>
                                        )}
                                        <span className="ml-auto text-[11px] text-[var(--text-subtle)] tabular-nums" title={ts.abs}>
                                            {ts.abs}
                                        </span>
                                    </div>
                                    <div className="mt-1 flex items-center gap-3 text-[12px] text-[var(--text-muted)]">
                                        <span>
                                            actor:{" "}
                                            <span className="font-mono text-[var(--text-secondary)]">
                                                {e.user_id ?? "system"}
                                            </span>
                                        </span>
                                        {e.ip_address && (
                                            <span className="font-mono">
                                                ip: {e.ip_address}
                                            </span>
                                        )}
                                    </div>
                                    {e.details && (
                                        <details className="mt-2">
                                            <summary className="text-[11px] uppercase tracking-wider text-[var(--text-subtle)] cursor-pointer hover:text-[var(--text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded">
                                                Diff
                                            </summary>
                                            <pre className="mt-2 text-xs text-[var(--text-secondary)] bg-[var(--bg-muted)] border border-[var(--border-default)] rounded p-3 overflow-x-auto whitespace-pre-wrap">
                                                {JSON.stringify(e.details, null, 2)}
                                            </pre>
                                        </details>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>
        </div>
    );
}
