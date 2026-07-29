"use client";

// Token-driven so chips stay AA in light and adapt under data-theme="dark".
// upi/invoices have no dedicated token — folded into nearest semantic family.
const categoryStyles: Record<string, { bg: string; fg: string; border: string }> = {
    bills:    { bg: "var(--success-soft)", fg: "var(--success)",       border: "var(--success-soft)" },
    upi:      { bg: "var(--accent-soft)",  fg: "var(--accent-strong)", border: "var(--accent-edge)" },
    tickets:  { bg: "var(--warning-soft)", fg: "var(--warning)",       border: "var(--warning-soft)" },
    tax:      { bg: "var(--accent-soft)",  fg: "var(--accent-strong)", border: "var(--accent-edge)" },
    bank:     { bg: "var(--info-soft)",    fg: "var(--info)",          border: "var(--info-soft)" },
    invoices: { bg: "var(--danger-soft)",  fg: "var(--danger)",        border: "var(--danger-soft)" },
    unknown:  { bg: "var(--bg-muted)",     fg: "var(--text-muted)",    border: "var(--border-default)" },
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
