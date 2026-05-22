"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { useState } from "react";
import {
    FiArrowLeft,
    FiMail,
    FiUser,
    FiShield,
    FiTrash2,
    FiKey,
    FiFileText,
    FiClock,
    FiCpu,
} from "react-icons/fi";

import { useAuth } from "@/context/AuthContext";
import { adminApi, extractErrorMessage } from "@/lib/api";
import { LoadingSpinner } from "@/components";
import DeleteUserModal from "@/components/admin/DeleteUserModal";

export const dynamic = "force-dynamic";

interface AdminUserDetail {
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
    // Backend currently does not track last_login on the User model; field
    // declared optional so future expansion plugs in without changes here.
    last_login?: string | null;
}

interface AuditLogItem {
    id: number;
    user_id: number | null;
    action: string;
    resource_type: string | null;
    resource_id: number | null;
    details: Record<string, unknown> | null;
    ip_address: string | null;
    created_at: string;
}

interface AuditLogList {
    items: AuditLogItem[];
    total: number;
}

function MetaRow({
    icon: Icon,
    label,
    value,
}: {
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    value: React.ReactNode;
}) {
    return (
        <div className="flex items-start gap-3 py-2.5 border-b border-[var(--border-subtle)] last:border-0">
            <Icon className="w-4 h-4 text-[var(--text-muted)] mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
                <p className="microtype text-[var(--text-muted)]">{label}</p>
                <div className="text-[13px] text-[var(--text-primary)] mt-0.5 break-words">
                    {value}
                </div>
            </div>
        </div>
    );
}

function formatDate(iso: string | null | undefined): string {
    if (!iso) return "Never";
    return new Date(iso).toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function formatAction(action: string): string {
    return action.replace(/_/g, " ");
}

export default function AdminUserDetailPage() {
    const params = useParams<{ id: string }>();
    const router = useRouter();
    const { user: currentUser } = useAuth();
    const [pendingDelete, setPendingDelete] = useState<AdminUserDetail | null>(null);

    const userId = Number(params.id);
    const isSelf = currentUser?.id === userId;

    const userQuery = useQuery<AdminUserDetail>({
        queryKey: ["admin", "user", userId],
        queryFn: () => adminApi.getUser(userId).then((r) => r.data),
        enabled: Number.isFinite(userId) && userId > 0,
    });

    const auditQuery = useQuery<AuditLogList>({
        queryKey: ["admin", "audit", { userId, page: 1, perPage: 25 }],
        queryFn: () =>
            adminApi
                .getAuditLogs({ userId, page: 1, perPage: 25 })
                .then((r) => r.data),
        enabled: Number.isFinite(userId) && userId > 0,
    });

    const handleRoleChange = async (newRole: string) => {
        if (!userQuery.data || newRole === userQuery.data.role) return;
        const confirmed = window.confirm(
            `Change role from "${userQuery.data.role}" to "${newRole}"?`,
        );
        if (!confirmed) return;
        try {
            await adminApi.updateRole(userId, newRole);
            toast.success("Role updated");
            userQuery.refetch();
            auditQuery.refetch();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Failed to update role"));
        }
    };

    const handleStatusToggle = async () => {
        if (!userQuery.data) return;
        const action = userQuery.data.is_active ? "deactivate" : "activate";
        const confirmed = window.confirm(`Are you sure you want to ${action} this user?`);
        if (!confirmed) return;
        try {
            await adminApi.updateStatus(userId, !userQuery.data.is_active);
            toast.success(
                userQuery.data.is_active ? "User deactivated" : "User activated",
            );
            userQuery.refetch();
            auditQuery.refetch();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Failed to update status"));
        }
    };

    const handleResetPassword = () => {
        // Backend endpoint not yet implemented; placeholder action.
        toast("Password reset will be available in a future phase.", {
            icon: "i",
            duration: 4000,
        });
    };

    if (!Number.isFinite(userId) || userId <= 0) {
        return (
            <div className="surface-card p-6">
                <p className="text-[13px] text-[var(--danger)]">Invalid user id.</p>
            </div>
        );
    }

    if (userQuery.isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <LoadingSpinner />
            </div>
        );
    }

    if (userQuery.isError || !userQuery.data) {
        return (
            <div className="space-y-4">
                <Link
                    href="/dashboard/admin/users"
                    className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors cursor-pointer"
                >
                    <FiArrowLeft className="w-3 h-3" />
                    Back to users
                </Link>
                <div className="surface-card p-6">
                    <p className="text-[13px] text-[var(--danger)]">
                        User not found, or you don&rsquo;t have permission to view this record.
                    </p>
                </div>
            </div>
        );
    }

    const u = userQuery.data;
    const audit = auditQuery.data;

    return (
        <div className="space-y-6">
            <div>
                <Link
                    href="/dashboard/admin/users"
                    className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                >
                    <FiArrowLeft className="w-3 h-3" />
                    Back to users
                </Link>
            </div>

            <header className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-md bg-[var(--accent)] flex items-center justify-center text-[16px] font-semibold text-white shrink-0 shadow-sm">
                    {(u.full_name || u.username || u.email).charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                    <h1 className="text-[22px] font-semibold tracking-tight text-[var(--text-primary)] truncate">
                        {u.full_name || u.username}
                    </h1>
                    <p className="text-[13px] text-[var(--text-muted)] mt-1 truncate">
                        {u.email}
                    </p>
                </div>
                <span
                    className={`px-2 py-1 rounded text-xs font-medium ${
                        u.is_active
                            ? "bg-[var(--success-soft)] text-[var(--success)]"
                            : "bg-[var(--danger-soft)] text-[var(--danger)]"
                    }`}
                >
                    {u.is_active ? "Active" : "Inactive"}
                </span>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 surface-card p-5">
                    <h2 className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)] mb-3">
                        Profile
                    </h2>
                    <MetaRow icon={FiUser} label="Username" value={u.username} />
                    <MetaRow icon={FiMail} label="Email" value={u.email} />
                    <MetaRow
                        icon={FiShield}
                        label="Role"
                        value={
                            <span className="capitalize font-medium">{u.role}</span>
                        }
                    />
                    <MetaRow
                        icon={FiCpu}
                        label="Auth provider"
                        value={u.auth_provider}
                    />
                    <MetaRow
                        icon={FiFileText}
                        label="Documents"
                        value={
                            <span className="tabular-nums">{u.document_count}</span>
                        }
                    />
                    <MetaRow
                        icon={FiClock}
                        label="Joined"
                        value={formatDate(u.created_at)}
                    />
                    <MetaRow
                        icon={FiClock}
                        label="Last updated"
                        value={formatDate(u.updated_at)}
                    />
                    <MetaRow
                        icon={FiClock}
                        label="Last login"
                        value={
                            <span className="text-[var(--text-muted)] italic">
                                Not tracked
                            </span>
                        }
                    />
                </div>

                <div className="surface-card p-5 space-y-4">
                    <h2 className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]">
                        Actions
                    </h2>

                    <label className="block">
                        <span className="microtype block mb-1.5">Role</span>
                        <select
                            value={u.role}
                            onChange={(e) => handleRoleChange(e.target.value)}
                            disabled={isSelf}
                            className="w-full bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md px-2 py-1.5 text-[13px] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                        >
                            <option value="admin">Admin</option>
                            <option value="editor">Editor</option>
                            <option value="viewer">Viewer</option>
                        </select>
                        {isSelf && (
                            <p className="text-[11px] text-[var(--text-subtle)] mt-1">
                                You cannot change your own role.
                            </p>
                        )}
                    </label>

                    <button
                        type="button"
                        onClick={handleStatusToggle}
                        disabled={isSelf}
                        className="
                            w-full inline-flex items-center justify-center gap-1.5
                            px-3 py-2 rounded-md text-[12.5px] font-medium
                            bg-[var(--bg-elevated)] border border-[var(--border-default)]
                            text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                            disabled:opacity-50 disabled:cursor-not-allowed
                            transition-colors cursor-pointer
                        "
                    >
                        {u.is_active ? "Deactivate" : "Activate"} user
                    </button>

                    <button
                        type="button"
                        onClick={handleResetPassword}
                        disabled={u.auth_provider !== "local"}
                        title={
                            u.auth_provider !== "local"
                                ? "Password reset is only available for local accounts."
                                : "Send reset email"
                        }
                        className="
                            w-full inline-flex items-center justify-center gap-1.5
                            px-3 py-2 rounded-md text-[12.5px] font-medium
                            bg-[var(--bg-elevated)] border border-[var(--border-default)]
                            text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                            disabled:opacity-50 disabled:cursor-not-allowed
                            transition-colors cursor-pointer
                        "
                    >
                        <FiKey className="w-3.5 h-3.5" />
                        Reset password
                    </button>

                    <button
                        type="button"
                        onClick={() => setPendingDelete(u)}
                        disabled={isSelf}
                        title={
                            isSelf
                                ? "Cannot delete your own account"
                                : "Soft-delete and anonymize"
                        }
                        className="
                            w-full inline-flex items-center justify-center gap-1.5
                            px-3 py-2 rounded-md text-[12.5px] font-medium
                            bg-[var(--danger-soft)] border border-transparent
                            text-[var(--danger)]
                            hover:opacity-90
                            disabled:opacity-50 disabled:cursor-not-allowed
                            transition-opacity cursor-pointer
                        "
                    >
                        <FiTrash2 className="w-3.5 h-3.5" />
                        Delete user
                    </button>
                </div>
            </div>

            <div>
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]">
                        Audit history
                    </h2>
                    {audit && audit.total > 0 && (
                        <Link
                            href={`/dashboard/admin/audit?user_id=${userId}`}
                            className="text-[12.5px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors cursor-pointer"
                        >
                            Open in full audit log
                        </Link>
                    )}
                </div>
                <div className="surface-card overflow-hidden">
                    {auditQuery.isLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <LoadingSpinner />
                        </div>
                    ) : auditQuery.isError ? (
                        <p className="px-4 py-6 text-center text-[13px] text-[var(--text-muted)]">
                            Failed to load audit history.
                        </p>
                    ) : audit && audit.items.length > 0 ? (
                        <ul className="divide-y divide-[var(--border-subtle)]">
                            {audit.items.map((item) => (
                                <li key={item.id} className="px-4 py-3">
                                    <div className="flex items-baseline gap-2 flex-wrap">
                                        <p className="text-[13px] text-[var(--text-primary)]">
                                            <span className="font-medium capitalize">
                                                {formatAction(item.action)}
                                            </span>
                                            {item.resource_type && (
                                                <span className="text-[var(--text-muted)]">
                                                    {" on "}
                                                    {item.resource_type}
                                                    {item.resource_id != null &&
                                                        ` #${item.resource_id}`}
                                                </span>
                                            )}
                                        </p>
                                        <span className="text-[11px] text-[var(--text-subtle)] tabular-nums">
                                            {formatDate(item.created_at)}
                                        </span>
                                    </div>
                                    {item.details &&
                                        Object.keys(item.details).length > 0 && (
                                            <p className="text-[11.5px] text-[var(--text-muted)] mt-1 font-mono break-words">
                                                {JSON.stringify(item.details)}
                                            </p>
                                        )}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="px-4 py-6 text-center text-[13px] text-[var(--text-muted)]">
                            No audit history for this user.
                        </p>
                    )}
                </div>
            </div>

            <DeleteUserModal
                user={pendingDelete}
                onClose={() => setPendingDelete(null)}
                onDeleted={() => {
                    setPendingDelete(null);
                    router.push("/dashboard/admin/users");
                }}
            />
        </div>
    );
}
