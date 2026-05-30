"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import FilterRulesEditor from "@/components/email/FilterRulesEditor";
import { Skeleton } from "@/components";
import { emailApi } from "@/lib/email-api";

/**
 * /dashboard/email/settings — EMAIL-04 filter rule CRUD surface.
 *
 * Selects the first credential whose status === "active" and renders
 * FilterRulesEditor. If no active credential exists, prompts the user
 * to connect Gmail first.
 */
export default function SettingsPage() {
    const [credId, setCredId] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        emailApi
            .listCredentials()
            .then((r) => {
                const active = r.data.find((c) => c.status === "active");
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
                className="space-y-4"
                role="status"
                aria-busy="true"
                aria-live="polite"
            >
                <span className="sr-only">Loading filter rules</span>
                <div className="flex items-center justify-between">
                    <Skeleton className="h-5 w-28" />
                    <Skeleton className="h-7 w-24 rounded-md" />
                </div>
                <div className="space-y-2">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-9 w-full rounded" />
                    ))}
                </div>
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
                Connect Gmail to manage filter rules.{" "}
                <Link
                    href="/dashboard/email/connect"
                    className="text-[var(--accent)] hover:underline"
                >
                    Go to Connect →
                </Link>
            </div>
        );
    }

    return <FilterRulesEditor credentialId={credId} />;
}
