"use client";

/** Status badge — Compliance Noir variant.
 *
 * Plex-Mono microcaps + dot indicator. The dot is what the eye locks onto
 * in dense rows; the label is supportive. Variant `degraded_local` is the
 * Phase 13 hardening status for documents that fell back to the local
 * regex stub when all real LLM providers failed.
 */
const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
    completed: { color: "#10b981", label: "Completed" },
    processing: { color: "#f59e0b", label: "Processing" },
    pending: { color: "#3b82f6", label: "Pending" },
    failed: { color: "#ef4444", label: "Failed" },
    degraded_local: { color: "#a78bfa", label: "Degraded" },
    skipped: { color: "#71717a", label: "Skipped" },
};

export function StatusBadge({ status }: { status: string }) {
    const cfg = STATUS_CONFIG[status] ?? { color: "#71717a", label: status };
    return (
        <span
            className="inline-flex items-center gap-1.5 h-[22px] pl-2 pr-2.5 rounded-md text-[10.5px] font-medium tracking-wide"
            style={{
                backgroundColor: `${cfg.color}1a`,
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
