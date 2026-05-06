"use client";

import {
    FiCheckCircle,
    FiAlertCircle,
    FiAlertTriangle,
    FiUser,
} from "react-icons/fi";

/**
 * Confidence Badge — Phase 10 Plan 03.
 *
 * Renders a pill summarising classifier authority + type confidence.
 * v2.0: classifier confidences are NULL (BERT deferred to v2.1) — badge
 * shows "Manual entry · 100%" in muted gray.
 * v2.1: pill color encodes the worst of the two confidences:
 *   ≥ 0.90  → green  (FiCheckCircle)
 *   0.75-0.89 → amber (FiAlertCircle)
 *   < 0.75    → red   (FiAlertTriangle "Needs review")
 */
type ConfidenceBucket = "manual" | "high" | "medium" | "low";

const BUCKET_CONFIG: Record<
    ConfidenceBucket,
    {
        color: string;
        icon: React.ComponentType<{ className?: string }>;
        defaultLabel: string;
    }
> = {
    manual: { color: "#71717a", icon: FiUser, defaultLabel: "Manual entry" },
    high: { color: "#10b981", icon: FiCheckCircle, defaultLabel: "Confident" },
    medium: { color: "#f59e0b", icon: FiAlertCircle, defaultLabel: "Review" },
    low: { color: "#ef4444", icon: FiAlertTriangle, defaultLabel: "Needs review" },
};

function bucketFor(authConf: number | null, typeConf: number | null): ConfidenceBucket {
    if (authConf === null && typeConf === null) return "manual";
    const worst = Math.min(authConf ?? 1, typeConf ?? 1);
    if (worst >= 0.9) return "high";
    if (worst >= 0.75) return "medium";
    return "low";
}

interface ConfidenceBadgeProps {
    authorityConfidence: number | null;
    typeConfidence: number | null;
    authorityLabel?: string;
    typeLabel?: string;
    size?: "sm" | "md";
}

export function ConfidenceBadge({
    authorityConfidence,
    typeConfidence,
    authorityLabel,
    typeLabel,
    size = "sm",
}: ConfidenceBadgeProps) {
    const bucket = bucketFor(authorityConfidence, typeConfidence);
    const cfg = BUCKET_CONFIG[bucket];
    const Icon = cfg.icon;
    const padding = size === "md" ? "px-3 py-1.5" : "px-2 py-1";
    const text = size === "md" ? "text-[13px]" : "text-[11px]";

    let label: string;
    if (bucket === "manual") {
        label = cfg.defaultLabel;
    } else {
        const conf = Math.min(authorityConfidence ?? 1, typeConfidence ?? 1);
        const pct = Math.round(conf * 100);
        const tag = [authorityLabel, typeLabel].filter(Boolean).join(" · ");
        label = tag ? `${tag} · ${pct}%` : `${pct}%`;
    }

    const tooltip =
        bucket === "manual"
            ? "Notice classified by manual entry — BERT auto-classification ships in v2.1"
            : `Authority: ${formatConf(authorityConfidence)} · Type: ${formatConf(typeConfidence)}`;

    return (
        <span
            className={`inline-flex items-center gap-1 ${padding} ${text} rounded font-medium`}
            style={{ backgroundColor: `${cfg.color}1a`, color: cfg.color }}
            aria-label={`Classification confidence: ${label}`}
            title={tooltip}
        >
            <Icon className="w-3 h-3" />
            {label}
        </span>
    );
}

function formatConf(c: number | null): string {
    if (c === null) return "—";
    return `${Math.round(c * 100)}%`;
}
