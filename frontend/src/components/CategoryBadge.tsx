"use client";

const categoryStyles: Record<string, { bg: string; fg: string; border: string }> = {
    bills:    { bg: "rgba(4, 120, 87, 0.10)",  fg: "#047857", border: "rgba(4, 120, 87, 0.20)" },
    upi:      { bg: "rgba(124, 58, 237, 0.10)", fg: "#6d28d9", border: "rgba(124, 58, 237, 0.20)" },
    tickets:  { bg: "rgba(180, 83, 9, 0.10)",   fg: "#b45309", border: "rgba(180, 83, 9, 0.20)" },
    tax:      { bg: "rgba(37, 99, 235, 0.10)",  fg: "#1d4ed8", border: "rgba(37, 99, 235, 0.20)" },
    bank:     { bg: "rgba(14, 116, 144, 0.10)", fg: "#0e7490", border: "rgba(14, 116, 144, 0.20)" },
    invoices: { bg: "rgba(190, 24, 93, 0.10)",  fg: "#be185d", border: "rgba(190, 24, 93, 0.20)" },
};

export function CategoryBadge({ category }: { category: string }) {
    const style = categoryStyles[category];
    if (!style) {
        return (
            <span
                className="inline-flex items-center text-[11px] px-2 py-0.5 rounded capitalize border"
                style={{
                    background: "var(--bg-muted)",
                    color: "var(--text-muted)",
                    borderColor: "var(--border-default)",
                }}
            >
                {category}
            </span>
        );
    }
    return (
        <span
            className="inline-flex items-center text-[11px] px-2 py-0.5 rounded capitalize border font-medium"
            style={{
                background: style.bg,
                color: style.fg,
                borderColor: style.border,
            }}
        >
            {category}
        </span>
    );
}
