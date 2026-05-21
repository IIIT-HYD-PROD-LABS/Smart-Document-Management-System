"use client";

import { useState } from "react";
import { FiTrash2, FiPlus, FiInfo } from "react-icons/fi";
import { useAuth } from "@/context/AuthContext";
import {
    useOnboardingWizard,
    type WizardTeamMember,
} from "@/stores/onboardingWizardStore";
import {
    COMPLIANCE_ROLE_LABELS,
    COMPLIANCE_ROLE_COLORS,
    type ComplianceRole,
} from "@/types/compliance";

/**
 * Wizard Step 3 — Team assignment (D-25 7-role chips, D-27 Auditor time-bound).
 *
 * The 7 compliance roles render as visually equal-weight chips (D-26 — flat
 * permissions, no inheritance hierarchy). Auditor role exposes access_start
 * and access_end date pickers; other roles do not.
 *
 * This step uses local React state (not RHF) because the structure is
 * "draft a row → click Add → push to wizard.team list" rather than a
 * single form submit. Step 3 is optional (zero team members allowed —
 * the workspace owner can add them later from Team page).
 */
export function StepTeam() {
    const { team, setTeam, setStep, markComplete } = useOnboardingWizard();
    const { user: currentUser } = useAuth();
    const [draft, setDraft] = useState<WizardTeamMember | null>(null);
    const [accessStart, setAccessStart] = useState<string>("");
    const [accessEnd, setAccessEnd] = useState<string>("");
    const [error, setError] = useState<string | null>(null);

    const EMAIL_RX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    // The backend auto-adds the current user as compliance_head if they
    // aren't already on the team list. Surface that here so the user
    // knows they don't need to do anything to be added.
    const currentUserOnTeam = currentUser
        ? team.some(
              (m) =>
                  m.user_id === currentUser.id ||
                  (m.email && m.email.toLowerCase() === currentUser.email.toLowerCase()),
          )
        : false;

    const beginAdd = () => {
        setDraft({ email: "", full_name: "", compliance_role: "staff" });
        setAccessStart("");
        setAccessEnd("");
        setError(null);
    };

    const cancelAdd = () => {
        setDraft(null);
        setAccessStart("");
        setAccessEnd("");
        setError(null);
    };

    const addMember = () => {
        if (!draft) return;
        const email = (draft.email || "").trim().toLowerCase();
        if (!email) {
            setError("Email is required");
            return;
        }
        if (!EMAIL_RX.test(email)) {
            setError("Enter a valid email");
            return;
        }
        if (
            draft.compliance_role === "auditor" &&
            accessEnd &&
            accessStart &&
            new Date(accessEnd) < new Date(accessStart)
        ) {
            setError("Access end date must be on or after start date");
            return;
        }
        const newMember: WizardTeamMember = {
            email,
            full_name: draft.full_name?.trim() || undefined,
            compliance_role: draft.compliance_role,
            access_start:
                draft.compliance_role === "auditor" && accessStart
                    ? accessStart
                    : undefined,
            access_end:
                draft.compliance_role === "auditor" && accessEnd
                    ? accessEnd
                    : undefined,
        };
        setTeam([...team, newMember]);
        cancelAdd();
    };

    const removeMember = (idx: number) => {
        setTeam(team.filter((_, i) => i !== idx));
    };

    const onContinue = () => {
        markComplete(3);
        setStep(4);
    };

    const draftInputClass =
        "w-full px-3 py-2 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-primary)] text-sm placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)]";

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">Team</h1>
                <p className="text-[var(--text-muted)] text-sm">
                    Assign users to compliance roles for this client. Auditor
                    roles can be time-bound. You can add team members later
                    from the Team page.
                </p>
            </div>

            {!currentUserOnTeam && currentUser && (
                <div
                    className="flex items-start gap-3 p-3 rounded-md bg-[var(--accent-soft)] border border-[var(--accent-edge)]"
                    role="note"
                >
                    <FiInfo
                        className="w-4 h-4 text-[var(--accent)] mt-0.5 shrink-0"
                        aria-hidden="true"
                    />
                    <div className="text-[13px] text-[var(--text-secondary)]">
                        <span className="text-[var(--text-primary)]">{currentUser.email}</span>{" "}
                        will be added automatically as{" "}
                        <span
                            className="px-1.5 py-0.5 rounded text-[11px] font-medium"
                            style={{
                                backgroundColor: `color-mix(in srgb, ${COMPLIANCE_ROLE_COLORS.compliance_head} 12%, transparent)`,
                                color: COMPLIANCE_ROLE_COLORS.compliance_head,
                            }}
                        >
                            Compliance Head
                        </span>
                        . Add other team members below or skip — you can manage
                        roles later from the Team page.
                    </div>
                </div>
            )}

            {team.length === 0 && !draft && (
                <p className="text-[var(--text-muted)] text-sm py-2">
                    No additional team members yet.
                </p>
            )}

            <div className="space-y-2">
                {team.map((m, idx) => (
                    <div
                        key={`${m.email || m.user_id}-${idx}`}
                        className="flex items-center gap-3 p-3 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-default)]"
                    >
                        <span
                            className="px-2 py-1 rounded text-[11px] font-medium"
                            style={{
                                backgroundColor: `color-mix(in srgb, ${COMPLIANCE_ROLE_COLORS[m.compliance_role]} 12%, transparent)`,
                                color: COMPLIANCE_ROLE_COLORS[
                                    m.compliance_role
                                ],
                            }}
                        >
                            {COMPLIANCE_ROLE_LABELS[m.compliance_role]}
                        </span>
                        <span className="text-sm text-[var(--text-primary)]">
                            {m.email || `User #${m.user_id}`}
                        </span>
                        {m.access_end && (
                            <span className="text-xs text-[var(--text-muted)] ml-auto">
                                Until{" "}
                                {new Date(m.access_end).toLocaleDateString(
                                    "en-IN",
                                    {
                                        day: "numeric",
                                        month: "short",
                                        year: "numeric",
                                    }
                                )}
                            </span>
                        )}
                        <button
                            type="button"
                            onClick={() => removeMember(idx)}
                            className={`p-2 text-[var(--text-muted)] hover:text-[var(--danger)] transition-colors ${
                                m.access_end ? "" : "ml-auto"
                            }`}
                            aria-label={`Remove ${m.email || `user ${m.user_id}`}`}
                        >
                            <FiTrash2 className="w-3.5 h-3.5" />
                        </button>
                    </div>
                ))}
            </div>

            {!draft && (
                <button
                    type="button"
                    onClick={beginAdd}
                    className="text-[13px] text-[var(--accent)] hover:underline flex items-center gap-1 transition-colors"
                >
                    <FiPlus className="w-3.5 h-3.5" />
                    Add team member
                </button>
            )}

            {draft && (
                <div className="p-4 rounded-md bg-[var(--bg-muted)] border border-[var(--border-default)] space-y-3">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                                Email *
                            </label>
                            <input
                                type="email"
                                autoComplete="email"
                                placeholder="name@example.com"
                                value={draft.email || ""}
                                onChange={(e) =>
                                    setDraft({
                                        ...draft,
                                        email: e.target.value,
                                    })
                                }
                                className={draftInputClass}
                            />
                            <p className="text-[11px] text-[var(--text-muted)] mt-1">
                                Invitee gets an email link to set their password.
                            </p>
                        </div>
                        <div>
                            <label className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1">
                                Role *
                            </label>
                            <select
                                value={draft.compliance_role}
                                onChange={(e) =>
                                    setDraft({
                                        ...draft,
                                        compliance_role: e.target
                                            .value as ComplianceRole,
                                    })
                                }
                                className={draftInputClass}
                            >
                                {(
                                    Object.entries(COMPLIANCE_ROLE_LABELS) as [
                                        ComplianceRole,
                                        string,
                                    ][]
                                ).map(([key, label]) => (
                                    <option key={key} value={key}>
                                        {label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    {draft.compliance_role === "auditor" && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
                                    className={draftInputClass}
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
                                    className={draftInputClass}
                                />
                            </div>
                        </div>
                    )}
                    {error && (
                        <p className="text-xs text-[var(--danger)]">{error}</p>
                    )}
                    <div className="flex justify-end gap-2">
                        <button
                            type="button"
                            onClick={cancelAdd}
                            className="text-[var(--text-secondary)] text-sm hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] px-3 py-1.5 rounded transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            onClick={addMember}
                            className="px-3 py-1.5 rounded-md bg-[var(--accent)] text-white text-sm hover:bg-[var(--accent-strong)] transition-colors"
                        >
                            Add
                        </button>
                    </div>
                </div>
            )}

            <div className="flex justify-between gap-2 pt-4">
                <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="px-4 py-2 rounded-md text-[var(--text-secondary)] text-sm hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
                >
                    Back
                </button>
                <button
                    type="button"
                    onClick={onContinue}
                    className="px-4 py-2 rounded-md bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-strong)] transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]"
                >
                    Continue
                </button>
            </div>
        </div>
    );
}
