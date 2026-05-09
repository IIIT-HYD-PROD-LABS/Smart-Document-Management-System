"use client";

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import {
    FiUser,
    FiMail,
    FiCpu,
    FiArrowRight,
    FiShield,
} from "react-icons/fi";

/**
 * Profile hub — single landing for everything tied to the signed-in user.
 *
 * Phase 17 IA reset: Email center and AI assistant moved under Profile so
 * the sidebar's top groups (Workspace, Compliance) only carry tenant-scoped
 * work, while user-scoped settings live here.
 *
 * The Email center and AI assistant pages already exist with their own
 * sub-nav and forms; this page is purely a hub + account summary.
 */
export default function ProfilePage() {
    const { user } = useAuth();

    const initial = (user?.full_name || user?.username || user?.email || "?")
        .charAt(0)
        .toUpperCase();

    const links = [
        {
            href: "/dashboard/email",
            icon: FiMail,
            title: "Email center",
            description:
                "Connect Gmail, manage filter rules, watch fetch activity, and review extracted vendor invoices.",
            cta: "Manage email",
        },
        {
            href: "/dashboard/settings/ai",
            icon: FiCpu,
            title: "AI assistant",
            description:
                "Bring your own Claude or Gemini key. Summaries and actions stay scoped to TaxSync work only.",
            cta: "Configure AI",
        },
    ];

    return (
        <div className="px-6 py-8 max-w-4xl mx-auto">
            <header className="mb-8">
                <h1 className="text-2xl font-semibold text-[var(--text-primary)] tracking-tight">
                    Profile
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1">
                    Your account, email integration, and AI assistant — all in one place.
                </p>
            </header>

            {/* Account identity card */}
            <section className="surface-card p-6 mb-6">
                <div className="flex items-start gap-4">
                    <div
                        className="w-14 h-14 rounded-full bg-[var(--accent)] flex items-center justify-center text-white font-semibold text-lg shrink-0 shadow-sm"
                        aria-hidden
                    >
                        {initial}
                    </div>
                    <div className="min-w-0 flex-1">
                        <p className="text-[16px] font-semibold text-[var(--text-primary)] tracking-tight truncate">
                            {user?.full_name || user?.username || "Signed in"}
                        </p>
                        {user?.email && (
                            <p className="text-[13px] text-[var(--text-muted)] mt-0.5 truncate">
                                {user.email}
                            </p>
                        )}
                        <div className="mt-3 flex items-center gap-2 flex-wrap">
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--accent-soft)] text-[var(--accent)] text-[11px] font-medium uppercase tracking-wider">
                                <FiShield className="w-3 h-3" />
                                {user?.role || "viewer"}
                            </span>
                            {user?.username && (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--bg-muted)] text-[var(--text-secondary)] text-[11px] font-mono">
                                    <FiUser className="w-3 h-3" />
                                    {user.username}
                                </span>
                            )}
                        </div>
                    </div>
                </div>
            </section>

            {/* Profile-scoped destinations */}
            <h2 className="microtype mb-3">Settings</h2>
            <ul className="grid gap-3" role="list">
                {links.map(({ href, icon: Icon, title, description, cta }) => (
                    <li key={href}>
                        <Link
                            href={href}
                            className="
                                group block p-5 rounded-lg border border-[var(--border-default)]
                                bg-[var(--bg-surface)]
                                hover:border-[var(--accent-edge)] hover:bg-[var(--accent-soft)]
                                transition-colors cursor-pointer
                                focus-visible:outline-none focus-visible:ring-2
                                focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2
                                focus-visible:ring-offset-[var(--bg-page)]
                            "
                        >
                            <div className="flex items-start gap-4">
                                <span className="w-10 h-10 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0 group-hover:bg-[var(--accent)] transition-colors">
                                    <Icon className="w-4.5 h-4.5 text-[var(--accent)] group-hover:text-white transition-colors" />
                                </span>
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center justify-between gap-3">
                                        <p className="text-[14.5px] font-semibold text-[var(--text-primary)] tracking-tight">
                                            {title}
                                        </p>
                                        <span className="inline-flex items-center gap-1 text-[12px] text-[var(--text-muted)] group-hover:text-[var(--accent)] transition-colors">
                                            {cta}
                                            <FiArrowRight className="w-3.5 h-3.5" />
                                        </span>
                                    </div>
                                    <p className="text-[12.5px] text-[var(--text-muted)] mt-1 leading-relaxed">
                                        {description}
                                    </p>
                                </div>
                            </div>
                        </Link>
                    </li>
                ))}
            </ul>
        </div>
    );
}
