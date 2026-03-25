"use client";

export function LoadingSpinner({ size = "w-5 h-5", className = "" }: { size?: string; className?: string }) {
    return (
        <div className={`${size} border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin ${className}`} />
    );
}
