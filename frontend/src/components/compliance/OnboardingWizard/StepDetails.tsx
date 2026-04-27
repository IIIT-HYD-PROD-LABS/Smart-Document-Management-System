"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
    useOnboardingWizard,
    type WizardDetails,
} from "@/stores/onboardingWizardStore";

/**
 * Wizard Step 1 — basic client details.
 *
 * Per RESEARCH Pattern 6: we use react-hook-form's onSubmit handler (which
 * passes validated values explicitly) rather than form-level watch().
 * `formState.isValid` + `trigger()` would be alternatives, but onSubmit is
 * the simplest path here since each step is a self-contained form.
 */
const schema = z.object({
    name: z
        .string()
        .min(2, "Client name must be at least 2 characters")
        .max(200, "Client name must be 200 characters or fewer"),
    client_type: z.enum([
        "pvt_ltd",
        "llp",
        "partnership",
        "sole_prop",
        "opc",
    ]),
    industry: z.string().max(100).optional().or(z.literal("")),
    primary_contact_email: z
        .string()
        .email("Invalid email")
        .optional()
        .or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export function StepDetails() {
    const { details, setDetails, setStep, markComplete } =
        useOnboardingWizard();

    const { register, handleSubmit, formState } = useForm<FormValues>({
        resolver: zodResolver(schema),
        defaultValues: details ?? {
            name: "",
            client_type: "pvt_ltd",
            industry: "",
            primary_contact_email: "",
        },
        mode: "onSubmit",
    });

    const onSubmit = (values: FormValues) => {
        // Strip empty strings to undefined for the optional fields so the
        // backend gets clean payloads.
        const cleaned: WizardDetails = {
            name: values.name,
            client_type: values.client_type,
            industry: values.industry || undefined,
            primary_contact_email:
                values.primary_contact_email || undefined,
        };
        setDetails(cleaned);
        markComplete(1);
        setStep(2);
    };

    return (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div>
                <h1 className="text-lg font-semibold text-white mb-2">
                    Client details
                </h1>
                <p className="text-[#71717a] text-sm">
                    Start with the basics. You&apos;ll add registrations and team
                    members in the next steps.
                </p>
            </div>

            <div>
                <label
                    htmlFor="wizard-name"
                    className="block text-[11px] font-medium uppercase tracking-wider text-[#a1a1aa] mb-2"
                >
                    Client name *
                </label>
                <input
                    id="wizard-name"
                    {...register("name")}
                    className="
                        w-full px-3 py-2 rounded-md
                        bg-[#18181b] border border-[#27272a] text-white text-sm
                        focus:outline-none focus:border-[#3b82f6]/40
                        focus:ring-2 focus:ring-[#3b82f6]/20
                    "
                    placeholder="Acme Pvt Ltd"
                    aria-invalid={Boolean(formState.errors.name)}
                />
                {formState.errors.name && (
                    <p className="mt-1 text-xs text-[#ef4444]">
                        {formState.errors.name.message}
                    </p>
                )}
            </div>

            <div>
                <label
                    htmlFor="wizard-client-type"
                    className="block text-[11px] font-medium uppercase tracking-wider text-[#a1a1aa] mb-2"
                >
                    Client type *
                </label>
                <select
                    id="wizard-client-type"
                    {...register("client_type")}
                    className="
                        w-full px-3 py-2 rounded-md
                        bg-[#18181b] border border-[#27272a] text-white text-sm
                        focus:outline-none focus:border-[#3b82f6]/40
                        focus:ring-2 focus:ring-[#3b82f6]/20
                    "
                >
                    <option value="pvt_ltd">Private Limited</option>
                    <option value="llp">Limited Liability Partnership</option>
                    <option value="partnership">Partnership</option>
                    <option value="sole_prop">Sole Proprietorship</option>
                    <option value="opc">One Person Company</option>
                </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label
                        htmlFor="wizard-industry"
                        className="block text-[11px] font-medium uppercase tracking-wider text-[#a1a1aa] mb-2"
                    >
                        Industry
                    </label>
                    <input
                        id="wizard-industry"
                        {...register("industry")}
                        className="
                            w-full px-3 py-2 rounded-md
                            bg-[#18181b] border border-[#27272a] text-white text-sm
                            focus:outline-none focus:border-[#3b82f6]/40
                            focus:ring-2 focus:ring-[#3b82f6]/20
                        "
                        placeholder="Manufacturing"
                    />
                </div>
                <div>
                    <label
                        htmlFor="wizard-email"
                        className="block text-[11px] font-medium uppercase tracking-wider text-[#a1a1aa] mb-2"
                    >
                        Primary contact email
                    </label>
                    <input
                        id="wizard-email"
                        type="email"
                        {...register("primary_contact_email")}
                        className="
                            w-full px-3 py-2 rounded-md
                            bg-[#18181b] border border-[#27272a] text-white text-sm
                            focus:outline-none focus:border-[#3b82f6]/40
                            focus:ring-2 focus:ring-[#3b82f6]/20
                        "
                        placeholder="cfo@acme.com"
                        aria-invalid={Boolean(
                            formState.errors.primary_contact_email
                        )}
                    />
                    {formState.errors.primary_contact_email && (
                        <p className="mt-1 text-xs text-[#ef4444]">
                            {formState.errors.primary_contact_email.message}
                        </p>
                    )}
                </div>
            </div>

            <div className="flex justify-end gap-2 pt-4">
                <button
                    type="submit"
                    className="
                        px-4 py-2 rounded-md bg-[#3b82f6] text-white text-sm font-medium
                        hover:bg-[#3b82f6]/90 transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40
                    "
                >
                    Continue
                </button>
            </div>
        </form>
    );
}
