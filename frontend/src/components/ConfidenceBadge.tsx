"use client";

interface ConfidenceBadgeProps {
    score: number;
    variant?: "badge" | "display";
}

export function ConfidenceBadge({ score, variant = "badge" }: ConfidenceBadgeProps) {
    if (score <= 0) return null;
    const pct = Math.round(score * 100);

    if (variant === "display") {
        let color: string;
        if (score >= 0.8) color = "text-[#10b981]";
        else if (score >= 0.5) color = "text-[#f59e0b]";
        else color = "text-[#ef4444]";
        return <span className={`text-2xl font-semibold ${color}`}>{pct}%</span>;
    }

    let colorClass: string;
    let label: string;
    if (score >= 0.8) {
        colorClass = "bg-[#10b981]/10 text-[#10b981]";
        label = "High";
    } else if (score >= 0.5) {
        colorClass = "bg-[#f59e0b]/10 text-[#f59e0b]";
        label = "Medium";
    } else {
        colorClass = "bg-[#ef4444]/10 text-[#ef4444]";
        label = "Low";
    }
    return (
        <span className={`text-[11px] px-2 py-0.5 rounded ${colorClass}`} title={`${label} confidence`}>
            {pct}%
        </span>
    );
}
