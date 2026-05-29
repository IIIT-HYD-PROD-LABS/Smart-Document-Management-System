"use client";

import { use, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FiPlus, FiClock, FiTrash2, FiAlertTriangle } from "react-icons/fi";
import toast from "react-hot-toast";
import { complianceApi } from "@/lib/api/compliance";
import {
    COMPLIANCE_ROLE_LABELS,
    COMPLIANCE_ROLE_COLORS,
    type ClientDetail,
    type Membership,
    type ComplianceRole,
} from "@/types/compliance";
import { AddMemberDialog } from "@/components/compliance/AddMemberDialog";
import { RoleDescriptionDrawer } from "@/components/compliance/RoleDescriptionDrawer";
import { extractErrorMessage } from "@/lib/api";

/**
 * Team management page (RBAC-01..06, D-25, D-26, D-27).
 *
 * - 7 role chips render equal-weight (no hierarchy implied).
 * - Auditor row treatment: shows access_end inline; if expired, row dims to
 *   opacity-50 and a red "Expired" badge appears; if expiring in < 7 days,
 *   amber "Expires in N days" warning shows instead (UI-SPEC Section 7).
 * - Click a role chip → drawer with explicit permission list (D-26).
 * - Add member opens AddMemberDialog; success invalidates the client query
 *   so the membership list re-renders.
 */
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

function isExpired(m: Membership): boolean {
    if (!m.access_end) return false;
    return new Date(m.access_end) < new Date();
}

function daysUntilExpiry(m: Membership): number | null {
    if (!m.access_end) return null;
    const diffMs = new Date(m.access_end).getTime() - Date.now();
    if (diffMs < 0) return -1;
    return Math.ceil(diffMs / (24 * 60 * 60 * 1000));
}

function isExpiringSoon(m: Membership): boolean {
    if (!m.access_end) return false;
    const diffMs = new Date(m.access_end).getTime() - Date.now();
    return diffMs > 0 && diffMs < SEVEN_DAYS_MS;
}

export default function TeamPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = use(params);
    const clientId = parseInt(id, 10);
    const qc = useQueryClient();
    const [showAdd, setShowAdd] = useState(false);
    const [drawerRole, setDrawerRole] = useState<ComplianceRole | null>(null);
    const [pendingRemoval, setPendingRemoval] = useState<{
        membershipId: number;
        userId: number;
    } | null>(null);
    const [removing, setRemoving] = useState(false);

    const { data: client, isLoading, error } = useQuery<ClientDetail>({
        queryKey: ["client", clientId],
        queryFn: () => complianceApi.getClient(clientId).then((r) => r.data),
        enabled: !Number.isNaN(clientId),
    });

    const confirmRemoval = async () => {
        if (!pendingRemoval || removing) return;
        setRemoving(true);
        try {
            await complianceApi.removeMember(
                clientId,
                pendingRemoval.membershipId
            );
            toast.success("Member removed");
            qc.invalidateQueries({ queryKey: ["client", clientId] });
            setPendingRemoval(null);
        } catch (err) {
            toast.error(extractErrorMessage(err, "Failed to remove member"));
        } finally {
            setRemoving(false);
        }
    };

    useEffect(() => {
        if (!pendingRemoval) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !removing) setPendingRemoval(null);
        };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [pendingRemoval, removing]);

    if (Number.isNaN(clientId)) {
        return (
            <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    Invalid client ID
                </h1>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="px-6 py-8 max-w-5xl mx-auto">
                <div className="h-7 w-64 bg-[var(--bg-hover)] animate-pulse rounded mb-6" />
                {[0, 1, 2].map((i) => (
                    <div
                        key={i}
                        className="h-16 bg-[var(--bg-hover)] animate-pulse rounded mb-2"
                    />
                ))}
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
                    </p>
                </div>
            );
        }
        return (
            <div className="px-6 py-12 max-w-4xl mx-auto text-center">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                    Couldn&apos;t load this team
                </h1>
            </div>
        );
    }

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-lg font-semibold text-[var(--text-primary)]">
                    Team — {client.name}
                </h1>
                <button
                    type="button"
                    onClick={() => setShowAdd(true)}
                    className="
                        inline-flex items-center gap-2 px-3 py-1.5 rounded-md
                        bg-[var(--accent)] text-white text-sm font-medium
                        hover:bg-[var(--accent-strong)] transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                    "
                >
                    <FiPlus className="w-3.5 h-3.5" />
                    Add member
                </button>
            </div>

            {client.memberships.length === 0 ? (
                <div className="text-center py-12 text-[var(--text-muted)] text-sm">
                    No team members yet.
                </div>
            ) : (
                <div className="space-y-2">
                    {client.memberships.map((m) => {
                        const expired = isExpired(m);
                        const expiringSoon = isExpiringSoon(m);
                        const days = daysUntilExpiry(m);
                        const role = m.compliance_role as ComplianceRole;
                        return (
                            <div
                                key={m.id}
                                className={`
                                    flex items-center gap-3 p-4 rounded-md
                                    bg-[var(--bg-elevated)] border border-[var(--border-default)]
                                    shadow-[var(--shadow-sm)]
                                    ${expired ? "opacity-50" : ""}
                                `}
                            >
                                <button
                                    type="button"
                                    onClick={() => setDrawerRole(role)}
                                    className="px-2 py-1 rounded text-[11px] font-medium hover:opacity-80 transition-opacity focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]"
                                    style={{
                                        backgroundColor: `color-mix(in srgb, ${COMPLIANCE_ROLE_COLORS[role]} 12%, transparent)`,
                                        color: COMPLIANCE_ROLE_COLORS[role],
                                    }}
                                    aria-label={`View ${COMPLIANCE_ROLE_LABELS[role]} permissions`}
                                >
                                    {COMPLIANCE_ROLE_LABELS[role]}
                                </button>
                                <span className="text-sm text-[var(--text-primary)] flex-1">
                                    User #{m.user_id}
                                </span>
                                {role === "auditor" && m.access_end && (
                                    <span
                                        className={`text-xs flex items-center gap-1 ${
                                            expired
                                                ? "text-[var(--danger)]"
                                                : expiringSoon
                                                ? "text-[var(--warning)]"
                                                : "text-[var(--text-muted)]"
                                        }`}
                                    >
                                        <FiClock className="w-3 h-3" />
                                        {expired
                                            ? "Expired"
                                            : expiringSoon &&
                                                days !== null
                                              ? `Expires in ${days} day${days === 1 ? "" : "s"}`
                                              : `Expires ${new Date(m.access_end).toLocaleDateString(
                                                    "en-IN",
                                                    {
                                                        day: "numeric",
                                                        month: "short",
                                                        year: "numeric",
                                                    }
                                                )}`}
                                    </span>
                                )}
                                <button
                                    type="button"
                                    onClick={() =>
                                        setPendingRemoval({
                                            membershipId: m.id,
                                            userId: m.user_id,
                                        })
                                    }
                                    className="p-1.5 text-[var(--text-muted)] hover:text-[var(--danger)] transition-colors focus:outline-none focus:ring-2 focus:ring-[color:color-mix(in_srgb,var(--danger)_40%,transparent)] rounded"
                                    aria-label={`Remove user ${m.user_id}`}
                                >
                                    <FiTrash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        );
                    })}
                </div>
            )}

            {showAdd && (
                <AddMemberDialog
                    clientId={clientId}
                    onClose={() => setShowAdd(false)}
                    onAdded={() =>
                        qc.invalidateQueries({
                            queryKey: ["client", clientId],
                        })
                    }
                />
            )}
            {drawerRole && (
                <RoleDescriptionDrawer
                    role={drawerRole}
                    onClose={() => setDrawerRole(null)}
                />
            )}
            {pendingRemoval && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(15,23,42,0.45)] backdrop-blur-sm motion-safe:animate-in motion-safe:fade-in motion-safe:duration-150"
                    onClick={() => !removing && setPendingRemoval(null)}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="revoke-title"
                    aria-describedby="revoke-desc"
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        className="
                            w-[420px] max-w-[92vw] rounded-[10px]
                            bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                            shadow-[var(--shadow-lg)] p-5
                            motion-safe:animate-in motion-safe:zoom-in-95 motion-safe:duration-150
                        "
                    >
                        <div className="flex items-start gap-3">
                            <FiAlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-[var(--danger)]" aria-hidden="true" />
                            <div>
                                <h2
                                    id="revoke-title"
                                    className="text-sm font-semibold text-[var(--text-primary)]"
                                >
                                    Revoke access for User #{pendingRemoval.userId}?
                                </h2>
                                <p
                                    id="revoke-desc"
                                    className="mt-1 text-sm text-[var(--text-muted)]"
                                >
                                    Their access ends immediately.
                                </p>
                            </div>
                        </div>
                        <div className="mt-5 flex justify-end gap-2">
                            <button
                                type="button"
                                onClick={() => setPendingRemoval(null)}
                                disabled={removing}
                                className="px-3 py-1.5 rounded-md text-sm font-medium text-[var(--text-primary)] border border-[var(--border-default)] hover:bg-[var(--bg-hover)] transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={confirmRemoval}
                                disabled={removing}
                                className="px-3 py-1.5 rounded-md text-sm font-medium text-white bg-[var(--danger)] hover:opacity-90 transition-opacity disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[color:color-mix(in_srgb,var(--danger)_40%,transparent)]"
                            >
                                {removing ? "Revoking..." : "Revoke access"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
