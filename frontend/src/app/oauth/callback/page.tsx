"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { oauthApi } from "@/lib/api";
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

        oauthApi.exchangeCode(code, token)
            .then((res) => {
                const { access_token, refresh_token, user } = res.data;
                setTokensFromOAuth(access_token, refresh_token, user);
                toast.success("Signed in successfully");
                router.replace("/dashboard");
            })
            .catch((err) => {
                const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
                setError(message || "OAuth sign-in failed");
                toast.error(message || "OAuth sign-in failed");
            });
    }, [searchParams, setTokensFromOAuth, router]);

    if (error) {
        return (
            <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-6">
                <div className="text-center">
                    <p className="text-sm text-[#ef4444] mb-4">{error}</p>
                    <button
                        onClick={() => router.push("/login")}
                        className="text-sm text-[#a1a1aa] hover:text-white transition-colors cursor-pointer"
                    >
                        Back to login
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
            <div className="text-center">
                <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin mx-auto mb-4" />
                <p className="text-sm text-[#71717a]">Completing sign-in...</p>
            </div>
        </div>
    );
}

export default function OAuthCallbackPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
                    <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin" />
                </div>
            }
        >
            <OAuthCallbackInner />
        </Suspense>
    );
}
