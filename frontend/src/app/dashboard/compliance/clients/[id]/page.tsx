"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FiUsers, FiFileText } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import type { ClientDetail, DashboardAggregates } from "@/types/compliance";

/**
 * Client detail page (CLIENT-01).
 *
 * Shows client name, type, registrations list, and a 4-card stats summary
 * from the dashboard aggregates endpoint. Risk tier "unscored" stat reflects
 * the Phase 9 reality (Phase 10 will populate risk_score; for now every
 * notice is unscored — UI-SPEC reserves the layout).
 */
export default function ClientDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = use(params);
    const clientId = parseInt(id, 10);

    const { data: client, isLoading, error } = useQuery<ClientDetail>({
        queryKey: ["client", clientId],
        queryFn: () => complianceApi.getClient(clientId).then((r) => r.data),
        enabled: !Number.isNaN(clientId),
    });

    const { data: dashboard } = useQuery<DashboardAggregates>({
        queryKey: ["client-dashboard", clientId],
        queryFn: () =>
            complianceApi
                .getClientDashboard(clientId)
                .then((r) => r.data),
        enabled: !Number.isNaN(clientId) && Boolean(client),
    });

    if (Number.isNaN(clientId)) {
        return (
            <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                <h1 className="text-lg font-semibold text-white mb-2">
                    Invalid client ID
                </h1>
                <p className="text-[#71717a] text-sm">
                    The URL is missing a valid client ID.
                </p>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto space-y-6">
                <div className="h-7 w-48 bg-[#18181b] animate-pulse rounded" />
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[0, 1, 2, 3].map((i) => (
                        <div
                            key={i}
                            className="h-24 bg-[#18181b] animate-pulse rounded-md"
                        />
                    ))}
                </div>
            </div>
        );
    }

    if (error || !client) {
        const status = (error as { response?: { status?: number } })?.response
            ?.status;
        if (status === 403) {
            return (
                <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                    <h1 className="text-lg font-semibold text-white mb-2">
                        You don&apos;t have access to this client
                    </h1>
                    <p className="text-[#71717a] text-sm">
                        Your membership for this client may have changed.
                        Switch clients above, or request access from the
                        workspace owner.
                    </p>
                </div>
            );
        }
        return (
            <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                <h1 className="text-lg font-semibold text-white mb-2">
                    Couldn&apos;t load this client
                </h1>
                <p className="text-[#71717a] text-sm">
                    Try refreshing the page.
                </p>
            </div>
        );
    }

    const unscored = dashboard?.by_risk_tier?.unscored ?? 0;

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto space-y-6">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-lg font-semibold text-white">
                        {client.name}
                    </h1>
                    <p className="text-[#71717a] text-sm">
                        {client.client_type
                            .replace("_", " ")
                            .toUpperCase()}
                        {client.industry && ` — ${client.industry}`}
                    </p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                    <Link
                        href={`/dashboard/compliance/clients/${clientId}/team`}
                        className="
                            inline-flex items-center gap-2 px-3 py-1.5 rounded-md
                            bg-[#18181b] border border-[#27272a] text-white text-sm
                            hover:border-[#3f3f46] transition-colors
                        "
                    >
                        <FiUsers className="w-3.5 h-3.5" />
                        Team
                    </Link>
                </div>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="Total notices" value={dashboard?.total ?? 0} />
                <StatCard
                    label="Overdue"
                    value={dashboard?.overdue ?? 0}
                    accent="#ef4444"
                />
                <StatCard
                    label="Authorities"
                    value={
                        Object.keys(dashboard?.by_authority ?? {}).length
                    }
                    accent="#3b82f6"
                />
                <StatCard
                    label="Unscored"
                    value={unscored}
                    accent="#71717a"
                />
            </div>

            <div className="bg-[#111113] border border-[#27272a] rounded-md p-6">
                <h2 className="text-[11px] font-medium uppercase tracking-wider text-[#a1a1aa] mb-4">
                    Registrations
                </h2>
                {client.registrations.length === 0 ? (
                    <p className="text-sm text-[#71717a]">
                        No registrations.
                    </p>
                ) : (
                    <div className="space-y-2">
                        {client.registrations.map((r) => (
                            <div
                                key={r.id}
                                className="flex items-center gap-3 text-sm"
                            >
                                <span className="text-[11px] uppercase text-[#71717a] w-12 font-medium tracking-wider">
                                    {r.type}
                                </span>
                                <span className="text-white tabular-nums font-medium">
                                    {r.value}
                                </span>
                                {r.state && (
                                    <span className="text-[11px] text-[#52525b]">
                                        State {r.state}
                                    </span>
                                )}
                                {!r.is_active && (
                                    <span className="text-[11px] text-[#ef4444] uppercase">
                                        Inactive
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div>
                <Link
                    href={`/dashboard/compliance?client_id=${clientId}`}
                    className="
                        inline-flex items-center gap-2 px-4 py-2 rounded-md
                        bg-[#3b82f6] text-white text-sm font-medium
                        hover:bg-[#3b82f6]/90 transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40
                    "
                >
                    <FiFileText className="w-4 h-4" />
                    View notices
                </Link>
            </div>
        </div>
    );
}

function StatCard({
    label,
    value,
    accent,
}: {
    label: string;
    value: number;
    accent?: string;
}) {
    return (
        <div className="bg-[#111113] border border-[#27272a] rounded-md p-5">
            <div className="text-[11px] font-medium uppercase tracking-wider text-[#a1a1aa] mb-2">
                {label}
            </div>
            <div
                className="text-2xl font-semibold tabular-nums leading-tight"
                style={{ color: accent ?? "#ffffff" }}
            >
                {value}
            </div>
        </div>
    );
}
