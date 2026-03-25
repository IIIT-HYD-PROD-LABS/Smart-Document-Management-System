"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { adminApi } from "@/lib/api";
import toast from "react-hot-toast";
import { FiUsers, FiFileText, FiSearch, FiChevronLeft, FiChevronRight } from "react-icons/fi";

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

export default function AdminPage() {
    const { user } = useAuth();
    const router = useRouter();
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [stats, setStats] = useState<AdminStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const perPage = 20;
    const debounceTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

    // Role guard: redirect non-admins
    useEffect(() => {
        if (user && user.role !== "admin") {
            router.replace("/dashboard");
        }
    }, [user, router]);

    // Immediate render guard: don't show admin UI to non-admins
    if (user?.role !== "admin") return null;

    // Debounce search input (400ms)
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
        if (user?.role !== "admin") return;
        setLoading(true);
        Promise.all([fetchUsers(), fetchStats()]).finally(() => setLoading(false));
    }, [fetchUsers, fetchStats, user?.role]);

    const handleRoleChange = async (userId: number, newRole: string) => {
        try {
            await adminApi.updateRole(userId, newRole);
            toast.success("Role updated");
            fetchUsers();
        } catch (err: unknown) {
            const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            toast.error(message || "Failed to update role");
        }
    };

    const handleStatusToggle = async (userId: number, currentStatus: boolean) => {
        try {
            await adminApi.updateStatus(userId, !currentStatus);
            toast.success(currentStatus ? "User deactivated" : "User activated");
            fetchUsers();
            fetchStats();
        } catch (err: unknown) {
            const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            toast.error(message || "Failed to update status");
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="w-5 h-5 border-2 border-[#27272a] border-t-[#a1a1aa] rounded-full animate-spin" />
            </div>
        );
    }

    const totalPages = Math.ceil(total / perPage);

    return (
        <div>
            <h1 className="text-lg font-semibold text-white mb-6">Admin Dashboard</h1>

            {/* Stats */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <StatCard label="Total Users" value={stats.total_users} icon={FiUsers} />
                    <StatCard label="Active Users" value={stats.active_users} icon={FiUsers} />
                    <StatCard label="Total Documents" value={stats.total_documents} icon={FiFileText} />
                    <StatCard
                        label="Users by Role"
                        value={Object.entries(stats.users_by_role).map(([r, c]) => `${r}: ${c}`).join(", ") || "—"}
                        icon={FiUsers}
                    />
                </div>
            )}

            {/* Search */}
            <div className="flex items-center gap-3 mb-4">
                <div className="relative flex-1 max-w-sm">
                    <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525b]" />
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search users..."
                        aria-label="Search users"
                        className="w-full pl-9 pr-3 py-2 bg-[#09090b] border border-[#27272a] rounded-md text-sm text-white placeholder:text-[#52525b] focus:outline-none focus:border-[#3f3f46] transition-colors"
                    />
                </div>
            </div>

            {/* User table */}
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
                                    <div>
                                        <p className="text-sm text-white">{u.username}</p>
                                        <p className="text-xs text-[#52525b]">{u.email}</p>
                                    </div>
                                </td>
                                <td className="px-4 py-3">
                                    <select
                                        value={u.role}
                                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                                        disabled={u.id === user?.id}
                                        className="bg-[#09090b] border border-[#27272a] rounded px-2 py-1 text-xs text-white focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                                    >
                                        <option value="admin">Admin</option>
                                        <option value="editor">Editor</option>
                                        <option value="viewer">Viewer</option>
                                    </select>
                                </td>
                                <td className="px-4 py-3">
                                    <button
                                        onClick={() => handleStatusToggle(u.id, u.is_active)}
                                        disabled={u.id === user?.id}
                                        className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                                            u.is_active
                                                ? "bg-[#10b981]/10 text-[#10b981]"
                                                : "bg-[#ef4444]/10 text-[#ef4444]"
                                        }`}
                                    >
                                        {u.is_active ? "Active" : "Inactive"}
                                    </button>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="text-xs text-[#71717a]">{u.auth_provider}</span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="text-sm text-white">{u.document_count}</span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="text-xs text-[#71717a]">
                                        {new Date(u.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                                    </span>
                                </td>
                            </tr>
                        ))}
                        {users.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-4 py-8 text-center text-sm text-[#52525b]">
                                    No users found
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                    <p className="text-xs text-[#52525b]">
                        Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} of {total}
                    </p>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={page === 1}
                            className="p-1.5 rounded border border-[#27272a] text-[#71717a] hover:text-white hover:border-[#3f3f46] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                        >
                            <FiChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-xs text-[#71717a]">{page} / {totalPages}</span>
                        <button
                            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                            disabled={page === totalPages}
                            className="p-1.5 rounded border border-[#27272a] text-[#71717a] hover:text-white hover:border-[#3f3f46] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                        >
                            <FiChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
