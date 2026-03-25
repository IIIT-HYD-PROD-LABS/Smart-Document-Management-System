"use client";

const statusStyles: Record<string, string> = {
    completed: "bg-[#10b981]/10 text-[#10b981]",
    processing: "bg-[#f59e0b]/10 text-[#f59e0b]",
    pending: "bg-[#3b82f6]/10 text-[#3b82f6]",
    failed: "bg-[#ef4444]/10 text-[#ef4444]",
};

export function StatusBadge({ status }: { status: string }) {
    return (
        <span className={`text-xs px-2.5 py-1 rounded-md ${statusStyles[status] || "bg-[#27272a] text-[#71717a]"}`}>
            {status}
        </span>
    );
}
