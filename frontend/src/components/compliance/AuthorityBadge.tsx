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
        color: string;
        icon: React.ComponentType<{ className?: string }>;
        label: string;
    }
> = {
    GST: { color: "#06b6d4", icon: FiPieChart, label: "GST" },
    IT: { color: "#3b82f6", icon: FiDollarSign, label: "Income Tax" },
    MCA: { color: "#8b5cf6", icon: FiBriefcase, label: "MCA" },
    RBI: { color: "#ec4899", icon: FiCreditCard, label: "RBI" },
    SEBI: { color: "#f97316", icon: FiTrendingUp, label: "SEBI" },
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
                backgroundColor: `${cfg.color}1a`,
                color: cfg.color,
            }}
            aria-label={`Authority: ${cfg.label}`}
        >
            <Icon className="w-3 h-3" />
            {cfg.label}
        </span>
    );
}

export { AUTHORITY_CONFIG };
