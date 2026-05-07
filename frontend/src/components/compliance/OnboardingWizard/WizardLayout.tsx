"use client";

import { ReactNode } from "react";
import { FiCheck } from "react-icons/fi";
import { useOnboardingWizard } from "@/stores/onboardingWizardStore";

const STEPS = [
    { id: 1, label: "Details" },
    { id: 2, label: "Registrations" },
    { id: 3, label: "Team" },
    { id: 4, label: "Import" },
] as const;

/**
 * Wizard chrome per UI-SPEC Section 6.
 *
 * Progress indicator: 4 circles connected by line, labeled Details / Registrations / Team / Import.
 * Tokens: pending → bordered with --border-default, current → --accent fill,
 * complete → --success fill, connectors switch through the same trio. Click-back
 * is enabled on completed steps only (form-level validation still gates Continue).
 */
export function WizardLayout({ children }: { children: ReactNode }) {
    const { step, completedSteps, setStep } = useOnboardingWizard();

    return (
        <div className="max-w-2xl mx-auto py-12 px-6">
            {/* Step circles + connectors */}
            <div className="flex items-center justify-between mb-3">
                {STEPS.map((s, idx) => {
                    const isCurrent = s.id === step;
                    const isComplete = completedSteps.includes(s.id);
                    // A step is clickable if completed OR if it's a previous step
                    // (we let users go back even if validation hasn't fired yet for that exact step).
                    const canClick =
                        (isComplete || s.id < step) && !isCurrent;

                    // Connector to the right of this circle
                    const nextIsConnected =
                        idx < STEPS.length - 1
                            ? completedSteps.includes(s.id)
                                ? "bg-[var(--success)]"
                                : isCurrent
                                ? "bg-[var(--accent)]"
                                : "bg-[var(--border-default)]"
                            : "";

                    return (
                        <div
                            key={s.id}
                            className="flex items-center flex-1 last:flex-none"
                        >
                            <button
                                type="button"
                                disabled={!canClick}
                                onClick={() =>
                                    canClick &&
                                    setStep(s.id as 1 | 2 | 3 | 4)
                                }
                                className={`
                                    w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-medium
                                    transition-colors flex-shrink-0
                                    ${
                                        isComplete
                                            ? "bg-[var(--success)] text-white"
                                            : isCurrent
                                            ? "bg-[var(--accent)] text-white"
                                            : "border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-muted)]"
                                    }
                                    ${canClick ? "cursor-pointer hover:opacity-80" : "cursor-default"}
                                `}
                                aria-current={isCurrent ? "step" : undefined}
                                aria-label={`Step ${s.id}: ${s.label}${isCurrent ? " (current)" : isComplete ? " (complete)" : ""}`}
                            >
                                {isComplete ? (
                                    <FiCheck className="w-4 h-4" />
                                ) : (
                                    s.id
                                )}
                            </button>
                            {idx < STEPS.length - 1 && (
                                <div
                                    className={`flex-1 h-0.5 mx-2 ${nextIsConnected}`}
                                />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Step labels (caption tier — UI-SPEC typography) */}
            <div className="flex justify-between text-[11px] uppercase tracking-wider mb-12">
                {STEPS.map((s, idx) => (
                    <div
                        key={s.id}
                        className={`
                            flex-1 last:flex-none text-center
                            ${idx === 0 ? "text-left" : ""}
                            ${idx === STEPS.length - 1 ? "text-right" : ""}
                            ${
                                s.id === step
                                    ? "text-[var(--accent)]"
                                    : completedSteps.includes(s.id)
                                    ? "text-[var(--text-muted)]"
                                    : "text-[var(--text-disabled)]"
                            }
                        `}
                    >
                        {s.label}
                    </div>
                ))}
            </div>

            {/* Step pane */}
            <div className="surface-card p-8">
                {children}
            </div>
        </div>
    );
}
