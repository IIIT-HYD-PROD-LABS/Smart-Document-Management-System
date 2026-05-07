"use client";

interface ConfidenceBadgeProps {
    score: number;
    variant?: "badge" | "display";
}

export function ConfidenceBadge({ score, variant = "badge" }: ConfidenceBadgeProps) {
    if (score <= 0) return null;
    const pct = Math.round(score * 100);

    // Pick color band by confidence score
    let token: "success" | "warning" | "danger";
    let label: "High" | "Medium" | "Low";
    if (score >= 0.8)      { token = "success"; label = "High"; }
    else if (score >= 0.5) { token = "warning"; label = "Medium"; }
    else                   { token = "danger";  label = "Low"; }

    const color = `var(--${token})`;
    const softBg = `var(--${token}-soft)`;

    if (variant === "display") {
        return (
            <span className="text-2xl font-semibold tabular-nums" style={{ color }}>
                {pct}%
            </span>
        );
    }

    return (
        <span
            className="inline-flex items-center text-[11px] px-2 py-0.5 rounded font-medium border tabular-nums"
            style={{ background: softBg, color, borderColor: `color-mix(in srgb, ${color} 25%, transparent)` }}
            title={`${label} confidence`}
        >
            {pct}%
        </span>
    );
}
