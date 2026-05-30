"use client";

import { FiChevronRight, FiInfo } from "react-icons/fi";
import type { RiskFactor, RiskTier } from "@/types/compliance";
import { TIER_CONFIG, RiskTierDot } from "./RiskTierDot";

/**
 * "Why this risk score?" expandable panel — Phase 10 Plan 03.
 *
 * Renders the rule-based scorer's SHAP-style explanations as a 3-bullet list.
 * Designed as a <details> element so it works without JS (progressive
 * enhancement) and matches the existing notice-detail-page minimalism.
 *
 * Empty state: notices that haven't been scored yet (risk_score === null,
 * model_version === null) show a muted "Risk score pending" note instead
 * of an empty panel.
 */
interface WhyThisRiskScoreProps {
    score: number | null;
    tier: RiskTier | null;
    factors: RiskFactor[] | null | undefined;
    modelVersion: string | null;
    scoredAt: string | null;
}

export function WhyThisRiskScore({
    score,
    tier,
    factors,
    modelVersion,
    scoredAt,
}: WhyThisRiskScoreProps) {
    if (score === null || tier === null) {
        return (
            <div
                className="
                    rounded border border-[var(--border-default)] bg-[var(--bg-elevated)]
                    px-4 py-3 text-sm text-[var(--text-muted)]
                    flex items-start gap-2
                "
            >
                <FiInfo className="w-4 h-4 mt-0.5 shrink-0" />
                <div>
                    <div className="text-[13px] text-[var(--text-primary)] font-medium">
                        Risk score pending
                    </div>
                    <p className="text-xs leading-relaxed mt-1">
                        Risk scoring runs automatically when this notice
                        transitions from <span className="font-mono">received</span>{" "}
                        to <span className="font-mono">under_review</span>.
                    </p>
                </div>
            </div>
        );
    }

    const tierColor = TIER_CONFIG[tier]?.textColor ?? "var(--text-muted)";
    const tierLabel = TIER_CONFIG[tier]?.label ?? tier;
    const safeFactors = factors ?? [];

    return (
        <details
            className="
                group rounded border border-[var(--border-default)] bg-[var(--bg-elevated)]
                open:border-[var(--border-emphasis)]
            "
        >
            <summary
                className="
                    list-none cursor-pointer select-none px-4 py-3
                    flex items-center justify-between gap-3
                    rounded
                    hover:bg-[var(--bg-hover)]
                    focus-visible:outline-none focus-visible:ring-2
                    focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2
                    focus-visible:ring-offset-[var(--bg-page)]
                "
            >
                <span className="flex items-center gap-3 min-w-0">
                    <RiskTierDot tier={tier} />
                    <span className="text-[13px] font-medium text-[var(--text-primary)]">
                        Risk score
                    </span>
                    <span
                        className="font-mono tabular-nums text-[15px]"
                        style={{ color: tierColor }}
                    >
                        {score.toFixed(1)}
                    </span>
                    <span
                        className="
                            text-[11px] uppercase tracking-wider font-semibold
                            px-1.5 py-0.5 rounded
                        "
                        style={{
                            backgroundColor: `color-mix(in srgb, ${tierColor} 12%, transparent)`,
                            color: tierColor,
                        }}
                    >
                        {tierLabel}
                    </span>
                </span>
                <FiChevronRight
                    className="w-4 h-4 text-[var(--text-muted)] shrink-0 transition-transform group-open:rotate-90"
                />
            </summary>
            <div className="px-4 pb-4 pt-0 border-t border-[var(--border-default)]">
                <p className="text-xs text-[var(--text-secondary)] mt-3 mb-3 leading-relaxed">
                    Top contributing factors:
                </p>
                {safeFactors.length === 0 ? (
                    <p className="text-xs text-[var(--text-muted)] italic">
                        No explanatory factors persisted for this notice.
                    </p>
                ) : (
                    <ol className="space-y-2 text-[13px] text-[var(--text-secondary)]">
                        {safeFactors.slice(0, 3).map((f, idx) => (
                            <li
                                key={`${f.feature}-${idx}`}
                                className="flex gap-3"
                            >
                                <span className="font-mono tabular-nums text-[11px] text-[var(--text-muted)] mt-0.5 w-5 shrink-0">
                                    {idx + 1}.
                                </span>
                                <span className="leading-relaxed">{f.phrase}</span>
                            </li>
                        ))}
                    </ol>
                )}
                {(modelVersion || scoredAt) && (
                    <div className="mt-4 pt-3 border-t border-[var(--border-default)] flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-[var(--text-muted)]">
                        {modelVersion && (
                            <span>
                                Model:{" "}
                                <span className="font-mono text-[var(--text-secondary)]">
                                    {modelVersion}
                                </span>
                            </span>
                        )}
                        {scoredAt && (
                            <span>
                                Scored:{" "}
                                <span className="font-mono text-[var(--text-secondary)]">
                                    {new Date(scoredAt).toLocaleString()}
                                </span>
                            </span>
                        )}
                    </div>
                )}
            </div>
        </details>
    );
}
