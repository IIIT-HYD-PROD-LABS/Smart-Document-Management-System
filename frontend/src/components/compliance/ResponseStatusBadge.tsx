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
    { color: string; icon: React.ComponentType<{ className?: string }>; label: string }
> = {
    draft: { color: "#71717a", icon: FiEdit3, label: "Draft" },
    reviewer_pending: { color: "#f59e0b", icon: FiClock, label: "Reviewer pending" },
    legal_pending: { color: "#8b5cf6", icon: FiShield, label: "Legal pending" },
    cfo_pending: { color: "#ec4899", icon: FiClock, label: "CFO pending" },
    approved: { color: "#10b981", icon: FiCheckCircle, label: "Approved" },
    rejected: { color: "#ef4444", icon: FiXCircle, label: "Rejected" },
    withdrawn: { color: "#71717a", icon: FiAlertOctagon, label: "Withdrawn" },
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
            style={{ backgroundColor: `${cfg.color}1a`, color: cfg.color }}
            aria-label={`Response status: ${cfg.label}`}
        >
            <Icon className="w-3 h-3" />
            {cfg.label}
        </span>
    );
}

export { CONFIG as RESPONSE_STATUS_CONFIG };
