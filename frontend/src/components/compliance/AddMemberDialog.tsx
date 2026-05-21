"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { complianceApi, type AddMemberResponse } from "@/lib/api/compliance";
import {
    COMPLIANCE_ROLE_LABELS,
    type ComplianceRole,
} from "@/types/compliance";
import { extractErrorMessage } from "@/lib/api";

const EMAIL_RX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Modal dialog to add a member to a client (RBAC-01..06).
 *
 * Invitation flow (2026-05-21):
 *   The dialog asks for the invitee's email + optional full name.
 *   When the email matches an existing TaxSync account, the membership
 *   is attached directly. Otherwise the backend pre-creates a pending
 *   User and emails an accept-invite link; the invitee sets a password
 *   on /accept-invite and is signed in. The toast confirms which path
 *   was taken so the admin knows whether to chase the invitee.
 *
 * For Auditor role, exposes access_start/access_end date pickers (D-27).
 * Closes on Escape (WCAG 2.1.1). The parent invokes onAdded() so it can
 * invalidate its react-query cache and re-render the team list.
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
    const [email, setEmail] = useState("");
    const [fullName, setFullName] = useState("");
    const [role, setRole] = useState<ComplianceRole>("staff");
    const [accessStart, setAccessStart] = useState("");
    const [accessEnd, setAccessEnd] = useState("");
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !submitting) onClose();
        };
        document.addEventListener("keydown", handler);
        return () => document.removeEventListener("keydown", handler);
    }, [onClose, submitting]);

    const submit = async () => {
        const trimmedEmail = email.trim().toLowerCase();
        if (!trimmedEmail) {
            toast.error("Email is required");
            return;
        }
        if (!EMAIL_RX.test(trimmedEmail)) {
            toast.error("Enter a valid email address");
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
            const res = await complianceApi.addMember(clientId, {
                email: trimmedEmail,
                full_name: fullName.trim() || undefined,
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
            const data = (res.data as unknown) as AddMemberResponse;
            if (data?.invited) {
                toast.success(
                    `Invitation sent to ${trimmedEmail}. They will receive an email link to set a password and sign in.`,
                    { duration: 6000 },
                );
                if (data.accept_invite_token) {
                    // DEBUG-only echo so a developer without SMTP can
                    // still complete the loop end-to-end locally.
                    // Production never sets accept_invite_token.
                    console.info(
                        `[dev] accept-invite URL: ${window.location.origin}/accept-invite?token=${data.accept_invite_token}`,
                    );
                }
            } else {
                toast.success("Member added");
            }
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
                <p className="text-[12px] text-[var(--text-muted)] mb-4">
                    The invitee gets an email with a link to set their password.
                    If they already have a TaxSync account, they are added to
                    the team immediately.
                </p>
                <div className="space-y-3">
                    <div>
                        <label
                            htmlFor="add-member-email"
                            className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1"
                        >
                            Email *
                        </label>
                        <input
                            id="add-member-email"
                            type="email"
                            autoComplete="email"
                            placeholder="name@example.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="
                                w-full px-3 py-2 rounded bg-[var(--bg-elevated)]
                                border border-[var(--border-default)] text-[var(--text-primary)] text-sm
                                placeholder:text-[var(--text-disabled)]
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                            "
                        />
                    </div>
                    <div>
                        <label
                            htmlFor="add-member-full-name"
                            className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1"
                        >
                            Full name (optional)
                        </label>
                        <input
                            id="add-member-full-name"
                            type="text"
                            placeholder="Jane Doe"
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            maxLength={200}
                            className="
                                w-full px-3 py-2 rounded bg-[var(--bg-elevated)]
                                border border-[var(--border-default)] text-[var(--text-primary)] text-sm
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
                            {submitting ? "Sending invite…" : "Send invite"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
