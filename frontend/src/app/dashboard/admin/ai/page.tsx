"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { FiCheck, FiCpu, FiTrash2, FiX, FiZap } from "react-icons/fi";

import { aiApi } from "@/lib/api/ai";
import {
    DEFAULT_MODEL,
    PROVIDER_LABEL,
    type AICredential,
    type AIProvider,
} from "@/types/ai";

/**
 * AI Settings page — Phase 16.
 *
 * Tenant admins (CLIENT_MANAGE_TEAM) connect a Claude or Gemini key here.
 * The key field is write-only; once saved, the backend stores Fernet
 * ciphertext and never returns the plaintext. The form re-renders with
 * "Connected" status; replacing the key replaces the row in-place.
 */
export default function AISettingsPage() {
    const queryClient = useQueryClient();

    const { data: cred, isLoading } = useQuery<AICredential | null>({
        queryKey: ["ai-credential"],
        queryFn: () => aiApi.getCredential().then((r) => r.data),
    });

    const [provider, setProvider] = useState<AIProvider>("anthropic");
    const [model, setModel] = useState<string>(DEFAULT_MODEL.anthropic);
    const [apiKey, setApiKey] = useState("");
    const [busy, setBusy] = useState<"test" | "save" | "delete" | null>(null);
    const [testStatus, setTestStatus] = useState<
        | { kind: "ok"; latency_ms: number }
        | { kind: "error"; detail: string }
        | null
    >(null);

    // When the existing credential loads, mirror it into the form so the
    // user sees what's connected. We do NOT prefill the key (it's gone).
    useEffect(() => {
        if (cred) {
            setProvider(cred.provider as AIProvider);
            setModel(cred.model);
            setApiKey("");
        }
    }, [cred]);

    const onProviderChange = (p: AIProvider) => {
        setProvider(p);
        setModel(DEFAULT_MODEL[p]);
        setTestStatus(null);
    };

    const handleTest = async () => {
        if (!apiKey || apiKey.length < 8) {
            toast.error("Enter an API key (8+ chars) to test.");
            return;
        }
        setBusy("test");
        setTestStatus(null);
        try {
            const r = await aiApi.testCredential({
                provider,
                model,
                api_key: apiKey,
            });
            if (r.data.ok) {
                setTestStatus({
                    kind: "ok",
                    latency_ms: r.data.latency_ms ?? 0,
                });
            } else {
                setTestStatus({
                    kind: "error",
                    detail: r.data.detail || "unknown error",
                });
            }
        } catch (e: unknown) {
            const detail =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Test failed.";
            setTestStatus({ kind: "error", detail });
        } finally {
            setBusy(null);
        }
    };

    const handleSave = async () => {
        if (!apiKey || apiKey.length < 8) {
            toast.error("Enter an API key to save.");
            return;
        }
        setBusy("save");
        try {
            await aiApi.setCredential({
                provider,
                model,
                api_key: apiKey,
            });
            await queryClient.invalidateQueries({ queryKey: ["ai-credential"] });
            setApiKey("");
            setTestStatus(null);
            toast.success("AI credential saved.");
        } catch (e: unknown) {
            const detail =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Save failed.";
            toast.error(detail);
        } finally {
            setBusy(null);
        }
    };

    const handleDelete = async () => {
        if (!cred) return;
        if (!confirm("Disconnect AI for this tenant?")) return;
        setBusy("delete");
        try {
            await aiApi.deleteCredential();
            await queryClient.invalidateQueries({ queryKey: ["ai-credential"] });
            setApiKey("");
            setTestStatus(null);
            toast.success("AI disconnected.");
        } catch (e: unknown) {
            const detail =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Delete failed.";
            toast.error(detail);
        } finally {
            setBusy(null);
        }
    };

    return (
        <div className="space-y-6 max-w-2xl">
            <header>
                <p className="microtype mb-2">Settings</p>
                <h1 className="text-[24px] font-semibold tracking-tight text-[var(--text-primary)] flex items-center gap-2">
                    <FiCpu className="w-5 h-5 text-[var(--accent)]" />
                    AI assistant
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-2 max-w-prose">
                    AI summaries, extraction, and drafts work out of the box
                    using TaxSync&apos;s built-in provider. Optionally connect
                    your own Anthropic Claude or Google Gemini API key to run on
                    your account instead. Either way, TaxSync uses it only for
                    compliance, notice, and invoice work; anything outside that
                    scope is refused.
                </p>
            </header>

            {isLoading ? (
                <div className="surface-card p-6">
                    <div className="h-4 w-32 bg-[var(--bg-hover)] animate-pulse rounded" />
                </div>
            ) : (
                <>
                    {cred && (
                        <div className="surface-card p-4 flex items-center justify-between gap-3">
                            <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-md bg-[var(--success-soft)] flex items-center justify-center shrink-0">
                                    <FiCheck className="w-4 h-4 text-[var(--success)]" />
                                </div>
                                <div className="min-w-0">
                                    <p className="text-[13.5px] font-medium text-[var(--text-primary)]">
                                        Connected to {PROVIDER_LABEL[cred.provider as AIProvider]}
                                    </p>
                                    <p className="text-[11.5px] text-[var(--text-muted)] font-mono mt-0.5">
                                        {cred.model}
                                        {cred.last_used_at && (
                                            <>
                                                {" · last used "}
                                                {new Date(
                                                    cred.last_used_at,
                                                ).toLocaleString("en-IN")}
                                            </>
                                        )}
                                    </p>
                                </div>
                            </div>
                            <button
                                type="button"
                                onClick={handleDelete}
                                disabled={busy !== null}
                                className="
                                    inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md
                                    text-[12.5px] text-[var(--text-muted)]
                                    hover:text-[var(--danger)] hover:bg-[var(--bg-hover)]
                                    transition-colors duration-150 cursor-pointer
                                    disabled:opacity-50
                                "
                            >
                                <FiTrash2 className="w-3 h-3" />
                                Disconnect
                            </button>
                        </div>
                    )}

                    <div className="surface-card p-6 space-y-5">
                        <h2 className="microtype">
                            {cred ? "Replace credential" : "Connect a provider"}
                        </h2>

                        <fieldset className="space-y-2">
                            <legend className="microtype block mb-1.5">
                                Provider
                            </legend>
                            <div className="grid grid-cols-2 gap-2">
                                {(["anthropic", "google"] as const).map((p) => (
                                    <label
                                        key={p}
                                        className={`
                                            cursor-pointer rounded-md p-3 border
                                            transition-colors duration-150
                                            ${
                                                provider === p
                                                    ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                                                    : "border-[var(--border-default)] hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)]"
                                            }
                                        `}
                                    >
                                        <input
                                            type="radio"
                                            name="provider"
                                            value={p}
                                            checked={provider === p}
                                            onChange={() => onProviderChange(p)}
                                            className="sr-only"
                                        />
                                        <p className="text-[13px] font-medium text-[var(--text-primary)]">
                                            {PROVIDER_LABEL[p]}
                                        </p>
                                        <p className="text-[11.5px] text-[var(--text-muted)] mt-0.5 font-mono">
                                            {DEFAULT_MODEL[p]}
                                        </p>
                                    </label>
                                ))}
                            </div>
                        </fieldset>

                        <label className="block">
                            <span className="microtype block mb-1.5">Model</span>
                            <input
                                type="text"
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                className="
                                    w-full px-3 py-2 rounded-md
                                    bg-[var(--bg-page)]
                                    border border-[var(--border-default)]
                                    text-[13px] text-[var(--text-primary)] font-mono
                                    placeholder:text-[var(--text-disabled)]
                                    focus:outline-none focus:border-[var(--accent)]
                                    focus:ring-2 focus:ring-[var(--accent-edge)]
                                    transition-colors duration-150
                                "
                                placeholder={DEFAULT_MODEL[provider]}
                            />
                            <p className="text-[11px] text-[var(--text-subtle)] mt-1">
                                Default for {PROVIDER_LABEL[provider]} is{" "}
                                <span className="font-mono">
                                    {DEFAULT_MODEL[provider]}
                                </span>
                                . Override only if you know your provider has
                                this model available.
                            </p>
                        </label>

                        <label className="block">
                            <span className="microtype block mb-1.5">
                                API key
                            </span>
                            <input
                                type="password"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder={
                                    cred
                                        ? "Enter a new key to replace the existing one"
                                        : "sk-ant-... or AIza..."
                                }
                                autoComplete="off"
                                className="
                                    w-full px-3 py-2 rounded-md
                                    bg-[var(--bg-page)]
                                    border border-[var(--border-default)]
                                    text-[13px] text-[var(--text-primary)] font-mono
                                    placeholder:text-[var(--text-disabled)]
                                    focus:outline-none focus:border-[var(--accent)]
                                    focus:ring-2 focus:ring-[var(--accent-edge)]
                                    transition-colors duration-150
                                "
                            />
                            <p className="text-[11px] text-[var(--text-subtle)] mt-1">
                                Stored encrypted at rest. The plaintext is never
                                returned to the browser after save.
                            </p>
                        </label>

                        {testStatus && (
                            <div
                                className={`
                                    rounded-md px-3 py-2 text-[12.5px]
                                    border
                                    ${
                                        testStatus.kind === "ok"
                                            ? "bg-[var(--success-soft)] border-[var(--success)]/30 text-[var(--success)]"
                                            : "bg-[var(--danger-soft)] border-[var(--danger)]/30 text-[var(--danger)]"
                                    }
                                    flex items-start gap-2
                                `}
                            >
                                {testStatus.kind === "ok" ? (
                                    <>
                                        <FiCheck className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                                        <span>
                                            Key works. Round-trip{" "}
                                            <span className="font-mono">
                                                {testStatus.latency_ms} ms
                                            </span>
                                            .
                                        </span>
                                    </>
                                ) : (
                                    <>
                                        <FiX className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                                        <span>{testStatus.detail}</span>
                                    </>
                                )}
                            </div>
                        )}

                        <div className="flex gap-2 justify-end">
                            <button
                                type="button"
                                onClick={handleTest}
                                disabled={busy !== null || !apiKey}
                                className="
                                    inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md
                                    text-[12.5px] font-medium
                                    bg-[var(--bg-elevated)] border border-[var(--border-default)]
                                    text-[var(--text-primary)]
                                    hover:bg-[var(--bg-hover)] hover:border-[var(--border-emphasis)]
                                    cursor-pointer
                                    disabled:opacity-50 disabled:cursor-not-allowed
                                    transition-colors duration-150
                                "
                            >
                                <FiZap className="w-3 h-3" />
                                {busy === "test" ? "Testing…" : "Test"}
                            </button>
                            <button
                                type="button"
                                onClick={handleSave}
                                disabled={busy !== null || !apiKey}
                                className="
                                    inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md
                                    text-[12.5px] font-medium
                                    bg-[var(--accent)] text-white
                                    hover:bg-[var(--accent-strong)]
                                    cursor-pointer
                                    disabled:bg-[var(--bg-hover)]
                                    disabled:text-[var(--text-disabled)]
                                    disabled:cursor-not-allowed
                                    transition-colors duration-150
                                "
                            >
                                {busy === "save"
                                    ? "Saving…"
                                    : cred
                                      ? "Replace key"
                                      : "Save"}
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
