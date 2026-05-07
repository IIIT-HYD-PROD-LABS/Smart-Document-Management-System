"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import ConnectGmailButton from "@/components/email/ConnectGmailButton";
import { emailApi, GmailCredentialResponse } from "@/lib/email-api";

/**
 * /dashboard/email/connect — EMAIL-01 OAuth flow entry + EMAIL-10 status surface.
 *
 * Handles the Google OAuth round-trip:
 *   1. POST /email/gmail/oauth/authorize → window.location = authorize_url
 *   2. Google redirects back to /api/email/gmail/oauth/callback
 *   3. Backend redirects browser to /dashboard/email/connect?status=success
 *      (or ?error=... on failure)
 *
 * Reads ?status= and ?error= from the URL and surfaces toasts; reloads
 * credentials so the connected email shows immediately.
 */
function ConnectInner() {
    const params = useSearchParams();
    const [creds, setCreds] = useState<GmailCredentialResponse[]>([]);
    const [loading, setLoading] = useState(true);

    const load = async () => {
        try {
            const r = await emailApi.listCredentials();
            setCreds(r.data);
        } catch {
            // Network or permission error — silent. UI shows "no credential" state.
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
        const status = params.get("status");
        const error = params.get("error");
        if (status === "success") {
            toast.success("Gmail connected");
        }
        if (error) {
            toast.error(`OAuth failed: ${error}`);
        }
    }, []);

    if (loading) {
        return (
            <div className="text-[13px] text-[var(--text-muted)]">
                Loading Gmail credentials…
            </div>
        );
    }

    // Surface the most-relevant credential: prefer active, then revoked, else null.
    const active =
        creds.find((c) => c.status === "active") ||
        creds.find((c) => c.status === "revoked") ||
        null;

    return (
        <div className="space-y-6 max-w-3xl">
            <section>
                <h2 className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Connection
                </h2>
                <p className="text-[12.5px] text-[var(--text-muted)] mt-1 mb-4">
                    Grants read + label access to your Gmail. The scanner runs
                    in the background and ingests matching messages per your
                    filter rules.
                </p>
                <ConnectGmailButton credential={active} onChange={load} />
            </section>

            {active && active.status === "active" && (
                <section
                    className="
                        rounded-md p-4
                        bg-[var(--bg-elevated)] border border-[var(--border-default)]
                    "
                >
                    <h3 className="microtype text-[var(--text-muted)] mb-2">
                        Scanner status
                    </h3>
                    <dl className="grid grid-cols-2 gap-3 text-[12.5px]">
                        <div>
                            <dt className="text-[var(--text-subtle)]">Cadence</dt>
                            <dd className="text-[var(--text-primary)] font-mono">
                                Every {active.cadence_minutes} minutes
                            </dd>
                        </div>
                        <div>
                            <dt className="text-[var(--text-subtle)]">Last scan</dt>
                            <dd className="text-[var(--text-primary)] font-mono">
                                {active.last_scan_at
                                    ? new Date(
                                          active.last_scan_at,
                                      ).toLocaleString()
                                    : "Pending first run"}
                            </dd>
                        </div>
                    </dl>
                </section>
            )}
        </div>
    );
}

export default function ConnectPage() {
    return (
        <Suspense
            fallback={
                <div className="text-[13px] text-[var(--text-muted)]">
                    Loading…
                </div>
            }
        >
            <ConnectInner />
        </Suspense>
    );
}
