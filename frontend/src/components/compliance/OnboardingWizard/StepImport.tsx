"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { FiUpload } from "react-icons/fi";
import { useOnboardingWizard } from "@/stores/onboardingWizardStore";
import { complianceApi } from "@/lib/api/compliance";
import { useCurrentClient } from "@/stores/currentClientStore";
import { extractErrorMessage } from "@/lib/api";

/**
 * Wizard Step 4 — Import (optional CSV) + final submit.
 *
 * Per UI-SPEC: CSV import is rendered as a "Coming in Phase X" empty state
 * (deferred to a future release) — NOT a TODO stub. The summary banner
 * shows what will be created on submit. "Create client" calls
 * complianceApi.onboardClient() which atomically creates Client + Registrations
 * + Memberships in a single transaction (Plan 03 service: client_service.onboard).
 *
 * On success: Zustand wizard state is reset, the new client is set as the
 * active client, and the user is redirected to the client detail page.
 */
export function StepImport() {
    const wizard = useOnboardingWizard();
    const router = useRouter();
    const { setActiveClientId } = useCurrentClient();
    const [submitting, setSubmitting] = useState(false);

    const onSubmit = async () => {
        if (!wizard.details) {
            toast.error("Please complete step 1 first");
            wizard.setStep(1);
            return;
        }
        if (wizard.registrations.length === 0) {
            toast.error("Please add at least one registration in step 2");
            wizard.setStep(2);
            return;
        }
        setSubmitting(true);
        try {
            const { data: client } = await complianceApi.onboardClient({
                details: wizard.details,
                registrations: wizard.registrations,
                team: wizard.team,
            });
            toast.success(`Onboarded ${client.name}`);
            setActiveClientId(client.id);
            wizard.reset();
            router.push(`/dashboard/compliance/clients/${client.id}`);
        } catch (err) {
            toast.error(extractErrorMessage(err, "Failed to onboard client"));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-lg font-semibold text-white mb-2">
                    Import (optional)
                </h1>
                <p className="text-[#71717a] text-sm">
                    CSV import for existing notices is coming in a future
                    release. For now, you can skip and finish onboarding —
                    you&apos;ll upload notices one by one.
                </p>
            </div>

            <div className="rounded-md border border-dashed border-[#27272a] p-12 text-center">
                <FiUpload className="w-8 h-8 mx-auto text-[#52525b] mb-3" />
                <p className="text-[#a1a1aa] text-sm mb-1">
                    CSV import will land in a future release
                </p>
                <p className="text-[#71717a] text-xs mb-4">
                    For now, upload notices individually after onboarding.
                </p>
                <button
                    type="button"
                    disabled
                    className="px-3 py-1.5 rounded-md bg-[#18181b] text-[#52525b] text-sm cursor-not-allowed border border-[#27272a]"
                    aria-disabled="true"
                >
                    Upload CSV (coming soon)
                </button>
            </div>

            {/* Review summary */}
            <div className="rounded-md bg-[#3b82f6]/10 border border-[#3b82f6]/20 p-4 text-sm text-[#a1a1aa]">
                <p className="text-[11px] uppercase tracking-wider text-[#3b82f6] mb-1">
                    Review
                </p>
                <p>
                    <span className="text-white">
                        {wizard.details?.name ?? "(no name)"}
                    </span>
                    {" — "}
                    {wizard.registrations.length} registration
                    {wizard.registrations.length === 1 ? "" : "s"}
                    {", "}
                    {wizard.team.length} team member
                    {wizard.team.length === 1 ? "" : "s"}
                </p>
            </div>

            <div className="flex justify-between gap-2 pt-4">
                <button
                    type="button"
                    onClick={() => wizard.setStep(3)}
                    disabled={submitting}
                    className="px-4 py-2 rounded-md text-[#a1a1aa] text-sm hover:text-white transition-colors disabled:opacity-50"
                >
                    Back
                </button>
                <button
                    type="button"
                    onClick={onSubmit}
                    disabled={submitting}
                    className="
                        px-4 py-2 rounded-md bg-[#3b82f6] text-white text-sm font-medium
                        hover:bg-[#3b82f6]/90 transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40
                        disabled:opacity-60 disabled:cursor-not-allowed
                    "
                >
                    {submitting ? "Creating…" : "Create client"}
                </button>
            </div>
        </div>
    );
}
