"use client";

import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FiTrash2, FiPlus } from "react-icons/fi";
import {
    useOnboardingWizard,
    type WizardRegistration,
} from "@/stores/onboardingWizardStore";

/**
 * Wizard Step 2 — Registrations.
 *
 * GSTIN format: 15 chars — 2-digit state + 10-char PAN + 1-digit entity + Z + 1 check char.
 * PAN  format: 10 chars — 5 letters + 4 digits + 1 letter (per Income Tax structure).
 * CIN  format: 21 chars — L|U + 5 digits + 2-letter state + 4 digit year + 3 letters + 6 digits.
 * DIN  format: 8 digits.
 *
 * Per RESEARCH Pattern 6: we use useFieldArray for the dynamic list. Validation
 * uses superRefine for per-row format checks (Zod's array.min ensures at least
 * one entry overall).
 */
const GSTIN_RX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
const PAN_RX = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
const CIN_RX = /^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$/;
const DIN_RX = /^[0-9]{8}$/;

const regSchema = z.object({
    type: z.enum(["GSTIN", "PAN", "CIN", "DIN"]),
    value: z.string().min(1, "Required"),
    state: z.string().optional().or(z.literal("")),
});

const schema = z.object({
    registrations: z
        .array(regSchema)
        .min(1, "Add at least one registration")
        .superRefine((arr, ctx) => {
            arr.forEach((reg, i) => {
                const v = (reg.value ?? "").toUpperCase();
                if (reg.type === "GSTIN" && !GSTIN_RX.test(v)) {
                    ctx.addIssue({
                        code: "custom",
                        path: [i, "value"],
                        message:
                            "GSTIN must be 15 chars: 2-digit state + 10-char PAN + 1-digit entity + Z + 1 check char. Example: 27AAAAA0000A1Z5.",
                    });
                }
                if (reg.type === "PAN" && !PAN_RX.test(v)) {
                    ctx.addIssue({
                        code: "custom",
                        path: [i, "value"],
                        message:
                            "Invalid PAN. Expected 10 chars: 5 letters + 4 digits + 1 letter. Example: AAAAA0000A.",
                    });
                }
                if (reg.type === "CIN" && !CIN_RX.test(v)) {
                    ctx.addIssue({
                        code: "custom",
                        path: [i, "value"],
                        message:
                            "Invalid CIN. Expected 21 chars: L|U + 5 digits + 2-letter state + 4 digit year + 3 letters + 6 digits.",
                    });
                }
                if (reg.type === "DIN" && !DIN_RX.test(v)) {
                    ctx.addIssue({
                        code: "custom",
                        path: [i, "value"],
                        message: "Invalid DIN. Expected 8 digits.",
                    });
                }
            });
        }),
});

type FormValues = z.infer<typeof schema>;

export function StepRegistrations() {
    const {
        registrations,
        setRegistrations,
        setStep,
        markComplete,
    } = useOnboardingWizard();

    const { register, control, handleSubmit, formState, getValues } =
        useForm<FormValues>({
            resolver: zodResolver(schema),
            defaultValues: {
                registrations:
                    registrations.length > 0
                        ? registrations
                        : [{ type: "GSTIN", value: "", state: "" }],
            },
            mode: "onSubmit",
        });

    const { fields, append, remove } = useFieldArray({
        control,
        name: "registrations",
    });

    const onSubmit = (values: FormValues) => {
        // Normalise: uppercase the value, drop empty optional fields
        const cleaned: WizardRegistration[] = values.registrations.map(
            (r) => ({
                type: r.type,
                value: r.value.toUpperCase(),
                state: r.state || undefined,
            })
        );
        setRegistrations(cleaned);
        markComplete(2);
        setStep(3);
    };

    return (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div>
                <h1 className="text-lg font-semibold text-white mb-2">
                    Registrations
                </h1>
                <p className="text-[#71717a] text-sm">
                    Add GSTINs, PAN, CIN, and DIN. Multi-state operations? Add
                    one GSTIN per state.
                </p>
            </div>

            <div className="space-y-3">
                {fields.map((field, idx) => {
                    // Compute placeholder based on the current row's type so it
                    // updates as the user changes the dropdown. Per RESEARCH:
                    // getValues() is the documented React 19 + RHF v7 pattern.
                    const currentType = getValues(
                        `registrations.${idx}.type`
                    );
                    const placeholder =
                        currentType === "GSTIN"
                            ? "27AAAAA0000A1Z5"
                            : currentType === "PAN"
                            ? "AAAAA0000A"
                            : currentType === "CIN"
                            ? "U12345MH2020PLC123456"
                            : "12345678";
                    return (
                        <div key={field.id} className="flex gap-2 items-start">
                            <select
                                {...register(`registrations.${idx}.type`)}
                                aria-label="Registration type"
                                className="
                                    px-3 py-2 rounded-md
                                    bg-[#18181b] border border-[#27272a] text-white text-sm w-28
                                    focus:outline-none focus:border-[#3b82f6]/40
                                "
                            >
                                <option value="GSTIN">GSTIN</option>
                                <option value="PAN">PAN</option>
                                <option value="CIN">CIN</option>
                                <option value="DIN">DIN</option>
                            </select>
                            <div className="flex-1">
                                <input
                                    {...register(
                                        `registrations.${idx}.value`
                                    )}
                                    aria-label="Registration value"
                                    aria-invalid={Boolean(
                                        formState.errors.registrations?.[idx]
                                            ?.value
                                    )}
                                    className="
                                        w-full px-3 py-2 rounded-md uppercase
                                        bg-[#18181b] border border-[#27272a] text-white text-sm tabular-nums
                                        focus:outline-none focus:border-[#3b82f6]/40
                                        focus:ring-2 focus:ring-[#3b82f6]/20
                                    "
                                    placeholder={placeholder}
                                />
                                {formState.errors.registrations?.[idx]
                                    ?.value && (
                                    <p className="mt-1 text-xs text-[#ef4444]">
                                        {
                                            formState.errors.registrations[
                                                idx
                                            ]?.value?.message
                                        }
                                    </p>
                                )}
                            </div>
                            {fields.length > 1 && (
                                <button
                                    type="button"
                                    onClick={() => remove(idx)}
                                    className="p-2.5 text-[#71717a] hover:text-[#ef4444] transition-colors"
                                    aria-label="Remove registration"
                                >
                                    <FiTrash2 className="w-4 h-4" />
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>

            <button
                type="button"
                onClick={() =>
                    append({ type: "GSTIN", value: "", state: "" })
                }
                className="text-[13px] text-[#3b82f6] hover:underline flex items-center gap-1 transition-colors"
            >
                <FiPlus className="w-3.5 h-3.5" />
                Add registration
            </button>

            {/* Top-level array error (e.g., "at least one registration") */}
            {formState.errors.registrations &&
                !Array.isArray(formState.errors.registrations) && (
                    <p className="text-xs text-[#ef4444]">
                        {formState.errors.registrations.message}
                    </p>
                )}

            <div className="flex justify-between gap-2 pt-4">
                <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="px-4 py-2 rounded-md text-[#a1a1aa] text-sm hover:text-white transition-colors"
                >
                    Back
                </button>
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
