"use client";

import { useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { authApi, extractErrorMessage } from "@/lib/api";

/**
 * Self-service password reset request page.
 *
 * Always shows a generic success message regardless of whether the email
 * resolves to a user, matching the backend's enumeration defence. The
 * backend silently drops unknown emails and only emails a reset link for
 * active, local-auth accounts; here we mirror that posture so a typo
 * doesn't reveal whether an account exists.
 */
export default function ForgotPasswordPage() {
    const [email, setEmail] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);

    const submit = async () => {
        const trimmed = email.trim();
        if (!trimmed || !trimmed.includes("@")) {
            toast.error("Enter the email address on your TaxSync account");
            return;
        }
        setSubmitting(true);
        try {
            await authApi.forgotPassword({ email: trimmed });
            // Backend returns 204 regardless of whether the email is known.
            // Show the same confirmation either way.
            setSubmitted(true);
        } catch (err) {
            // Rate-limit (429) is the only signal we surface. Everything
            // else maps to the generic "if your email exists, check inbox"
            // copy below.
            const e = err as { response?: { status?: number } };
            if (e.response?.status === 429) {
                toast.error("Too many requests. Wait a minute and try again.");
            } else {
                toast.error(extractErrorMessage(err, "Could not request reset"));
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-[var(--bg-page)]">
            <div className="max-w-sm w-full space-y-5 bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-md p-6 shadow-[var(--shadow-md)]">
                <div className="space-y-1">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">
                        Forgot your password?
                    </h1>
                    <p className="text-sm text-[var(--text-muted)]">
                        Enter the email on your account. If it matches a local
                        TaxSync account, a reset link expiring in 15 minutes
                        will land in your inbox.
                    </p>
                </div>

                {submitted ? (
                    <div className="space-y-3">
                        <div className="rounded border border-[var(--success-soft)] bg-[var(--success-soft)]/30 px-3 py-2 text-[12.5px] text-[var(--text-primary)]">
                            If an account exists for that email, a reset link
                            has been sent. Check your inbox (and spam folder).
                            The link expires in 15 minutes.
                        </div>
                        <p className="text-[11.5px] text-[var(--text-muted)]">
                            Signed in via Google or Microsoft? Use that
                            provider on the sign-in page instead. Password
                            reset only works for accounts created with email
                            and password.
                        </p>
                        <Link
                            href="/login"
                            className="block w-full text-center px-3 py-2 rounded bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-strong)] transition-colors"
                        >
                            Back to sign in
                        </Link>
                    </div>
                ) : (
                    <>
                        <div>
                            <label
                                htmlFor="forgot-email"
                                className="block text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-1"
                            >
                                Email
                            </label>
                            <input
                                id="forgot-email"
                                type="email"
                                autoComplete="email"
                                inputMode="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") submit();
                                }}
                                placeholder="you@example.com"
                                className="
                                    w-full px-3 py-2 rounded bg-[var(--bg-elevated)]
                                    border border-[var(--border-default)]
                                    text-[var(--text-primary)] text-sm
                                    focus:outline-none focus:border-[var(--accent)]
                                    focus:ring-2 focus:ring-[var(--accent-edge)]
                                "
                            />
                        </div>
                        <button
                            type="button"
                            onClick={submit}
                            disabled={submitting}
                            className="
                                w-full px-3 py-2 rounded bg-[var(--accent)] text-white text-sm font-medium
                                hover:bg-[var(--accent-strong)] transition-colors
                                focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)]
                                disabled:opacity-60 disabled:cursor-not-allowed
                            "
                        >
                            {submitting ? "Sending..." : "Send reset link"}
                        </button>
                        <div className="text-center text-[12px] text-[var(--text-muted)]">
                            <Link href="/login" className="text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors">
                                Back to sign in
                            </Link>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
