"use client";

import {
    FiInbox,
    FiEye,
    FiEdit3,
    FiSend,
    FiCheckCircle,
    FiXCircle,
    FiAlertTriangle,
} from "react-icons/fi";
import type { NoticeStatus } from "@/types/compliance";

/**
 * Maps each NoticeStatus to its UI-SPEC color hex, icon, and label.
 *
 * UI-SPEC § "Status Workflow Visual Treatment":
 *   received          #3b82f6  FiInbox          Received
 *   under_review      #f59e0b  FiEye            Under Review
 *   response_drafted  #8b5cf6  FiEdit3          Response Drafted
 *   submitted         #06b6d4  FiSend           Submitted
 *   resolved          #10b981  FiCheckCircle    Resolved
 *   dismissed         #ef4444  FiXCircle        Dismissed
 *
 * Backgrounds use /10 alpha (`#hex1a` inline-style) to match the v1.0
 * StatusBadge.tsx pattern (low visual weight on dark surfaces).
 */
const STATUS_CONFIG: Record<
    NoticeStatus,
    {
        color: string;
        icon: React.ComponentType<{ className?: string }>;
        label: string;
    }
> = {
    received: { color: "#3b82f6", icon: FiInbox, label: "Received" },
    under_review: { color: "#f59e0b", icon: FiEye, label: "Under Review" },
    response_drafted: {
        color: "#8b5cf6",
        icon: FiEdit3,
        label: "Response Drafted",
    },
    submitted: { color: "#06b6d4", icon: FiSend, label: "Submitted" },
    resolved: { color: "#10b981", icon: FiCheckCircle, label: "Resolved" },
    dismissed: { color: "#ef4444", icon: FiXCircle, label: "Dismissed" },
};

interface StatusPillProps {
    status: NoticeStatus;
    /** Render an FiAlertTriangle overlay before the pill (response_deadline < now). */
    overdue?: boolean;
    size?: "sm" | "md";
}

export function StatusPill({
    status,
    overdue = false,
    size = "sm",
}: StatusPillProps) {
    const cfg = STATUS_CONFIG[status];
    const Icon = cfg.icon;
    const padding = size === "md" ? "px-3 py-1.5" : "px-2 py-1";
    const text = size === "md" ? "text-[13px]" : "text-[11px]";

    return (
        <span className="inline-flex items-center gap-1.5">
            {overdue && (
                <FiAlertTriangle
                    className="w-3.5 h-3.5 text-[#ef4444]"
                    aria-label="Overdue"
                />
            )}
            <span
                className={`inline-flex items-center gap-1 ${padding} ${text} rounded font-medium`}
                style={{
                    backgroundColor: `${cfg.color}1a`,
                    color: cfg.color,
                }}
                aria-label={`Status: ${cfg.label}`}
            >
                <Icon className="w-3 h-3" />
                {cfg.label}
            </span>
        </span>
    );
}

export { STATUS_CONFIG };
