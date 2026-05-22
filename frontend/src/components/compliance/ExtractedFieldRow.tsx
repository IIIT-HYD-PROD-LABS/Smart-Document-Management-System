"use client";

import { FiAlertTriangle, FiCheck, FiInfo, FiX } from "react-icons/fi";
import type { ExtractedFieldDto } from "@/lib/api/compliance";

/**
 * Per-field row in the upload-first /notices/new flow — Phase 17 D-27.
 *
 * Wraps the field's input with a confidence pill (D-08 thresholds) and a
 * discard button. Editing is direct (the input is always editable); a
 * "user-edited" indicator appears when the value diverges from the
 * extracted value, so the audit row written on accept can record
 * `was_edited=true` per D-17.
 */

type Tone = "high" | "medium" | "low" | "edited" | "manual";

const TONE: Record<
    Tone,
    {
        label: string;
        chipBg: string;
        chipText: string;
        chipBorder: string;
        icon: React.ComponentType<{ className?: string }>;
    }
> = {
    high: {
        label: "Confident",
        chipBg: "bg-emerald-500/10",
        chipText: "text-emerald-700 dark:text-emerald-300",
        chipBorder: "border-emerald-500/30",
        icon: FiCheck,
    },
    medium: {
        label: "Review",
        chipBg: "bg-amber-500/10",
        chipText: "text-amber-700 dark:text-amber-300",
        chipBorder: "border-amber-500/30",
        icon: FiInfo,
    },
    low: {
        label: "Needs review",
        chipBg: "bg-rose-500/10",
        chipText: "text-rose-700 dark:text-rose-300",
        chipBorder: "border-rose-500/30",
        icon: FiAlertTriangle,
    },
    edited: {
        label: "Edited",
        chipBg: "bg-[var(--bg-hover)]",
        chipText: "text-[var(--text-secondary)]",
        chipBorder: "border-[var(--border-default)]",
        icon: FiCheck,
    },
    manual: {
        label: "Manual",
        chipBg: "bg-[var(--bg-elevated)]",
        chipText: "text-[var(--text-muted)]",
        chipBorder: "border-[var(--border-default)]",
        icon: FiCheck,
    },
};

function toneFor(confidence: number): Tone {
    if (confidence >= 0.75) return "high";
    if (confidence >= 0.55) return "medium";
    return "low";
}

interface Props {
    label: string;
    inputId: string;
    children: React.ReactNode;
    extracted?: ExtractedFieldDto | null;
    edited?: boolean;
    discarded?: boolean;
    onDiscard?: () => void;
    onRestore?: () => void;
}

export function ExtractedFieldRow({
    label,
    inputId,
    children,
    extracted,
    edited = false,
    discarded = false,
    onDiscard,
    onRestore,
}: Props) {
    let tone: Tone | null = null;
    let confidenceText = "";
    if (discarded) {
        tone = null;
    } else if (!extracted) {
        tone = "manual";
    } else if (edited) {
        tone = "edited";
        confidenceText = `Originally ${Math.round(extracted.confidence * 100)}%`;
    } else {
        tone = toneFor(extracted.confidence);
        confidenceText = `${Math.round(extracted.confidence * 100)}%`;
    }

    const cfg = tone ? TONE[tone] : null;
    const Icon = cfg?.icon;

    const tooltipBits: string[] = [];
    if (extracted?.source_span) tooltipBits.push(`Source: "${extracted.source_span}"`);
    if (extracted?.validation_failure) tooltipBits.push(`Issue: ${extracted.validation_failure}`);
    if (extracted?.original_confidence !== undefined && extracted?.original_confidence !== null) {
        tooltipBits.push(
            `Model: ${Math.round(extracted.original_confidence * 100)}% → Validated: ${Math.round(extracted.confidence * 100)}%`,
        );
    }
    const tooltip = tooltipBits.join("\n");

    return (
        <div>
            <div className="flex items-center justify-between mb-1.5">
                <label
                    htmlFor={inputId}
                    className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]"
                >
                    {label}
                </label>
                <div className="flex items-center gap-1.5">
                    {cfg && Icon ? (
                        <span
                            className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-[1px] text-[10px] ${cfg.chipBg} ${cfg.chipText} ${cfg.chipBorder}`}
                            title={tooltip || cfg.label}
                            aria-label={`${cfg.label}${confidenceText ? ` ${confidenceText}` : ""}`}
                        >
                            <Icon className="w-2.5 h-2.5" aria-hidden="true" />
                            {cfg.label}
                            {confidenceText ? (
                                <span className="tabular-nums opacity-70 ml-0.5">
                                    {confidenceText}
                                </span>
                            ) : null}
                        </span>
                    ) : null}
                    {extracted?.validation_failure && !discarded ? (
                        <span
                            className="inline-flex items-center text-rose-600 dark:text-rose-400"
                            title={extracted.validation_failure}
                            aria-label={`Validation: ${extracted.validation_failure}`}
                        >
                            <FiAlertTriangle className="w-3 h-3" />
                        </span>
                    ) : null}
                    {extracted && !discarded && onDiscard ? (
                        <button
                            type="button"
                            onClick={onDiscard}
                            className="inline-flex items-center justify-center w-5 h-5 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] cursor-pointer transition-colors"
                            title="Discard extracted value"
                            aria-label="Discard extracted value"
                        >
                            <FiX className="w-3 h-3" />
                        </button>
                    ) : null}
                    {discarded && extracted && onRestore ? (
                        <button
                            type="button"
                            onClick={onRestore}
                            className="text-[10px] text-[var(--accent)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded px-1 cursor-pointer"
                        >
                            Restore
                        </button>
                    ) : null}
                </div>
            </div>
            {children}
        </div>
    );
}
