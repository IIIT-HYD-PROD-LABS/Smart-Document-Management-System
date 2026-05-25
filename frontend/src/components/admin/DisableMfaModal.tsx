"use client";

import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { FiAlertTriangle, FiX } from "react-icons/fi";
import { authApi, extractErrorMessage } from "@/lib/api";

interface Props {
    open: boolean;
    onClose: () => void;
    onDisabled: () => void;
}

/**
 * DisableMfaModal — turn off TOTP.
 *
 * Requires a current 6-digit code (or backup code) to confirm, mirroring the
 * DeleteUserModal gate. On success the backend returns 204; the parent
 * refreshes user state so the entry point flips back to "Set up".
 */
export default function DisableMfaModal({ open, onClose, onDisabled }: Props) {
    const [code, setCode] = useState("");
    const [busy, setBusy] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (open) {
            setCode("");
            requestAnimationFrame(() => inputRef.current?.focus());
        }
    }, [open]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !busy) onClose();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, busy, onClose]);

    if (!open) return null;

    const handleDisable = async () => {
        if (!code.trim() || busy) return;
        setBusy(true);
        try {
            await authApi.disableTotp(code.trim());
            toast.success("Two-factor authentication disabled");
            onDisabled();
            onClose();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Could not disable. Check the code and try again."));
            setCode("");
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(15,23,42,0.45)] backdrop-blur-sm motion-safe:animate-in motion-safe:fade-in motion-safe:duration-150"
            onClick={() => !busy && onClose()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="disable-mfa-title"
        >
            <div
                onClick={(e) => e.stopPropagation()}
                className="
                    w-[440px] max-w-[92vw] rounded-[10px]
                    bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                    shadow-[var(--shadow-lg)]
                    motion-safe:animate-in motion-safe:zoom-in-95 motion-safe:duration-150
                "
            >
                <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border-default)]">
                    <div className="flex items-center gap-2.5">
                        <span
                            aria-hidden
                            className="flex items-center justify-center w-7 h-7 rounded-md bg-[var(--danger-soft)] text-[var(--danger)]"
                        >
                            <FiAlertTriangle className="w-4 h-4" />
                        </span>
                        <div>
                            <h3
                                id="disable-mfa-title"
                                className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]"
                            >
                                Disable two-factor authentication
                            </h3>
                            <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5">
                                Confirm with a current code to turn it off
                            </p>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={busy}
                        className="
                            p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)] transition-colors
                            focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]
                            disabled:opacity-50
                        "
                        aria-label="Close"
                    >
                        <FiX className="w-4 h-4" />
                    </button>
                </div>

                <div className="px-5 py-4 space-y-4">
                    <div className="rounded-md border border-[var(--danger-soft)] bg-[var(--danger-soft)]/40 px-3 py-2.5">
                        <p className="text-[12.5px] text-[var(--text-primary)] leading-relaxed">
                            Your account will rely on its password alone after this. You can re-enable
                            two-factor authentication at any time.
                        </p>
                    </div>

                    <label className="block">
                        <span className="microtype text-[var(--text-muted)] block mb-1.5">
                            Authenticator or backup code
                        </span>
                        <input
                            ref={inputRef}
                            type="text"
                            value={code}
                            onChange={(e) => setCode(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && code.trim() && !busy) {
                                    e.preventDefault();
                                    handleDisable();
                                }
                            }}
                            inputMode="numeric"
                            autoComplete="one-time-code"
                            spellCheck={false}
                            disabled={busy}
                            placeholder="123456"
                            className="
                                w-full px-3 py-2 rounded-md font-mono tracking-[0.3em]
                                bg-[var(--bg-page)]
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)]
                                placeholder:text-[var(--text-disabled)]
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                                disabled:opacity-50
                            "
                            aria-label="Authenticator or backup code"
                        />
                    </label>
                </div>

                <div className="flex justify-end gap-2 px-5 py-3 border-t border-[var(--border-default)]">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={busy}
                        className="
                            inline-flex items-center px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--bg-surface)] border border-[var(--border-emphasis)]
                            text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)] disabled:opacity-50
                            transition-colors cursor-pointer
                            focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]
                        "
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onClick={handleDisable}
                        disabled={!code.trim() || busy}
                        className="
                            inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--danger)] text-white font-medium
                            hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed
                            transition-opacity cursor-pointer
                            focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--danger)]
                        "
                    >
                        {busy ? "Disabling…" : "Disable"}
                    </button>
                </div>
            </div>
        </div>
    );
}
