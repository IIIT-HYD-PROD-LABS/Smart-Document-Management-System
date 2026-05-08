"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import {
    FiArrowLeft,
    FiCheck,
    FiCopy,
    FiExternalLink,
    FiInfo,
} from "react-icons/fi";

interface ProviderDiag {
    configured: boolean;
    client_id_hint: string | null;
    redirect_uris: string[];
    console_url: string;
}

interface DiagResponse {
    backend_url: string;
    frontend_url: string;
    providers: {
        google: ProviderDiag;
        microsoft: ProviderDiag;
    };
    javascript_origins: string[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Public OAuth setup helper.
 *
 * Hits /api/auth/oauth/diag (no auth) and renders the redirect URIs +
 * JavaScript origins with click-to-copy buttons. Linked from the login
 * page so anyone hitting `redirect_uri_mismatch` can self-serve without
 * grepping the source.
 */
export default function OAuthSetupPage() {
    const [diag, setDiag] = useState<DiagResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${API_URL}/api/auth/oauth/diag`)
            .then((r) => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then((d: DiagResponse) => setDiag(d))
            .catch((e) => setError(String(e?.message ?? e)))
            .finally(() => setLoading(false));
    }, []);

    return (
        <div className="min-h-screen bg-[var(--bg-page)]">
            <div className="max-w-3xl mx-auto px-6 py-10 md:px-10 md:py-16">
                <Link
                    href="/login"
                    className="
                        inline-flex items-center gap-1.5 text-[12.5px]
                        text-[var(--text-muted)] hover:text-[var(--text-primary)]
                        transition-colors mb-6
                    "
                >
                    <FiArrowLeft className="w-3.5 h-3.5" />
                    Back to sign in
                </Link>

                <header className="mb-8">
                    <p className="microtype mb-2">Setup help</p>
                    <h1 className="text-[28px] font-semibold tracking-tight text-[var(--text-primary)]">
                        OAuth configuration
                    </h1>
                    <p className="text-[13.5px] text-[var(--text-muted)] mt-2 max-w-prose leading-relaxed">
                        If you hit{" "}
                        <code className="font-mono text-[12.5px] bg-[var(--bg-hover)] px-1.5 py-0.5 rounded">
                            redirect_uri_mismatch
                        </code>{" "}
                        signing in, your OAuth client doesn&apos;t have the
                        URIs below registered. Copy each URI and paste it
                        into the provider&apos;s console. Full guide:{" "}
                        <a
                            href="https://github.com/IIIT-HYD-PROD-LABS/Smart-Document-Management-System/blob/main/OAUTH_SETUP.md"
                            target="_blank"
                            rel="noreferrer noopener"
                            className="text-[var(--accent)] hover:underline"
                        >
                            OAUTH_SETUP.md
                        </a>
                        .
                    </p>
                </header>

                {loading && (
                    <div className="surface-card p-6">
                        <div className="h-4 w-48 bg-[var(--bg-hover)] animate-pulse rounded" />
                    </div>
                )}

                {error && (
                    <div className="surface-card p-6 border-[var(--danger)]/30">
                        <p className="text-[13px] text-[var(--danger)]">
                            Couldn&apos;t reach the backend ({error}). Make sure
                            it&apos;s running at{" "}
                            <code className="font-mono">{API_URL}</code>.
                        </p>
                    </div>
                )}

                {diag && (
                    <div className="space-y-6">
                        <BackendBlock diag={diag} />
                        <ProviderBlock
                            name="Google"
                            data={diag.providers.google}
                        />
                        <ProviderBlock
                            name="Microsoft"
                            data={diag.providers.microsoft}
                        />
                        <OriginsBlock origins={diag.javascript_origins} />
                    </div>
                )}
            </div>
        </div>
    );
}

function BackendBlock({ diag }: { diag: DiagResponse }) {
    return (
        <div className="surface-card p-5">
            <h2 className="microtype mb-3">Backend tells Google</h2>
            <dl className="grid grid-cols-[120px_1fr] gap-y-1.5 gap-x-4 text-[12.5px]">
                <dt className="text-[var(--text-muted)]">Backend URL</dt>
                <dd className="font-mono text-[var(--text-primary)]">
                    {diag.backend_url}
                </dd>
                <dt className="text-[var(--text-muted)]">Frontend URL</dt>
                <dd className="font-mono text-[var(--text-primary)]">
                    {diag.frontend_url}
                </dd>
            </dl>
        </div>
    );
}

function ProviderBlock({
    name,
    data,
}: {
    name: string;
    data: ProviderDiag;
}) {
    return (
        <div className="surface-card p-5">
            <header className="flex items-center justify-between mb-3 gap-3">
                <h2 className="microtype">{name}</h2>
                <span
                    className={`
                        text-[10.5px] font-mono uppercase tracking-wider
                        px-2 py-0.5 rounded
                        ${
                            data.configured
                                ? "bg-[var(--success-soft)] text-[var(--success)]"
                                : "bg-[var(--bg-hover)] text-[var(--text-muted)]"
                        }
                    `}
                >
                    {data.configured ? "Configured" : "Not configured"}
                </span>
            </header>

            {!data.configured ? (
                <p className="text-[12.5px] text-[var(--text-muted)] leading-relaxed">
                    No client ID set in the backend{" "}
                    <code className="font-mono text-[11.5px]">.env</code>. Skip
                    this section unless you intend to enable {name} sign-in.
                </p>
            ) : (
                <>
                    {data.client_id_hint && (
                        <p className="text-[11.5px] text-[var(--text-subtle)] font-mono mb-3">
                            Client ID prefix:{" "}
                            <span className="text-[var(--text-primary)]">
                                {data.client_id_hint}
                            </span>
                        </p>
                    )}

                    <p className="text-[12.5px] text-[var(--text-secondary)] mb-2 mt-3">
                        Add these to{" "}
                        <strong className="text-[var(--text-primary)]">
                            Authorized redirect URIs
                        </strong>{" "}
                        in the {name} console:
                    </p>
                    <div className="space-y-1.5 mb-4">
                        {data.redirect_uris.map((uri) => (
                            <CopyRow key={uri} value={uri} />
                        ))}
                    </div>

                    <a
                        href={data.console_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="
                            inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md
                            text-[12.5px] font-medium
                            bg-[var(--accent)] text-white
                            hover:bg-[var(--accent-strong)]
                            transition-colors
                        "
                    >
                        <FiExternalLink className="w-3 h-3" />
                        Open {name} console
                    </a>
                </>
            )}
        </div>
    );
}

function OriginsBlock({ origins }: { origins: string[] }) {
    return (
        <div className="surface-card p-5">
            <h2 className="microtype mb-3">JavaScript origins</h2>
            <p className="text-[12.5px] text-[var(--text-secondary)] mb-2">
                Add these to{" "}
                <strong className="text-[var(--text-primary)]">
                    Authorized JavaScript origins
                </strong>{" "}
                in your Google OAuth client (Microsoft uses the redirect URI
                only, no separate origins list):
            </p>
            <div className="space-y-1.5">
                {origins.map((o) => (
                    <CopyRow key={o} value={o} />
                ))}
            </div>
            <div className="mt-4 flex items-start gap-2 text-[11.5px] text-[var(--text-muted)] leading-relaxed">
                <FiInfo className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--info)]" />
                <span>
                    Wait ~30 seconds after saving — Google takes a moment to
                    propagate changes to its OAuth servers.
                </span>
            </div>
        </div>
    );
}

function CopyRow({ value }: { value: string }) {
    const [copied, setCopied] = useState(false);

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            toast.error("Couldn't copy — select the text manually.");
        }
    };

    return (
        <div className="flex items-center gap-2">
            <code
                className="
                    flex-1 min-w-0 font-mono text-[12px]
                    bg-[var(--bg-page)] border border-[var(--border-default)]
                    rounded px-2.5 py-1.5
                    text-[var(--text-primary)] truncate
                "
                title={value}
            >
                {value}
            </code>
            <button
                type="button"
                onClick={copy}
                className="
                    shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 rounded
                    text-[11.5px] font-medium cursor-pointer
                    bg-[var(--bg-elevated)] border border-[var(--border-default)]
                    text-[var(--text-secondary)]
                    hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]
                    hover:border-[var(--border-emphasis)]
                    transition-colors duration-150
                "
                aria-label={copied ? "Copied" : `Copy ${value}`}
            >
                {copied ? (
                    <>
                        <FiCheck className="w-3 h-3 text-[var(--success)]" />
                        Copied
                    </>
                ) : (
                    <>
                        <FiCopy className="w-3 h-3" />
                        Copy
                    </>
                )}
            </button>
        </div>
    );
}
