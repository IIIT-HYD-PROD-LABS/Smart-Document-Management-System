"use client";

import type { RiskTier } from "@/types/compliance";

/**
 * Risk Tier indicator — Phase 10 Plan 03.
 *
 * Phase 9 originally rendered a hollow gray circle + em-dash for unscored
 * notices. Phase 10 reuses that same slot for the four real tiers. Critical
 * gets a subtle motion-safe pulse (animate-pulse) so the most-urgent rows
 * draw the eye without flashing — vestibular-safe via `motion-safe:`.
 *
 * Color contract (matches CONTEXT D-14 + 09-UI-SPEC):
 *   critical → #ef4444  (red)
 *   high     → #f97316  (orange)
 *   medium   → #f59e0b  (amber)
 *   low      → #10b981  (emerald)
 *   null/undefined → unscored stub (preserves Phase 9 behaviour)
 */
const TIER_CONFIG: Record<RiskTier, { color: string; label: string }> = {
    critical: { color: "#ef4444", label: "Critical" },
    high: { color: "#f97316", label: "High" },
    medium: { color: "#f59e0b", label: "Medium" },
    low: { color: "#10b981", label: "Low" },
};

interface RiskTierDotProps {
    tier?: RiskTier | null;
    showLabel?: boolean;
}

export function RiskTierDot({ tier, showLabel = false }: RiskTierDotProps) {
    if (!tier) {
        return (
            <span
                className="inline-flex items-center gap-1.5"
                aria-label="Risk tier: unscored"
            >
                <span className="w-2 h-2 rounded-full border border-[#71717a]" />
                <span className="text-[#71717a] text-xs">—</span>
            </span>
        );
    }

    const cfg = TIER_CONFIG[tier];
    const dotClass =
        tier === "critical"
            ? "w-2 h-2 rounded-full motion-safe:animate-pulse"
            : "w-2 h-2 rounded-full";

    return (
        <span
            className="inline-flex items-center gap-1.5"
            aria-label={`Risk tier: ${cfg.label}`}
        >
            <span
                className={dotClass}
                style={{ backgroundColor: cfg.color }}
            />
            {showLabel ? (
                <span
                    className="text-xs font-medium"
                    style={{ color: cfg.color }}
                >
                    {cfg.label}
                </span>
            ) : (
                <span className="sr-only">{cfg.label}</span>
            )}
        </span>
    );
}

export { TIER_CONFIG };
