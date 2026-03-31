"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { adminApi, extractErrorMessage } from "@/lib/api";
import { LoadingSpinner } from "@/components";
import toast from "react-hot-toast";
import { FiUsers, FiFileText, FiSearch, FiChevronLeft, FiChevronRight, FiMail, FiCheck, FiX, FiClock } from "react-icons/fi";

// ──── Shared types ────

interface AdminUser {
    id: number;
    email: string;
    username: string;
    full_name: string | null;
    role: string;
    is_active: boolean;
    auth_provider: string;
    document_count: number;
    created_at: string;
    updated_at: string | null;
}

interface AdminStats {
    total_users: number;
    active_users: number;
    users_by_role: Record<string, number>;
    total_documents: number;
    documents_by_status: Record<string, number>;
}

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

// ──── StatCard ────

function StatCard({ label, value, icon: Icon }: { label: string; value: number | string; icon: React.ComponentType<{ className?: string }> }) {
    return (
        <div className="bg-[#111113] border border-[#27272a] rounded-lg p-5">
            <div className="flex items-center gap-3 mb-2">
                <Icon className="w-4 h-4 text-[#52525b]" />
                <p className="text-[11px] text-[#52525b] uppercase tracking-wider">{label}</p>
            </div>
            <p className="text-2xl font-semibold text-white">{value}</p>
        </div>
    );
}

// ──── Users Tab ────

function UsersTab({ user }: { user: { id: number; role: string } }) {
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [stats, setStats] = useState<AdminStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const perPage = 20;
    const debounceTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

    useEffect(() => {
        debounceTimer.current = setTimeout(() => {
            setDebouncedSearch(search);
            setPage(1);
        }, 400);
        return () => clearTimeout(debounceTimer.current);
    }, [search]);

    const fetchUsers = useCallback(async () => {
        try {
            const res = await adminApi.getUsers(page, perPage, debouncedSearch || undefined);
            setUsers(res.data.users);
            setTotal(res.data.total);
        } catch {
            toast.error("Failed to load users");
        }
    }, [page, debouncedSearch]);

    const fetchStats = useCallback(async () => {
        try {
            const res = await adminApi.getStats();
            setStats(res.data);
        } catch {
            // Stats are optional
        }
    }, []);

    useEffect(() => {
        setLoading(true);
        Promise.all([fetchUsers(), fetchStats()]).finally(() => setLoading(false));
    }, [fetchUsers, fetchStats]);

    const handleRoleChange = async (targetUser: AdminUser, newRole: string) => {
        if (newRole === targetUser.role) return;
        const confirmed = window.confirm(
            `Change ${targetUser.username}'s role from "${targetUser.role}" to "${newRole}"?`
        );
        if (!confirmed) { fetchUsers(); return; }
        try {
            await adminApi.updateRole(targetUser.id, newRole);
            toast.success("Role updated");
            fetchUsers();
            fetchStats();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Failed to update role"));
            fetchUsers();
        }
    };

    const handleStatusToggle = async (targetUser: AdminUser) => {
        const action = targetUser.is_active ? "deactivate" : "activate";
        const confirmed = window.confirm(`Are you sure you want to ${action} ${targetUser.username}?`);
        if (!confirmed) return;
        try {
            await adminApi.updateStatus(targetUser.id, !targetUser.is_active);
            toast.success(targetUser.is_active ? "User deactivated" : "User activated");
            fetchUsers();
            fetchStats();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Failed to update status"));
        }
    };

    if (loading) return <div className="flex items-center justify-center h-64"><LoadingSpinner /></div>;

    const totalPages = Math.ceil(total / perPage);

    return (
        <>
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <StatCard label="Total Users" value={stats.total_users} icon={FiUsers} />
                    <StatCard label="Active Users" value={stats.active_users} icon={FiUsers} />
                    <StatCard label="Total Documents" value={stats.total_documents} icon={FiFileText} />
                    <StatCard
                        label="Users by Role"
                        value={Object.entries(stats.users_by_role).map(([r, c]) => `${r}: ${c}`).join(", ") || "\u2014"}
                        icon={FiUsers}
                    />
                </div>
            )}

            <div className="flex items-center gap-3 mb-4">
                <div className="relative flex-1 max-w-sm">
                    <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525b]" />
                    <input
                        type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search users..." aria-label="Search users"
                        className="w-full pl-9 pr-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors"
                    />
                </div>
            </div>

            <div className="bg-[#111113] border border-[#27272a] rounded-lg overflow-x-auto">
                <table className="w-full min-w-[700px]">
                    <thead>
                        <tr className="border-b border-[#27272a]">
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">User</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Role</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Status</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Provider</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Docs</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Joined</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map((u) => (
                            <tr key={u.id} className="border-b border-[#1e1e21] last:border-0 hover:bg-[#18181b]/50">
                                <td className="px-4 py-3">
                                    <div><p className="text-sm text-white">{u.username}</p><p className="text-xs text-[#52525b]">{u.email}</p></div>
                                </td>
                                <td className="px-4 py-3">
                                    <select
                                        value={u.role} onChange={(e) => handleRoleChange(u, e.target.value)} disabled={u.id === user.id}
                                        className="bg-[#09090b] border border-[#27272a] rounded px-2 py-1 text-xs text-white focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                                    >
                                        <option value="admin">Admin</option>
                                        <option value="editor">Editor</option>
                                        <option value="viewer">Viewer</option>
                                    </select>
                                </td>
                                <td className="px-4 py-3">
                                    <button onClick={() => handleStatusToggle(u)} disabled={u.id === user.id}
                                        className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${u.is_active ? "bg-[#10b981]/10 text-[#10b981]" : "bg-[#ef4444]/10 text-[#ef4444]"}`}
                                    >
                                        {u.is_active ? "Active" : "Inactive"}
                                    </button>
                                </td>
                                <td className="px-4 py-3"><span className="text-xs text-[#71717a]">{u.auth_provider}</span></td>
                                <td className="px-4 py-3"><span className="text-sm text-white">{u.document_count}</span></td>
                                <td className="px-4 py-3">
                                    <span className="text-xs text-[#71717a]">{new Date(u.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
                                </td>
                            </tr>
                        ))}
                        {users.length === 0 && (
                            <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-[#52525b]">No users found</td></tr>
                        )}
                    </tbody>
                </table>
            </div>

            {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                    <p className="text-xs text-[#52525b]">Showing {(page - 1) * perPage + 1}&ndash;{Math.min(page * perPage, total)} of {total}</p>
                    <div className="flex items-center gap-2">
                        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                            className="p-1.5 rounded border border-[#27272a] text-[#71717a] hover:text-white hover:border-[#3f3f46] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors">
                            <FiChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-xs text-[#71717a]">{page} / {totalPages}</span>
                        <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                            className="p-1.5 rounded border border-[#27272a] text-[#71717a] hover:text-white hover:border-[#3f3f46] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors">
                            <FiChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}
        </>
    );
}

// ──── Early Access Tab ────

function EarlyAccessTab() {
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
            const res = await adminApi.getEarlyAccess(page, perPage, statusFilter || undefined, debouncedSearch || undefined);
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
        const confirmed = window.confirm(`Are you sure you want to ${action} this request?`);
        if (!confirmed) return;
        try {
            await adminApi.reviewEarlyAccess(id, status, adminNote || undefined);
            toast.success(`Request ${status}`);
            setReviewingId(null);
            setAdminNote("");
            fetchItems();
            fetchStats();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, `Failed to ${action} request`));
        }
    };

    if (loading) return <div className="flex items-center justify-center h-64"><LoadingSpinner /></div>;

    const totalPages = Math.ceil(total / perPage);
    const statusFilters = [
        { value: "pending", label: "Pending", color: "text-[#f59e0b]" },
        { value: "approved", label: "Approved", color: "text-[#10b981]" },
        { value: "rejected", label: "Rejected", color: "text-[#ef4444]" },
        { value: "", label: "All", color: "text-[#a1a1aa]" },
    ];

    return (
        <>
            {/* Stats */}
            {eaStats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <StatCard label="Total Requests" value={eaStats.total} icon={FiMail} />
                    <StatCard label="Pending" value={eaStats.pending} icon={FiClock} />
                    <StatCard label="Approved" value={eaStats.approved} icon={FiCheck} />
                    <StatCard label="Rejected" value={eaStats.rejected} icon={FiX} />
                </div>
            )}

            {/* Filters */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
                <div className="flex items-center gap-1 bg-[#111113] border border-[#27272a] rounded-md p-0.5">
                    {statusFilters.map((sf) => (
                        <button
                            key={sf.value}
                            onClick={() => { setStatusFilter(sf.value); setPage(1); }}
                            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors cursor-pointer ${
                                statusFilter === sf.value
                                    ? "bg-[#27272a] text-white"
                                    : "text-[#71717a] hover:text-white"
                            }`}
                        >
                            {sf.label}
                            {eaStats && sf.value && (
                                <span className="ml-1 text-[10px] opacity-60">
                                    ({eaStats[sf.value as keyof EarlyAccessStats] ?? 0})
                                </span>
                            )}
                        </button>
                    ))}
                </div>
                <div className="relative flex-1 max-w-sm">
                    <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525b]" />
                    <input
                        type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search by name, email, company..." aria-label="Search early access requests"
                        className="w-full pl-9 pr-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors"
                    />
                </div>
            </div>

            {/* Table */}
            <div className="bg-[#111113] border border-[#27272a] rounded-lg overflow-x-auto">
                <table className="w-full min-w-[800px]">
                    <thead>
                        <tr className="border-b border-[#27272a]">
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Applicant</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Company</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Reason</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Status</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Submitted</th>
                            <th className="text-left px-4 py-3 text-[11px] text-[#52525b] uppercase tracking-wider font-medium">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items.map((item) => (
                            <tr key={item.id} className="border-b border-[#1e1e21] last:border-0 hover:bg-[#18181b]/50">
                                <td className="px-4 py-3">
                                    <div>
                                        <p className="text-sm text-white">{item.full_name}</p>
                                        <p className="text-xs text-[#52525b]">{item.email}</p>
                                    </div>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="text-xs text-[#71717a]">{item.company || "\u2014"}</span>
                                </td>
                                <td className="px-4 py-3 max-w-[200px]">
                                    <p className="text-xs text-[#71717a] truncate" title={item.reason || ""}>
                                        {item.reason || "\u2014"}
                                    </p>
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                        item.status === "pending" ? "bg-[#f59e0b]/10 text-[#f59e0b]" :
                                        item.status === "approved" ? "bg-[#10b981]/10 text-[#10b981]" :
                                        "bg-[#ef4444]/10 text-[#ef4444]"
                                    }`}>
                                        {item.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="text-xs text-[#71717a]">
                                        {new Date(item.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    {item.status === "pending" ? (
                                        <div className="flex items-center gap-1">
                                            {reviewingId === item.id ? (
                                                <div className="flex items-center gap-2">
                                                    <input
                                                        type="text"
                                                        value={adminNote}
                                                        onChange={(e) => setAdminNote(e.target.value)}
                                                        placeholder="Note (optional)"
                                                        className="px-2 py-1 bg-[#09090b] border border-[#27272a] rounded text-xs text-white placeholder:text-[#52525b] w-32 focus:outline-none focus:border-[#3f3f46]"
                                                    />
                                                    <button
                                                        onClick={() => handleReview(item.id, "approved")}
                                                        className="p-1.5 rounded bg-[#10b981]/10 text-[#10b981] hover:bg-[#10b981]/20 transition-colors cursor-pointer"
                                                        title="Approve"
                                                    >
                                                        <FiCheck className="w-3.5 h-3.5" />
                                                    </button>
                                                    <button
                                                        onClick={() => handleReview(item.id, "rejected")}
                                                        className="p-1.5 rounded bg-[#ef4444]/10 text-[#ef4444] hover:bg-[#ef4444]/20 transition-colors cursor-pointer"
                                                        title="Reject"
                                                    >
                                                        <FiX className="w-3.5 h-3.5" />
                                                    </button>
                                                    <button
                                                        onClick={() => { setReviewingId(null); setAdminNote(""); }}
                                                        className="text-xs text-[#52525b] hover:text-white transition-colors cursor-pointer"
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            ) : (
                                                <button
                                                    onClick={() => setReviewingId(item.id)}
                                                    className="px-2.5 py-1 rounded border border-[#27272a] text-xs text-[#a1a1aa] hover:text-white hover:border-[#3f3f46] transition-colors cursor-pointer"
                                                >
                                                    Review
                                                </button>
                                            )}
                                        </div>
                                    ) : (
                                        <span className="text-xs text-[#3f3f46]">
                                            {item.admin_note || "\u2014"}
                                        </span>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {items.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-4 py-8 text-center text-sm text-[#52525b]">
                                    No requests found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                    <p className="text-xs text-[#52525b]">Showing {(page - 1) * perPage + 1}&ndash;{Math.min(page * perPage, total)} of {total}</p>
                    <div className="flex items-center gap-2">
                        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                            className="p-1.5 rounded border border-[#27272a] text-[#71717a] hover:text-white hover:border-[#3f3f46] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors">
                            <FiChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-xs text-[#71717a]">{page} / {totalPages}</span>
                        <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                            className="p-1.5 rounded border border-[#27272a] text-[#71717a] hover:text-white hover:border-[#3f3f46] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors">
                            <FiChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}
        </>
    );
}

// ──── Main Admin Page ────

export default function AdminPage() {
    const { user } = useAuth();
    const router = useRouter();
    const [activeTab, setActiveTab] = useState<"users" | "early-access">("users");

    // Role guard: redirect non-admins
    useEffect(() => {
        if (user && user.role !== "admin") {
            router.replace("/dashboard");
        }
    }, [user, router]);

    // Render guard: don't show admin UI to non-admins
    if (user?.role !== "admin") return null;

    const tabs = [
        { id: "users" as const, label: "Users", icon: FiUsers },
        { id: "early-access" as const, label: "Early Access", icon: FiMail },
    ];

    return (
        <div>
            <h1 className="text-lg font-semibold text-white mb-6">Admin Dashboard</h1>

            {/* Tab switcher */}
            <div className="flex items-center gap-1 mb-6 bg-[#111113] border border-[#27272a] rounded-md p-0.5 w-fit">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded transition-colors cursor-pointer ${
                            activeTab === tab.id
                                ? "bg-[#27272a] text-white"
                                : "text-[#71717a] hover:text-white"
                        }`}
                    >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab content */}
            {activeTab === "users" && <UsersTab user={user} />}
            {activeTab === "early-access" && <EarlyAccessTab />}
        </div>
    );
}
