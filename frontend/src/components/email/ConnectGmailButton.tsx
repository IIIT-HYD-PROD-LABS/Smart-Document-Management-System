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
            <button
                type="button"
                onClick={handleConnect}
                disabled={busy}
                className="
                    inline-flex items-center gap-2 px-4 py-2 rounded-md
                    bg-[var(--accent)] text-white text-[13px] font-medium
                    hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed
                    transition-opacity duration-150
                    focus-visible:outline-none focus-visible:ring-2
                    focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2
                    focus-visible:ring-offset-[var(--bg-page)]
                "
            >
                <FiMail className="w-4 h-4" aria-hidden />
                {busy ? "Redirecting…" : "Connect Gmail"}
            </button>
        );
    }

    if (credential.status === "revoked") {
        return (
            <div className="space-y-3">
                <div
                    className="
                        flex items-start gap-3 p-3 rounded-md
                        bg-[#ef44441a] border border-[#ef444466]
                        text-[13px] text-[#fca5a5]
                    "
                    role="alert"
                    data-status="revoked"
                >
                    <FiAlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                    <div>
                        <div className="font-medium text-[#fecaca]">
                            Reconnect required
                        </div>
                        <div className="mt-0.5 text-[12px] text-[#fca5a5]">
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
                        bg-[var(--warning)] text-[#0c0c0f] text-[13px] font-medium
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
                    bg-[#10b9811a] text-[#10b981] text-[12px] font-medium
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
                    text-[var(--text-secondary)] hover:text-white
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
                    border border-[#ef444466] text-[#ef4444]
                    hover:bg-[#ef44441a] disabled:opacity-50
                    transition-colors duration-150
                "
            >
                Disconnect
            </button>
        </div>
    );
}
