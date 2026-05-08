"use client";

import { ClientSwitcher } from "@/components/compliance/ClientSwitcher";
import { NotificationBell } from "@/components/compliance/NotificationBell";
import { ComplianceScoreChip } from "@/components/compliance/ComplianceScoreChip";

/**
 * Compliance dashboard layout — wraps every /dashboard/compliance/** route.
 *
 * Renders the sticky top header with the ClientSwitcher. The `QueryClient`
 * lives in the outer `dashboard/layout.tsx` (Phase 16 hoist) so the
 * sidebar's active-client query and child page queries share a single
 * cache — no nested providers, no shape divergence between caches.
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
                    <ClientSwitcher />
                </div>
            </header>
            {children}
        </div>
    );
}
