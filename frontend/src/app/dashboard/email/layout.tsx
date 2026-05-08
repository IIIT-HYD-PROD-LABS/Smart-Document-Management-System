"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { complianceApi } from "@/lib/api/compliance";
import { useCurrentClient } from "@/stores/currentClientStore";

const SUB_NAV = [
    { href: "/dashboard/email/connect", label: "Connect" },
    { href: "/dashboard/email/settings", label: "Settings" },
    { href: "/dashboard/email/activity", label: "Activity" },
    { href: "/dashboard/email/bills", label: "Vendor invoices" },
];

/**
 * Email section layout — D-24 /dashboard/email route tree.
 *
 * Wraps all /dashboard/email/** subroutes with a shared header + horizontal
 * sub-nav. Sits inside the outer /dashboard layout (which provides the
 * sidebar + auth gate); we are an inner layout, NOT a replacement.
 */
export default function EmailLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const setActiveClientId = useCurrentClient((s) => s.setActiveClientId);
    const [bootstrapping, setBootstrapping] = useState(activeClientId === null);
    const [noMemberships, setNoMemberships] = useState(false);

    /**
     * Auto-select the user's first ClientMembership if no active client is set.
     * Email routes are gated by `require_compliance_permission('email_integration:use')`
     * which requires X-Client-Id on every call. Without this bootstrap, a fresh
     * login on /dashboard/email/* would 400 every API call until the user
     * navigated through Compliance to pick a client.
     */
    useEffect(() => {
        if (activeClientId !== null) {
            setBootstrapping(false);
            return;
        }
        let cancelled = false;
        complianceApi
            .listMyMemberships()
            .then((r) => {
                if (cancelled) return;
                const first = r.data?.[0];
                if (first?.client_id) {
                    setActiveClientId(first.client_id);
                } else {
                    setNoMemberships(true);
                }
            })
            .catch(() => {
                if (!cancelled) setNoMemberships(true);
            })
            .finally(() => {
                if (!cancelled) setBootstrapping(false);
            });
        return () => {
            cancelled = true;
        };
    }, [activeClientId, setActiveClientId]);

    const isActive = (href: string) => {
        if (pathname === href) return true;
        return pathname.startsWith(href + "/");
    };

    return (
        <div className="space-y-6">
            <header
                className="
                    sticky top-0 z-30 bg-[var(--bg-page)]
                    border-b border-[var(--border-default)]
                    -mx-6 -mt-6 px-6 pt-6 pb-3 md:-mx-10 md:-mt-10 md:px-10 md:pt-10
                "
            >
                <h1 className="text-[24px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Gmail
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1">
                    Connect Gmail to auto-ingest compliance notices and vendor
                    invoices.
                </p>
                <nav
                    className="mt-4 flex items-center gap-1"
                    aria-label="Email sub-navigation"
                >
                    {SUB_NAV.map((item) => {
                        const active = isActive(item.href);
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`
                                    relative px-3 py-1.5 text-[13px] rounded-t-md
                                    transition-colors duration-150
                                    ${
                                        active
                                            ? "text-[var(--text-primary)]"
                                            : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                                    }
                                `}
                                aria-current={active ? "page" : undefined}
                            >
                                {item.label}
                                {active && (
                                    <span
                                        className="
                                            absolute left-2 right-2 -bottom-px
                                            h-[2px] rounded-t bg-[var(--accent)]
                                        "
                                        aria-hidden
                                    />
                                )}
                            </Link>
                        );
                    })}
                </nav>
            </header>

            {bootstrapping ? (
                <div className="text-[13px] text-[var(--text-muted)]">
                    Loading active client…
                </div>
            ) : noMemberships ? (
                <div
                    className="
                        rounded-md p-4
                        bg-[var(--bg-elevated)] border border-[var(--border-default)]
                        text-[13px]
                    "
                >
                    <p className="text-[var(--text-primary)] font-medium">
                        No client memberships found
                    </p>
                    <p className="text-[var(--text-muted)] mt-1">
                        Email features require an active client. Visit{" "}
                        <Link
                            href="/dashboard/compliance/clients"
                            className="text-[var(--accent)] hover:underline"
                        >
                            Compliance → Clients
                        </Link>{" "}
                        to onboard or join a client.
                    </p>
                </div>
            ) : (
                <div>{children}</div>
            )}
        </div>
    );
}
