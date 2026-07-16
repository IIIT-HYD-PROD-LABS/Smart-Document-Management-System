"use client";

import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    FiChevronDown,
    FiCheck,
    FiGlobe,
    FiPlus,
    FiSearch,
    FiBriefcase,
} from "react-icons/fi";
import Link from "next/link";
import { complianceApi } from "@/lib/api/compliance";
import { useCurrentClient } from "@/stores/currentClientStore";
import { useAuth } from "@/context/AuthContext";
import {
    ROLES_ELIGIBLE_FOR_CROSS_CLIENT,
    type Membership,
    type Client,
} from "@/types/compliance";

/**
 * Top-bar client switcher per UI-SPEC Section 5 (D-22, D-23).
 *
 * Non-admin users get a clickable pill that opens their organization page
 * (the previous static div looked like a button but did nothing).
 * Platform admins with multiple memberships get the full dropdown.
 */
export function ClientSwitcher() {
    const {
        activeClientId,
        crossClientMode,
        eligibleForCrossClient,
        setActiveClientId,
        setCrossClientMode,
        setEligibleForCrossClient,
    } = useCurrentClient();
    const { user } = useAuth();

    const isPlatformAdmin = user?.role === "admin";

    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const dropdownRef = useRef<HTMLDivElement>(null);

    const { data: memberships, isLoading } = useQuery<Membership[]>({
        queryKey: ["memberships", "mine"],
        queryFn: () => complianceApi.listMyMemberships().then((r) => r.data),
    });

    useEffect(() => {
        if (!memberships) return;
        const eligible =
            isPlatformAdmin &&
            memberships.some((m) =>
                ROLES_ELIGIBLE_FOR_CROSS_CLIENT.includes(m.compliance_role)
            );
        setEligibleForCrossClient(eligible);
    }, [memberships, setEligibleForCrossClient, isPlatformAdmin]);

    // Auto-pin when the user has memberships and nothing selected yet.
    useEffect(() => {
        if (!memberships || memberships.length === 0) return;
        if (activeClientId === null) {
            setActiveClientId(memberships[0].client_id);
        }
    }, [memberships, activeClientId, setActiveClientId]);

    // Validate persisted activeClientId against fresh memberships.
    useEffect(() => {
        if (!memberships || activeClientId === null) return;
        if (!memberships.some((m) => m.client_id === activeClientId)) {
            setActiveClientId(memberships[0]?.client_id ?? null);
        }
    }, [memberships, activeClientId, setActiveClientId]);

    const { data: activeClient } = useQuery<Client>({
        queryKey: ["client", activeClientId],
        queryFn: () =>
            complianceApi.getClient(activeClientId!).then((r) => r.data),
        enabled: activeClientId !== null && !crossClientMode,
    });

    useEffect(() => {
        if (!open) return;
        const handleClick = (e: MouseEvent) => {
            if (
                dropdownRef.current &&
                !dropdownRef.current.contains(e.target as Node)
            ) {
                setOpen(false);
            }
        };
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") setOpen(false);
        };
        document.addEventListener("mousedown", handleClick);
        document.addEventListener("keydown", handleKey);
        return () => {
            document.removeEventListener("mousedown", handleClick);
            document.removeEventListener("keydown", handleKey);
        };
    }, [open]);

    const membershipLabel = useCallback((m: Membership) => {
        return (
            m.client_name?.trim() ||
            `Organization #${m.client_id}`
        );
    }, []);

    const filtered = useMemo(() => {
        if (!memberships) return [];
        const q = query.trim().toLowerCase();
        if (!q) return memberships;
        return memberships.filter((m) => {
            const name = (m.client_name || "").toLowerCase();
            return (
                name.includes(q) ||
                String(m.client_id).includes(q) ||
                m.compliance_role.toLowerCase().includes(q)
            );
        });
    }, [memberships, query]);

    const activeMembership = memberships?.find(
        (m) => m.client_id === activeClientId
    );

    const triggerLabel = crossClientMode
        ? "All Clients"
        : activeClient?.name ??
          activeMembership?.client_name ??
          (activeClientId ? `Organization #${activeClientId}` : "Select organization");

    const orgHref =
        activeClientId != null
            ? `/dashboard/compliance/clients/${activeClientId}`
            : "/dashboard/compliance/clients";

    const handleClientClick = useCallback(
        (clientId: number) => {
            setActiveClientId(clientId);
            setCrossClientMode(false);
            setOpen(false);
        },
        [setActiveClientId, setCrossClientMode]
    );

    // Platform admin with 2+ orgs: full switcher. Everyone else: clickable org pill.
    const showSwitcherDropdown =
        isPlatformAdmin && (memberships?.length ?? 0) > 1;

    if (!showSwitcherDropdown) {
        return (
            <Link
                href={orgHref}
                className="
                    inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-[13px]
                    bg-[var(--bg-elevated)] border border-[var(--border-default)]
                    text-[var(--text-primary)]
                    hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)]
                    transition-colors cursor-pointer
                    focus-visible:outline-none focus-visible:ring-2
                    focus-visible:ring-[var(--accent-edge)]
                "
                aria-label="Open your organization"
                title={triggerLabel}
            >
                <FiBriefcase className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                <span className="truncate max-w-[180px]">
                    {isLoading ? "Loading…" : triggerLabel}
                </span>
                {activeMembership?.compliance_role && (
                    <span className="hidden sm:inline text-[10.5px] uppercase tracking-wide text-[var(--text-muted)] border-l border-[var(--border-default)] pl-2">
                        {activeMembership.compliance_role.replaceAll("_", " ")}
                    </span>
                )}
            </Link>
        );
    }

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                type="button"
                onClick={() => setOpen(!open)}
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label="Switch organization"
                className={`
                    flex items-center gap-2 px-3 py-1.5 rounded-md text-[13px]
                    border transition-colors cursor-pointer
                    ${
                        crossClientMode
                            ? "bg-[var(--accent-soft)] border-[var(--accent-edge)] text-[var(--accent)]"
                            : "bg-[var(--bg-elevated)] border-[var(--border-default)] text-[var(--text-primary)] hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)]"
                    }
                `}
            >
                {crossClientMode ? (
                    <FiGlobe className="w-3.5 h-3.5" />
                ) : (
                    <FiBriefcase className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                )}
                <span className="truncate max-w-[160px]">{triggerLabel}</span>
                <FiChevronDown className="w-3.5 h-3.5 text-[var(--text-subtle)]" />
            </button>

            {open && (
                <div
                    role="menu"
                    className="
                        absolute right-0 mt-2 w-[320px] max-h-[480px] overflow-y-auto
                        bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md shadow-[var(--shadow-lg)]
                        z-50
                    "
                >
                    <div className="p-2 border-b border-[var(--border-default)]">
                        <div className="relative">
                            <FiSearch className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-subtle)]" />
                            <input
                                type="text"
                                placeholder="Search organizations"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                className="
                                    w-full pl-8 pr-2 py-1.5 text-[13.5px]
                                    bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md
                                    text-[var(--text-primary)] placeholder:text-[var(--text-disabled)]
                                    focus:outline-none focus:border-[var(--accent)]
                                    focus:ring-2 focus:ring-[var(--accent-edge)]
                                "
                                aria-label="Search organizations"
                            />
                        </div>
                    </div>

                    {isLoading && (
                        <div className="p-3 space-y-2">
                            {[0, 1, 2].map((i) => (
                                <div
                                    key={i}
                                    className="h-8 rounded bg-[var(--bg-hover)] animate-pulse"
                                />
                            ))}
                        </div>
                    )}

                    {!isLoading && memberships && memberships.length === 0 && (
                        <div className="p-4 text-[13px] text-[var(--text-muted)] text-center">
                            No organizations yet
                        </div>
                    )}

                    {!isLoading &&
                        memberships &&
                        memberships.length > 0 &&
                        filtered.length === 0 && (
                            <div className="p-4 text-[13px] text-[var(--text-muted)] text-center">
                                No organizations match {`"${query}"`}
                            </div>
                        )}

                    {!isLoading && filtered.length > 0 && (
                        <div className="py-1">
                            {filtered.map((m) => {
                                const isActive =
                                    m.client_id === activeClientId &&
                                    !crossClientMode;
                                return (
                                    <button
                                        key={m.client_id}
                                        type="button"
                                        role="menuitem"
                                        onClick={() =>
                                            handleClientClick(m.client_id)
                                        }
                                        className={`
                                            w-full flex items-center gap-2 px-3 py-2 text-[13.5px]
                                            text-left hover:bg-[var(--bg-hover)] transition-colors cursor-pointer
                                            focus-visible:outline-none focus-visible:bg-[var(--bg-hover)]
                                            focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)] focus-visible:ring-inset
                                            ${
                                                isActive
                                                    ? "border-l-[3px] border-[var(--accent)] pl-[9px] bg-[var(--accent-soft)]"
                                                    : ""
                                            }
                                        `}
                                    >
                                        <span className="flex-1 text-[var(--text-primary)] truncate">
                                            {membershipLabel(m)}
                                        </span>
                                        <span className="text-[11px] text-[var(--text-muted)] uppercase font-semibold">
                                            {m.compliance_role.replaceAll(
                                                "_",
                                                " "
                                            )}
                                        </span>
                                        {isActive && (
                                            <FiCheck className="w-3.5 h-3.5 text-[var(--accent)]" />
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {eligibleForCrossClient && (
                        <>
                            <div className="border-t border-[var(--border-default)]" />
                            <button
                                type="button"
                                role="menuitem"
                                onClick={() => {
                                    setCrossClientMode(!crossClientMode);
                                    setOpen(false);
                                }}
                                className={`
                                    w-full flex items-center gap-2 px-3 py-2 text-[13.5px]
                                    transition-colors hover:bg-[var(--bg-hover)] cursor-pointer
                                    focus-visible:outline-none focus-visible:bg-[var(--bg-hover)]
                                    focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)] focus-visible:ring-inset
                                    ${
                                        crossClientMode
                                            ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                                            : "text-[var(--text-primary)]"
                                    }
                                `}
                            >
                                <FiGlobe className="w-3.5 h-3.5" />
                                <span className="flex-1 text-left">
                                    View all clients
                                </span>
                                {crossClientMode && (
                                    <FiCheck className="w-3.5 h-3.5" />
                                )}
                            </button>
                        </>
                    )}

                    <div className="border-t border-[var(--border-default)]" />
                    {activeClientId != null && (
                        <Link
                            href={`/dashboard/compliance/clients/${activeClientId}`}
                            onClick={() => setOpen(false)}
                            className="
                                w-full flex items-center gap-2 px-3 py-2 text-[13.5px]
                                text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors
                                focus-visible:outline-none focus-visible:bg-[var(--bg-hover)]
                            "
                        >
                            <FiBriefcase className="w-3.5 h-3.5" />
                            Open current organization
                        </Link>
                    )}
                    <Link
                        href="/dashboard/compliance/clients/new"
                        onClick={() => setOpen(false)}
                        className="
                            w-full flex items-center gap-2 px-3 py-2 text-[13.5px]
                            text-[var(--accent)] hover:bg-[var(--bg-hover)] transition-colors
                            focus-visible:outline-none focus-visible:bg-[var(--bg-hover)]
                            focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)] focus-visible:ring-inset
                        "
                    >
                        <FiPlus className="w-3.5 h-3.5" />
                        Onboard new organization
                    </Link>
                </div>
            )}
        </div>
    );
}
