"use client";

import { useState } from "react";
import Link from "next/link";
import { FiBell, FiX } from "react-icons/fi";
import { useNotificationStream } from "@/hooks/useNotificationStream";
import { AuthorityBadge } from "./AuthorityBadge";
import { RiskTierDot } from "./RiskTierDot";

const ALERT_TYPE_LABEL: Record<string, string> = {
    deadline_t7: "Deadline T-7",
    deadline_t3: "Deadline T-3",
    deadline_t1: "Due tomorrow",
    overdue: "Overdue",
    status_change: "Status changed",
    received: "Notice received",
    escalation: "Escalation",
};

/**
 * Notification bell + drawer — Phase 11 D-16.
 *
 * Subscribes to the WebSocket stream on the active client. Renders a
 * count badge for unread notifications and a slide-over drawer with
 * the latest 50 alerts. Each row deep-links to the source notice.
 */
export function NotificationBell() {
    const [open, setOpen] = useState(false);
    const { notifications, unreadCount, status, markAllRead } = useNotificationStream();

    const handleOpen = () => {
        setOpen(true);
        markAllRead();
    };

    return (
        <>
            <button
                type="button"
                onClick={handleOpen}
                className="
                    relative inline-flex items-center justify-center w-8 h-8
                    rounded text-[#a1a1aa] hover:text-white
                    hover:bg-[#18181b]
                    focus-visible:outline-none focus-visible:ring-2
                    focus-visible:ring-[#3b82f6] focus-visible:ring-offset-2
                    focus-visible:ring-offset-[#09090b]
                "
                aria-label={`Notifications (${unreadCount} unread)`}
                title={`Notifications • ${status}`}
            >
                <FiBell className="w-4 h-4" />
                {unreadCount > 0 && (
                    <span
                        className="
                            absolute top-0 right-0 -translate-y-1/2 translate-x-1/2
                            min-w-[16px] h-4 px-1
                            inline-flex items-center justify-center
                            rounded-full bg-[#ef4444] text-[10px] font-bold text-white tabular-nums
                            motion-safe:animate-pulse
                        "
                    >
                        {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                )}
                {status === "open" && unreadCount === 0 && (
                    <span
                        className="absolute bottom-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-[#10b981]"
                        aria-hidden
                    />
                )}
            </button>

            {open && (
                <div
                    className="fixed inset-0 z-50 flex justify-end"
                    onClick={() => setOpen(false)}
                >
                    <div
                        className="
                            w-full max-w-md h-full bg-[#09090b]
                            border-l border-[#1f1f23] flex flex-col
                            shadow-2xl
                        "
                        onClick={(e) => e.stopPropagation()}
                    >
                        <header className="flex items-center justify-between px-5 py-4 border-b border-[#1f1f23]">
                            <h3 className="text-sm font-semibold text-white">
                                Notifications
                            </h3>
                            <button
                                type="button"
                                onClick={() => setOpen(false)}
                                className="text-[#a1a1aa] hover:text-white p-1"
                                aria-label="Close notifications"
                            >
                                <FiX className="w-4 h-4" />
                            </button>
                        </header>
                        <div className="px-5 py-3 border-b border-[#1f1f23] bg-[#0a0a0c]">
                            <span className="text-[11px] uppercase tracking-wider text-[#71717a]">
                                Status: {status === "open" ? "live" : status}
                            </span>
                        </div>
                        <div className="flex-1 overflow-y-auto">
                            {notifications.length === 0 ? (
                                <div className="px-5 py-8 text-center">
                                    <p className="text-[13px] text-[#a1a1aa]">
                                        No notifications yet.
                                    </p>
                                    <p className="text-[11px] text-[#71717a] mt-2 leading-relaxed">
                                        Real-time alerts about deadline reminders, status
                                        changes, and Critical-tier escalations will surface
                                        here as they fire.
                                    </p>
                                </div>
                            ) : (
                                <ul>
                                    {notifications.map((env, idx) => (
                                        <li
                                            key={`${env.payload.notice_id}-${idx}`}
                                            className="border-b border-[#1f1f23]"
                                        >
                                            <Link
                                                href={`/dashboard/compliance/notices/${env.payload.notice_id}`}
                                                onClick={() => setOpen(false)}
                                                className="block px-5 py-3 hover:bg-[#0c0c0f]"
                                            >
                                                <div className="flex items-center gap-2 mb-1.5">
                                                    <span
                                                        className="
                                                            text-[10px] font-semibold uppercase tracking-wider
                                                            px-1.5 py-0.5 rounded
                                                            bg-[#3b82f61a] text-[#3b82f6]
                                                        "
                                                    >
                                                        {ALERT_TYPE_LABEL[env.payload.alert_type] ?? env.payload.alert_type}
                                                    </span>
                                                    <AuthorityBadge authority={env.payload.authority} />
                                                    <RiskTierDot tier={env.payload.risk_tier} />
                                                </div>
                                                <p className="text-[13px] text-white font-mono">
                                                    {env.payload.notice_number}
                                                </p>
                                                <p className="text-[11px] text-[#71717a] mt-1">
                                                    {env.payload.response_deadline
                                                        ? `Deadline: ${env.payload.response_deadline}`
                                                        : "No deadline set"}
                                                </p>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
