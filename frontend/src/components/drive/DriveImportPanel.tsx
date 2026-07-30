"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { FiCheck, FiCloud, FiLoader, FiRefreshCw } from "react-icons/fi";
import { driveApi, DriveFileItem } from "@/lib/drive-api";

/**
 * Google Drive import panel for /dashboard/upload.
 * OAuth round-trip lands on ?drive_token=… which we stash in sessionStorage.
 */
export default function DriveImportPanel() {
    const [token, setToken] = useState<string | null>(null);
    const [files, setFiles] = useState<DriveFileItem[]>([]);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [loading, setLoading] = useState(false);
    const [importing, setImporting] = useState(false);
    const [query, setQuery] = useState("");
    const [createNotices, setCreateNotices] = useState(false);

    useEffect(() => {
        if (typeof window === "undefined") return;
        const params = new URLSearchParams(window.location.search);
        const code = params.get("drive_code");
        const legacyToken = params.get("drive_token");
        const err = params.get("drive_error");
        if (err) {
            toast.error(`Drive connect failed: ${err}`);
            window.history.replaceState({}, "", window.location.pathname);
        }
        if (code) {
            window.history.replaceState({}, "", window.location.pathname);
            void (async () => {
                try {
                    const { data } = await driveApi.exchangeSession(code);
                    sessionStorage.setItem("taxsync_drive_token", data.access_token);
                    setToken(data.access_token);
                } catch {
                    toast.error("Drive session expired. Connect again.");
                }
            })();
        } else if (legacyToken) {
            // Back-compat with older redirects that put the token in the URL.
            sessionStorage.setItem("taxsync_drive_token", legacyToken);
            setToken(legacyToken);
            window.history.replaceState({}, "", window.location.pathname);
        } else {
            const stored = sessionStorage.getItem("taxsync_drive_token");
            if (stored) setToken(stored);
        }
    }, []);

    useEffect(() => {
        if (!token) return;
        void loadFiles();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    const connect = async () => {
        setLoading(true);
        try {
            const { data } = await driveApi.authorize();
            window.location.href = data.authorize_url;
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Could not start Drive OAuth";
            toast.error(msg);
            setLoading(false);
        }
    };

    const loadFiles = async (q = query) => {
        if (!token) return;
        setLoading(true);
        try {
            const { data } = await driveApi.listFiles(token, q);
            setFiles(data.files);
        } catch (e: unknown) {
            const status = (e as { response?: { status?: number } })?.response
                ?.status;
            if (status === 401) {
                sessionStorage.removeItem("taxsync_drive_token");
                setToken(null);
                toast.error("Drive session expired. Connect again.");
            } else {
                toast.error("Failed to list Drive files");
            }
        } finally {
            setLoading(false);
        }
    };

    const toggle = (id: string) => {
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const importSelected = async () => {
        if (!token || selected.size === 0) return;
        setImporting(true);
        try {
            const { data } = await driveApi.importFiles(
                token,
                Array.from(selected),
                createNotices,
            );
            toast.success(
                `Imported ${data.summary.ok} file${data.summary.ok === 1 ? "" : "s"}` +
                    (data.summary.failed
                        ? ` (${data.summary.failed} failed)`
                        : ""),
            );
            setSelected(new Set());
        } catch {
            toast.error("Import failed");
        } finally {
            setImporting(false);
        }
    };

    const formatSize = (n: number | null) => {
        if (n == null) return "";
        if (n >= 1048576) return `${(n / 1048576).toFixed(1)} MB`;
        return `${(n / 1024).toFixed(0)} KB`;
    };

    return (
        <section
            className="
                mt-8 rounded-xl border border-[var(--border-default)]
                bg-[var(--bg-elevated)] overflow-hidden
            "
        >
            <div className="px-5 py-4 border-b border-[var(--border-default)] flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0">
                    <span
                        className="
                            shrink-0 w-10 h-10 rounded-md
                            bg-[var(--accent-soft)] border border-[var(--accent-edge)]
                            flex items-center justify-center
                        "
                        aria-hidden
                    >
                        <FiCloud className="w-4.5 h-4.5 text-[var(--accent)]" />
                    </span>
                    <div className="min-w-0">
                        <h2 className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
                            Google Drive
                        </h2>
                        <p className="text-[12.5px] text-[var(--text-muted)] mt-0.5">
                            Pull PDFs, images, and DOCX from Drive into TaxSync
                            for OCR and compliance.
                        </p>
                    </div>
                </div>
                {!token ? (
                    <button
                        type="button"
                        onClick={connect}
                        disabled={loading}
                        className="
                            shrink-0 inline-flex items-center gap-2 h-9 px-3.5 rounded-md
                            bg-[var(--accent)] text-white text-[13px] font-medium
                            hover:bg-[var(--accent-strong)] disabled:opacity-50
                            transition-colors duration-150
                        "
                    >
                        <FiCloud className="w-4 h-4" aria-hidden />
                        {loading ? "Redirecting…" : "Connect Drive"}
                    </button>
                ) : (
                    <button
                        type="button"
                        onClick={() => loadFiles()}
                        disabled={loading}
                        className="
                            shrink-0 inline-flex items-center gap-1.5 h-9 px-3 rounded-md
                            border border-[var(--border-default)] text-[12.5px]
                            text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]
                            disabled:opacity-50
                        "
                    >
                        <FiRefreshCw
                            className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
                        />
                        Refresh
                    </button>
                )}
            </div>

            {token && (
                <div className="p-5 space-y-4">
                    <div className="flex flex-wrap gap-2 items-center">
                        <input
                            type="search"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter") void loadFiles(query);
                            }}
                            placeholder="Search Drive files"
                            className="
                                flex-1 min-w-[12rem] h-9 px-3 rounded-md text-[13px]
                                bg-[var(--bg-surface)] border border-[var(--border-default)]
                                text-[var(--text-primary)] placeholder:text-[var(--text-subtle)]
                                focus:outline-none focus:ring-2 focus:ring-[var(--accent)]
                            "
                        />
                        <button
                            type="button"
                            onClick={() => loadFiles(query)}
                            className="h-9 px-3 rounded-md text-[12.5px] border border-[var(--border-default)] hover:bg-[var(--bg-hover)]"
                        >
                            Search
                        </button>
                        <label className="inline-flex items-center gap-2 text-[12.5px] text-[var(--text-secondary)] ml-auto">
                            <input
                                type="checkbox"
                                checked={createNotices}
                                onChange={(e) => setCreateNotices(e.target.checked)}
                                className="rounded border-[var(--border-emphasis)]"
                            />
                            Create compliance notice stubs
                        </label>
                    </div>

                    {loading && files.length === 0 ? (
                        <div className="flex items-center gap-2 text-[13px] text-[var(--text-muted)] py-8 justify-center">
                            <FiLoader className="w-4 h-4 animate-spin" />
                            Loading Drive files…
                        </div>
                    ) : files.length === 0 ? (
                        <p className="text-[13px] text-[var(--text-muted)] py-6 text-center">
                            No matching files found.
                        </p>
                    ) : (
                        <ul className="divide-y divide-[var(--border-default)] rounded-md border border-[var(--border-default)] max-h-72 overflow-y-auto">
                            {files.map((f) => {
                                const on = selected.has(f.id);
                                return (
                                    <li key={f.id}>
                                        <button
                                            type="button"
                                            onClick={() => toggle(f.id)}
                                            className={`
                                                w-full flex items-center gap-3 px-3 py-2.5 text-left
                                                hover:bg-[var(--bg-hover)] transition-colors
                                                ${on ? "bg-[var(--accent-soft)]" : ""}
                                            `}
                                        >
                                            <span
                                                className={`
                                                    w-5 h-5 rounded border flex items-center justify-center shrink-0
                                                    ${
                                                        on
                                                            ? "bg-[var(--accent)] border-[var(--accent)] text-white"
                                                            : "border-[var(--border-emphasis)]"
                                                    }
                                                `}
                                            >
                                                {on && <FiCheck className="w-3 h-3" />}
                                            </span>
                                            <span className="min-w-0 flex-1">
                                                <span className="block text-[13px] font-medium text-[var(--text-primary)] truncate">
                                                    {f.name}
                                                </span>
                                                <span className="block text-[11px] text-[var(--text-subtle)]">
                                                    {f.mime_type}
                                                    {f.size != null
                                                        ? ` · ${formatSize(f.size)}`
                                                        : ""}
                                                </span>
                                            </span>
                                        </button>
                                    </li>
                                );
                            })}
                        </ul>
                    )}

                    <div className="flex justify-end">
                        <button
                            type="button"
                            disabled={selected.size === 0 || importing}
                            onClick={importSelected}
                            className="
                                inline-flex items-center gap-2 h-9 px-4 rounded-md
                                bg-[var(--accent)] text-white text-[13px] font-medium
                                hover:bg-[var(--accent-strong)]
                                disabled:opacity-40 disabled:cursor-not-allowed
                            "
                        >
                            {importing ? (
                                <FiLoader className="w-4 h-4 animate-spin" />
                            ) : (
                                <FiCloud className="w-4 h-4" />
                            )}
                            Import {selected.size || ""} selected
                        </button>
                    </div>
                </div>
            )}
        </section>
    );
}
