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
 * - Pending: hollow border-[#27272a] circle, gray text
 * - Current: filled bg-[#3b82f6] circle, accent text label
 * - Complete: filled bg-[#10b981] circle with white check, gray label
 * - Connector line: bg-[#27272a] unwalked, bg-[#3b82f6] walked-up-to-current,
 *   bg-[#10b981] fully completed
 *
 * Click-back: completed step circles are clickable; pending steps are not
 * (the form's own validation gates Continue, the indicator just respects it).
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
                                ? "bg-[#10b981]"
                                : isCurrent
                                ? "bg-[#3b82f6]"
                                : "bg-[#27272a]"
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
                                            ? "bg-[#10b981] text-white"
                                            : isCurrent
                                            ? "bg-[#3b82f6] text-white"
                                            : "border border-[#27272a] text-[#52525b]"
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
                                    ? "text-[#3b82f6]"
                                    : completedSteps.includes(s.id)
                                    ? "text-[#71717a]"
                                    : "text-[#52525b]"
                            }
                        `}
                    >
                        {s.label}
                    </div>
                ))}
            </div>

            {/* Step pane */}
            <div className="bg-[#111113] border border-[#27272a] rounded-md p-8">
                {children}
            </div>
        </div>
    );
}
