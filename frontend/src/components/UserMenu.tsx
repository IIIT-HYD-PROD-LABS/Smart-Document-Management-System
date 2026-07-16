"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
    FiUser,
    FiMail,
    FiCpu,
    FiShield,
    FiBriefcase,
    FiUsers,
    FiList,
    FiLogOut,
    FiChevronUp,
} from "react-icons/fi";

/**
 * Sidebar user menu — popover that opens upward from the user cluster.
 *
 * Phase 17 IA reset (2026-05-09): Profile and Admin groups were removed
 * from the sidebar. Their items live here instead, behind a click on the
 * user cluster, so the daily-use sidebar stays focused on Core +
 * Workspace + Compliance and personal/admin tools are one tap away.
 *
 * Admin items only render when the signed-in user has `role === 'admin'`,
 * matching the route-level guards on those pages.
 */

interface UserMenuItem {
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
}

const PERSONAL_ITEMS: UserMenuItem[] = [
    { href: "/dashboard/profile", icon: FiUser, label: "Account" },
    { href: "/dashboard/email", icon: FiMail, label: "Email center" },
];

// Shown for any user with an active org (compliance membership). Platform
// admins still get the Admin group below; everyone else needs a path into
// their organization without guessing URLs.
const ORG_ITEM: UserMenuItem = {
    href: "/dashboard/compliance/clients",
    icon: FiBriefcase,
    label: "Your organization",
};

// Admin entries point at the new unified /dashboard/admin shell (a
// second-level sidebar lives inside that layout for deeper navigation).
// Legacy URLs (/dashboard/settings/ai, /dashboard/model-evaluation)
// still resolve via redirect stubs for backwards-compat.
const ADMIN_ITEMS: UserMenuItem[] = [
    { href: "/dashboard/admin", icon: FiShield, label: "Admin home" },
    { href: "/dashboard/admin/users", icon: FiUsers, label: "Users" },
    { href: "/dashboard/admin/audit", icon: FiList, label: "Audit log" },
    { href: "/dashboard/admin/ai", icon: FiCpu, label: "AI provider" },
    {
        href: "/dashboard/admin/organization",
        icon: FiBriefcase,
        label: "Organization settings",
    },
    {
        href: "/dashboard/compliance/clients",
        icon: FiUsers,
        label: "All organizations",
    },
];

interface UserShape {
    username?: string;
    email?: string;
    full_name?: string | null;
    role?: string;
}

export function UserMenu({
    user,
    onSignOut,
    organizationHref,
}: {
    user: UserShape;
    onSignOut: () => Promise<void> | void;
    /** Deep-link for "Your organization" when a client is selected. */
    organizationHref?: string | null;
}) {
    const [open, setOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);

    const isAdmin = user.role === "admin";
    const displayName =
        user.full_name?.trim() || user.username || user.email || "User";
    const initial = displayName.charAt(0).toUpperCase();
    const orgHref = organizationHref || ORG_ITEM.href;

    // Outside-click + Escape close. WCAG 2.1.1 keyboard accessibility.
    // Uses `click` (not `mousedown`) so a Link inside the menu still
    // gets its onClick before the document handler closes the menu —
    // important on touch devices where mousedown-then-click can race.
    useEffect(() => {
        if (!open) return;
        const handleClick = (e: MouseEvent) => {
            if (
                containerRef.current &&
                !containerRef.current.contains(e.target as Node)
            ) {
                setOpen(false);
            }
        };
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                setOpen(false);
                // Return focus to the trigger so keyboard users don't
                // get stranded after dismissing the popover.
                triggerRef.current?.focus();
            }
        };
        document.addEventListener("click", handleClick);
        document.addEventListener("keydown", handleKey);
        return () => {
            document.removeEventListener("click", handleClick);
            document.removeEventListener("keydown", handleKey);
        };
    }, [open]);

    // When the menu opens, move focus to the first menuitem so screen
    // reader + keyboard navigation lands inside the popover instead of
    // staying on the trigger.
    useEffect(() => {
        if (!open || !menuRef.current) return;
        const first = menuRef.current.querySelector<HTMLElement>(
            '[role="menuitem"]'
        );
        first?.focus();
    }, [open]);

    const handleSignOut = async () => {
        setOpen(false);
        await onSignOut();
    };

    return (
        <div ref={containerRef} className="relative">
            <button
                ref={triggerRef}
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label="Open account menu"
                className={`
                    w-full flex items-center gap-2.5 px-2 py-2 rounded-md
                    transition-colors duration-150 cursor-pointer
                    ${
                        open
                            ? "bg-[var(--bg-hover)]"
                            : "hover:bg-[var(--bg-hover)]"
                    }
                    focus-visible:outline-none focus-visible:ring-2
                    focus-visible:ring-[var(--accent)]
                    focus-visible:ring-offset-2
                    focus-visible:ring-offset-[var(--bg-page)]
                `}
            >
                <div
                    className="w-8 h-8 rounded-full bg-[var(--accent)] flex items-center justify-center text-[12px] font-semibold text-white shrink-0 shadow-sm"
                    aria-hidden
                >
                    {initial}
                </div>
                <div className="flex-1 min-w-0 text-left">
                    <p className="text-[13px] font-medium text-[var(--text-primary)] truncate">
                        {user.username || displayName}
                    </p>
                    {user.email && (
                        <p className="text-[11.5px] text-[var(--text-subtle)] truncate">
                            {user.email}
                        </p>
                    )}
                </div>
                {user.role && (
                    <span className="microtype shrink-0 px-1.5 py-0.5 rounded bg-[var(--bg-hover)] border border-[var(--border-default)] text-[var(--text-muted)]">
                        {user.role}
                    </span>
                )}
                <FiChevronUp
                    className={`w-3.5 h-3.5 text-[var(--text-subtle)] shrink-0 motion-safe:transition-transform motion-safe:duration-150 ${
                        open ? "" : "rotate-180"
                    }`}
                    aria-hidden
                />
            </button>

            {open && (
                <div
                    ref={menuRef}
                    role="menu"
                    aria-label="Account menu"
                    className="
                        absolute left-0 right-0 bottom-full mb-2
                        bg-[var(--bg-elevated)]
                        border border-[var(--border-default)]
                        rounded-lg shadow-[var(--shadow-lg)]
                        overflow-hidden z-50
                    "
                >
                    {/* Identity strip */}
                    <div className="px-3 py-3 border-b border-[var(--border-default)]">
                        <p className="text-[13px] font-semibold text-[var(--text-primary)] truncate">
                            {displayName}
                        </p>
                        {user.email && (
                            <p className="text-[11.5px] text-[var(--text-muted)] truncate mt-0.5">
                                {user.email}
                            </p>
                        )}
                    </div>

                    {/* Personal */}
                    <ul className="py-1.5" role="none">
                        {PERSONAL_ITEMS.map(({ href, icon: Icon, label }) => (
                            <li key={href} role="none">
                                <Link
                                    href={href}
                                    role="menuitem"
                                    onClick={() => setOpen(false)}
                                    className="
                                        flex items-center gap-2.5
                                        mx-1.5 px-2.5 py-2 rounded-md
                                        text-[13px] text-[var(--text-primary)]
                                        hover:bg-[var(--bg-hover)]
                                        transition-colors duration-150 cursor-pointer
                                        focus:outline-none focus:bg-[var(--bg-hover)]
                                    "
                                >
                                    <Icon className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                                    <span className="truncate">{label}</span>
                                </Link>
                            </li>
                        ))}
                        {/* Your organization — every member, not only platform admin */}
                        <li role="none">
                            <Link
                                href={orgHref}
                                role="menuitem"
                                onClick={() => setOpen(false)}
                                className="
                                    flex items-center gap-2.5
                                    mx-1.5 px-2.5 py-2 rounded-md
                                    text-[13px] text-[var(--text-primary)]
                                    hover:bg-[var(--bg-hover)]
                                    transition-colors duration-150 cursor-pointer
                                    focus:outline-none focus:bg-[var(--bg-hover)]
                                "
                            >
                                <ORG_ITEM.icon className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                                <span className="truncate">{ORG_ITEM.label}</span>
                            </Link>
                        </li>
                    </ul>

                    {/* Admin (role-gated) */}
                    {isAdmin && (
                        <>
                            <div className="border-t border-[var(--border-default)]" />
                            <p
                                className="microtype px-3 pt-2 pb-1"
                                role="presentation"
                            >
                                Admin
                            </p>
                            <ul className="pb-1.5" role="none">
                                {ADMIN_ITEMS.map(
                                    ({ href, icon: Icon, label }) => (
                                        <li key={href} role="none">
                                            <Link
                                                href={href}
                                                role="menuitem"
                                                onClick={() => setOpen(false)}
                                                className="
                                                    flex items-center gap-2.5
                                                    mx-1.5 px-2.5 py-2 rounded-md
                                                    text-[13px] text-[var(--text-primary)]
                                                    hover:bg-[var(--bg-hover)]
                                                    transition-colors duration-150 cursor-pointer
                                                    focus:outline-none focus:bg-[var(--bg-hover)]
                                                "
                                            >
                                                <Icon className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                                                <span className="truncate">
                                                    {label}
                                                </span>
                                            </Link>
                                        </li>
                                    )
                                )}
                            </ul>
                        </>
                    )}

                    {/* Sign out */}
                    <div className="border-t border-[var(--border-default)]">
                        <button
                            type="button"
                            role="menuitem"
                            onClick={handleSignOut}
                            className="
                                w-full flex items-center gap-2.5 px-3 py-2.5
                                text-[13px] text-[var(--text-muted)]
                                hover:text-[var(--danger)] hover:bg-[var(--bg-hover)]
                                transition-colors duration-150 cursor-pointer
                                focus:outline-none focus:bg-[var(--bg-hover)]
                                focus:text-[var(--danger)]
                            "
                        >
                            <FiLogOut className="w-3.5 h-3.5 shrink-0" />
                            Sign out
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
