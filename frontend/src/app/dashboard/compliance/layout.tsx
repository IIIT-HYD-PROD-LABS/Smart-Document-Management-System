"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClientSwitcher } from "@/components/compliance/ClientSwitcher";
import { NotificationBell } from "@/components/compliance/NotificationBell";
import { ComplianceScoreChip } from "@/components/compliance/ComplianceScoreChip";

/**
 * Compliance dashboard layout — wraps every /dashboard/compliance/** route.
 *
 * - Mounts a single QueryClient for the entire compliance section so caches
 *   (memberships, clients, notices) survive navigation between pages.
 * - Renders the sticky top header with the ClientSwitcher.
 * - Sits inside the existing /dashboard layout (which provides the sidebar
 *   nav + auth gate); we are an inner layout, NOT a replacement.
 */
export default function ComplianceLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        staleTime: 30_000,
                        refetchOnWindowFocus: false,
                        retry: 1,
                    },
                },
            })
    );

    return (
        <QueryClientProvider client={queryClient}>
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
        </QueryClientProvider>
    );
}
