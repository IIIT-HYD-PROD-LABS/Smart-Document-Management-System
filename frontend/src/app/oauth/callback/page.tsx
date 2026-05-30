"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { oauthApi, extractErrorMessage } from "@/lib/api";
import { LoadingSpinner } from "@/components";
import toast from "react-hot-toast";

function OAuthCallbackInner() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { setTokensFromOAuth } = useAuth();
    const [error, setError] = useState<string | null>(null);
    const exchanged = useRef(false);

    useEffect(() => {
        // Guard against React StrictMode double-fire
        if (exchanged.current) return;
        exchanged.current = true;

        const code = searchParams.get("code");
        const token = searchParams.get("token");

        if (!code || !token) {
            setError("Missing OAuth parameters");
            return;
        }

        // Immediately strip sensitive exchange tokens from the URL / browser history
        // so they cannot be leaked via Referer header, browser history, or shoulder-surfing
        if (typeof window !== "undefined") {
            window.history.replaceState({}, "", "/oauth/callback");
        }

        oauthApi.exchangeCode(code, token)
            .then((res) => {
                const { access_token, refresh_token, user } = res.data;
                setTokensFromOAuth(access_token, refresh_token, user);
                toast.success("Signed in successfully");
                router.replace("/dashboard");
            })
            .catch((err) => {
                const message = extractErrorMessage(err, "OAuth sign-in failed");
                setError(message);
                toast.error(message);
            });
    }, [searchParams, setTokensFromOAuth, router]);

    if (error) {
        return (
            <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center px-6">
                <div className="text-center">
                    <p className="text-sm text-[var(--danger)] mb-4">{error}</p>
                    <button
                        onClick={() => router.push("/login")}
                        className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-page)]"
                    >
                        Back to login
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center">
            <div className="text-center">
                <LoadingSpinner className="mx-auto mb-4" />
                <p className="text-sm text-[var(--text-subtle)]">Completing sign-in...</p>
            </div>
        </div>
    );
}

export default function OAuthCallbackPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center">
                    <LoadingSpinner />
                </div>
            }
        >
            <OAuthCallbackInner />
        </Suspense>
    );
}
