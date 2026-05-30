"use client";

/** Status badge — Compliance Noir variant.
 *
 * Plex-Mono microcaps + dot indicator. The dot is what the eye locks onto
 * in dense rows; the label is supportive. Variant `degraded_local` is the
 * Phase 13 hardening status for documents that fell back to the local
 * regex stub when all real LLM providers failed.
 */
const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
    completed: { color: "var(--success)", bg: "var(--success-soft)", label: "Completed" },
    processing: { color: "var(--warning)", bg: "var(--warning-soft)", label: "Processing" },
    pending: { color: "var(--accent)", bg: "var(--accent-soft)", label: "Pending" },
    failed: { color: "var(--danger)", bg: "var(--danger-soft)", label: "Failed" },
    // degraded_local is a soft-failure / LLM-fallback state — map to warning
    degraded_local: { color: "var(--warning)", bg: "var(--warning-soft)", label: "Degraded" },
    skipped: { color: "var(--text-subtle)", bg: "var(--bg-muted)", label: "Skipped" },
};

export function StatusBadge({ status }: { status: string }) {
    const cfg = STATUS_CONFIG[status] ?? { color: "var(--text-subtle)", bg: "var(--bg-muted)", label: status };
    return (
        <span
            className="inline-flex items-center gap-1.5 h-[22px] pl-2 pr-2.5 rounded-md text-[10.5px] font-medium tracking-wide"
            style={{
                backgroundColor: cfg.bg,
                color: cfg.color,
            }}
            aria-label={`Status: ${cfg.label}`}
        >
            <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: cfg.color }}
                aria-hidden
            />
            {cfg.label}
        </span>
    );
}
