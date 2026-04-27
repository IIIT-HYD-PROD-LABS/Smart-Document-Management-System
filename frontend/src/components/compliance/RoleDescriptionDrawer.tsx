"use client";

import { useEffect } from "react";
import {
    COMPLIANCE_ROLE_LABELS,
    COMPLIANCE_ROLE_COLORS,
    type ComplianceRole,
} from "@/types/compliance";

/**
 * Right-side drawer that documents the explicit permission set for each
 * compliance role (D-26 — flat permissions, no inheritance hierarchy).
 *
 * The permission lists below mirror the backend RBAC matrix from Plan 02
 * (compliance_permissions.py). Showing the explicit list to users (rather
 * than implying a hierarchy) is a deliberate design choice: it prevents
 * users from assuming a "Compliance Head ⊃ Legal Team" relationship that
 * the matrix does not encode.
 */
const ROLE_PERMISSIONS_DESCRIPTION: Record<ComplianceRole, string[]> = {
    compliance_head: [
        "View all notices",
        "Create notices",
        "Approve responses",
        "Submit responses",
        "Bulk update notices",
        "Manage team",
        "View / Export reports",
        "Trigger escalation",
    ],
    legal_team: ["View notices", "Draft responses", "View reports"],
    finance_team: ["View tax notices (GST / IT)", "View reports"],
    auditor: [
        "View notices (read-only)",
        "View audit log",
        "View / Export reports",
    ],
    ca_consultant: [
        "View notices",
        "Create notices",
        "Draft responses",
        "Approve responses",
        "Submit responses",
        "Bulk update notices",
        "Create clients",
        "Manage team",
        "View / Export reports",
    ],
    staff: [
        "View notices",
        "Create notices",
        "Draft responses",
        "Trigger escalation",
    ],
    cfo: [
        "View notices (read-only)",
        "View / Export reports",
        "Trigger escalation",
    ],
};

export function RoleDescriptionDrawer({
    role,
    onClose,
}: {
    role: ComplianceRole;
    onClose: () => void;
}) {
    // Close on Escape
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        document.addEventListener("keydown", handler);
        return () => document.removeEventListener("keydown", handler);
    }, [onClose]);

    return (
        <div
            className="fixed inset-0 z-40 bg-black/40"
            role="dialog"
            aria-modal="true"
            aria-labelledby="role-drawer-title"
            onClick={onClose}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                className="absolute right-0 top-0 h-full w-full max-w-sm bg-[#111113] border-l border-[#27272a] p-6 overflow-y-auto"
            >
                <div className="flex items-center gap-3 mb-4">
                    <span
                        className="px-2 py-1 rounded text-[11px] font-medium"
                        style={{
                            backgroundColor: `${COMPLIANCE_ROLE_COLORS[role]}1a`,
                            color: COMPLIANCE_ROLE_COLORS[role],
                        }}
                    >
                        {COMPLIANCE_ROLE_LABELS[role]}
                    </span>
                </div>
                <h2
                    id="role-drawer-title"
                    className="text-base font-semibold text-white mb-2"
                >
                    {COMPLIANCE_ROLE_LABELS[role]} permissions
                </h2>
                <p className="text-[#71717a] text-xs mb-4">
                    The explicit permissions granted to a user with this role
                    on this client. Roles are flat — none inherits from another.
                </p>
                <p className="text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-3">
                    Permissions
                </p>
                <ul className="space-y-2 text-sm text-white">
                    {ROLE_PERMISSIONS_DESCRIPTION[role].map((perm) => (
                        <li key={perm} className="flex items-start gap-2">
                            <span
                                className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                                style={{
                                    backgroundColor:
                                        COMPLIANCE_ROLE_COLORS[role],
                                }}
                            />
                            <span>{perm}</span>
                        </li>
                    ))}
                </ul>
                <button
                    type="button"
                    onClick={onClose}
                    className="mt-6 px-3 py-1.5 rounded text-[#a1a1aa] text-sm hover:text-white hover:bg-[#18181b] transition-colors"
                >
                    Close
                </button>
            </div>
        </div>
    );
}
