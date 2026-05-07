"use client";

import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    FiChevronDown,
    FiCheck,
    FiGlobe,
    FiPlus,
    FiSearch,
} from "react-icons/fi";
import Link from "next/link";
import { complianceApi } from "@/lib/api/compliance";
import { useCurrentClient } from "@/stores/currentClientStore";
import {
    ROLES_ELIGIBLE_FOR_CROSS_CLIENT,
    type Membership,
    type Client,
} from "@/types/compliance";

/**
 * Top-bar client switcher per UI-SPEC Section 5 (D-22, D-23).
 *
 * - Trigger pill: current client name + chevron; cross-client mode shows globe
 *   icon + faint accent background.
 * - Dropdown: 320px wide, max-height 480px, search input, alphabetical client
 *   list, "View all clients" toggle (gated by eligibility), "Onboard new client" link.
 * - Active client: 3px accent left-border + check icon.
 * - Outside-click + Escape close the dropdown (keyboard accessible per WCAG 2.1.1).
 * - Membership validation: persisted activeClientId is cleared if not present in
 *   fresh /memberships/me response (auditor expired, access revoked, etc.).
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

    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const dropdownRef = useRef<HTMLDivElement>(null);

    const { data: memberships, isLoading } = useQuery<Membership[]>({
        queryKey: ["memberships", "mine"],
        queryFn: () => complianceApi.listMyMemberships().then((r) => r.data),
    });

    // Determine eligibility for cross-client mode (any membership has eligible role)
    useEffect(() => {
        if (!memberships) return;
        const eligible = memberships.some((m) =>
            ROLES_ELIGIBLE_FOR_CROSS_CLIENT.includes(m.compliance_role)
        );
        setEligibleForCrossClient(eligible);
    }, [memberships, setEligibleForCrossClient]);

    // Validate persisted activeClientId against fresh memberships on mount.
    // If the user no longer has access (auditor expired, membership revoked),
    // clear the active client to avoid sending a forbidden X-Client-Id.
    useEffect(() => {
        if (!memberships || activeClientId === null) return;
        if (!memberships.some((m) => m.client_id === activeClientId)) {
            setActiveClientId(null);
        }
    }, [memberships, activeClientId, setActiveClientId]);

    // Fetch active client name for the trigger button. Disabled in cross-client mode
    // (we display "All Clients" then) and when no client is selected.
    const { data: activeClient } = useQuery<Client>({
        queryKey: ["client", activeClientId],
        queryFn: () =>
            complianceApi.getClient(activeClientId!).then((r) => r.data),
        enabled: activeClientId !== null && !crossClientMode,
    });

    // Close dropdown on outside click and Escape key (WCAG 2.1.1 keyboard accessibility).
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

    const filtered = useMemo(() => {
        if (!memberships) return [];
        const q = query.trim().toLowerCase();
        if (!q) return memberships;
        // Client names not yet loaded for the full list (would require N+1 fetches);
        // filter by client_id substring as a stable interim. Notice/Detail pages
        // load names individually; future enhancement: batch /clients?ids=1,2,3.
        return memberships.filter((m) => String(m.client_id).includes(q));
    }, [memberships, query]);

    const triggerLabel = crossClientMode
        ? "All Clients"
        : activeClient?.name ??
          (activeClientId ? `Client #${activeClientId}` : "Select a client");

    const handleClientClick = useCallback(
        (clientId: number) => {
            setActiveClientId(clientId);
            setCrossClientMode(false);
            setOpen(false);
        },
        [setActiveClientId, setCrossClientMode]
    );

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                type="button"
                onClick={() => setOpen(!open)}
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label="Switch client"
                className={`
                    flex items-center gap-2 px-3 py-1.5 rounded-md text-[13px]
                    border transition-colors
                    ${
                        crossClientMode
                            ? "bg-[var(--accent-soft)] border-[var(--accent-edge)] text-[var(--accent)]"
                            : "bg-[var(--bg-elevated)] border-[var(--border-default)] text-[var(--text-primary)] hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)]"
                    }
                `}
            >
                {crossClientMode && <FiGlobe className="w-3.5 h-3.5" />}
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
                    {/* Search input */}
                    <div className="p-2 border-b border-[var(--border-default)]">
                        <div className="relative">
                            <FiSearch className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-subtle)]" />
                            <input
                                type="text"
                                placeholder="Search clients"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                className="
                                    w-full pl-8 pr-2 py-1.5 text-[13.5px]
                                    bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md
                                    text-[var(--text-primary)] placeholder:text-[var(--text-disabled)]
                                    focus:outline-none focus:border-[var(--accent)]
                                    focus:ring-2 focus:ring-[var(--accent-edge)]
                                "
                                aria-label="Search clients"
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
                            No clients yet
                        </div>
                    )}

                    {!isLoading &&
                        memberships &&
                        memberships.length > 0 &&
                        filtered.length === 0 && (
                            <div className="p-4 text-[13px] text-[var(--text-muted)] text-center">
                                No clients match {`"${query}"`}
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
                                            text-left hover:bg-[var(--bg-hover)] transition-colors
                                            ${
                                                isActive
                                                    ? "border-l-[3px] border-[var(--accent)] pl-[9px] bg-[var(--accent-soft)]"
                                                    : ""
                                            }
                                        `}
                                    >
                                        <span className="flex-1 text-[var(--text-primary)] truncate">
                                            Client #{m.client_id}
                                        </span>
                                        <span className="text-[11px] text-[var(--text-muted)] uppercase font-semibold">
                                            {m.compliance_role.replace(
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

                    {/* Cross-client toggle (D-23) — gated by eligibility */}
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
                                    transition-colors hover:bg-[var(--bg-hover)]
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

                    {/* Onboard new client */}
                    <div className="border-t border-[var(--border-default)]" />
                    <Link
                        href="/dashboard/compliance/clients/new"
                        onClick={() => setOpen(false)}
                        className="
                            w-full flex items-center gap-2 px-3 py-2 text-[13.5px]
                            text-[var(--accent)] hover:bg-[var(--bg-hover)] transition-colors
                        "
                    >
                        <FiPlus className="w-3.5 h-3.5" />
                        Onboard new client
                    </Link>
                </div>
            )}
        </div>
    );
}
