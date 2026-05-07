"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { complianceApi } from "@/lib/api/compliance";
import {
    COMPLIANCE_ROLE_LABELS,
    type ComplianceRole,
} from "@/types/compliance";
import { extractErrorMessage } from "@/lib/api";

/**
 * Modal dialog to add a member to a client (RBAC-01..06).
 *
 * For Auditor role, exposes access_start/access_end date pickers (D-27).
 * Closes on Escape (WCAG 2.1.1 keyboard accessible). The parent invokes
 * onAdded() so it can invalidate its react-query cache and re-render the team list.
 */
export function AddMemberDialog({
    clientId,
    onClose,
    onAdded,
}: {
    clientId: number;
    onClose: () => void;
    onAdded: () => void;
}) {
    const [userId, setUserId] = useState<number>(0);
    const [role, setRole] = useState<ComplianceRole>("staff");
    const [accessStart, setAccessStart] = useState("");
    const [accessEnd, setAccessEnd] = useState("");
    const [submitting, setSubmitting] = useState(false);

    // Close on Escape
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !submitting) onClose();
        };
        document.addEventListener("keydown", handler);
        return () => document.removeEventListener("keydown", handler);
    }, [onClose, submitting]);

    const submit = async () => {
        if (!userId) {
            toast.error("User ID is required");
            return;
        }
        if (
            role === "auditor" &&
            accessEnd &&
            accessStart &&
            new Date(accessEnd) < new Date(accessStart)
        ) {
            toast.error("Access end date must be on or after start date");
            return;
        }
        setSubmitting(true);
        try {
            await complianceApi.addMember(clientId, {
                user_id: userId,
                compliance_role: role,
                access_start:
                    role === "auditor" && accessStart
                        ? accessStart
                        : undefined,
                access_end:
                    role === "auditor" && accessEnd
                        ? accessEnd
                        : undefined,
            });
            toast.success("Member added");
            onAdded();
            onClose();
        } catch (err) {
            toast.error(extractErrorMessage(err, "Failed to add member"));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div
            className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6"
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-member-title"
            onClick={(e) => {
                // Close on backdrop click (only the backdrop, not bubbled)
                if (e.target === e.currentTarget && !submitting) onClose();
            }}
        >
            <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-md p-6 w-full max-w-md shadow-[var(--shadow-lg)]">
                <h2
                    id="add-member-title"
                    className="text-base font-semibold text-[var(--text-primary)] mb-4"
                >
                    Add team member
                </h2>
                <div className="space-y-3">
                    <div>
                        <label
                            htmlFor="add-member-user-id"
                            className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1"
                        >
                            User ID *
                        </label>
                        <input
                            id="add-member-user-id"
                            type="number"
                            min={1}
                            placeholder="42"
                            value={userId || ""}
                            onChange={(e) =>
                                setUserId(parseInt(e.target.value, 10) || 0)
                            }
                            className="
                                w-full px-3 py-2 rounded bg-[var(--bg-elevated)]
                                border border-[var(--border-default)] text-[var(--text-primary)] text-sm tabular-nums
                                placeholder:text-[var(--text-disabled)]
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                            "
                        />
                    </div>
                    <div>
                        <label
                            htmlFor="add-member-role"
                            className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1"
                        >
                            Role *
                        </label>
                        <select
                            id="add-member-role"
                            value={role}
                            onChange={(e) =>
                                setRole(e.target.value as ComplianceRole)
                            }
                            className="
                                w-full px-3 py-2 rounded bg-[var(--bg-elevated)]
                                border border-[var(--border-default)] text-[var(--text-primary)] text-sm
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                            "
                        >
                            {(
                                Object.entries(COMPLIANCE_ROLE_LABELS) as [
                                    ComplianceRole,
                                    string,
                                ][]
                            ).map(([k, v]) => (
                                <option key={k} value={k}>
                                    {v}
                                </option>
                            ))}
                        </select>
                    </div>
                    {role === "auditor" && (
                        <div className="grid grid-cols-2 gap-2">
                            <div>
                                <label className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                                    Access start
                                </label>
                                <input
                                    type="date"
                                    value={accessStart}
                                    onChange={(e) =>
                                        setAccessStart(e.target.value)
                                    }
                                    className="w-full px-3 py-2 rounded bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]"
                                />
                            </div>
                            <div>
                                <label className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                                    Access end
                                </label>
                                <input
                                    type="date"
                                    value={accessEnd}
                                    onChange={(e) =>
                                        setAccessEnd(e.target.value)
                                    }
                                    className="w-full px-3 py-2 rounded bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]"
                                />
                            </div>
                        </div>
                    )}
                    <div className="flex justify-end gap-2 pt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            disabled={submitting}
                            className="px-3 py-1.5 text-[var(--text-secondary)] text-sm hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded transition-colors disabled:opacity-50"
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            onClick={submit}
                            disabled={submitting}
                            className="
                                px-3 py-1.5 rounded bg-[var(--accent)] text-white text-sm font-medium
                                hover:bg-[var(--accent-strong)] transition-colors
                                focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                                disabled:opacity-60 disabled:cursor-not-allowed
                            "
                        >
                            {submitting ? "Adding…" : "Add member"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
