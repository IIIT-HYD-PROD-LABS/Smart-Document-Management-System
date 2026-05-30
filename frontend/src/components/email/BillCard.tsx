"use client";

import Link from "next/link";
import {
    FiZap,
    FiPhone,
    FiCreditCard,
    FiMonitor,
    FiPackage,
    FiAlertTriangle,
    FiCheckCircle,
    FiClock,
} from "react-icons/fi";
import type { Bill, BillPaymentStatus } from "@/lib/email-api";

const CATEGORY_ICON: Record<
    string,
    React.ComponentType<{ className?: string }>
> = {
    utility: FiZap,
    telecom: FiPhone,
    credit_card: FiCreditCard,
    subscription: FiMonitor,
    other: FiPackage,
};

export type VisualStatus = BillPaymentStatus | "due_soon";

export const VISUAL_STATUS: Record<
    VisualStatus,
    { label: string; bg: string; text: string; icon: React.ComponentType<{ className?: string }> }
> = {
    pending: {
        label: "Pending",
        bg: "var(--info-soft)",
        text: "var(--info)",
        icon: FiClock,
    },
    due_soon: {
        label: "Due soon",
        bg: "var(--warning-soft)",
        text: "var(--warning)",
        icon: FiClock,
    },
    overdue: {
        label: "Overdue",
        bg: "var(--danger-soft)",
        text: "var(--danger)",
        icon: FiAlertTriangle,
    },
    paid: {
        label: "Paid",
        bg: "var(--success-soft)",
        text: "var(--success)",
        icon: FiCheckCircle,
    },
};

interface BillCardProps {
    bill: Bill;
}

/**
 * BillCard — single bill row in the dashboard grid.
 *
 * Derives a visual status from `payment_status` plus a real-time
 * "due_soon" classification (due_date within 3 days). The backend
 * also computes buckets server-side for filter queries; this client
 * derivation keeps the badge in sync with the page-load timestamp.
 */
export function classifyVisualStatus(bill: Bill): VisualStatus {
    if (bill.payment_status === "paid") return "paid";
    if (!bill.due_date) return bill.payment_status;
    const due = new Date(bill.due_date).getTime();
    const now = Date.now();
    if (due < now) return "overdue";
    const threeDays = 3 * 24 * 60 * 60 * 1000;
    if (due - now < threeDays) return "due_soon";
    return "pending";
}

export default function BillCard({ bill }: BillCardProps) {
    const visual = classifyVisualStatus(bill);
    const cfg = VISUAL_STATUS[visual];
    const StatusIcon = cfg.icon;
    const CategoryIcon =
        CATEGORY_ICON[bill.biller_category] || CATEGORY_ICON.other;

    return (
        <Link
            href={`/dashboard/email/bills/${bill.id}`}
            className="
                block p-4 rounded-md
                bg-[var(--bg-elevated)] border border-[var(--border-default)]
                hover:border-[var(--border-emphasis)]
                hover:bg-[var(--bg-hover)]
                transition-colors duration-150
                focus-visible:outline-none focus-visible:ring-2
                focus-visible:ring-[var(--accent)]
            "
            data-bill-id={bill.id}
        >
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                    <CategoryIcon
                        className="w-4 h-4 text-[var(--text-muted)] shrink-0"
                        aria-hidden
                    />
                    <div className="min-w-0">
                        <div className="microtype text-[var(--text-subtle)]">
                            {bill.biller_category.replace("_", " ")}
                        </div>
                        <div className="text-[13px] font-medium text-[var(--text-primary)] truncate">
                            {bill.biller_name}
                        </div>
                    </div>
                </div>
                <span
                    className="
                        inline-flex items-center gap-1 shrink-0
                        px-2 py-0.5 rounded text-[11px] font-medium
                    "
                    style={{
                        backgroundColor: cfg.bg,
                        color: cfg.text,
                    }}
                >
                    <StatusIcon className="w-3 h-3" aria-hidden />
                    {cfg.label}
                </span>
            </div>

            <div className="mt-3 font-mono tabular-nums text-[20px] font-semibold text-[var(--text-primary)]">
                {bill.currency}{" "}
                {Number(bill.amount_due).toLocaleString("en-IN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                })}
            </div>

            <div className="mt-1 text-[11.5px] text-[var(--text-muted)] flex items-center gap-2">
                <span>
                    Due{" "}
                    <span className="font-mono text-[var(--text-secondary)]">
                        {bill.due_date || "—"}
                    </span>
                </span>
                {bill.account_number_last4 && (
                    <>
                        <span aria-hidden>•</span>
                        <span className="font-mono">
                            ****{bill.account_number_last4}
                        </span>
                    </>
                )}
                {bill.is_recurring && (
                    <>
                        <span aria-hidden>•</span>
                        <span className="microtype">
                            {bill.recurrence_period || "recurring"}
                        </span>
                    </>
                )}
            </div>
        </Link>
    );
}
