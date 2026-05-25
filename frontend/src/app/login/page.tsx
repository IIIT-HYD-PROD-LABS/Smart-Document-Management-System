"use client";

import { Suspense, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { oauthApi, extractErrorMessage } from "@/lib/api";
import { LoadingSpinner } from "@/components";
import toast from "react-hot-toast";
import Link from "next/link";

function LoginInner() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [providers, setProviders] = useState<string[]>([]);
    // MFA second step: when set, the form swaps in place to a code prompt.
    const [mfaToken, setMfaToken] = useState<string | null>(null);
    const [mfaCode, setMfaCode] = useState("");
    const { login, verifyMfa, user, isLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    // Sanitize redirect parameter: only allow relative paths starting with "/"
    // to prevent open-redirect attacks (e.g., ?redirect=https://evil.com)
    const rawRedirect = searchParams.get("redirect") || "/dashboard";
    const redirectTo = rawRedirect.startsWith("/") && !rawRedirect.startsWith("//")
        ? rawRedirect
        : "/dashboard";

    // Redirect already logged-in users to their intended destination
    useEffect(() => {
        if (!isLoading && user) router.replace(redirectTo);
    }, [user, isLoading, router, redirectTo]);

    useEffect(() => {
        // Always offer Google + Microsoft alongside whatever the backend
        // confirms. Backend filters by configured creds; we let users see
        // the SSO option and surface a clear error if not yet provisioned.
        oauthApi
            .getProviders()
            .then((res) => {
                const merged = Array.from(
                    new Set([...res.data.providers, "google", "microsoft"])
                );
                setProviders(merged);
            })
            .catch(() => setProviders(["local", "google", "microsoft"]));
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const result = await login(email, password);
            if (result.mfaRequired) {
                // Swap the form in place to the code step; no toast yet, the
                // session isn't established until verifyMfa succeeds.
                setMfaToken(result.mfaToken);
                setMfaCode("");
                return;
            }
            toast.success("Welcome back");
        } catch (err: unknown) {
            const resp = err as { response?: { status?: number } };
            if (resp?.response?.status === 429) {
                toast.error("Too many attempts. Please wait a minute and try again.");
            } else {
                toast.error(extractErrorMessage(err, "Login failed"));
            }
        } finally {
            setLoading(false);
        }
    };

    const handleMfaSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!mfaToken) return;
        setLoading(true);
        try {
            await verifyMfa(mfaToken, mfaCode.trim());
            // Same success path as a normal login: the redirect effect fires
            // once `user` is set; surface the identical confirmation toast.
            toast.success("Welcome back");
        } catch (err: unknown) {
            const resp = err as { response?: { status?: number; data?: { detail?: unknown } } };
            const status = resp?.response?.status;
            if (status === 429) {
                toast.error(extractErrorMessage(err, "Too many attempts. Please wait and try again."));
            } else if (status === 401) {
                toast.error(extractErrorMessage(err, "Invalid code. Try again."));
                setMfaCode("");
            } else {
                toast.error(extractErrorMessage(err, "Verification failed"));
            }
        } finally {
            setLoading(false);
        }
    };

    const inputClass = "w-full px-3 h-10 bg-[var(--bg-page)] border border-[var(--border-emphasis)] rounded-md text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] transition-colors focus:outline-none focus:border-[var(--accent)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-elevated)]";
    const focusRing = "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-page)]";

    return (
        <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center px-6">
            <div className="w-full max-w-sm">
                <div className="flex flex-col items-center mb-8">
                    <Link
                        href="/"
                        className={`flex items-center gap-2 group rounded-sm ${focusRing}`}
                        aria-label="TaxSync home"
                    >
                        <span className="w-7 h-7 rounded-md bg-[var(--accent-soft)] border border-[var(--accent-edge)] flex items-center justify-center">
                            <span className="font-mono text-[13px] font-semibold text-[var(--accent)]">Tx</span>
                        </span>
                        <span className="text-[14px] font-semibold text-[var(--text-primary)] tracking-tight">TaxSync</span>
                    </Link>
                    <h1 className="text-[22px] font-semibold text-[var(--text-primary)] mt-7 tracking-tight">
                        {mfaToken ? "Two-factor authentication" : "Sign in"}
                    </h1>
                    <p className="text-[13px] text-[var(--text-subtle)] mt-1">
                        {mfaToken ? "Enter the code from your authenticator app" : "Welcome back to your account"}
                    </p>
                </div>
                <div className="surface-card p-6">
                    {mfaToken ? (
                        <form onSubmit={handleMfaSubmit} className="space-y-4" aria-busy={loading}>
                            <div>
                                <label htmlFor="mfa-code" className="text-xs font-medium text-[var(--text-muted)] mb-1.5 block">
                                    6-digit code
                                </label>
                                <input
                                    id="mfa-code"
                                    type="text"
                                    name="one-time-code"
                                    autoComplete="one-time-code"
                                    inputMode="numeric"
                                    autoFocus
                                    value={mfaCode}
                                    onChange={(e) => setMfaCode(e.target.value)}
                                    className={`${inputClass} font-mono tracking-[0.3em]`}
                                    placeholder="123456"
                                    required
                                />
                                <p className="text-[11px] text-[var(--text-subtle)] mt-1.5">
                                    Lost your device? Enter one of your backup codes instead.
                                </p>
                            </div>
                            <button
                                type="submit"
                                disabled={loading || !mfaCode.trim()}
                                className={`w-full h-10 text-[13px] font-medium bg-[var(--accent)] text-white rounded-md hover:bg-[var(--accent-strong)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer mt-2 ${focusRing}`}
                            >
                                {loading ? "Verifying…" : "Verify"}
                            </button>
                            <button
                                type="button"
                                onClick={() => {
                                    setMfaToken(null);
                                    setMfaCode("");
                                }}
                                disabled={loading}
                                className={`w-full h-9 text-[12.5px] font-medium bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-md transition-colors disabled:opacity-50 cursor-pointer ${focusRing}`}
                            >
                                Back to sign in
                            </button>
                        </form>
                    ) : (
                    <>
                    <form onSubmit={handleSubmit} className="space-y-4" aria-busy={loading}>
                        <div>
                            <label htmlFor="login-email" className="text-xs font-medium text-[var(--text-muted)] mb-1.5 block">Email</label>
                            <input
                                id="login-email"
                                type="email"
                                name="email"
                                autoComplete="email"
                                inputMode="email"
                                autoFocus
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className={inputClass}
                                placeholder="you@example.com"
                                required
                            />
                        </div>
                        <div>
                            <div className="flex items-center justify-between mb-1.5">
                                <label htmlFor="login-password" className="text-xs font-medium text-[var(--text-muted)]">Password</label>
                                <Link
                                    href="/forgot-password"
                                    className="text-[11px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors"
                                >
                                    Forgot password?
                                </Link>
                            </div>
                            <input
                                id="login-password"
                                type="password"
                                name="password"
                                autoComplete="current-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className={inputClass}
                                placeholder="Enter your password"
                                required
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading}
                            className={`w-full h-10 text-[13px] font-medium bg-[var(--accent)] text-white rounded-md hover:bg-[var(--accent-strong)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer mt-2 ${focusRing}`}
                        >
                            {loading ? "Signing in…" : "Sign in"}
                        </button>
                    </form>
                    {(providers.includes("google") || providers.includes("microsoft")) && (
                        <>
                            <div className="flex items-center gap-3 my-5">
                                <div className="flex-1 h-px bg-[var(--border-default)]" />
                                <span className="microtype">or continue with</span>
                                <div className="flex-1 h-px bg-[var(--border-default)]" />
                            </div>
                            <div className="space-y-2">
                                {providers.includes("google") && (
                                    <button
                                        type="button"
                                        onClick={async () => {
                                            try {
                                                const res = await oauthApi.getGoogleUrl();
                                                window.location.href = res.data.url;
                                            } catch (err: unknown) {
                                                const status = (err as { response?: { status?: number } })?.response?.status;
                                                if (status === 404) {
                                                    toast.error("Google sign-in not yet configured. Set GOOGLE_CLIENT_ID in backend .env to enable.");
                                                } else {
                                                    toast.error("Failed to start Google sign-in");
                                                }
                                            }
                                        }}
                                        className={`w-full h-10 text-[13px] font-medium bg-[var(--bg-surface)] border border-[var(--border-emphasis)] text-[var(--text-primary)] rounded-md hover:bg-[var(--bg-hover)] hover:border-[var(--text-disabled)] transition-colors cursor-pointer flex items-center justify-center gap-2.5 ${focusRing}`}
                                    >
                                        <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                                        Continue with Google
                                    </button>
                                )}
                                {providers.includes("microsoft") && (
                                    <button
                                        type="button"
                                        onClick={async () => {
                                            try {
                                                const res = await oauthApi.getMicrosoftUrl();
                                                window.location.href = res.data.url;
                                            } catch (err: unknown) {
                                                const status = (err as { response?: { status?: number } })?.response?.status;
                                                if (status === 404) {
                                                    toast.error("Microsoft sign-in not yet configured. Set MICROSOFT_CLIENT_ID in backend .env to enable.");
                                                } else {
                                                    toast.error("Failed to start Microsoft sign-in");
                                                }
                                            }
                                        }}
                                        className={`w-full h-10 text-[13px] font-medium bg-[var(--bg-surface)] border border-[var(--border-emphasis)] text-[var(--text-primary)] rounded-md hover:bg-[var(--bg-hover)] hover:border-[var(--text-disabled)] transition-colors cursor-pointer flex items-center justify-center gap-2.5 ${focusRing}`}
                                    >
                                        <svg className="w-4 h-4" viewBox="0 0 21 21" aria-hidden="true"><rect x="1" y="1" width="9" height="9" fill="#f25022"/><rect x="1" y="11" width="9" height="9" fill="#00a4ef"/><rect x="11" y="1" width="9" height="9" fill="#7fba00"/><rect x="11" y="11" width="9" height="9" fill="#ffb900"/></svg>
                                        Continue with Microsoft
                                    </button>
                                )}
                            </div>
                            {/* Operator-facing helper for first-install OAuth config.
                                Hidden in production so end users do not see
                                developer jargon (redirect_uri_mismatch) on the
                                login page. /oauth-setup is also admin-gated
                                outside DEBUG on the backend (M-1 fix). */}
                            {process.env.NODE_ENV !== "production" && (
                                <p className="text-center text-[11.5px] text-[var(--text-subtle)] mt-3">
                                    Hitting{" "}
                                    <code className="font-mono text-[10.5px]">
                                        redirect_uri_mismatch
                                    </code>
                                    ?{" "}
                                    <Link
                                        href="/oauth-setup"
                                        className={`text-[var(--text-secondary)] hover:text-[var(--accent)] underline-offset-2 hover:underline transition-colors rounded-sm ${focusRing}`}
                                    >
                                        OAuth setup help
                                    </Link>
                                </p>
                            )}
                        </>
                    )}
                    </>
                    )}
                </div>
                {!mfaToken && (
                    <p className="text-center text-[12px] text-[var(--text-subtle)] mt-5">
                        No account?{" "}<Link href="/" className={`text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors rounded-sm ${focusRing}`}>Request early access</Link>
                    </p>
                )}
            </div>
        </div>
    );
}

export default function LoginPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center">
                    <LoadingSpinner />
                </div>
            }
        >
            <LoginInner />
        </Suspense>
    );
}
