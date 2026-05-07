"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import FilterRulesEditor from "@/components/email/FilterRulesEditor";
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
            <div className="text-[13px] text-[var(--text-muted)]">
                Loading…
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
