"use client";

/** Shimmer placeholder block.
 *
 * Used as a structured loading state instead of a lonely centered spinner:
 * the page's data lives behind a ~1s remote-DB fetch, so showing the shape
 * of the content that's coming reads as "loading this", not "nothing here".
 * Pass Tailwind sizing via `className`.
 */
export function Skeleton({ className = "" }: { className?: string }) {
    return (
        <div
            className={`motion-safe:animate-pulse rounded-md bg-[var(--border-default)] ${className}`}
            aria-hidden
        />
    );
}
