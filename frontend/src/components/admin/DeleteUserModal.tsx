"use client";

import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { FiAlertTriangle, FiX } from "react-icons/fi";
import { adminApi, extractErrorMessage } from "@/lib/api";

interface AdminUserSummary {
    id: number;
    username: string;
    email: string;
    role: string;
    document_count: number;
}

interface Props {
    user: AdminUserSummary | null;
    onClose: () => void;
    onDeleted: () => void;
}

/**
 * DeleteUserModal — admin destructive action.
 *
 * Type-to-confirm gates the destructive button. PII is anonymized server
 * side and the row is soft-deleted (see backend migration 0030 for why).
 * The modal mirrors the established modal pattern in MarkPaidModal.tsx
 * (size, header/body/footer rhythm, focus management) so the design
 * language stays consistent across the app.
 */
export default function DeleteUserModal({ user, onClose, onDeleted }: Props) {
    const [confirmText, setConfirmText] = useState("");
    const [busy, setBusy] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (user) {
            setConfirmText("");
            // autofocus the type-to-confirm input on open
            requestAnimationFrame(() => inputRef.current?.focus());
        }
    }, [user]);

    useEffect(() => {
        if (!user) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !busy) onClose();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [user, busy, onClose]);

    if (!user) return null;

    const matched = confirmText === user.username;

    const handleDelete = async () => {
        if (!matched || busy) return;
        setBusy(true);
        try {
            await adminApi.deleteUser(user.id);
            toast.success(`Deleted ${user.username}`);
            onDeleted();
            onClose();
        } catch (err: unknown) {
            toast.error(extractErrorMessage(err, "Failed to delete user"));
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(15,23,42,0.45)] backdrop-blur-sm motion-safe:animate-in motion-safe:fade-in motion-safe:duration-150"
            onClick={() => !busy && onClose()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-user-title"
            aria-describedby="delete-user-desc"
        >
            <div
                onClick={(e) => e.stopPropagation()}
                className="
                    w-[440px] max-w-[92vw] rounded-[10px]
                    bg-[var(--bg-elevated)] border border-[var(--border-emphasis)]
                    shadow-[var(--shadow-lg)]
                    motion-safe:animate-in motion-safe:zoom-in-95 motion-safe:duration-150
                "
            >
                <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border-default)]">
                    <div className="flex items-center gap-2.5">
                        <span
                            aria-hidden
                            className="flex items-center justify-center w-7 h-7 rounded-md bg-[var(--danger-soft)] text-[var(--danger)]"
                        >
                            <FiAlertTriangle className="w-4 h-4" />
                        </span>
                        <div>
                            <h3
                                id="delete-user-title"
                                className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]"
                            >
                                Delete user
                            </h3>
                            <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5">
                                {user.username} · {user.email}
                            </p>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={busy}
                        className="
                            p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)] transition-colors
                            focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]
                            disabled:opacity-50
                        "
                        aria-label="Close"
                    >
                        <FiX className="w-4 h-4" />
                    </button>
                </div>

                <div className="px-5 py-4 space-y-4" id="delete-user-desc">
                    <div className="rounded-md border border-[var(--danger-soft)] bg-[var(--danger-soft)]/40 px-3 py-2.5">
                        <p className="text-[12.5px] text-[var(--text-primary)] leading-relaxed">
                            This will <span className="font-semibold text-[var(--danger)]">permanently anonymize</span> the
                            account and revoke all sessions. The user&rsquo;s {user.document_count}
                            {" "}
                            document{user.document_count === 1 ? "" : "s"} will be removed.
                        </p>
                        <p className="text-[11.5px] text-[var(--text-muted)] mt-1.5 leading-relaxed">
                            Audit history is preserved (anonymized). The action cannot be undone from the UI.
                        </p>
                    </div>

                    <label className="block">
                        <span className="microtype text-[var(--text-muted)] block mb-1.5">
                            Type <span className="font-mono text-[var(--text-primary)]">{user.username}</span> to confirm
                        </span>
                        <input
                            ref={inputRef}
                            type="text"
                            value={confirmText}
                            onChange={(e) => setConfirmText(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && matched && !busy) {
                                    e.preventDefault();
                                    handleDelete();
                                }
                            }}
                            autoComplete="off"
                            spellCheck={false}
                            disabled={busy}
                            className="
                                w-full px-3 py-2 rounded-md font-mono
                                bg-[var(--bg-page)]
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)]
                                placeholder:text-[var(--text-disabled)]
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                                disabled:opacity-50
                            "
                            placeholder={user.username}
                            aria-label={`Type ${user.username} to confirm deletion`}
                        />
                    </label>
                </div>

                <div className="flex justify-end gap-2 px-5 py-3 border-t border-[var(--border-default)]">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={busy}
                        className="
                            inline-flex items-center px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--bg-surface)] border border-[var(--border-emphasis)]
                            text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                            hover:bg-[var(--bg-hover)] disabled:opacity-50
                            transition-colors cursor-pointer
                            focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)]
                        "
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onClick={handleDelete}
                        disabled={!matched || busy}
                        className="
                            inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12.5px]
                            bg-[var(--danger)] text-white font-medium
                            hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed
                            transition-opacity cursor-pointer
                            focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--danger)]
                        "
                    >
                        {busy ? "Deleting…" : "Delete user"}
                    </button>
                </div>
            </div>
        </div>
    );
}
