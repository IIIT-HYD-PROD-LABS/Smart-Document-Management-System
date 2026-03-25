"use client";

export function LoadingSpinner({ className = "" }: { className?: string }) {
    return (
        <div className={`w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin ${className}`} />
    );
}
