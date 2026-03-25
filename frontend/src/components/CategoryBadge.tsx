"use client";

const categoryColors: Record<string, string> = {
    bills: "bg-[#10b981]/10 text-[#10b981]",
    upi: "bg-[#8b5cf6]/10 text-[#8b5cf6]",
    tickets: "bg-[#f59e0b]/10 text-[#f59e0b]",
    tax: "bg-[#3b82f6]/10 text-[#3b82f6]",
    bank: "bg-[#06b6d4]/10 text-[#06b6d4]",
    invoices: "bg-[#ec4899]/10 text-[#ec4899]",
};

export function CategoryBadge({ category }: { category: string }) {
    const style = categoryColors[category] || "bg-[#27272a] text-[#71717a]";
    return (
        <span className={`text-[11px] px-2 py-0.5 rounded capitalize ${style}`}>
            {category}
        </span>
    );
}
