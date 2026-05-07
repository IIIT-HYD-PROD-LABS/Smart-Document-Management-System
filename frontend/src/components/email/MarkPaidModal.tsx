"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { FiX } from "react-icons/fi";
import { Bill, MarkPaidPayload, emailApi } from "@/lib/email-api";

interface Props {
    bill: Bill;
    open: boolean;
    onClose: () => void;
    onMarked: () => void;
}

const PAYMENT_METHODS = [
    "upi",
    "netbanking",
    "card",
    "cash",
    "cheque",
    "autopay",
    "other",
] as const;

/**
 * MarkPaidModal — BILL-05 mark-as-paid form.
 *
 * Three required fields: payment_date, payment_reference, payment_method.
 * On submit, calls POST /email/bills/{id}/mark-paid which writes the
 * BILL_MARK_PAID audit row and cancels the three reminder jobs (T-3,
 * T-1, overdue) per Plan 03 wiring.
 */
export default function MarkPaidModal({
    bill,
    open,
    onClose,
    onMarked,
}: Props) {
    const today = new Date().toISOString().slice(0, 10);
    const [paymentDate, setPaymentDate] = useState(today);
    const [reference, setReference] = useState("");
    const [method, setMethod] = useState<typeof PAYMENT_METHODS[number]>("upi");
    const [busy, setBusy] = useState(false);

    // Reset form when re-opening for a different bill
    useEffect(() => {
        if (open) {
            setPaymentDate(today);
            setReference("");
            setMethod("upi");
        }
    }, [open, bill.id]);

    if (!open) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!reference.trim()) {
            toast.error("Payment reference is required");
            return;
        }
        setBusy(true);
        try {
            const payload: MarkPaidPayload = {
                payment_date: paymentDate,
                payment_reference: reference.trim(),
                payment_method: method,
            };
            await emailApi.markBillPaid(bill.id, payload);
            toast.success(`Marked ${bill.biller_name} as paid`);
            onMarked();
            onClose();
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to mark paid";
            toast.error(msg);
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
            onClick={onClose}
            role="dialog"
            aria-modal="true"
            aria-labelledby="mark-paid-title"
        >
            <form
                onSubmit={handleSubmit}
                onClick={(e) => e.stopPropagation()}
                className="
                    w-[440px] max-w-[92vw] rounded-md
                    bg-[var(--bg-surface)] border border-[var(--border-emphasis)]
                    shadow-2xl shadow-black/40
                "
            >
                <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border-default)]">
                    <div>
                        <h3
                            id="mark-paid-title"
                            className="text-[14px] font-semibold tracking-tight text-white"
                        >
                            Mark as paid
                        </h3>
                        <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5">
                            {bill.biller_name} · {bill.currency} {bill.amount_due}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="
                            p-1 rounded text-[var(--text-muted)] hover:text-white
                            hover:bg-[var(--bg-elevated)] transition-colors
                        "
                        aria-label="Close"
                    >
                        <FiX className="w-4 h-4" />
                    </button>
                </div>

                <div className="px-5 py-4 space-y-4">
                    <label className="block">
                        <span className="microtype text-[var(--text-muted)] block mb-1">
                            Payment date
                        </span>
                        <input
                            type="date"
                            value={paymentDate}
                            onChange={(e) => setPaymentDate(e.target.value)}
                            required
                            max={today}
                            className="
                                w-full px-3 py-2 rounded-md
                                bg-[var(--bg-page)]
                                border border-[var(--border-emphasis)]
                                text-[13px] text-[var(--text-primary)] font-mono
                                focus:outline-none focus:border-[var(--accent)]
                            "
                        />
                    </label>

                    <label className="block">
                        <span className="microtype text-[var(--text-muted)] block mb-1">
                            Payment reference
                        </span>
                        <input
                            type="text"
                            value={reference}
                            onChange={(e) => setReference(e.target.value)}
                            required
                            maxLength={255}
                            placeholder="UPI txn ID, cheque #, etc."
                            className="
                                w-full px-3 py-2 rounded-md
                                bg-[var(--bg-page)]
                                border border-[var(--border-emphasis)]
                                text-[13px] text-[var(--text-primary)]
                                placeholder:text-[var(--text-disabled)]
                                focus:outline-none focus:border-[var(--accent)]
                            "
                        />
                    </label>

                    <label className="block">
                        <span className="microtype text-[var(--text-muted)] block mb-1">
                            Payment method
                        </span>
                        <select
                            value={method}
                            onChange={(e) =>
                                setMethod(
                                    e.target.value as typeof PAYMENT_METHODS[number],
                                )
                            }
                            className="
                                w-full px-3 py-2 rounded-md
                                bg-[var(--bg-page)]
                                border border-[var(--border-emphasis)]
                                text-[13px] text-[var(--text-primary)]
                                focus:outline-none focus:border-[var(--accent)]
                            "
                        >
                            {PAYMENT_METHODS.map((m) => (
                                <option key={m} value={m}>
                                    {m}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>

                <div className="flex justify-end gap-2 px-5 py-3 border-t border-[var(--border-default)]">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={busy}
                        className="
                            inline-flex items-center px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                            text-[var(--text-secondary)] hover:text-white
                            hover:bg-[var(--bg-hover)] disabled:opacity-50
                            transition-colors
                        "
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={busy}
                        className="
                            inline-flex items-center px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--accent)] text-white font-medium
                            hover:opacity-90 disabled:opacity-50
                            transition-opacity
                        "
                    >
                        {busy ? "Saving…" : "Mark paid"}
                    </button>
                </div>
            </form>
        </div>
    );
}
