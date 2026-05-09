"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueries, useQuery } from "@tanstack/react-query";
import { FiBriefcase, FiPlus } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import { useAuth } from "@/context/AuthContext";
import { useCurrentClient } from "@/stores/currentClientStore";
import {
    COMPLIANCE_ROLE_LABELS,
    type Client,
    type Membership,
} from "@/types/compliance";

/**
 * Clients list page (CLIENT-01..03).
 *
 * Renders the user's memberships as a list. Empty state per UI-SPEC copy:
 * heading "No clients yet" + body + primary CTA "Onboard first client".
 *
 * **Phase 4 tenant-isolation guard (2026-05-09):** route-restricted to
 * `users.role === 'admin'`. The page enumerates client names via a
 * fan-out `getClient` and would otherwise leak the existence of other
 * organizations to non-admin users with multiple memberships. Sidebar
 * already hides the link from non-admins; this is the URL-tampering
 * defense.
 *
 * Note: this page lists memberships (one per client the user has access to);
 * clicking a row navigates to the client detail page. The full client name is
 * fetched on the detail page — here we show "Client #{id}" as a stable label
 * (a future enhancement is a /clients?ids=... batch endpoint).
 */
export default function ClientsListPage() {
    const { user, isLoading: authLoading } = useAuth();
    const router = useRouter();

    // Admin-only route. Non-admins (editor/viewer) get redirected to the
    // dashboard. We wait for auth to finish loading before deciding so a
    // valid admin doesn't get a one-frame redirect on hard refresh.
    useEffect(() => {
        if (!authLoading && user && user.role !== "admin") {
            router.replace("/dashboard");
        }
    }, [authLoading, user, router]);

    const setActiveClientId = useCurrentClient((s) => s.setActiveClientId);

    const { data: memberships, isLoading, error } = useQuery<Membership[]>({
        queryKey: ["memberships", "mine"],
        queryFn: () => complianceApi.listMyMemberships().then((r) => r.data),
    });

    // Fan-out fetch the actual client names — listMyMemberships returns
    // only ids, but the user expects names. The detail-page useEffect
    // sets the active client BEFORE its own getClient fires; here we do
    // the same just in time for each row's query so a fresh-page-load
    // shows real names instead of "Client #206".
    const clientQueries = useQueries({
        queries: (memberships ?? []).map((m) => ({
            queryKey: ["client", m.client_id],
            queryFn: async () => {
                setActiveClientId(m.client_id);
                const { data } = await complianceApi.getClient(m.client_id);
                return data;
            },
            enabled: Boolean(memberships),
            staleTime: 60_000,
        })),
    });
    const clientById = new Map<number, Client>();
    clientQueries.forEach((q, i) => {
        const m = memberships?.[i];
        if (m && q.data) clientById.set(m.client_id, q.data as Client);
    });

    // Render-time guard so non-admins don't see org names for the brief
    // window before the useEffect redirect fires. Placed AFTER all hooks
    // to keep React's hook-count contract intact.
    if (!authLoading && user && user.role !== "admin") return null;

    if (isLoading) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto">
                <div className="h-7 w-32 bg-[var(--bg-hover)] animate-pulse rounded mb-6" />
                <div className="space-y-2">
                    {[0, 1, 2].map((i) => (
                        <div
                            key={i}
                            className="h-16 bg-[var(--bg-hover)] animate-pulse rounded"
                        />
                    ))}
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    Couldn&apos;t load your clients
                </h1>
                <p className="text-[var(--text-muted)] text-sm">
                    Try refreshing the page. If the problem persists, contact
                    your workspace owner.
                </p>
            </div>
        );
    }

    if (!memberships || memberships.length === 0) {
        return (
            <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                <FiBriefcase className="w-12 h-12 mx-auto text-[var(--text-disabled)] mb-4" />
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    No clients yet
                </h1>
                <p className="text-[var(--text-muted)] text-sm mb-6 max-w-md mx-auto">
                    Add your first client to start managing their compliance
                    notices. You can add multiple GSTINs and PANs per client.
                </p>
                <Link
                    href="/dashboard/compliance/clients/new"
                    className="
                        inline-flex items-center gap-2 px-4 py-2 rounded-md
                        bg-[var(--accent)] text-white text-sm font-medium
                        hover:bg-[var(--accent-strong)] transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                    "
                >
                    <FiPlus className="w-4 h-4" />
                    Onboard first client
                </Link>
            </div>
        );
    }

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-lg font-semibold text-[var(--text-primary)]">Clients</h1>
                <Link
                    href="/dashboard/compliance/clients/new"
                    className="
                        inline-flex items-center gap-2 px-3 py-1.5 rounded-md
                        bg-[var(--accent)] text-white text-sm font-medium
                        hover:bg-[var(--accent-strong)] transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                    "
                >
                    <FiPlus className="w-3.5 h-3.5" />
                    Onboard client
                </Link>
            </div>
            <div className="space-y-2">
                {memberships.map((m) => {
                    const c = clientById.get(m.client_id);
                    return (
                        <Link
                            key={m.id}
                            href={`/dashboard/compliance/clients/${m.client_id}`}
                            onClick={() => setActiveClientId(m.client_id)}
                            className="
                                block p-4 rounded-md
                                bg-[var(--bg-elevated)] border border-[var(--border-default)]
                                hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)] transition-colors
                                focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                                shadow-[var(--shadow-sm)]
                            "
                        >
                            <div className="flex items-center justify-between gap-3">
                                <div className="min-w-0">
                                    <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                                        {c?.name ?? `Client #${m.client_id}`}
                                    </p>
                                    {c && (
                                        <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5 truncate">
                                            {c.client_type
                                                .replace("_", " ")
                                                .toUpperCase()}
                                            {c.industry ? ` · ${c.industry}` : ""}
                                        </p>
                                    )}
                                </div>
                                <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider shrink-0">
                                    {COMPLIANCE_ROLE_LABELS[m.compliance_role]}
                                </span>
                            </div>
                        </Link>
                    );
                })}
            </div>
        </div>
    );
}
