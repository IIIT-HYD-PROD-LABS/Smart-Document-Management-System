"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import {
    FiArrowLeft,
    FiExternalLink,
    FiFileText,
    FiMail,
} from "react-icons/fi";
import MarkPaidModal from "@/components/email/MarkPaidModal";
import InvoiceAISection from "@/components/email/InvoiceAISection";
import {
    VISUAL_STATUS,
    classifyVisualStatus,
} from "@/components/email/BillCard";
import { Skeleton } from "@/components";
import { Bill, SourceEmailView, emailApi } from "@/lib/email-api";

/**
 * /dashboard/email/bills/[id] — BILL-05 detail page (D-37).
 *
 * Renders bill metadata + payment status, with an on-demand "View source
 * email" button that calls /email/messages/{id}/view (which delegates to
 * the MCP gmail_read_message tool — body is NEVER cached at rest per D-34).
 *
 * The Mark-as-paid button opens MarkPaidModal which posts to
 * /email/bills/{id}/mark-paid; the bill state reloads on success.
 */
export default function BillDetailPage() {
    const { id } = useParams<{ id: string }>();
    const billId = id ? parseInt(id, 10) : NaN;

    const [bill, setBill] = useState<Bill | null>(null);
    const [loading, setLoading] = useState(true);
    const [showPaid, setShowPaid] = useState(false);

    const [sourceEmail, setSourceEmail] = useState<SourceEmailView | null>(
        null,
    );
    const [sourceLoading, setSourceLoading] = useState(false);

    const load = async () => {
        if (!Number.isFinite(billId)) {
            setLoading(false);
            return;
        }
        try {
            const r = await emailApi.getBill(billId);
            setBill(r.data);
        } catch (e: unknown) {
            const status = (e as { response?: { status?: number } })?.response
                ?.status;
            if (status === 404) {
                toast.error("Invoice not found");
            } else {
                const msg =
                    (e as { response?: { data?: { detail?: string } } })
                        ?.response?.data?.detail || "Failed to load invoice";
                toast.error(msg);
            }
            setBill(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [id]);

    const handleViewEmail = async () => {
        if (!bill?.source_email_id) return;
        setSourceLoading(true);
        try {
            const r = await emailApi.viewSourceEmail(bill.source_email_id);
            setSourceEmail(r.data);
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to fetch source email";
            toast.error(msg);
        } finally {
            setSourceLoading(false);
        }
    };

    if (loading) {
        return (
            <div
                className="space-y-6 max-w-4xl"
                role="status"
                aria-busy="true"
                aria-live="polite"
            >
                <span className="sr-only">Loading invoice</span>
                <div>
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-6 w-48 mt-2" />
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-[76px] rounded-md" />
                    ))}
                </div>
            </div>
        );
    }

    if (!bill) {
        return (
            <div className="space-y-3">
                <Link
                    href="/dashboard/email/bills"
                    className="
                        inline-flex items-center gap-1.5 text-[12.5px]
                        text-[var(--text-muted)] hover:text-[var(--text-primary)]
                    "
                >
                    <FiArrowLeft className="w-3.5 h-3.5" />
                    Back to invoices
                </Link>
                <div
                    className="
                        rounded-md p-4
                        bg-[var(--bg-elevated)] border border-[var(--border-default)]
                        text-[13px] text-[var(--text-muted)]
                    "
                >
                    Invoice not found.
                </div>
            </div>
        );
    }

    const visual = classifyVisualStatus(bill);
    const visualCfg = VISUAL_STATUS[visual];
    const StatusIcon = visualCfg.icon;

    return (
        <div className="space-y-6 max-w-4xl">
            <div>
                <Link
                    href="/dashboard/email/bills"
                    className="
                        inline-flex items-center gap-1.5 text-[12.5px]
                        text-[var(--text-muted)] hover:text-[var(--text-primary)]
                    "
                >
                    <FiArrowLeft className="w-3.5 h-3.5" />
                    Back to invoices
                </Link>
            </div>

            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <span className="microtype text-[var(--text-subtle)] block">
                        {bill.biller_category.replace("_", " ")}
                    </span>
                    <h1 className="text-[20px] font-semibold tracking-tight text-[var(--text-primary)] mt-0.5">
                        {bill.biller_name}
                    </h1>
                </div>
                <span
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium"
                    style={{
                        backgroundColor: visualCfg.bg,
                        color: visualCfg.text,
                    }}
                >
                    <StatusIcon className="w-3 h-3" aria-hidden />
                    {visualCfg.label}
                </span>
            </div>

            {/* Stat grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <Stat label="Amount">
                    <span className="font-mono tabular-nums">
                        {bill.currency}{" "}
                        {Number(bill.amount_due).toLocaleString("en-IN", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                        })}
                    </span>
                </Stat>
                <Stat label="Due date">
                    <span className="font-mono">{bill.due_date || "—"}</span>
                </Stat>
                <Stat label="Account">
                    <span className="font-mono">
                        {bill.account_number_last4
                            ? `****${bill.account_number_last4}`
                            : "—"}
                    </span>
                </Stat>
                <Stat label="Recurring">
                    <span className="font-mono">
                        {bill.is_recurring
                            ? bill.recurrence_period || "yes"
                            : "no"}
                    </span>
                </Stat>
            </div>

            {/* Payment metadata once paid */}
            {bill.payment_status === "paid" && (
                <section
                    className="
                        rounded-md p-4
                        bg-[var(--bg-elevated)] border border-[var(--border-default)]
                    "
                >
                    <h3 className="microtype text-[var(--text-muted)] mb-2">
                        Payment details
                    </h3>
                    <dl className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-[12.5px]">
                        <div>
                            <dt className="text-[var(--text-subtle)]">Paid on</dt>
                            <dd className="font-mono text-[var(--text-primary)]">
                                {bill.payment_date || "—"}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-[var(--text-subtle)]">Reference</dt>
                            <dd className="font-mono text-[var(--text-primary)] truncate">
                                {bill.payment_reference || "—"}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-[var(--text-subtle)]">Method</dt>
                            <dd className="font-mono text-[var(--text-primary)]">
                                {bill.payment_method || "—"}
                            </dd>
                        </div>
                    </dl>
                </section>
            )}

            <InvoiceAISection billId={bill.id} />

            {/* Action row */}
            <div className="flex flex-wrap gap-2">
                {bill.payment_status !== "paid" && (
                    <button
                        type="button"
                        onClick={() => setShowPaid(true)}
                        className="
                            inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--accent)] text-white font-medium
                            hover:bg-[var(--accent-strong)] transition-colors
                        "
                    >
                        Mark as paid
                    </button>
                )}
                {bill.source_email_id && (
                    <button
                        type="button"
                        onClick={handleViewEmail}
                        disabled={sourceLoading}
                        className="
                            inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                            text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)]
                            disabled:opacity-50
                            transition-colors
                        "
                    >
                        <FiMail className="w-3.5 h-3.5" />
                        {sourceLoading ? "Fetching…" : "View source email"}
                    </button>
                )}
                {bill.source_document_id && (
                    <Link
                        href={`/dashboard/documents/${bill.source_document_id}`}
                        className="
                            inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                            text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)]
                            transition-colors
                        "
                    >
                        <FiFileText className="w-3.5 h-3.5" />
                        Source document
                        <FiExternalLink className="w-3 h-3" aria-hidden />
                    </Link>
                )}
            </div>

            {/* Source email body (rendered after on-demand fetch; never cached) */}
            {sourceEmail && (
                <section
                    className="
                        rounded-md
                        bg-[var(--bg-surface)] border border-[var(--border-default)]
                    "
                >
                    <header className="px-4 py-3 border-b border-[var(--border-default)]">
                        <div className="text-[12.5px] text-[var(--text-muted)] flex flex-wrap gap-x-4 gap-y-0.5">
                            <span>
                                <span className="microtype text-[var(--text-subtle)]">
                                    From{" "}
                                </span>
                                <span className="font-mono">
                                    {sourceEmail.sender}
                                </span>
                            </span>
                            <span>
                                <span className="microtype text-[var(--text-subtle)]">
                                    Date{" "}
                                </span>
                                <span className="font-mono">
                                    {sourceEmail.date}
                                </span>
                            </span>
                        </div>
                        <div className="mt-1 text-[13px] font-medium text-[var(--text-primary)]">
                            {sourceEmail.subject}
                        </div>
                    </header>
                    <pre
                        className="
                            p-4 text-[12px] font-mono whitespace-pre-wrap
                            text-[var(--text-secondary)] max-h-96 overflow-auto
                        "
                    >
                        {sourceEmail.body}
                    </pre>
                </section>
            )}

            <MarkPaidModal
                bill={bill}
                open={showPaid}
                onClose={() => setShowPaid(false)}
                onMarked={load}
            />
        </div>
    );
}

function Stat({
    label,
    children,
}: {
    label: string;
    children: React.ReactNode;
}) {
    return (
        <div
            className="
                p-4 rounded-md
                bg-[var(--bg-elevated)] border border-[var(--border-default)]
            "
        >
            <div className="microtype text-[var(--text-muted)] mb-1">
                {label}
            </div>
            <div className="text-[16px] text-[var(--text-primary)]">{children}</div>
        </div>
    );
}
