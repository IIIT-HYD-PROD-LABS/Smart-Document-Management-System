"use client";

import { NotificationBell } from "@/components/compliance/NotificationBell";
import { ComplianceScoreChip } from "@/components/compliance/ComplianceScoreChip";

/**
 * Compliance dashboard layout — wraps every /dashboard/compliance/** route.
 *
 * ClientSwitcher lives in the global dashboard topbar so "Your organization"
 * works on every page. This header keeps compliance-only chrome (score +
 * notifications).
 */
export default function ComplianceLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="min-h-screen">
            <header
                className="
                    sticky top-0 z-20 bg-[var(--bg-page)]/90 backdrop-blur
                    border-b border-[var(--border-default)]
                    h-12 flex items-center justify-between px-6 -mx-6 -mt-6 md:-mx-10 md:-mt-10
                    mb-6
                "
            >
                <h2 className="text-[13.5px] font-semibold text-[var(--text-primary)] tracking-tight">
                    Compliance
                </h2>
                <div className="flex items-center gap-3">
                    <ComplianceScoreChip />
                    <NotificationBell />
                </div>
            </header>
            {children}
        </div>
    );
}
