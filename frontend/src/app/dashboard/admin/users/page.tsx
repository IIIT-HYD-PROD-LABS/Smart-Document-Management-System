"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
    FiSearch,
    FiChevronLeft,
    FiChevronRight,
    FiTrash2,
    FiArrowRight,
} from "react-icons/fi";

import { useAuth } from "@/context/AuthContext";
import { adminApi, extractErrorMessage } from "@/lib/api";
import { LoadingSpinner } from "@/components";
import DeleteUserModal from "@/components/admin/DeleteUserModal";

export const dynamic = "force-dynamic";

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

interface AdminUserList {
    users: AdminUser[];
    total: number;
    page: number;
    per_page: number;
}

const PER_PAGE = 20;

export default function AdminUsersPage() {
    const { user } = useAuth();
    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [page, setPage] = useState(1);
    const [pendingDelete, setPendingDelete] = useState<AdminUser | null>(null);
    const debounceTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

    useEffect(() => {
        debounceTimer.current = setTimeout(() => {
            setDebouncedSearch(search);
            setPage(1);
        }, 400);
        return () => clearTimeout(debounceTimer.current);
    }, [search]);

    const usersQuery = useQuery<AdminUserList>({
        queryKey: ["admin", "users", { page, search: debouncedSearch }],
        queryFn: () =>
            adminApi
                .getUsers(page, PER_PAGE, debouncedSearch || undefined)
                .then((r) => r.data),
    });

    const handleRoleChange = async (targetUser: AdminUser, newRole: string) => {
        if (newRole === targetUser.role) return;
        const confirmed = window.confirm(
            `Change ${targetUser.username}'s role from "${targetUser.role}" to "${newRole}"?`,
        );
        if (!confirmed) {
            usersQuery.refetch();
            return;
        }
        try {
            await adminApi.updateRole(targetUser.id, newRole);
            toast.success("Role updated");
            usersQuery.refetch();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Failed to update role"));
            usersQuery.refetch();
        }
    };

    const handleStatusToggle = async (targetUser: AdminUser) => {
        const action = targetUser.is_active ? "deactivate" : "activate";
        const confirmed = window.confirm(
            `Are you sure you want to ${action} ${targetUser.username}?`,
        );
        if (!confirmed) return;
        try {
            await adminApi.updateStatus(targetUser.id, !targetUser.is_active);
            toast.success(targetUser.is_active ? "User deactivated" : "User activated");
            usersQuery.refetch();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Failed to update status"));
        }
    };

    const data = usersQuery.data;
    const users = data?.users ?? [];
    const total = data?.total ?? 0;
    const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

    if (usersQuery.isLoading && !data) {
        return (
            <div className="flex items-center justify-center h-64">
                <LoadingSpinner />
            </div>
        );
    }

    if (usersQuery.isError) {
        return (
            <div className="surface-card p-6">
                <p className="text-[13px] text-[var(--danger)]">
                    Failed to load users. Try refreshing the page.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <header>
                <p className="microtype mb-2">Admin</p>
                <h1 className="text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Users
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1.5">
                    {total} {total === 1 ? "member" : "members"}. Click a row for details.
                </p>
            </header>

            <div className="flex items-center gap-3">
                <div className="relative flex-1 max-w-sm">
                    <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search by name, email, username..."
                        aria-label="Search users"
                        className="w-full pl-9 pr-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md text-sm text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-edge)] transition-colors"
                    />
                </div>
            </div>

            <div className="surface-card overflow-x-auto">
                <table className="w-full min-w-[720px]">
                    <thead>
                        <tr className="border-b border-[var(--border-default)] bg-[var(--bg-muted)]">
                            <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                User
                            </th>
                            <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                Role
                            </th>
                            <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                Status
                            </th>
                            <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                Provider
                            </th>
                            <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                Docs
                            </th>
                            <th className="text-left px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                Joined
                            </th>
                            <th className="text-right px-4 py-3 microtype text-[var(--text-muted)] font-medium">
                                Actions
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map((u) => (
                            <tr
                                key={u.id}
                                className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)] transition-colors"
                            >
                                <td className="px-4 py-3">
                                    <Link
                                        href={`/dashboard/admin/users/${u.id}`}
                                        className="group inline-flex items-center gap-2 cursor-pointer"
                                        aria-label={`Open ${u.username} detail`}
                                    >
                                        <div>
                                            <p className="text-sm text-[var(--text-primary)] group-hover:text-[var(--accent)] transition-colors">
                                                {u.username}
                                            </p>
                                            <p className="text-xs text-[var(--text-muted)]">
                                                {u.email}
                                            </p>
                                        </div>
                                        <FiArrowRight className="w-3 h-3 text-[var(--text-subtle)] opacity-0 group-hover:opacity-100 transition-opacity" />
                                    </Link>
                                </td>
                                <td className="px-4 py-3">
                                    <select
                                        value={u.role}
                                        onChange={(e) => handleRoleChange(u, e.target.value)}
                                        disabled={u.id === user?.id}
                                        className="bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                                    >
                                        <option value="admin">Admin</option>
                                        <option value="editor">Editor</option>
                                        <option value="viewer">Viewer</option>
                                    </select>
                                </td>
                                <td className="px-4 py-3">
                                    <button
                                        onClick={() => handleStatusToggle(u)}
                                        disabled={u.id === user?.id}
                                        className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                                            u.is_active
                                                ? "bg-[var(--success-soft)] text-[var(--success)]"
                                                : "bg-[var(--danger-soft)] text-[var(--danger)]"
                                        }`}
                                    >
                                        {u.is_active ? "Active" : "Inactive"}
                                    </button>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="text-xs text-[var(--text-muted)]">
                                        {u.auth_provider}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="text-sm text-[var(--text-primary)] tabular-nums">
                                        {u.document_count}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="text-xs text-[var(--text-muted)]">
                                        {new Date(u.created_at).toLocaleDateString("en-IN", {
                                            day: "numeric",
                                            month: "short",
                                            year: "numeric",
                                        })}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-right">
                                    <button
                                        onClick={() => setPendingDelete(u)}
                                        disabled={u.id === user?.id}
                                        title={
                                            u.id === user?.id
                                                ? "Cannot delete your own account"
                                                : "Delete user"
                                        }
                                        aria-label={`Delete ${u.username}`}
                                        className="p-1.5 rounded text-[var(--text-muted)] hover:text-[var(--danger)] hover:bg-[var(--danger-soft)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--danger)]"
                                    >
                                        <FiTrash2 className="w-4 h-4" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {users.length === 0 && (
                            <tr>
                                <td
                                    colSpan={7}
                                    className="px-4 py-8 text-center text-sm text-[var(--text-muted)]"
                                >
                                    No users found.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {totalPages > 1 && (
                <div className="flex items-center justify-between">
                    <p className="text-xs text-[var(--text-muted)]">
                        Showing {(page - 1) * PER_PAGE + 1} to{" "}
                        {Math.min(page * PER_PAGE, total)} of {total}
                    </p>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page === 1}
                            className="p-1.5 rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-emphasis)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                            aria-label="Previous page"
                        >
                            <FiChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-xs text-[var(--text-secondary)] tabular-nums">
                            {page} / {totalPages}
                        </span>
                        <button
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page === totalPages}
                            className="p-1.5 rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-emphasis)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                            aria-label="Next page"
                        >
                            <FiChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}

            <DeleteUserModal
                user={pendingDelete}
                onClose={() => setPendingDelete(null)}
                onDeleted={() => usersQuery.refetch()}
            />
        </div>
    );
}
