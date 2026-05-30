"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import FetchActivity from "@/components/email/FetchActivity";
import { Skeleton } from "@/components";
import { emailApi } from "@/lib/email-api";

/**
 * /dashboard/email/activity — EMAIL-07 GmailFetchLog viewer.
 *
 * Renders activity for the first non-disabled credential. Disabled
 * credentials never run scanner jobs (Plan 05 DELETE soft-disables),
 * so their fetch log is functionally empty going forward.
 */
export default function ActivityPage() {
    const [credId, setCredId] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        emailApi
            .listCredentials()
            .then((r) => {
                const active = r.data.find((c) => c.status !== "disabled");
                setCredId(active?.id ?? null);
            })
            .catch(() => {
                setCredId(null);
            })
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div
                className="space-y-2"
                role="status"
                aria-busy="true"
                aria-live="polite"
            >
                <span className="sr-only">Loading fetch activity</span>
                {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full rounded" />
                ))}
            </div>
        );
    }

    if (credId === null) {
        return (
            <div
                className="
                    rounded-md p-4
                    bg-[var(--bg-elevated)] border border-[var(--border-default)]
                    text-[13px] text-[var(--text-muted)]
                "
            >
                No active Gmail credential.{" "}
                <Link
                    href="/dashboard/email/connect"
                    className="text-[var(--accent)] hover:underline"
                >
                    Connect one →
                </Link>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <h2 className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
                Recent scans
            </h2>
            <FetchActivity credentialId={credId} />
        </div>
    );
}
