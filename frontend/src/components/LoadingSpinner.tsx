"use client";

/** Loading spinner — refined for Compliance Noir.
 *
 * Uses brand accent (sharp blue) instead of muted gray so loading states
 * read as deliberate motion, not absence. The remaining 75% of the ring
 * is rendered at a subtle opacity so the spinning quarter visually leads
 * the eye.
 */
export function LoadingSpinner({
    size = "w-5 h-5",
    className = "",
}: {
    size?: string;
    className?: string;
}) {
    return (
        <div
            className={`${size} border-2 border-[var(--border-emphasis)] border-t-[var(--accent)] rounded-full motion-safe:animate-spin ${className}`}
            role="status"
            aria-label="Loading"
        />
    );
}
