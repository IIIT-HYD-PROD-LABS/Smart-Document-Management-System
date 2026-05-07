"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function DashboardError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
    useEffect(() => {
        console.error("Dashboard error:", error);
    }, [error]);

    return (
        <div className="flex items-center justify-center min-h-[60vh] px-6">
            <div className="max-w-md w-full text-center">
                <div className="w-12 h-12 rounded-full bg-[var(--danger-soft)] flex items-center justify-center mx-auto mb-4">
                    <svg className="w-6 h-6 text-[var(--danger)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.27 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                </div>
                <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-2">Something went wrong</h2>
                <p className="text-sm text-[var(--text-muted)] mb-6">An error occurred while loading this page.</p>
                <div className="flex items-center justify-center gap-3">
                    <button onClick={reset} className="px-4 py-2 text-sm font-medium bg-[var(--accent)] text-white rounded-md hover:bg-[var(--accent-strong)] transition-colors cursor-pointer">
                        Try again
                    </button>
                    <Link href="/dashboard" className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-default)] rounded-md hover:bg-[var(--bg-hover)] transition-colors">
                        Back to dashboard
                    </Link>
                </div>
            </div>
        </div>
    );
}
