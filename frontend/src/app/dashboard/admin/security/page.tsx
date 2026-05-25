"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
    FiAlertTriangle,
    FiCheck,
    FiClock,
    FiExternalLink,
    FiKey,
    FiLock,
    FiShield,
    FiUsers,
} from "react-icons/fi";

import { oauthApi } from "@/lib/api";

export const dynamic = "force-dynamic";

function SectionCard({
    title,
    description,
    icon: Icon,
    children,
}: {
    title: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
    children: React.ReactNode;
}) {
    return (
        <section className="surface-card p-6">
            <div className="flex items-start gap-3 mb-4">
                <span className="w-8 h-8 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4 text-[var(--accent)]" />
                </span>
                <div className="min-w-0">
                    <h2 className="text-[14px] font-semibold text-[var(--text-primary)]">
                        {title}
                    </h2>
                    <p className="text-[12px] text-[var(--text-muted)] mt-0.5">
                        {description}
                    </p>
                </div>
            </div>
            {children}
        </section>
    );
}

function PolicyRow({
    label,
    enabled,
    detail,
    pending,
}: {
    label: string;
    enabled: boolean;
    detail: string;
    pending?: boolean;
}) {
    return (
        <div className="flex items-start justify-between gap-4 py-2.5 border-b border-[var(--border-subtle)] last:border-0">
            <div className="min-w-0">
                <p className="text-[13px] text-[var(--text-primary)]">{label}</p>
                <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5">
                    {detail}
                </p>
            </div>
            <span
                className={`shrink-0 inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium ${
                    pending
                        ? "bg-[var(--bg-hover)] text-[var(--text-muted)] border border-[var(--border-default)]"
                        : enabled
                          ? "bg-[var(--success-soft)] text-[var(--success)]"
                          : "bg-[var(--bg-hover)] text-[var(--text-muted)]"
                }`}
            >
                {pending ? <FiClock className="w-3 h-3" /> : enabled ? <FiCheck className="w-3 h-3" /> : <FiAlertTriangle className="w-3 h-3" />}
                {pending ? "Planned" : enabled ? "Enforced" : "Off"}
            </span>
        </div>
    );
}

export default function SecurityPage() {
    const [providers, setProviders] = useState<string[]>([]);
    const [providersLoading, setProvidersLoading] = useState(true);

    useEffect(() => {
        oauthApi
            .getProviders()
            .then((res) => setProviders(res.data.providers || []))
            .catch(() => setProviders([]))
            .finally(() => setProvidersLoading(false));
    }, []);

    return (
        <div className="space-y-6">
            <header>
                <p className="microtype mb-2">Admin</p>
                <h1 className="text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Security
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1.5">
                    Authentication policies, sign-in providers, and account hardening.
                </p>
            </header>

            <SectionCard
                title="Password policy"
                description="Applies to all newly-set passwords (register + invite accept + reset)."
                icon={FiKey}
            >
                <ul className="text-[13px] text-[var(--text-primary)] space-y-1.5">
                    <li className="flex items-center gap-2">
                        <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> Minimum 8 characters (registration), 12 characters (team invite)
                    </li>
                    <li className="flex items-center gap-2">
                        <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> At least one uppercase letter
                    </li>
                    <li className="flex items-center gap-2">
                        <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> At least one lowercase letter
                    </li>
                    <li className="flex items-center gap-2">
                        <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> At least one digit
                    </li>
                    <li className="flex items-center gap-2">
                        <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> At least one special character
                    </li>
                </ul>
            </SectionCard>

            <SectionCard
                title="Account hardening"
                description="Defence in depth on top of password policy."
                icon={FiShield}
            >
                <PolicyRow
                    label="Multi-factor authentication (MFA)"
                    detail="TOTP authenticator app with one-time backup codes, enforced on every sign-in once a user enrolls. Users manage their own enrollment from Profile."
                    enabled
                />
                <PolicyRow
                    label="Session timeout"
                    detail="Access token 30 min, refresh token 7 days, single-use refresh with reuse detection."
                    enabled
                />
                <PolicyRow
                    label="Brute-force lockout"
                    detail="5 failed attempts trigger a 15-minute lock with exponential backoff, per account, on top of the global rate limit."
                    enabled
                />
                <PolicyRow
                    label="Audit log immutability"
                    detail="Database trigger blocks UPDATE or DELETE on audit_logs."
                    enabled
                />
                <PolicyRow
                    label="Self-service password reset"
                    detail="Forgot-password flow emails a 15-minute single-use signed link; completing a reset revokes every outstanding refresh token. Audit rows on request + completion."
                    enabled
                />
            </SectionCard>

            <SectionCard
                title="Sign-in providers"
                description="Which authentication providers users can pick on the login page."
                icon={FiUsers}
            >
                {providersLoading ? (
                    <p className="text-[12px] text-[var(--text-muted)]">Loading...</p>
                ) : (
                    <ul className="text-[13px] text-[var(--text-primary)] space-y-1.5">
                        {["local", "google", "microsoft"].map((p) => {
                            const enabled = providers.includes(p);
                            return (
                                <li key={p} className="flex items-center justify-between">
                                    <span className="capitalize">{p === "local" ? "Email and password" : p}</span>
                                    <span
                                        className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                                            enabled
                                                ? "bg-[var(--success-soft)] text-[var(--success)]"
                                                : "bg-[var(--bg-hover)] text-[var(--text-muted)]"
                                        }`}
                                    >
                                        {enabled ? "Configured" : "Not configured"}
                                    </span>
                                </li>
                            );
                        })}
                    </ul>
                )}
                <div className="mt-4 pt-4 border-t border-[var(--border-subtle)]">
                    <Link
                        href="/oauth-setup"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors"
                    >
                        OAuth setup helper
                        <FiExternalLink className="w-3.5 h-3.5" />
                    </Link>
                </div>
            </SectionCard>

            <SectionCard
                title="Registration gate"
                description="Only invited applicants can register after the bootstrap admin."
                icon={FiLock}
            >
                <ul className="text-[13px] text-[var(--text-primary)] space-y-1.5">
                    <li className="flex items-center gap-2">
                        <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> Early-access invitation token required (single-use, 7 day expiry)
                    </li>
                    <li className="flex items-center gap-2">
                        <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> First-user bootstrap protected by Postgres advisory lock
                    </li>
                    <li className="flex items-center gap-2">
                        <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> Invitation tokens never returned in API responses
                    </li>
                </ul>
            </SectionCard>
        </div>
    );
}
