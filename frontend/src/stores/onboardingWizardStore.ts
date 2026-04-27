"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
    ComplianceRole,
    RegistrationType,
    ClientType,
} from "@/types/compliance";

/**
 * Zustand store for the 4-step client onboarding wizard (D-16).
 *
 * Persisted to localStorage so users can resume after a refresh (WCAG 2.2 — 3.3.7
 * Redundant Entry — users are not asked to re-enter data they've already provided).
 *
 * Per RESEARCH Pattern 6: react-hook-form's getValues() drives per-step submission;
 * we never call watch() at the form level (incompatible with React 19 + RHF v7 in
 * some edge cases). On step submit, RHF's onSubmit handler stuffs the validated
 * values into this store; the next step reads from the store as defaultValues.
 */
export interface WizardDetails {
    name: string;
    client_type: ClientType;
    industry?: string;
    primary_contact_email?: string;
}

export interface WizardRegistration {
    type: RegistrationType;
    value: string;
    state?: string;
}

export interface WizardTeamMember {
    user_id: number;
    compliance_role: ComplianceRole;
    access_start?: string;
    access_end?: string;
}

interface OnboardingWizardState {
    step: 1 | 2 | 3 | 4;
    details: WizardDetails | null;
    registrations: WizardRegistration[];
    team: WizardTeamMember[];
    // Tracks which steps the user has validated and committed (for click-back UX).
    completedSteps: number[];
    setStep: (s: 1 | 2 | 3 | 4) => void;
    setDetails: (d: WizardDetails) => void;
    setRegistrations: (r: WizardRegistration[]) => void;
    setTeam: (t: WizardTeamMember[]) => void;
    markComplete: (s: number) => void;
    reset: () => void;
}

export const useOnboardingWizard = create<OnboardingWizardState>()(
    persist(
        (set, get) => ({
            step: 1,
            details: null,
            registrations: [],
            team: [],
            completedSteps: [],
            setStep: (step) => set({ step }),
            setDetails: (details) => set({ details }),
            setRegistrations: (registrations) => set({ registrations }),
            setTeam: (team) => set({ team }),
            markComplete: (s) => {
                const completed = get().completedSteps;
                if (!completed.includes(s)) {
                    set({ completedSteps: [...completed, s] });
                }
            },
            reset: () =>
                set({
                    step: 1,
                    details: null,
                    registrations: [],
                    team: [],
                    completedSteps: [],
                }),
        }),
        { name: "compliance-onboarding-wizard" }
    )
);
