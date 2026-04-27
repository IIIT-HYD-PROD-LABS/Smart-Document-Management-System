"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClientSwitcher } from "@/components/compliance/ClientSwitcher";

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
                        sticky top-0 z-30 bg-[#09090b] border-b border-[#1f1f23]
                        h-14 flex items-center justify-between px-6 -mx-6 -mt-6 md:-mx-8 md:-mt-8
                        mb-6
                    "
                >
                    <h2 className="text-sm font-semibold text-white tracking-tight">
                        Compliance
                    </h2>
                    <ClientSwitcher />
                </header>
                {children}
            </div>
        </QueryClientProvider>
    );
}
