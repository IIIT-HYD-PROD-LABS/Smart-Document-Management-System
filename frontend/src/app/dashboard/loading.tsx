import { Skeleton } from "@/components/Skeleton";

/**
 * Route-transition fallback for the whole dashboard subtree.
 *
 * The layout is `force-dynamic`, so navigating between dashboard pages used to
 * block on a server round-trip with no feedback. App Router prefetches this
 * loading boundary and paints it the instant a link is clicked, while the
 * destination segment streams — the sidebar (owned by layout) stays put and
 * only the content area shows this neutral scaffold. Each page then swaps in
 * its own shape-matched skeleton on mount, so this stays deliberately generic.
 */
export default function DashboardLoading() {
    return (
        <div className="space-y-8" role="status" aria-busy="true" aria-live="polite">
            <span className="sr-only">Loading</span>
            <div>
                <Skeleton className="h-3 w-40" />
                <Skeleton className="h-7 w-64 mt-3" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-[110px]" />
                ))}
            </div>
            <Skeleton className="h-72 w-full" />
        </div>
    );
}
