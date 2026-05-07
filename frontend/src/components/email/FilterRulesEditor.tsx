"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { FiPlus, FiTrash2 } from "react-icons/fi";
import {
    emailApi,
    FilterRouteTo,
    GmailFilterRule,
} from "@/lib/email-api";

interface Props {
    credentialId: number;
}

const ROUTE_OPTIONS: { value: FilterRouteTo; label: string }[] = [
    { value: "compliance_notice", label: "Compliance" },
    { value: "bill", label: "Bill" },
    { value: "dms_only", label: "DMS only" },
    { value: "ignore", label: "Ignore" },
];

/**
 * FilterRulesEditor — EMAIL-04 priority-ordered rule CRUD.
 *
 * Lists rules ordered by priority ASC, then id ASC (matches Plan 05
 * router ordering). Inline-edit pattern: onBlur on each field commits
 * the patch via PATCH /email/filter-rules/{id}; toast surfaces success
 * or backend error detail.
 *
 * Optimistic-UI is intentionally avoided — Plan 06 keeps the request
 * round-trip visible so misconfigured rules surface immediately.
 */
export default function FilterRulesEditor({ credentialId }: Props) {
    const [rules, setRules] = useState<GmailFilterRule[]>([]);
    const [loading, setLoading] = useState(true);
    const [savingId, setSavingId] = useState<number | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const resp = await emailApi.listFilterRules(credentialId);
            setRules(resp.data);
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to load filter rules";
            toast.error(msg);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [credentialId]);

    const handleAdd = async () => {
        try {
            const nextPriority =
                rules.length > 0
                    ? Math.max(...rules.map((r) => r.priority)) + 10
                    : 100;
            await emailApi.createFilterRule(credentialId, {
                priority: nextPriority,
                sender_pattern: "",
                subject_pattern: "",
                route_to: "ignore",
                enabled: true,
            });
            await load();
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to create rule";
            toast.error(msg);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm("Delete this filter rule?")) return;
        try {
            await emailApi.deleteFilterRule(id);
            await load();
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to delete rule";
            toast.error(msg);
        }
    };

    const handleSave = async (
        rule: GmailFilterRule,
        patch: Partial<GmailFilterRule>,
    ) => {
        setSavingId(rule.id);
        try {
            await emailApi.updateFilterRule(rule.id, patch);
            // Reload to keep priority ordering authoritative server-side
            await load();
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to save rule";
            toast.error(msg);
        } finally {
            setSavingId(null);
        }
    };

    if (loading) {
        return (
            <div className="text-[13px] text-[var(--text-muted)]">
                Loading filter rules…
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-[15px] font-semibold tracking-tight text-white">
                    Filter rules
                </h2>
                <button
                    type="button"
                    onClick={handleAdd}
                    className="
                        inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md
                        bg-[var(--accent)] text-white text-[12.5px] font-medium
                        hover:opacity-90 transition-opacity duration-150
                    "
                >
                    <FiPlus className="w-3.5 h-3.5" aria-hidden />
                    Add rule
                </button>
            </div>

            {rules.length === 0 ? (
                <div
                    className="
                        text-[13px] text-[var(--text-muted)]
                        bg-[var(--bg-elevated)] border border-[var(--border-default)]
                        rounded-md p-4
                    "
                >
                    No filter rules yet. Defaults will be seeded on first
                    Gmail connect; add custom rules to route specific senders.
                </div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-[12.5px]">
                        <thead>
                            <tr className="text-left text-[var(--text-muted)] border-b border-[var(--border-default)]">
                                <th className="py-2 pr-3 font-medium w-20">
                                    Priority
                                </th>
                                <th className="py-2 pr-3 font-medium">Sender pattern</th>
                                <th className="py-2 pr-3 font-medium">Subject pattern</th>
                                <th className="py-2 pr-3 font-medium w-36">Route to</th>
                                <th className="py-2 pr-3 font-medium w-20">Enabled</th>
                                <th className="py-2 font-medium w-10" aria-label="Delete" />
                            </tr>
                        </thead>
                        <tbody>
                            {rules.map((r) => (
                                <tr
                                    key={r.id}
                                    className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-elevated)]/40"
                                    data-saving={savingId === r.id ? "true" : undefined}
                                >
                                    <td className="py-2 pr-3 align-middle">
                                        <input
                                            type="number"
                                            min={0}
                                            defaultValue={r.priority}
                                            onBlur={(e) => {
                                                const next = parseInt(
                                                    e.target.value,
                                                    10,
                                                );
                                                if (
                                                    !Number.isNaN(next) &&
                                                    next !== r.priority
                                                ) {
                                                    handleSave(r, {
                                                        priority: next,
                                                    });
                                                }
                                            }}
                                            className="
                                                w-20 px-2 py-1 rounded
                                                bg-[var(--bg-page)]
                                                border border-[var(--border-emphasis)]
                                                text-[var(--text-primary)] font-mono tabular-nums
                                                focus:outline-none focus:border-[var(--accent)]
                                            "
                                        />
                                    </td>
                                    <td className="py-2 pr-3 align-middle">
                                        <input
                                            type="text"
                                            defaultValue={r.sender_pattern || ""}
                                            placeholder="*.gov.in"
                                            onBlur={(e) => {
                                                const next = e.target.value || null;
                                                if (next !== r.sender_pattern) {
                                                    handleSave(r, {
                                                        sender_pattern: next,
                                                    });
                                                }
                                            }}
                                            className="
                                                w-full px-2 py-1 rounded
                                                bg-[var(--bg-page)]
                                                border border-[var(--border-emphasis)]
                                                text-[var(--text-primary)] font-mono
                                                focus:outline-none focus:border-[var(--accent)]
                                            "
                                        />
                                    </td>
                                    <td className="py-2 pr-3 align-middle">
                                        <input
                                            type="text"
                                            defaultValue={r.subject_pattern || ""}
                                            placeholder="show.cause|notice"
                                            onBlur={(e) => {
                                                const next = e.target.value || null;
                                                if (next !== r.subject_pattern) {
                                                    handleSave(r, {
                                                        subject_pattern: next,
                                                    });
                                                }
                                            }}
                                            className="
                                                w-full px-2 py-1 rounded
                                                bg-[var(--bg-page)]
                                                border border-[var(--border-emphasis)]
                                                text-[var(--text-primary)] font-mono
                                                focus:outline-none focus:border-[var(--accent)]
                                            "
                                        />
                                    </td>
                                    <td className="py-2 pr-3 align-middle">
                                        <select
                                            defaultValue={r.route_to}
                                            onChange={(e) => {
                                                const next = e.target
                                                    .value as FilterRouteTo;
                                                if (next !== r.route_to) {
                                                    handleSave(r, {
                                                        route_to: next,
                                                    });
                                                }
                                            }}
                                            className="
                                                w-full px-2 py-1 rounded
                                                bg-[var(--bg-page)]
                                                border border-[var(--border-emphasis)]
                                                text-[var(--text-primary)]
                                                focus:outline-none focus:border-[var(--accent)]
                                            "
                                        >
                                            {ROUTE_OPTIONS.map((o) => (
                                                <option key={o.value} value={o.value}>
                                                    {o.label}
                                                </option>
                                            ))}
                                        </select>
                                    </td>
                                    <td className="py-2 pr-3 align-middle text-center">
                                        <input
                                            type="checkbox"
                                            defaultChecked={r.enabled}
                                            onChange={(e) =>
                                                handleSave(r, {
                                                    enabled: e.target.checked,
                                                })
                                            }
                                            className="accent-[var(--accent)]"
                                        />
                                    </td>
                                    <td className="py-2 align-middle text-right">
                                        <button
                                            type="button"
                                            onClick={() => handleDelete(r.id)}
                                            className="
                                                p-1.5 rounded text-[var(--text-muted)]
                                                hover:text-[var(--danger)]
                                                hover:bg-[#ef44441a]
                                                transition-colors duration-150
                                            "
                                            aria-label="Delete rule"
                                        >
                                            <FiTrash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <p className="text-[11px] text-[var(--text-subtle)]">
                Lower priority value wins. Defaults: gov.in domains route to
                compliance; known billers route to bill; everything else is
                ignored.
            </p>
        </div>
    );
}
