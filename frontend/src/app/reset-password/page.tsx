"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import Cookies from "js-cookie";
import { authApi, extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

/**
 * Self-service password reset completion page.
 *
 * Lands here from `${FRONTEND_URL}/reset-password?token=<JWT>` emailed
 * by the backend forgot-password endpoint. The 15-minute JWT is anchored
 * to users.updated_at so a successful reset (which advances updated_at)
 * invalidates the token, giving single-use semantics without a separate
 * tokens table.
 */
function ResetPasswordInner() {
    const router = useRouter();
    const params = useSearchParams();
    const token = params.get("token") || "";
    const { setTokensFromOAuth } = useAuth();
    const [password, setPassword] = useState("");
    const [confirm, setConfirm] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [complexityError, setComplexityError] = useState("");
    const [mismatchError, setMismatchError] = useState("");

    const focusRing = "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-page)]";
    const inputClass = "w-full px-3 h-10 bg-[var(--bg-page)] border border-[var(--border-emphasis)] rounded-md text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] transition-colors focus:outline-none focus:border-[var(--accent)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-elevated)]";

    if (!token) {
        return (
            <div className="min-h-screen flex items-center justify-center p-6 bg-[var(--bg-page)]">
                <div className="max-w-sm w-full text-center space-y-3">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">
                        Reset link missing token
                    </h1>
                    <p className="text-sm text-[var(--text-muted)]">
                        Open the link from your reset email exactly as it was
                        sent. If you no longer have it, request a new one.
                    </p>
                    <Link
                        href="/forgot-password"
                        className="inline-block px-3 h-10 leading-10 rounded-md bg-[var(--accent)] text-white text-sm"
                    >
                        Request new link
                    </Link>
                </div>
            </div>
        );
    }

    const passesComplexity = (pw: string) =>
        pw.length >= 8 &&
        /[A-Z]/.test(pw) &&
        /[a-z]/.test(pw) &&
        /[0-9]/.test(pw) &&
        /[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\/~`]/.test(pw);

    const submit = async () => {
        setComplexityError("");
        setMismatchError("");
        if (!passesComplexity(password)) {
            setComplexityError(
                "Password must be 8+ chars with upper, lower, digit, and special.",
            );
            return;
        }
        if (password !== confirm) {
            setMismatchError("Passwords do not match");
            return;
        }
        setSubmitting(true);
        try {
            const res = await authApi.resetPassword({ token, password });
            const { access_token, refresh_token, user } = res.data;
            const secure = process.env.NODE_ENV === "production";
            Cookies.set("token", access_token, {
                sameSite: "Strict",
                secure,
                expires: 1 / 48,
            });
            Cookies.set("refresh_token", refresh_token, {
                sameSite: "Strict",
                secure,
                expires: 7,
            });
            Cookies.set("user", JSON.stringify(user), {
                sameSite: "Strict",
                secure,
                expires: 7,
            });
            setTokensFromOAuth(access_token, refresh_token, user);
            toast.success("Password updated. You are signed in.");
            router.replace("/dashboard");
        } catch (err) {
            const e = err as { response?: { status?: number } };
            if (e.response?.status === 429) {
                toast.error("Too many attempts. Wait a minute and retry.");
            } else {
                toast.error(extractErrorMessage(err, "Could not reset password"));
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-[var(--bg-page)]">
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    submit();
                }}
                aria-busy={submitting}
                className="surface-card max-w-sm w-full space-y-5 p-6"
            >
                <div className="space-y-1">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">
                        Set a new password
                    </h1>
                    <p className="text-sm text-[var(--text-muted)]">
                        Choose a new password for your TaxSync account. You
                        will be signed in immediately and all other sessions
                        will be revoked.
                    </p>
                </div>
                <div>
                    <label
                        htmlFor="reset-password-input"
                        className="text-xs font-medium text-[var(--text-muted)] mb-1.5 block"
                    >
                        New password
                    </label>
                    <input
                        id="reset-password-input"
                        type="password"
                        autoComplete="new-password"
                        value={password}
                        onChange={(e) => {
                            setPassword(e.target.value);
                            if (complexityError) setComplexityError("");
                        }}
                        minLength={8}
                        aria-invalid={complexityError ? true : undefined}
                        aria-describedby="reset-password-help"
                        className={inputClass}
                    />
                    {complexityError ? (
                        <p id="reset-password-help" role="alert" className="text-[12px] text-[var(--danger)] mt-1">
                            {complexityError}
                        </p>
                    ) : (
                        <p id="reset-password-help" className="text-[11px] text-[var(--text-muted)] mt-1">
                            Minimum 8 characters with upper, lower, digit, and special.
                        </p>
                    )}
                </div>
                <div>
                    <label
                        htmlFor="reset-confirm-input"
                        className="text-xs font-medium text-[var(--text-muted)] mb-1.5 block"
                    >
                        Confirm password
                    </label>
                    <input
                        id="reset-confirm-input"
                        type="password"
                        autoComplete="new-password"
                        value={confirm}
                        onChange={(e) => {
                            setConfirm(e.target.value);
                            if (mismatchError) setMismatchError("");
                        }}
                        minLength={8}
                        aria-invalid={mismatchError ? true : undefined}
                        aria-describedby={mismatchError ? "reset-confirm-error" : undefined}
                        className={inputClass}
                    />
                    {mismatchError && (
                        <p id="reset-confirm-error" role="alert" className="text-[12px] text-[var(--danger)] mt-1">
                            {mismatchError}
                        </p>
                    )}
                </div>
                <button
                    type="submit"
                    disabled={submitting}
                    className={`w-full h-10 rounded-md bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-strong)] transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${focusRing}`}
                >
                    {submitting ? "Updating..." : "Update password and sign in"}
                </button>
            </form>
        </div>
    );
}

export default function ResetPasswordPage() {
    return (
        <Suspense fallback={null}>
            <ResetPasswordInner />
        </Suspense>
    );
}
