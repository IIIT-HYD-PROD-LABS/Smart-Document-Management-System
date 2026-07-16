"use client";

/**
 * SourceFilterChip — D-25 reusable source filter.
 *
 * Renders a 4-option chip group: All / Manual / Portal / Gmail.
 * Built for /dashboard/email/bills, /dashboard/documents, and the
 * compliance notice list (Plan 09-07). Single source of truth so
 * all three surfaces stay in sync visually.
 */
export type SourceFilterValue =
    | "all"
    | "manual"
    | "portal"
    | "gmail"
    | "google_drive";

const OPTIONS: { value: SourceFilterValue; label: string }[] = [
    { value: "all", label: "All" },
    { value: "manual", label: "Manual" },
    { value: "portal", label: "Portal" },
    { value: "gmail", label: "Gmail" },
    { value: "google_drive", label: "Drive" },
];

interface Props {
    value: SourceFilterValue;
    onChange: (value: SourceFilterValue) => void;
    /** Optional aria-label for the chip group root. */
    label?: string;
}

export default function SourceFilterChip({
    value,
    onChange,
    label = "Source filter",
}: Props) {
    return (
        <div
            role="radiogroup"
            aria-label={label}
            className="
                inline-flex items-center p-0.5 rounded-md
                bg-[var(--bg-elevated)] border border-[var(--border-default)]
            "
        >
            {OPTIONS.map((opt) => {
                const active = opt.value === value;
                return (
                    <button
                        key={opt.value}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        onClick={() => onChange(opt.value)}
                        className={`
                            px-3 py-1 rounded text-[12px] font-medium
                            transition-colors duration-150
                            ${
                                active
                                    ? "bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-[var(--shadow-sm)]"
                                    : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                            }
                        `}
                        data-source={opt.value}
                    >
                        {opt.label}
                    </button>
                );
            })}
        </div>
    );
}

export { OPTIONS as SOURCE_FILTER_OPTIONS };
