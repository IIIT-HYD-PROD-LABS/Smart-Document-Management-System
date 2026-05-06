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
                    rounded border border-[#1f1f23] bg-[#0c0c0f]
                    px-4 py-3 text-sm text-[#71717a]
                    flex items-start gap-2
                "
            >
                <FiInfo className="w-4 h-4 mt-0.5 shrink-0" />
                <div>
                    <div className="text-[13px] text-white font-medium">
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

    const tierColor = TIER_CONFIG[tier]?.color ?? "#71717a";
    const tierLabel = TIER_CONFIG[tier]?.label ?? tier;
    const safeFactors = factors ?? [];

    return (
        <details
            className="
                group rounded border border-[#1f1f23] bg-[#0c0c0f]
                open:border-[#2a2a30]
            "
        >
            <summary
                className="
                    list-none cursor-pointer select-none px-4 py-3
                    flex items-center justify-between gap-3
                    rounded
                    hover:bg-[#0f0f12]
                    focus-visible:outline-none focus-visible:ring-2
                    focus-visible:ring-[#3b82f6] focus-visible:ring-offset-2
                    focus-visible:ring-offset-[#09090b]
                "
            >
                <span className="flex items-center gap-3 min-w-0">
                    <RiskTierDot tier={tier} />
                    <span className="text-[13px] font-medium text-white">
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
                            backgroundColor: `${tierColor}1a`,
                            color: tierColor,
                        }}
                    >
                        {tierLabel}
                    </span>
                </span>
                <FiChevronRight
                    className="w-4 h-4 text-[#71717a] shrink-0 transition-transform group-open:rotate-90"
                />
            </summary>
            <div className="px-4 pb-4 pt-0 border-t border-[#1f1f23]">
                <p className="text-xs text-[#a1a1aa] mt-3 mb-3 leading-relaxed">
                    Top contributing factors:
                </p>
                {safeFactors.length === 0 ? (
                    <p className="text-xs text-[#71717a] italic">
                        No explanatory factors persisted for this notice.
                    </p>
                ) : (
                    <ol className="space-y-2 text-[13px] text-[#d4d4d8]">
                        {safeFactors.slice(0, 3).map((f, idx) => (
                            <li
                                key={`${f.feature}-${idx}`}
                                className="flex gap-3"
                            >
                                <span className="font-mono tabular-nums text-[11px] text-[#71717a] mt-0.5 w-5 shrink-0">
                                    {idx + 1}.
                                </span>
                                <span className="leading-relaxed">{f.phrase}</span>
                            </li>
                        ))}
                    </ol>
                )}
                {(modelVersion || scoredAt) && (
                    <div className="mt-4 pt-3 border-t border-[#1f1f23] flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-[#71717a]">
                        {modelVersion && (
                            <span>
                                Model:{" "}
                                <span className="font-mono text-[#a1a1aa]">
                                    {modelVersion}
                                </span>
                            </span>
                        )}
                        {scoredAt && (
                            <span>
                                Scored:{" "}
                                <span className="font-mono text-[#a1a1aa]">
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
