"use client";

import {
    FiPieChart,
    FiDollarSign,
    FiBriefcase,
    FiCreditCard,
    FiTrendingUp,
} from "react-icons/fi";
import type { Authority } from "@/types/compliance";

/**
 * Maps each Authority to its UI-SPEC color hex, icon, and human label.
 *
 * UI-SPEC § "Authority Color Coding":
 *   GST   #06b6d4  FiPieChart      GST
 *   IT    #3b82f6  FiDollarSign    Income Tax
 *   MCA   #8b5cf6  FiBriefcase     MCA
 *   RBI   #ec4899  FiCreditCard    RBI
 *   SEBI  #f97316  FiTrendingUp    SEBI
 */
const AUTHORITY_CONFIG: Record<
    Authority,
    {
        /** Bright hue for the decorative icon / dot fill (theme-agnostic). */
        color: string;
        /** AA-passing foreground text color (token or dark brand hue). */
        text: string;
        icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
        label: string;
    }
> = {
    GST: { color: "#06b6d4", text: "var(--info)", icon: FiPieChart, label: "GST" },
    IT: { color: "#3b82f6", text: "var(--accent)", icon: FiDollarSign, label: "Income Tax" },
    MCA: { color: "#8b5cf6", text: "#6d28d9", icon: FiBriefcase, label: "MCA" },
    RBI: { color: "#ec4899", text: "#be185d", icon: FiCreditCard, label: "RBI" },
    SEBI: { color: "#f97316", text: "#c2410c", icon: FiTrendingUp, label: "SEBI" },
};

interface AuthorityBadgeProps {
    authority: Authority;
    size?: "sm" | "md";
}

export function AuthorityBadge({ authority, size = "sm" }: AuthorityBadgeProps) {
    const cfg = AUTHORITY_CONFIG[authority];
    const Icon = cfg.icon;
    const padding = size === "md" ? "px-3 py-1.5" : "px-2 py-1";
    const text = size === "md" ? "text-[13px]" : "text-[11px]";

    return (
        <span
            className={`inline-flex items-center gap-1 ${padding} ${text} rounded font-medium`}
            style={{
                backgroundColor: `color-mix(in srgb, ${cfg.text} 10%, transparent)`,
                color: cfg.text,
            }}
            aria-label={`Authority: ${cfg.label}`}
        >
            <Icon className="w-3 h-3" style={{ color: cfg.color }} />
            {cfg.label}
        </span>
    );
}

export { AUTHORITY_CONFIG };
