"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { FiAlertTriangle, FiCheckCircle, FiMail } from "react-icons/fi";
import { emailApi, GmailCredentialResponse } from "@/lib/email-api";

interface Props {
    credential: GmailCredentialResponse | null;
    onChange?: () => void;
}

/**
 * ConnectGmailButton — EMAIL-01 OAuth handoff + EMAIL-10 revoked-state surface.
 *
 * Three render branches:
 *   - no credential → primary "Connect Gmail" CTA
 *   - credential.status === "revoked" → red banner + amber Reconnect CTA
 *   - credential.status === "active" → muted "Connected to {email}" with
 *     Reconnect + Disconnect controls
 *
 * Disconnect calls DELETE /email/credentials/{id}; the backend soft-disables
 * the row + removes the APScheduler job (Plan 05 D-EMAIL-10).
 */
export default function ConnectGmailButton({ credential, onChange }: Props) {
    const [busy, setBusy] = useState(false);

    const handleConnect = async () => {
        setBusy(true);
        try {
            const resp = await emailApi.connectGmail();
            window.location.href = resp.data.authorize_url;
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to start Gmail OAuth";
            toast.error(msg);
            setBusy(false);
        }
    };

    const handleDisconnect = async () => {
        if (!credential) return;
        if (
            !confirm(
                "Disconnect Gmail? The scanner will stop and existing ingested documents are preserved.",
            )
        ) {
            return;
        }
        setBusy(true);
        try {
            await emailApi.deleteCredential(credential.id);
            toast.success("Gmail disconnected");
            onChange?.();
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Disconnect failed";
            toast.error(msg);
        } finally {
            setBusy(false);
        }
    };

    if (!credential) {
        return (
            <div
                className="
                    rounded-lg p-6 md:p-8
                    bg-[var(--bg-elevated)] border border-[var(--border-default)]
                    flex flex-col md:flex-row md:items-center gap-5
                "
                data-state="not-connected"
            >
                <div className="flex items-start gap-4 flex-1 min-w-0">
                    <span
                        className="
                            shrink-0 w-12 h-12 rounded-md
                            bg-[var(--accent-soft)] border border-[var(--accent-edge)]
                            flex items-center justify-center
                        "
                        aria-hidden
                    >
                        <FiMail className="w-5 h-5 text-[var(--accent)]" />
                    </span>
                    <div className="min-w-0">
                        <h3 className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
                            Connect your Gmail
                        </h3>
                        <p className="text-[12.5px] text-[var(--text-muted)] mt-1 leading-relaxed">
                            We&apos;ll scan for compliance notices and vendor
                            invoices from approved senders. Email bodies are read
                            on-demand and never stored at rest.
                        </p>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={handleConnect}
                    disabled={busy}
                    className="
                        shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-md
                        bg-[var(--accent)] text-white text-[13px] font-medium
                        hover:bg-[var(--accent-strong)]
                        disabled:opacity-50 disabled:cursor-not-allowed
                        transition-colors duration-150
                        focus-visible:outline-none focus-visible:ring-2
                        focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2
                        focus-visible:ring-offset-[var(--bg-elevated)]
                    "
                >
                    <FiMail className="w-4 h-4" aria-hidden />
                    {busy ? "Redirecting…" : "Connect Gmail"}
                </button>
            </div>
        );
    }

    if (credential.status === "revoked") {
        return (
            <div className="space-y-3">
                <div
                    className="
                        flex items-start gap-3 p-3 rounded-md
                        bg-[var(--danger-soft)] border
                        text-[13px] text-[var(--danger)]
                    "
                    style={{
                        borderColor:
                            "color-mix(in srgb, var(--danger) 30%, transparent)",
                    }}
                    role="alert"
                    data-status="revoked"
                >
                    <FiAlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                    <div>
                        <div className="font-medium text-[var(--danger)]">
                            Reconnect required
                        </div>
                        <div className="mt-0.5 text-[12px] text-[var(--text-secondary)]">
                            Gmail revoked the saved credential. Scanner is paused
                            until you reconnect.
                        </div>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={handleConnect}
                    disabled={busy}
                    className="
                        inline-flex items-center gap-2 px-4 py-2 rounded-md
                        bg-[var(--warning)] text-white text-[13px] font-medium
                        hover:opacity-90 disabled:opacity-50
                        transition-opacity duration-150
                    "
                >
                    {busy ? "Redirecting…" : "Reconnect Gmail"}
                </button>
            </div>
        );
    }

    return (
        <div className="flex flex-wrap items-center gap-3">
            <span
                className="
                    inline-flex items-center gap-1.5 px-2.5 py-1 rounded
                    bg-[var(--success-soft)] text-[var(--success)] text-[12px] font-medium
                "
            >
                <FiCheckCircle className="w-3.5 h-3.5" aria-hidden />
                Connected
                {credential.google_account_email
                    ? ` to ${credential.google_account_email}`
                    : ""}
            </span>
            <button
                type="button"
                onClick={handleConnect}
                disabled={busy}
                className="
                    inline-flex items-center px-3 py-1.5 rounded-md text-[12.5px]
                    bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                    text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                    hover:bg-[var(--bg-hover)] disabled:opacity-50
                    transition-colors duration-150
                "
            >
                Reconnect
            </button>
            <button
                type="button"
                onClick={handleDisconnect}
                disabled={busy}
                className="
                    inline-flex items-center px-3 py-1.5 rounded-md text-[12.5px]
                    border text-[var(--danger)]
                    hover:bg-[var(--danger-soft)] disabled:opacity-50
                    transition-colors duration-150
                "
                style={{
                    borderColor:
                        "color-mix(in srgb, var(--danger) 30%, transparent)",
                }}
            >
                Disconnect
            </button>
        </div>
    );
}
