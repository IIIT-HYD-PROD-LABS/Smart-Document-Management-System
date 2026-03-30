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
    const { login, user, isLoading } = useAuth();
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
        oauthApi.getProviders().then((res) => setProviders(res.data.providers)).catch(() => {});
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            await login(email, password);
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

    return (
        <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-6">
            <div className="w-full max-w-sm">
                <div className="text-center mb-8">
                    <Link href="/" className="text-sm font-semibold text-white tracking-tight">TaxSync</Link>
                    <h1 className="text-xl font-semibold text-white mt-6">Sign in</h1>
                    <p className="text-sm text-[#71717a] mt-1">Welcome back to your account</p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-6">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label htmlFor="login-email" className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">Email</label>
                            <input id="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors" placeholder="you@example.com" required />
                        </div>
                        <div>
                            <label htmlFor="login-password" className="text-xs font-medium text-[#a1a1aa] mb-1.5 block">Password</label>
                            <input id="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors" placeholder="Enter your password" required />
                        </div>
                        <button type="submit" disabled={loading} className="w-full py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors disabled:opacity-50 cursor-pointer mt-2">
                            {loading ? "Signing in..." : "Sign in"}
                        </button>
                    </form>
                    {(providers.includes("google") || providers.includes("microsoft")) && (
                        <>
                            <div className="flex items-center gap-3 my-4">
                                <div className="flex-1 h-px bg-[#27272a]" />
                                <span className="text-[11px] text-[#52525b] uppercase">or continue with</span>
                                <div className="flex-1 h-px bg-[#27272a]" />
                            </div>
                            <div className="space-y-2">
                                {providers.includes("google") && (
                                    <button
                                        type="button"
                                        onClick={async () => {
                                            try {
                                                const res = await oauthApi.getGoogleUrl();
                                                window.location.href = res.data.url;
                                            } catch { toast.error("Failed to start Google sign-in"); }
                                        }}
                                        className="w-full py-2 text-sm font-medium bg-[#09090b] border border-[#27272a] text-white rounded-md hover:bg-[#18181b] transition-colors cursor-pointer flex items-center justify-center gap-2"
                                    >
                                        <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                                        Google
                                    </button>
                                )}
                                {providers.includes("microsoft") && (
                                    <button
                                        type="button"
                                        onClick={async () => {
                                            try {
                                                const res = await oauthApi.getMicrosoftUrl();
                                                window.location.href = res.data.url;
                                            } catch { toast.error("Failed to start Microsoft sign-in"); }
                                        }}
                                        className="w-full py-2 text-sm font-medium bg-[#09090b] border border-[#27272a] text-white rounded-md hover:bg-[#18181b] transition-colors cursor-pointer flex items-center justify-center gap-2"
                                    >
                                        <svg className="w-4 h-4" viewBox="0 0 21 21"><rect x="1" y="1" width="9" height="9" fill="#f25022"/><rect x="1" y="11" width="9" height="9" fill="#00a4ef"/><rect x="11" y="1" width="9" height="9" fill="#7fba00"/><rect x="11" y="11" width="9" height="9" fill="#ffb900"/></svg>
                                        Microsoft
                                    </button>
                                )}
                            </div>
                        </>
                    )}
                </div>
                <p className="text-center text-xs text-[#52525b] mt-5">
                    No account?{" "}<Link href="/register" className="text-[#a1a1aa] hover:text-white transition-colors">Create one</Link>
                </p>
            </div>
        </div>
    );
}

export default function LoginPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
                    <LoadingSpinner />
                </div>
            }
        >
            <LoginInner />
        </Suspense>
    );
}
