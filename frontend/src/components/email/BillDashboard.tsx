"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import {
    FiAlertTriangle,
    FiCheckCircle,
    FiClock,
    FiInbox,
} from "react-icons/fi";
import BillCard from "./BillCard";
import { Skeleton } from "@/components";
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
        accentSoft: string;
    }
> = {
    upcoming: {
        label: "Upcoming",
        icon: FiInbox,
        accent: "var(--info)",
        accentSoft: "var(--info-soft)",
    },
    due_soon: {
        label: "Due Soon",
        icon: FiClock,
        accent: "var(--warning)",
        accentSoft: "var(--warning-soft)",
    },
    overdue: {
        label: "Overdue",
        icon: FiAlertTriangle,
        accent: "var(--danger)",
        accentSoft: "var(--danger-soft)",
    },
    paid: {
        label: "Paid",
        icon: FiCheckCircle,
        accent: "var(--success)",
        accentSoft: "var(--success-soft)",
    },
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
            // Promise.allSettled so a single bucket's failure (e.g. slow
            // server-side filter on Overdue) does not blank the entire
            // dashboard. The user must still see paid/upcoming bills so
            // they can act on real liabilities; otherwise they could miss
            // a payment thinking they have nothing due.
            const settled = await Promise.allSettled(
                BUCKETS.map((b) => emailApi.listBills({ status: b })),
            );
            const failedBuckets: BillStatusBucket[] = [];
            const dataByBucket: Record<BillStatusBucket, Bill[]> = {
                upcoming: [],
                due_soon: [],
                overdue: [],
                paid: [],
            };
            settled.forEach((res, idx) => {
                const bucketName = BUCKETS[idx];
                if (res.status === "fulfilled") {
                    dataByBucket[bucketName] = res.value.data;
                } else {
                    failedBuckets.push(bucketName);
                }
            });
            const map: Record<BillStatusBucket, number> = {
                upcoming: dataByBucket.upcoming.length,
                due_soon: dataByBucket.due_soon.length,
                overdue: dataByBucket.overdue.length,
                paid: dataByBucket.paid.length,
            };
            setCounts(map);
            if (currentBucket) {
                setBills(dataByBucket[currentBucket]);
            } else {
                // No bucket → show all four merged, de-duped by id. A bill on a
                // boundary date can appear in two buckets server-side (e.g.
                // due_soon ∩ upcoming for the 3-day window edge); we keep the
                // first occurrence so the grid renders each bill once.
                const seen = new Set<number>();
                const merged: Bill[] = [];
                for (const bucketName of BUCKETS) {
                    for (const b of dataByBucket[bucketName]) {
                        if (!seen.has(b.id)) {
                            seen.add(b.id);
                            merged.push(b);
                        }
                    }
                }
                setBills(merged);
            }
            if (failedBuckets.length > 0) {
                toast.error(
                    `Could not load: ${failedBuckets
                        .map((b) => BUCKET_META[b].label)
                        .join(", ")}. Other buckets still shown.`,
                );
            }
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Failed to load invoices";
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
                                stat-strip text-left p-4 rounded-[10px] border
                                bg-[var(--bg-elevated)]
                                transition-all duration-150
                                ${
                                    active
                                        ? "border-[var(--accent)] shadow-[var(--shadow-md)]"
                                        : "border-[var(--border-default)] hover:border-[var(--border-emphasis)] hover:shadow-[var(--shadow-sm)]"
                                }
                            `}
                            style={{ color: meta.accent }}
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
                                    className="
                                        w-7 h-7 rounded-md
                                        flex items-center justify-center
                                    "
                                    style={{
                                        backgroundColor: meta.accentSoft,
                                        color: meta.accent,
                                    }}
                                    aria-hidden
                                >
                                    <Icon className="w-3.5 h-3.5" />
                                </span>
                            </div>
                            <div className="mt-3 font-mono tabular-nums text-[28px] font-semibold text-[var(--text-primary)] leading-none">
                                {counts[b]}
                            </div>
                            <div className="mt-1.5 text-[11.5px] text-[var(--text-muted)]">
                                {b === "paid" ? "this month" : "invoices"}
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
                                text-[var(--text-muted)] hover:text-[var(--text-primary)]
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
                                bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)]
                            "
                        >
                            Bulk mark paid
                        </button>
                    </div>
                </div>
            )}

            {/* Grid */}
            {loading ? (
                <div
                    className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"
                    role="status"
                    aria-busy="true"
                    aria-live="polite"
                >
                    <span className="sr-only">Loading invoices</span>
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-[116px] rounded-md" />
                    ))}
                </div>
            ) : bills.length === 0 ? (
                <div
                    className="
                        rounded-md p-6 text-center
                        bg-[var(--bg-elevated)] border border-[var(--border-default)]
                        text-[13px] text-[var(--text-muted)]
                    "
                >
                    No invoices{bucket ? ` in ${BUCKET_META[bucket].label}` : ""} yet.
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {bills.map((b) => (
                        <div key={b.id} className="relative">
                            <label
                                className="
                                    touch-target absolute top-1.5 left-1.5 z-10
                                    flex items-center justify-center rounded
                                    bg-[var(--bg-elevated)] border border-[var(--border-default)]
                                    cursor-pointer
                                "
                                onClick={(e) => e.stopPropagation()}
                            >
                                <input
                                    type="checkbox"
                                    checked={selected.has(b.id)}
                                    onChange={() => toggle(b.id)}
                                    className="accent-[var(--accent)] cursor-pointer"
                                    aria-label={`Select ${b.biller_name}`}
                                />
                            </label>
                            <div className="pl-9">
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
    const formRef = useRef<HTMLFormElement>(null);

    // a11y: focus first field on open, restore trigger focus on close, trap Tab
    useEffect(() => {
        const previouslyFocused = document.activeElement as HTMLElement | null;
        const focusables = () =>
            Array.from(
                formRef.current?.querySelectorAll<HTMLElement>(
                    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
                ) ?? [],
            );
        focusables()[0]?.focus();
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                onClose();
                return;
            }
            if (e.key === "Tab") {
                const els = focusables();
                if (els.length === 0) return;
                const first = els[0];
                const last = els[els.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        };
        document.addEventListener("keydown", onKeyDown);
        return () => {
            document.removeEventListener("keydown", onKeyDown);
            previouslyFocused?.focus();
        };
    }, [onClose]);

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
                toast.success(`Marked ${ok} invoices paid`);
            } else {
                // Surface which IDs failed so the user can reconcile rather
                // than wondering which 2 of 5 bills didn't apply. The toast
                // stays for longer so the user can read the IDs before it
                // auto-dismisses.
                const failedIds = r.data.results
                    .filter((row) => row.status === "failed")
                    .map((row) => `#${row.id}`)
                    .join(", ");
                toast(
                    `Marked ${ok} paid, ${failed} failed: ${failedIds}`,
                    {
                        icon: (
                            <FiAlertTriangle
                                className="w-4 h-4 text-[var(--warning)]"
                                aria-hidden
                            />
                        ),
                        duration: 8000,
                    },
                );
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
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
            onClick={onClose}
            role="dialog"
            aria-modal="true"
            aria-labelledby="bulk-mark-paid-title"
        >
            <form
                ref={formRef}
                onSubmit={handleSubmit}
                onClick={(e) => e.stopPropagation()}
                className="
                    w-[480px] max-w-[92vw] rounded-[10px]
                    bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                    shadow-[var(--shadow-lg)]
                "
            >
                <div className="px-5 py-3 border-b border-[var(--border-default)]">
                    <h3
                        id="bulk-mark-paid-title"
                        className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]"
                    >
                        Bulk mark paid
                    </h3>
                    <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5">
                        {bills.length} invoice{bills.length !== 1 ? "s" : ""}{" "}
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
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)] font-mono
                                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus:border-[var(--accent)]
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
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)]
                                placeholder:text-[var(--text-disabled)]
                                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus:border-[var(--accent)]
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
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)]
                                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus:border-[var(--accent)]
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
                            bg-[var(--bg-surface)] border border-[var(--border-emphasis)]
                            text-[var(--text-secondary)] hover:text-[var(--text-primary)]
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
                            bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)]
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
