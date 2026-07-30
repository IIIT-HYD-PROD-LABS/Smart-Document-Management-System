"use client";

import { useQuery } from "@tanstack/react-query";
import { FiTrendingUp, FiTrendingDown, FiMinus } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import { useCurrentClient } from "@/stores/currentClientStore";

/**
 * Compliance Score chip — Phase 11 D-14.
 *
 * Shows the rolling 90-day on-time filing percentage. Color-coded:
 *   ≥90 green, 70-89 amber, <70 red. Score formula is "% on time"
 *   per RESEARCH-FINAL §5 (severity-weighted variants ship in v2.1).
 */
export function ComplianceScoreChip() {
    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const scoreQ = useQuery({
        enabled: activeClientId !== null,
        queryKey: ["compliance-score-90d"],
        queryFn: async () => {
            const { data } = await complianceApi.getComplianceScore(90);
            return data;
        },
        staleTime: 5 * 60 * 1000,
    });

    if (scoreQ.isLoading || !scoreQ.data) {
        return (
            <div className="hidden md:inline-flex items-center gap-1.5 px-3 h-8 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-default)]">
                <div className="w-12 h-3 bg-[var(--bg-hover)] rounded animate-pulse" />
            </div>
        );
    }

    const { score, notices_total } = scoreQ.data;
    const color =
        score >= 90
            ? "var(--success)"
            : score >= 70
                ? "var(--warning)"
                : "var(--danger)";
    const Icon =
        score >= 90 ? FiTrendingUp : score >= 70 ? FiMinus : FiTrendingDown;

    return (
        <div
            className="
                hidden md:inline-flex items-center gap-2 px-3 h-8
                rounded-md border bg-[var(--bg-elevated)]
            "
            style={{ borderColor: `color-mix(in srgb, ${color} 30%, transparent)` }}
            aria-label={`Compliance score ${score}% over rolling 90 days based on ${notices_total} notices`}
            title={`${notices_total} notices in 90-day window`}
        >
            <Icon className="w-3.5 h-3.5" style={{ color }} />
            <span className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
                90d
            </span>
            <span
                className="text-[13px] font-semibold tabular-nums"
                style={{ color }}
            >
                {score.toFixed(1)}%
            </span>
        </div>
    );
}
