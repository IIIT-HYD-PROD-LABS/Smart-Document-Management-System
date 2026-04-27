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

    // The backend auto-adds the current user as compliance_head if they
    // aren't already on the team list. Surface that here so the user
    // knows they don't need to do anything to be added.
    const currentUserOnTeam = currentUser
        ? team.some((m) => m.user_id === currentUser.id)
        : false;

    const beginAdd = () => {
        setDraft({ user_id: 0, compliance_role: "staff" });
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
        if (!draft || !draft.user_id) {
            setError("User ID is required");
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
            user_id: draft.user_id,
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

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-lg font-semibold text-white mb-2">Team</h1>
                <p className="text-[#71717a] text-sm">
                    Assign users to compliance roles for this client. Auditor
                    roles can be time-bound. You can add team members later
                    from the Team page.
                </p>
            </div>

            {!currentUserOnTeam && currentUser && (
                <div
                    className="flex items-start gap-3 p-3 rounded-md bg-[#3b82f6]/10 border border-[#3b82f6]/30"
                    role="note"
                >
                    <FiInfo
                        className="w-4 h-4 text-[#3b82f6] mt-0.5 shrink-0"
                        aria-hidden="true"
                    />
                    <div className="text-[13px] text-[#a1a1aa]">
                        <span className="text-white">{currentUser.email}</span>{" "}
                        will be added automatically as{" "}
                        <span
                            className="px-1.5 py-0.5 rounded text-[11px] font-medium"
                            style={{
                                backgroundColor: `${COMPLIANCE_ROLE_COLORS.compliance_head}1a`,
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
                <p className="text-[#52525b] text-sm py-2">
                    No additional team members yet.
                </p>
            )}

            <div className="space-y-2">
                {team.map((m, idx) => (
                    <div
                        key={`${m.user_id}-${idx}`}
                        className="flex items-center gap-3 p-3 rounded-md bg-[#18181b] border border-[#27272a]"
                    >
                        <span
                            className="px-2 py-1 rounded text-[11px] font-medium"
                            style={{
                                backgroundColor: `${COMPLIANCE_ROLE_COLORS[m.compliance_role]}1a`,
                                color: COMPLIANCE_ROLE_COLORS[
                                    m.compliance_role
                                ],
                            }}
                        >
                            {COMPLIANCE_ROLE_LABELS[m.compliance_role]}
                        </span>
                        <span className="text-sm text-white">
                            User #{m.user_id}
                        </span>
                        {m.access_end && (
                            <span className="text-xs text-[#71717a] ml-auto">
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
                            className={`p-2 text-[#71717a] hover:text-[#ef4444] transition-colors ${
                                m.access_end ? "" : "ml-auto"
                            }`}
                            aria-label={`Remove user ${m.user_id}`}
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
                    className="text-[13px] text-[#3b82f6] hover:underline flex items-center gap-1 transition-colors"
                >
                    <FiPlus className="w-3.5 h-3.5" />
                    Add team member
                </button>
            )}

            {draft && (
                <div className="p-4 rounded-md bg-[#18181b] border border-[#27272a] space-y-3">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1">
                                User ID *
                            </label>
                            <input
                                type="number"
                                min={1}
                                placeholder="42"
                                value={draft.user_id || ""}
                                onChange={(e) =>
                                    setDraft({
                                        ...draft,
                                        user_id:
                                            parseInt(e.target.value, 10) || 0,
                                    })
                                }
                                className="
                                    w-full px-3 py-2 rounded-md tabular-nums
                                    bg-[#111113] border border-[#27272a] text-white text-sm
                                    focus:outline-none focus:border-[#3b82f6]/40
                                "
                            />
                        </div>
                        <div>
                            <label className="block text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1">
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
                                className="
                                    w-full px-3 py-2 rounded-md
                                    bg-[#111113] border border-[#27272a] text-white text-sm
                                    focus:outline-none focus:border-[#3b82f6]/40
                                "
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
                                <label className="block text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1">
                                    Access start
                                </label>
                                <input
                                    type="date"
                                    value={accessStart}
                                    onChange={(e) =>
                                        setAccessStart(e.target.value)
                                    }
                                    className="w-full px-3 py-2 rounded-md bg-[#111113] border border-[#27272a] text-white text-sm focus:outline-none focus:border-[#3b82f6]/40"
                                />
                            </div>
                            <div>
                                <label className="block text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1">
                                    Access end
                                </label>
                                <input
                                    type="date"
                                    value={accessEnd}
                                    onChange={(e) =>
                                        setAccessEnd(e.target.value)
                                    }
                                    className="w-full px-3 py-2 rounded-md bg-[#111113] border border-[#27272a] text-white text-sm focus:outline-none focus:border-[#3b82f6]/40"
                                />
                            </div>
                        </div>
                    )}
                    {error && (
                        <p className="text-xs text-[#ef4444]">{error}</p>
                    )}
                    <div className="flex justify-end gap-2">
                        <button
                            type="button"
                            onClick={cancelAdd}
                            className="text-[#a1a1aa] text-sm hover:text-white transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            onClick={addMember}
                            className="px-3 py-1.5 rounded-md bg-[#3b82f6] text-white text-sm hover:bg-[#3b82f6]/90 transition-colors"
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
                    className="px-4 py-2 rounded-md text-[#a1a1aa] text-sm hover:text-white transition-colors"
                >
                    Back
                </button>
                <button
                    type="button"
                    onClick={onContinue}
                    className="px-4 py-2 rounded-md bg-[#3b82f6] text-white text-sm font-medium hover:bg-[#3b82f6]/90 transition-colors focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                >
                    Continue
                </button>
            </div>
        </div>
    );
}
