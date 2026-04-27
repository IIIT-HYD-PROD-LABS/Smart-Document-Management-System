"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Zustand store for the active client (multi-tenant frontend state).
 *
 * - `activeClientId` — single-client mode; null until user picks one in switcher.
 * - `crossClientMode` — "All Clients" mode (D-23); only allowed for compliance_head/ca_consultant/cfo.
 * - `eligibleForCrossClient` — set after fetching memberships, gates the toggle visibility.
 *
 * Persisted to localStorage so the active client survives refresh; ClientSwitcher
 * validates the persisted id against fresh /memberships/me on mount and clears
 * if the user no longer has access (e.g., auditor expired, membership revoked).
 */
interface CurrentClientState {
    activeClientId: number | null;
    crossClientMode: boolean;
    eligibleForCrossClient: boolean;
    setActiveClientId: (id: number | null) => void;
    setCrossClientMode: (enabled: boolean) => void;
    setEligibleForCrossClient: (eligible: boolean) => void;
    reset: () => void;
}

export const useCurrentClient = create<CurrentClientState>()(
    persist(
        (set) => ({
            activeClientId: null,
            crossClientMode: false,
            eligibleForCrossClient: false,
            setActiveClientId: (id) =>
                set({ activeClientId: id, crossClientMode: false }),
            setCrossClientMode: (enabled) => set({ crossClientMode: enabled }),
            setEligibleForCrossClient: (eligible) =>
                set({ eligibleForCrossClient: eligible }),
            reset: () =>
                set({
                    activeClientId: null,
                    crossClientMode: false,
                    eligibleForCrossClient: false,
                }),
        }),
        {
            name: "compliance-current-client",
            // Only persist activeClientId + crossClientMode; eligibility is recomputed from API
            partialize: (state) => ({
                activeClientId: state.activeClientId,
                crossClientMode: state.crossClientMode,
            }),
        }
    )
);
