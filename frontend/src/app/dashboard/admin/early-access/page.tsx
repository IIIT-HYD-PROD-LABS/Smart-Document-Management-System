"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import {
    FiCheck,
    FiChevronLeft,
    FiChevronRight,
    FiClock,
    FiMail,
    FiSearch,
    FiX,
} from "react-icons/fi";

import { adminApi, extractErrorMessage } from "@/lib/api";
import { Skeleton } from "@/components";

export const dynamic = "force-dynamic";

interface EarlyAccessItem {
    id: number;
    full_name: string;
    email: string;
    company: string | null;
    reason: string | null;
    status: string;
    admin_note: string | null;
    created_at: string;
    reviewed_at: string | null;
    reviewed_by: number | null;
}

interface EarlyAccessStats {
    pending: number;
    approved: number;
    rejected: number;
    total: number;
}

function StatCard({
    label,
    value,
    icon: Icon,
}: {
    label: string;
    value: number | string;
    icon: React.ComponentType<{ className?: string }>;
}) {
    return (
        <div className="surface-card p-5">
            <div className="flex items-center gap-3 mb-2">
                <Icon className="w-4 h-4 text-[var(--text-muted)]" />
                <p className="microtype text-[var(--text-muted)]">{label}</p>
            </div>
            <p className="text-2xl font-semibold text-[var(--text-primary)] tabular-nums">
                {value}
            </p>
        </div>
    );
}

export default function EarlyAccessPage() {
    const [items, setItems] = useState<EarlyAccessItem[]>([]);
    const [eaStats, setEaStats] = useState<EarlyAccessStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<string>("pending");
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const perPage = 20;
    const debounceTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
    const [reviewingId, setReviewingId] = useState<number | null>(null);
    const [adminNote, setAdminNote] = useState("");

    useEffect(() => {
        debounceTimer.current = setTimeout(() => {
            setDebouncedSearch(search);
            setPage(1);
        }, 400);
        return () => clearTimeout(debounceTimer.current);
    }, [search]);

    const fetchItems = useCallback(async () => {
        try {
            const res = await adminApi.getEarlyAccess(
                page,
                perPage,
                statusFilter || undefined,
                debouncedSearch || undefined,
            );
            setItems(res.data.items);
            setTotal(res.data.total);
        } catch {
            toast.error("Failed to load requests");
        }
    }, [page, statusFilter, debouncedSearch]);

    const fetchStats = useCallback(async () => {
        try {
            const res = await adminApi.getEarlyAccessStats();
            setEaStats(res.data);
        } catch {
            // optional
        }
    }, []);

    useEffect(() => {
        setLoading(true);
        Promise.all([fetchItems(), fetchStats()]).finally(() => setLoading(false));
    }, [fetchItems, fetchStats]);

    const handleReview = async (id: number, status: "approved" | "rejected") => {
        const action = status === "approved" ? "approve" : "reject";
        const confirmed = window.confirm(
            `Are you sure you want to ${action} this request?`,
        );
        if (!confirmed) return;
        try {
            const res = await adminApi.reviewEarlyAccess(id, status, adminNote || undefined);
            const { email_sent, email_error } = (res?.data ?? {}) as {
                email_sent?: boolean;
                email_error?: string | null;
            };
            if (email_sent) {
                toast.success(`Request ${status}, invitation email sent`);
            } else {
                toast.error(
                    `Request ${status}, but email was NOT delivered${
                        email_error ? ` (${email_error})` : ""
                    }. Check server logs.`,
                    { duration: 6000 },
                );
            }
            setReviewingId(null);
            setAdminNote("");
            fetchItems();
            fetchStats();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, `Failed to ${action} request`));
        }
    };

    const statusFilters = [
        { value: "pending", label: "Pending" },
        { value: "approved", label: "Approved" },
        { value: "rejected", label: "Rejected" },
        { value: "", label: "All" },
    ];
    const totalPages = Math.ceil(total / perPage);

    return (
        <div className="space-y-6">
            <header>
                <p className="microtype mb-2">Admin</p>
                <h1 className="text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Early access
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1.5">
                    Review pending invitation requests and approve qualified members.
                </p>
            </header>

            {eaStats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <StatCard label="Total" value={eaStats.total} icon={FiMail} />
                    <StatCard label="Pending" value={eaStats.pending} icon={FiClock} />
                    <StatCard label="Approved" value={eaStats.approved} icon={FiCheck} />
                    <StatCard label="Rejected" value={eaStats.rejected} icon={FiX} />
                </div>
            )}

            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                <div className="flex items-center gap-1 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md p-0.5">
                    {statusFilters.map((sf) => (
                        <button
                            key={sf.value}
                            onClick={() => {
                                setStatusFilter(sf.value);
                                setPage(1);
                            }}
                            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors cursor-pointer ${
                                statusFilter === sf.value
                                    ? "bg-[var(--bg-hover)] text-[var(--text-primary)]"
                                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                            }`}
                        >
                            {sf.label}
                        </button>
                    ))}
                </div>
                <div className="relative flex-1 max-w-sm">
                    <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search by name, email, company..."
                        aria-label="Search early access requests"
                        className="w-full pl-9 pr-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md text-sm text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)] transition-colors"
                    />
                </div>
            </div>

            {loading ? (
                <div
                    role="status"
                    aria-busy="true"
                    aria-live="polite"
                    className="space-y-6"
                >
                    <span className="sr-only">Loading early access requests</span>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <div key={i} className="surface-card p-5">
                                <Skeleton className="h-4 w-20 mb-3" />
                                <Skeleton className="h-7 w-12" />
                            </div>
                        ))}
                    </div>
                    <div className="surface-card overflow-x-auto">
                        <table className="w-full min-w-[800px]">
                            <thead>
                                <tr className="border-b border-[var(--border-default)]">
                                    <th className="text-left px-4 py-3 microtype">Applicant</th>
                                    <th className="text-left px-4 py-3 microtype">Company</th>
                                    <th className="text-left px-4 py-3 microtype">Reason</th>
                                    <th className="text-left px-4 py-3 microtype">Status</th>
                                    <th className="text-left px-4 py-3 microtype">Submitted</th>
                                    <th className="text-left px-4 py-3 microtype">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Array.from({ length: 6 }).map((_, i) => (
                                    <tr
                                        key={i}
                                        className="border-b border-[var(--border-subtle)] last:border-0"
                                    >
                                        <td className="px-4 py-3">
                                            <Skeleton className="h-[13px] w-32 mb-1.5" />
                                            <Skeleton className="h-[11.5px] w-40" />
                                        </td>
                                        <td className="px-4 py-3">
                                            <Skeleton className="h-[12px] w-24" />
                                        </td>
                                        <td className="px-4 py-3 max-w-[220px]">
                                            <Skeleton className="h-[12px] w-44" />
                                        </td>
                                        <td className="px-4 py-3">
                                            <Skeleton className="h-[18px] w-16 rounded" />
                                        </td>
                                        <td className="px-4 py-3">
                                            <Skeleton className="h-[11.5px] w-20" />
                                        </td>
                                        <td className="px-4 py-3">
                                            <Skeleton className="h-7 w-16 rounded" />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : (
                <>
                    <div className="surface-card overflow-x-auto">
                        <table className="w-full min-w-[800px]">
                            <thead>
                                <tr className="border-b border-[var(--border-default)]">
                                    <th className="text-left px-4 py-3 microtype">Applicant</th>
                                    <th className="text-left px-4 py-3 microtype">Company</th>
                                    <th className="text-left px-4 py-3 microtype">Reason</th>
                                    <th className="text-left px-4 py-3 microtype">Status</th>
                                    <th className="text-left px-4 py-3 microtype">Submitted</th>
                                    <th className="text-left px-4 py-3 microtype">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items.map((item) => (
                                    <tr
                                        key={item.id}
                                        className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]"
                                    >
                                        <td className="px-4 py-3">
                                            <p className="text-[13px] text-[var(--text-primary)]">{item.full_name}</p>
                                            <p className="text-[11.5px] text-[var(--text-muted)]">{item.email}</p>
                                        </td>
                                        <td className="px-4 py-3 text-[12px] text-[var(--text-muted)]">
                                            {item.company || (
                                                <span className="text-[var(--text-disabled)]">None</span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3 max-w-[220px]">
                                            <p
                                                className="text-[12px] text-[var(--text-muted)] truncate"
                                                title={item.reason || ""}
                                            >
                                                {item.reason || (
                                                    <span className="text-[var(--text-disabled)]">None</span>
                                                )}
                                            </p>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span
                                                className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                                                    item.status === "pending"
                                                        ? "bg-[var(--warning-soft)] text-[var(--warning)]"
                                                        : item.status === "approved"
                                                          ? "bg-[var(--success-soft)] text-[var(--success)]"
                                                          : "bg-[var(--danger-soft)] text-[var(--danger)]"
                                                }`}
                                            >
                                                {item.status}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-[11.5px] text-[var(--text-muted)]">
                                            {new Date(item.created_at).toLocaleDateString("en-IN", {
                                                day: "numeric",
                                                month: "short",
                                                year: "numeric",
                                            })}
                                        </td>
                                        <td className="px-4 py-3">
                                            {item.status === "pending" ? (
                                                reviewingId === item.id ? (
                                                    <div className="flex items-center gap-2">
                                                        <input
                                                            type="text"
                                                            value={adminNote}
                                                            onChange={(e) => setAdminNote(e.target.value)}
                                                            placeholder="Note (optional)"
                                                            className="px-2 py-1 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded text-[12px] text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] w-32 focus:outline-none focus:border-[var(--accent)]"
                                                        />
                                                        <button
                                                            onClick={() => handleReview(item.id, "approved")}
                                                            className="p-1.5 rounded bg-[var(--success-soft)] text-[var(--success)] hover:opacity-80 transition-opacity cursor-pointer"
                                                            title="Approve"
                                                        >
                                                            <FiCheck className="w-3.5 h-3.5" />
                                                        </button>
                                                        <button
                                                            onClick={() => handleReview(item.id, "rejected")}
                                                            className="p-1.5 rounded bg-[var(--danger-soft)] text-[var(--danger)] hover:opacity-80 transition-opacity cursor-pointer"
                                                            title="Reject"
                                                        >
                                                            <FiX className="w-3.5 h-3.5" />
                                                        </button>
                                                        <button
                                                            onClick={() => {
                                                                setReviewingId(null);
                                                                setAdminNote("");
                                                            }}
                                                            className="text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => setReviewingId(item.id)}
                                                        className="px-2.5 py-1 rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[12px] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
                                                    >
                                                        Review
                                                    </button>
                                                )
                                            ) : (
                                                <span className="text-[11.5px] text-[var(--text-disabled)]">
                                                    {item.admin_note || "None"}
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {items.length === 0 && (
                                    <tr>
                                        <td
                                            colSpan={6}
                                            className="px-4 py-8 text-center text-[13px] text-[var(--text-muted)]"
                                        >
                                            No requests found
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    {totalPages > 1 && (
                        <div className="flex items-center justify-between">
                            <p className="text-[11.5px] text-[var(--text-muted)]">
                                Showing {(page - 1) * perPage + 1} to {Math.min(page * perPage, total)} of {total}
                            </p>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                    className="p-1.5 rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-emphasis)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                                >
                                    <FiChevronLeft className="w-4 h-4" />
                                </button>
                                <span className="text-[12px] text-[var(--text-muted)]">
                                    {page} / {totalPages}
                                </span>
                                <button
                                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                    className="p-1.5 rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-emphasis)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                                >
                                    <FiChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
