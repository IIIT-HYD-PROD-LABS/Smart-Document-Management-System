"use client";

import {
    FiEdit3,
    FiSend,
    FiClock,
    FiShield,
    FiCheckCircle,
    FiXCircle,
    FiAlertOctagon,
} from "react-icons/fi";
import type { ResponseStatus } from "@/types/compliance";

const CONFIG: Record<
    ResponseStatus,
    {
        /** Bright hue for the decorative icon (theme-agnostic). */
        color: string;
        /** AA-passing foreground text color + matching soft tint. */
        text: string;
        soft: string;
        icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
        label: string;
    }
> = {
    draft: { color: "#71717a", text: "var(--text-muted)", soft: "var(--bg-muted)", icon: FiEdit3, label: "Draft" },
    reviewer_pending: { color: "#f59e0b", text: "var(--warning)", soft: "var(--warning-soft)", icon: FiClock, label: "Reviewer pending" },
    legal_pending: { color: "#8b5cf6", text: "#6d28d9", soft: "color-mix(in srgb, #6d28d9 10%, transparent)", icon: FiShield, label: "Legal pending" },
    cfo_pending: { color: "#ec4899", text: "#be185d", soft: "color-mix(in srgb, #be185d 10%, transparent)", icon: FiClock, label: "CFO pending" },
    approved: { color: "#10b981", text: "var(--success)", soft: "var(--success-soft)", icon: FiCheckCircle, label: "Approved" },
    rejected: { color: "#ef4444", text: "var(--danger)", soft: "var(--danger-soft)", icon: FiXCircle, label: "Rejected" },
    withdrawn: { color: "#71717a", text: "var(--text-muted)", soft: "var(--bg-muted)", icon: FiAlertOctagon, label: "Withdrawn" },
};

interface ResponseStatusBadgeProps {
    status: ResponseStatus;
    size?: "sm" | "md";
}

export function ResponseStatusBadge({
    status,
    size = "sm",
}: ResponseStatusBadgeProps) {
    const cfg = CONFIG[status];
    const Icon = cfg.icon;
    const padding = size === "md" ? "px-3 py-1.5" : "px-2 py-1";
    const text = size === "md" ? "text-[13px]" : "text-[11px]";

    return (
        <span
            className={`inline-flex items-center gap-1 ${padding} ${text} rounded font-medium`}
            style={{ backgroundColor: cfg.soft, color: cfg.text }}
            aria-label={`Response status: ${cfg.label}`}
        >
            <Icon className="w-3 h-3" style={{ color: cfg.color }} />
            {cfg.label}
        </span>
    );
}

export { CONFIG as RESPONSE_STATUS_CONFIG };
