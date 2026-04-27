"use client";

/**
 * Risk Tier indicator (Phase 9 stub).
 *
 * UI-SPEC § "Risk Tier Color Contract" reserves this slot now so Phase 10's
 * BERT classifier + risk scoring can drop in tier badges (critical / high /
 * medium / low) with zero notice-table reflow.
 *
 * Phase 9 ALWAYS renders the unscored placeholder: a hollow gray circle plus
 * an em-dash inside an 80px column. ARIA-label "Risk tier: unscored".
 *
 * Phase 10 will swap this to a tier-aware variant:
 *   critical → #ef4444 filled dot + "Critical" badge
 *   high     → #f97316 filled dot + "High" badge
 *   medium   → #f59e0b filled dot + "Medium" badge
 *   low      → #10b981 filled dot + "Low" badge
 */
export function RiskTierDot() {
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
