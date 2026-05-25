"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { FiCheck, FiCopy, FiShield, FiSmartphone, FiX } from "react-icons/fi";
import { authApi, extractErrorMessage } from "@/lib/api";

interface Props {
    open: boolean;
    onClose: () => void;
    onEnrolled: () => void;
}

interface EnrollData {
    secret: string;
    otpauth_uri: string;
    qr_data_uri: string;
}

/**
 * EnrollMfaModal — per-user TOTP enrollment.
 *
 * Mirrors the established modal pattern (MarkPaidModal header/body/footer
 * rhythm + DeleteUserModal backdrop animation, Escape, click-outside, focus
 * management) so the design language stays consistent.
 *
 * Step "scan": on open, POST /auth/totp/enroll, render the returned QR PNG
 * (qr_data_uri is a data: URL) plus the manual secret, then confirm a 6-digit
 * code via POST /auth/totp/confirm.
 * Step "backup": show the one-time backup codes returned by confirm. These are
 * shown ONCE, so the modal blocks Escape/click-outside on this step.
 */
export default function EnrollMfaModal({ open, onClose, onEnrolled }: Props) {
    const [step, setStep] = useState<"scan" | "backup">("scan");
    const [enrollData, setEnrollData] = useState<EnrollData | null>(null);
    const [enrollError, setEnrollError] = useState<string | null>(null);
    const [code, setCode] = useState("");
    const [backupCodes, setBackupCodes] = useState<string[]>([]);
    const [busy, setBusy] = useState(false);
    const [secretCopied, setSecretCopied] = useState(false);
    const [codesCopied, setCodesCopied] = useState(false);
    const codeInputRef = useRef<HTMLInputElement>(null);

    const loadEnrollment = useCallback(async () => {
        setBusy(true);
        setEnrollError(null);
        try {
            const res = await authApi.enrollTotp();
            setEnrollData(res.data);
            requestAnimationFrame(() => codeInputRef.current?.focus());
        } catch (err: unknown) {
            const msg = extractErrorMessage(err, "Could not start enrollment");
            setEnrollError(msg);
            toast.error(msg);
        } finally {
            setBusy(false);
        }
    }, []);

    // Reset + kick off enrollment each time the modal opens.
    useEffect(() => {
        if (!open) return;
        setStep("scan");
        setEnrollData(null);
        setCode("");
        setBackupCodes([]);
        setSecretCopied(false);
        setCodesCopied(false);
        loadEnrollment();
    }, [open, loadEnrollment]);

    // Escape closes — but never on the backup step (codes shown once).
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !busy && step !== "backup") onClose();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, busy, step, onClose]);

    if (!open) return null;

    const dismiss = () => {
        // Click-outside / X: blocked while busy and on the backup step.
        if (busy || step === "backup") return;
        onClose();
    };

    const copySecret = async () => {
        if (!enrollData) return;
        try {
            await navigator.clipboard.writeText(enrollData.secret);
            setSecretCopied(true);
            setTimeout(() => setSecretCopied(false), 1500);
        } catch {
            toast.error("Copy failed — select the code manually");
        }
    };

    const copyAllCodes = async () => {
        try {
            await navigator.clipboard.writeText(backupCodes.join("\n"));
            setCodesCopied(true);
            toast.success("Backup codes copied");
            setTimeout(() => setCodesCopied(false), 1500);
        } catch {
            toast.error("Copy failed — select the codes manually");
        }
    };

    const handleConfirm = async (e: React.FormEvent) => {
        e.preventDefault();
        if (busy || !code.trim()) return;
        setBusy(true);
        try {
            const res = await authApi.confirmTotp(code.trim());
            setBackupCodes(res.data.backup_codes || []);
            setStep("backup");
            // Reflect mfa_enabled in shared state for the parent.
            onEnrolled();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Invalid code. Try again."));
            setCode("");
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(15,23,42,0.45)] backdrop-blur-sm motion-safe:animate-in motion-safe:fade-in motion-safe:duration-150"
            onClick={dismiss}
            role="dialog"
            aria-modal="true"
            aria-labelledby="enroll-mfa-title"
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
                            className="flex items-center justify-center w-7 h-7 rounded-md bg-[var(--accent-soft)] text-[var(--accent)]"
                        >
                            <FiShield className="w-4 h-4" />
                        </span>
                        <div>
                            <h3
                                id="enroll-mfa-title"
                                className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]"
                            >
                                {step === "scan" ? "Set up two-factor authentication" : "Save your backup codes"}
                            </h3>
                            <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5">
                                {step === "scan"
                                    ? "Scan the QR code with your authenticator app"
                                    : "Store these somewhere safe — shown only once"}
                            </p>
                        </div>
                    </div>
                    {step !== "backup" && (
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
                    )}
                </div>

                {step === "scan" ? (
                    <form onSubmit={handleConfirm}>
                        <div className="px-5 py-4 space-y-4">
                            {enrollError ? (
                                <div className="rounded-md border border-[var(--danger-soft)] bg-[var(--danger-soft)]/40 px-3 py-2.5">
                                    <p className="text-[12.5px] text-[var(--text-primary)] leading-relaxed">
                                        {enrollError}
                                    </p>
                                    <button
                                        type="button"
                                        onClick={loadEnrollment}
                                        className="text-[12px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors mt-1.5"
                                    >
                                        Try again
                                    </button>
                                </div>
                            ) : (
                                <>
                                    <div className="flex justify-center">
                                        {enrollData ? (
                                            // qr_data_uri is a data:image/png;base64 string — plain <img>.
                                            <img
                                                src={enrollData.qr_data_uri}
                                                alt="TOTP enrollment QR code"
                                                width={176}
                                                height={176}
                                                className="rounded-md border border-[var(--border-default)] bg-white p-2"
                                            />
                                        ) : (
                                            <div
                                                className="w-[176px] h-[176px] rounded-md border border-[var(--border-default)] bg-[var(--bg-page)] animate-pulse"
                                                aria-hidden
                                            />
                                        )}
                                    </div>

                                    <div>
                                        <span className="microtype text-[var(--text-muted)] block mb-1">
                                            Or enter this key manually
                                        </span>
                                        <div className="flex items-center gap-2">
                                            <code className="flex-1 px-3 py-2 rounded-md bg-[var(--bg-page)] border border-[var(--border-default)] text-[12px] font-mono text-[var(--text-primary)] break-all">
                                                {enrollData?.secret ?? "…"}
                                            </code>
                                            <button
                                                type="button"
                                                onClick={copySecret}
                                                disabled={!enrollData}
                                                className="
                                                    shrink-0 p-2 rounded-md
                                                    bg-[var(--bg-surface)] border border-[var(--border-emphasis)]
                                                    text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                                                    hover:bg-[var(--bg-hover)] disabled:opacity-50
                                                    transition-colors cursor-pointer
                                                    focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]
                                                "
                                                aria-label="Copy setup key"
                                            >
                                                {secretCopied ? (
                                                    <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" />
                                                ) : (
                                                    <FiCopy className="w-3.5 h-3.5" />
                                                )}
                                            </button>
                                        </div>
                                    </div>

                                    <label className="block">
                                        <span className="microtype text-[var(--text-muted)] flex items-center gap-1.5 mb-1">
                                            <FiSmartphone className="w-3.5 h-3.5" />
                                            Enter the 6-digit code
                                        </span>
                                        <input
                                            ref={codeInputRef}
                                            type="text"
                                            value={code}
                                            onChange={(e) => setCode(e.target.value)}
                                            inputMode="numeric"
                                            autoComplete="one-time-code"
                                            maxLength={6}
                                            placeholder="123456"
                                            disabled={busy || !enrollData}
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
                                            aria-label="6-digit verification code"
                                        />
                                    </label>
                                </>
                            )}
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
                                type="submit"
                                disabled={busy || !enrollData || !code.trim()}
                                className="
                                    inline-flex items-center px-3 py-1.5 rounded-md text-[12.5px]
                                    bg-[var(--accent)] text-white font-medium
                                    hover:bg-[var(--accent-strong)] disabled:opacity-50 disabled:cursor-not-allowed
                                    transition-colors cursor-pointer
                                    focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
                                "
                            >
                                {busy ? "Verifying…" : "Verify & enable"}
                            </button>
                        </div>
                    </form>
                ) : (
                    <>
                        <div className="px-5 py-4 space-y-4">
                            <div className="rounded-md border border-[var(--danger-soft)] bg-[var(--danger-soft)]/40 px-3 py-2.5">
                                <p className="text-[12.5px] text-[var(--text-primary)] leading-relaxed">
                                    Each code works <span className="font-semibold">once</span>. Store them now — they will
                                    not be shown again. Use one to sign in if you lose your authenticator device.
                                </p>
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                                {backupCodes.map((c) => (
                                    <code
                                        key={c}
                                        className="px-3 py-1.5 rounded-md bg-[var(--bg-page)] border border-[var(--border-default)] text-[13px] font-mono text-[var(--text-primary)] text-center tracking-wide"
                                    >
                                        {c}
                                    </code>
                                ))}
                            </div>

                            <button
                                type="button"
                                onClick={copyAllCodes}
                                className="
                                    w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[12.5px]
                                    bg-[var(--bg-surface)] border border-[var(--border-emphasis)]
                                    text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                                    hover:bg-[var(--bg-hover)] transition-colors cursor-pointer
                                    focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]
                                "
                            >
                                {codesCopied ? <FiCheck className="w-3.5 h-3.5 text-[var(--success)]" /> : <FiCopy className="w-3.5 h-3.5" />}
                                Copy all
                            </button>
                        </div>

                        <div className="flex justify-end gap-2 px-5 py-3 border-t border-[var(--border-default)]">
                            <button
                                type="button"
                                onClick={onClose}
                                className="
                                    inline-flex items-center px-3 py-1.5 rounded-md text-[12.5px]
                                    bg-[var(--accent)] text-white font-medium
                                    hover:bg-[var(--accent-strong)]
                                    transition-colors cursor-pointer
                                    focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
                                "
                            >
                                Done
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
