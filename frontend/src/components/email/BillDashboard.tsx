"use client";

import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
    FiAlertTriangle,
    FiCheckCircle,
    FiClock,
    FiInbox,
} from "react-icons/fi";
import BillCard from "./BillCard";
import {
    Bill,
    BillStatusBucket,
    BulkMarkPaidPayload,
    emailApi,
} from "@/lib/email-api";

const BUCKETS: BillStatusBucket[] = [
    "upcoming",
    "due_soon",
    "overdue",
    "paid",
];

const BUCKET_META: Record<
    BillStatusBucket,
    {
        label: string;
        icon: React.ComponentType<{ className?: string }>;
        accent: string;
    }
> = {
    upcoming: { label: "Upcoming", icon: FiInbox, accent: "#3b82f6" },
    due_soon: { label: "Due Soon", icon: FiClock, accent: "#f59e0b" },
    overdue: { label: "Overdue", icon: FiAlertTriangle, accent: "#ef4444" },
    paid: { label: "Paid", icon: FiCheckCircle, accent: "#10b981" },
};

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
 * BillDashboard — BILL-03 stat cards + filterable grid + bulk mark-paid.
 *
 * Layout (D-26 v1.0 admin pattern):
 *   - Stat cards row: Upcoming / Due Soon / Overdue / Paid
 *     Click a card to scope the grid below to that bucket; click again to clear.
 *   - Selection toolbar appears when ≥1 bill is checked: Bulk mark paid CTA
 *     opens a modal that POSTs /email/bills/bulk-mark-paid with the selected ids.
 *   - Grid of BillCard tiles with overlay checkbox (selection independent of
 *     navigation; clicking the card body navigates to /bills/[id]).
 */
export default function BillDashboard() {
    const [bucket, setBucket] = useState<BillStatusBucket | null>(null);
    const [bills, setBills] = useState<Bill[]>([]);
    const [counts, setCounts] = useState<Record<BillStatusBucket, number>>({
        upcoming: 0,
        due_soon: 0,
        overdue: 0,
        paid: 0,
    });
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [bulkOpen, setBulkOpen] = useState(false);
    const [loading, setLoading] = useState(true);

    const loadCountsAndList = async (
        currentBucket: BillStatusBucket | null,
    ) => {
        setLoading(true);
        try {
            const responses = await Promise.all(
                BUCKETS.map((b) => emailApi.listBills({ status: b })),
            );
            const map: Record<BillStatusBucket, number> = {
                upcoming: responses[0].data.length,
                due_soon: responses[1].data.length,
                overdue: responses[2].data.length,
                paid: responses[3].data.length,
            };
            setCounts(map);
            if (currentBucket) {
                const idx = BUCKETS.indexOf(currentBucket);
                setBills(responses[idx].data);
            } else {
                // No bucket → show all four merged (overdue + due_soon + upcoming + paid)
                setBills(responses.flatMap((r) => r.data));
            }
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to load bills";
            toast.error(msg);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadCountsAndList(bucket);
        // Clear selection when bucket changes
        setSelected(new Set());
    }, [bucket]);

    const toggle = (id: number) => {
        const next = new Set(selected);
        if (next.has(id)) {
            next.delete(id);
        } else {
            next.add(id);
        }
        setSelected(next);
    };

    const selectedBillsList = useMemo(
        () => bills.filter((b) => selected.has(b.id)),
        [bills, selected],
    );

    return (
        <div className="space-y-6">
            {/* Stat cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {BUCKETS.map((b) => {
                    const meta = BUCKET_META[b];
                    const Icon = meta.icon;
                    const active = bucket === b;
                    return (
                        <button
                            key={b}
                            type="button"
                            onClick={() => setBucket(active ? null : b)}
                            className={`
                                text-left p-4 rounded-md border
                                transition-colors duration-150
                                ${
                                    active
                                        ? "bg-[var(--bg-elevated)] border-[var(--accent)]"
                                        : "bg-[var(--bg-elevated)] border-[var(--border-default)] hover:border-[var(--border-emphasis)]"
                                }
                            `}
                            aria-pressed={active}
                            data-bucket={b}
                        >
                            <div className="flex items-center justify-between">
                                <span
                                    className="microtype"
                                    style={{ color: meta.accent }}
                                >
                                    {meta.label}
                                </span>
                                <span
                                    style={{ color: meta.accent }}
                                    aria-hidden
                                >
                                    <Icon className="w-3.5 h-3.5" />
                                </span>
                            </div>
                            <div className="mt-2 font-mono tabular-nums text-[28px] font-semibold text-white">
                                {counts[b]}
                            </div>
                        </button>
                    );
                })}
            </div>

            {/* Selection toolbar */}
            {selected.size > 0 && (
                <div
                    className="
                        flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-md
                        bg-[var(--bg-elevated)] border border-[var(--accent-edge)]
                    "
                >
                    <span className="text-[12.5px] text-[var(--text-secondary)]">
                        {selected.size} selected
                    </span>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setSelected(new Set())}
                            className="
                                px-3 py-1.5 rounded text-[12px]
                                text-[var(--text-muted)] hover:text-white
                                hover:bg-[var(--bg-hover)]
                            "
                        >
                            Clear
                        </button>
                        <button
                            type="button"
                            onClick={() => setBulkOpen(true)}
                            className="
                                px-3 py-1.5 rounded text-[12px] font-medium
                                bg-[var(--accent)] text-white hover:opacity-90
                            "
                        >
                            Bulk mark paid
                        </button>
                    </div>
                </div>
            )}

            {/* Grid */}
            {loading ? (
                <div className="text-[13px] text-[var(--text-muted)]">
                    Loading bills…
                </div>
            ) : bills.length === 0 ? (
                <div
                    className="
                        rounded-md p-6 text-center
                        bg-[var(--bg-elevated)] border border-[var(--border-default)]
                        text-[13px] text-[var(--text-muted)]
                    "
                >
                    No bills{bucket ? ` in ${BUCKET_META[bucket].label}` : ""} yet.
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {bills.map((b) => (
                        <div key={b.id} className="relative">
                            <input
                                type="checkbox"
                                checked={selected.has(b.id)}
                                onChange={() => toggle(b.id)}
                                onClick={(e) => e.stopPropagation()}
                                className="
                                    absolute top-3 left-3 z-10 accent-[var(--accent)]
                                    cursor-pointer
                                "
                                aria-label={`Select ${b.biller_name}`}
                            />
                            <div className="pl-5">
                                <BillCard bill={b} />
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {bulkOpen && (
                <BulkMarkPaidModal
                    bills={selectedBillsList}
                    onClose={() => setBulkOpen(false)}
                    onDone={() => {
                        setBulkOpen(false);
                        setSelected(new Set());
                        loadCountsAndList(bucket);
                    }}
                />
            )}
        </div>
    );
}

interface BulkModalProps {
    bills: Bill[];
    onClose: () => void;
    onDone: () => void;
}

function BulkMarkPaidModal({ bills, onClose, onDone }: BulkModalProps) {
    const today = new Date().toISOString().slice(0, 10);
    const [paymentDate, setPaymentDate] = useState(today);
    const [reference, setReference] = useState("");
    const [method, setMethod] = useState<typeof PAYMENT_METHODS[number]>("upi");
    const [busy, setBusy] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!reference.trim()) {
            toast.error("Payment reference is required");
            return;
        }
        setBusy(true);
        try {
            const payload: BulkMarkPaidPayload = {
                ids: bills.map((b) => b.id),
                payment_date: paymentDate,
                payment_reference: reference.trim(),
                payment_method: method,
            };
            const r = await emailApi.bulkMarkBillsPaid(payload);
            const { ok, failed } = r.data.summary;
            if (failed === 0) {
                toast.success(`Marked ${ok} bills paid`);
            } else {
                toast(`Marked ${ok} paid, ${failed} failed`, { icon: "⚠" });
            }
            onDone();
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Bulk mark-paid failed";
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
        >
            <form
                onSubmit={handleSubmit}
                onClick={(e) => e.stopPropagation()}
                className="
                    w-[480px] max-w-[92vw] rounded-md
                    bg-[var(--bg-surface)] border border-[var(--border-emphasis)]
                    shadow-2xl shadow-black/40
                "
            >
                <div className="px-5 py-3 border-b border-[var(--border-default)]">
                    <h3 className="text-[14px] font-semibold tracking-tight text-white">
                        Bulk mark paid
                    </h3>
                    <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5">
                        {bills.length} bill{bills.length !== 1 ? "s" : ""}{" "}
                        selected
                    </p>
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
                            Reference (applied to all)
                        </span>
                        <input
                            type="text"
                            value={reference}
                            onChange={(e) => setReference(e.target.value)}
                            required
                            maxLength={255}
                            placeholder="Bulk reference, batch ID, etc."
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
                            Method
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
                            px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                            text-[var(--text-secondary)] hover:text-white
                            hover:bg-[var(--bg-hover)] disabled:opacity-50
                        "
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={busy}
                        className="
                            px-3 py-1.5 rounded-md text-[12.5px] font-medium
                            bg-[var(--accent)] text-white hover:opacity-90
                            disabled:opacity-50
                        "
                    >
                        {busy ? "Saving…" : `Mark ${bills.length} paid`}
                    </button>
                </div>
            </form>
        </div>
    );
}
