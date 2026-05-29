"use client";

import { use, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FiUsers, FiFileText } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import { useCurrentClient } from "@/stores/currentClientStore";
import type { ClientDetail, DashboardAggregates } from "@/types/compliance";
import BrandingSection from "@/components/compliance/BrandingSection";

/**
 * Client detail page (CLIENT-01).
 *
 * Shows client name, type, registrations list, and a 4-card stats summary
 * from the dashboard aggregates endpoint. Mirrors the route param into the
 * Zustand active-client store so subsequent API calls (which read the
 * X-Client-Id header from the store) target the client whose URL the user
 * is viewing — without this, navigating directly to a client URL while the
 * store still holds a stale id from a prior session causes a header/path
 * mismatch and the backend 400s every fetch.
 */
export default function ClientDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = use(params);
    const clientId = parseInt(id, 10);

    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const setActiveClientId = useCurrentClient((s) => s.setActiveClientId);

    // Sync the store to the route param. The query below depends on this
    // running first, so we gate the queries on `enabled` matching.
    useEffect(() => {
        if (!Number.isNaN(clientId) && clientId !== activeClientId) {
            setActiveClientId(clientId);
        }
    }, [clientId, activeClientId, setActiveClientId]);

    const tenantReady =
        !Number.isNaN(clientId) && activeClientId === clientId;

    const { data: client, isLoading, error } = useQuery<ClientDetail>({
        queryKey: ["client", clientId],
        queryFn: () => complianceApi.getClient(clientId).then((r) => r.data),
        enabled: tenantReady,
    });

    const { data: dashboard } = useQuery<DashboardAggregates>({
        queryKey: ["client-dashboard", clientId],
        queryFn: () =>
            complianceApi
                .getClientDashboard(clientId)
                .then((r) => r.data),
        enabled: tenantReady && Boolean(client),
    });

    if (Number.isNaN(clientId)) {
        return (
            <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    Invalid client ID
                </h1>
                <p className="text-[var(--text-muted)] text-sm">
                    The URL is missing a valid client ID.
                </p>
            </div>
        );
    }

    if (isLoading || !tenantReady) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto space-y-6">
                <div className="h-7 w-48 bg-[var(--bg-hover)] animate-pulse rounded" />
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[0, 1, 2, 3].map((i) => (
                        <div
                            key={i}
                            className="h-24 bg-[var(--bg-hover)] animate-pulse rounded-md"
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
                    <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                        You don&apos;t have access to this client
                    </h1>
                    <p className="text-[var(--text-muted)] text-sm">
                        Your membership for this client may have changed.
                        Switch clients above, or request access from the
                        workspace owner.
                    </p>
                </div>
            );
        }
        return (
            <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    Couldn&apos;t load this client
                </h1>
                <p className="text-[var(--text-muted)] text-sm">
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
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">
                        {client.name}
                    </h1>
                    <p className="text-[var(--text-muted)] text-sm">
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
                            bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-primary)] text-sm
                            hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)] transition-colors
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
                    accent="var(--danger)"
                />
                <StatCard
                    label="Authorities"
                    value={
                        Object.keys(dashboard?.by_authority ?? {}).length
                    }
                    accent="var(--accent)"
                />
                <StatCard
                    label="Unscored"
                    value={unscored}
                    accent="var(--text-muted)"
                />
            </div>

            <BrandingSection client={client} />

            <div className="surface-card p-6">
                <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)] mb-4">
                    Registrations
                </h2>
                {client.registrations.length === 0 ? (
                    <p className="text-sm text-[var(--text-muted)]">
                        No registrations.
                    </p>
                ) : (
                    <div className="space-y-2">
                        {client.registrations.map((r) => (
                            <div
                                key={r.id}
                                className="flex items-center gap-3 text-sm"
                            >
                                <span className="text-[11px] uppercase text-[var(--text-muted)] w-12 font-medium tracking-wider">
                                    {r.type}
                                </span>
                                <span className="text-[var(--text-primary)] tabular-nums font-medium">
                                    {r.value}
                                </span>
                                {r.state && (
                                    <span className="text-[11px] text-[var(--text-subtle)]">
                                        State {r.state}
                                    </span>
                                )}
                                {!r.is_active && (
                                    <span className="text-[11px] text-[var(--danger)] uppercase">
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
                        bg-[var(--accent)] text-white text-sm font-medium
                        hover:bg-[var(--accent-strong)] transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
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
        <div className="surface-card p-5">
            <div className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">
                {label}
            </div>
            <div
                className="text-2xl font-semibold tabular-nums leading-tight"
                style={{ color: accent ?? "var(--text-primary)" }}
            >
                {value}
            </div>
        </div>
    );
}
