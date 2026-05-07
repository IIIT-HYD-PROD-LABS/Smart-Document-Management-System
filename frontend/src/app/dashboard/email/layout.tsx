"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SUB_NAV = [
    { href: "/dashboard/email/connect", label: "Connect" },
    { href: "/dashboard/email/settings", label: "Settings" },
    { href: "/dashboard/email/activity", label: "Activity" },
    { href: "/dashboard/email/bills", label: "Bills" },
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
                <h1 className="text-[20px] font-semibold tracking-tight text-white">
                    Gmail
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1">
                    Connect Gmail to auto-ingest compliance notices and personal
                    bills.
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
                                    relative px-3 py-1.5 text-[12.5px] rounded-t-md
                                    transition-colors duration-150
                                    ${
                                        active
                                            ? "text-white"
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

            <div>{children}</div>
        </div>
    );
}
