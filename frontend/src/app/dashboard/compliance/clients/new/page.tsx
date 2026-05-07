"use client";

import { useEffect, useState } from "react";
import { useOnboardingWizard } from "@/stores/onboardingWizardStore";
import { WizardLayout } from "@/components/compliance/OnboardingWizard/WizardLayout";
import { StepDetails } from "@/components/compliance/OnboardingWizard/StepDetails";
import { StepRegistrations } from "@/components/compliance/OnboardingWizard/StepRegistrations";
import { StepTeam } from "@/components/compliance/OnboardingWizard/StepTeam";
import { StepImport } from "@/components/compliance/OnboardingWizard/StepImport";

/**
 * Onboarding wizard page (D-16).
 *
 * The Zustand store auto-restores from localStorage on mount; if the user
 * was mid-wizard, we show a "Resume your previous onboarding session?" banner
 * with Resume (continue) / Discard (reset to step 1) actions.
 *
 * This satisfies WCAG 2.2 SC 3.3.7 (Redundant Entry) — users are not asked
 * to re-enter values they've already provided.
 */
export default function OnboardingPage() {
    const { step, reset } = useOnboardingWizard();
    const [showResume, setShowResume] = useState(false);

    // Show resume banner if user lands on page mid-wizard.
    // We track this in local state so dismissing it doesn't unmount the wizard.
    useEffect(() => {
        if (step > 1) setShowResume(true);
    }, [step]);

    return (
        <>
            {showResume && (
                <div className="max-w-2xl mx-auto mt-6 px-6">
                    <div
                        className="
                            flex items-center justify-between gap-3 p-3 rounded-md
                            bg-[var(--accent-soft)] border border-[var(--accent-edge)] text-sm
                        "
                        role="status"
                    >
                        <span className="text-[var(--accent)]">
                            Resume your previous onboarding session?
                        </span>
                        <div className="flex gap-2 flex-shrink-0">
                            <button
                                type="button"
                                onClick={() => {
                                    reset();
                                    setShowResume(false);
                                }}
                                className="px-3 py-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] text-xs transition-colors"
                            >
                                Discard
                            </button>
                            <button
                                type="button"
                                onClick={() => setShowResume(false)}
                                className="px-3 py-1 rounded bg-[var(--accent)] text-white text-xs hover:bg-[var(--accent-strong)] transition-colors"
                            >
                                Resume
                            </button>
                        </div>
                    </div>
                </div>
            )}
            <WizardLayout>
                {step === 1 && <StepDetails />}
                {step === 2 && <StepRegistrations />}
                {step === 3 && <StepTeam />}
                {step === 4 && <StepImport />}
            </WizardLayout>
        </>
    );
}
