"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import toast from "react-hot-toast";
import {
    FiCpu,
    FiMessageCircle,
    FiSend,
    FiSettings,
    FiX,
} from "react-icons/fi";

import { extractErrorMessage } from "@/lib/api";
import { aiApi } from "@/lib/api/ai";
import {
    PROVIDER_LABEL,
    type AIProvider,
    type ChatTurn,
} from "@/types/ai";

// Mirrors the backend cap (compliance/schemas/ai.py ChatRequest).
const MAX_HISTORY = 20;

const PROMPT_HINTS = [
    "Summarise my latest GST notice",
    "What's the deadline for GSTR-3B this month?",
    "Explain the drafter → reviewer → legal → CFO chain",
    "Which invoices look anomalous?",
];

/**
 * Floating "Ask AI" entry — visible on every dashboard route.
 *
 * - FAB at bottom-right of the viewport (z-40, above sidebar's z-30).
 * - Click toggles a right-side drawer (full-width on mobile, 400px on
 *   desktop) with a chat thread + input.
 * - Conversation is held in component state only; refreshing clears it.
 *   Backend cap on history size matches `MAX_HISTORY`.
 * - The scope-locked AI returns a friendly canned message + an
 *   `out_of_scope` flag for refused topics; the drawer styles those
 *   bubbles with a warning tint.
 */
export default function AIChatFloating() {
    const [open, setOpen] = useState(false);
    const [turns, setTurns] = useState<ChatTurn[]>([]);
    const [input, setInput] = useState("");
    const [busy, setBusy] = useState(false);
    const scrollRef = useRef<HTMLDivElement | null>(null);
    const inputRef = useRef<HTMLTextAreaElement | null>(null);

    const { data: cred } = useQuery({
        queryKey: ["ai-credential"],
        queryFn: () => aiApi.getCredential().then((r) => r.data),
        staleTime: 30_000,
    });

    // Keep the message list scrolled to the bottom whenever turns change.
    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }, [turns, busy]);

    // Auto-focus the input when the drawer opens.
    useEffect(() => {
        if (open && cred) inputRef.current?.focus();
    }, [open, cred]);

    const send = async (text: string) => {
        const trimmed = text.trim();
        if (!trimmed || busy) return;
        const userTurn: ChatTurn = { role: "user", content: trimmed };
        const next: ChatTurn[] = [...turns, userTurn].slice(-MAX_HISTORY);
        setTurns(next);
        setInput("");
        setBusy(true);
        try {
            // Strip the local-only `out_of_scope` flag before sending.
            const payload = next.map((t) => ({
                role: t.role,
                content: t.content,
            }));
            const r = await aiApi.chat(payload);
            setTurns([
                ...next,
                {
                    role: "assistant",
                    content: r.data.reply,
                    out_of_scope: r.data.out_of_scope,
                },
            ]);
        } catch (e) {
            toast.error(extractErrorMessage(e, "AI chat failed."));
        } finally {
            setBusy(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send(input);
        }
    };

    return (
        <>
            {/* FAB */}
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className={`
                    fixed bottom-6 right-6 z-40
                    w-12 h-12 rounded-full
                    flex items-center justify-center cursor-pointer
                    shadow-[var(--shadow-lg)]
                    transition-all duration-200
                    ${
                        open
                            ? "bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-emphasis)] rotate-90"
                            : "bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] hover:scale-105"
                    }
                `}
                aria-label={open ? "Close AI chat" : "Open AI chat"}
                aria-expanded={open}
            >
                {open ? (
                    <FiX className="w-5 h-5" />
                ) : (
                    <FiMessageCircle className="w-5 h-5" />
                )}
            </button>

            {/* Mobile backdrop */}
            {open && (
                <div
                    className="fixed inset-0 z-30 bg-[var(--text-primary)]/30 backdrop-blur-sm md:hidden"
                    onClick={() => setOpen(false)}
                    aria-hidden
                />
            )}

            {/* Drawer */}
            <aside
                className={`
                    fixed top-0 right-0 z-40 h-full
                    w-full md:w-[400px]
                    bg-[var(--bg-surface)]
                    border-l border-[var(--border-default)]
                    flex flex-col
                    shadow-[var(--shadow-lg)]
                    transition-transform duration-200 ease-in-out
                    ${open ? "translate-x-0" : "translate-x-full"}
                `}
                aria-hidden={!open}
                aria-label="AI assistant chat"
            >
                <header className="px-4 h-14 flex items-center gap-2 border-b border-[var(--border-default)] shrink-0">
                    <div className="w-8 h-8 rounded-md bg-[var(--accent-soft)] flex items-center justify-center">
                        <FiCpu className="w-4 h-4 text-[var(--accent)]" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-[13.5px] font-semibold text-[var(--text-primary)] tracking-tight">
                            AI assistant
                        </p>
                        {cred ? (
                            <p className="text-[11px] text-[var(--text-subtle)] font-mono truncate">
                                {PROVIDER_LABEL[cred.provider as AIProvider]} ·{" "}
                                {cred.model}
                            </p>
                        ) : (
                            <p className="text-[11px] text-[var(--text-subtle)] truncate">
                                Not configured
                            </p>
                        )}
                    </div>
                    {turns.length > 0 && (
                        <button
                            type="button"
                            onClick={() => setTurns([])}
                            className="text-[11.5px] text-[var(--text-muted)] hover:text-[var(--text-primary)] px-2 py-1 rounded hover:bg-[var(--bg-hover)] cursor-pointer"
                            aria-label="Clear chat"
                        >
                            Clear
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={() => setOpen(false)}
                        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1.5 rounded hover:bg-[var(--bg-hover)] cursor-pointer"
                        aria-label="Close"
                    >
                        <FiX className="w-4 h-4" />
                    </button>
                </header>

                {!cred ? (
                    <ConnectFirstState />
                ) : (
                    <>
                        <div
                            ref={scrollRef}
                            className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
                        >
                            {turns.length === 0 ? (
                                <EmptyState onPick={(s) => void send(s)} />
                            ) : (
                                turns.map((t, i) => (
                                    <ChatBubble key={i} turn={t} />
                                ))
                            )}
                            {busy && <TypingBubble />}
                        </div>

                        <div className="border-t border-[var(--border-default)] p-3 shrink-0">
                            <div className="flex items-end gap-2">
                                <textarea
                                    ref={inputRef}
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    placeholder="Ask about a notice, invoice, or deadline…"
                                    rows={1}
                                    maxLength={8000}
                                    className="
                                        flex-1 px-3 py-2 rounded-md resize-none
                                        bg-[var(--bg-page)]
                                        border border-[var(--border-default)]
                                        text-[13px] text-[var(--text-primary)]
                                        placeholder:text-[var(--text-disabled)]
                                        focus:outline-none focus:border-[var(--accent)]
                                        focus:ring-2 focus:ring-[var(--accent-edge)]
                                        max-h-32
                                    "
                                    style={{ minHeight: "38px" }}
                                />
                                <button
                                    type="button"
                                    onClick={() => send(input)}
                                    disabled={!input.trim() || busy}
                                    className="
                                        w-9 h-9 rounded-md shrink-0
                                        bg-[var(--accent)] text-white
                                        hover:bg-[var(--accent-strong)]
                                        flex items-center justify-center cursor-pointer
                                        disabled:bg-[var(--bg-hover)]
                                        disabled:text-[var(--text-disabled)]
                                        disabled:cursor-not-allowed
                                        transition-colors duration-150
                                    "
                                    aria-label="Send"
                                >
                                    <FiSend className="w-3.5 h-3.5" />
                                </button>
                            </div>
                            <p className="text-[10.5px] text-[var(--text-subtle)] mt-1.5 leading-snug">
                                Scope-locked to compliance, notices, vendor
                                invoices, and TaxSync workflow.
                            </p>
                        </div>
                    </>
                )}
            </aside>
        </>
    );
}

function ConnectFirstState() {
    return (
        <div className="flex-1 flex items-center justify-center px-6 py-12">
            <div className="text-center max-w-sm">
                <div className="w-12 h-12 rounded-full bg-[var(--accent-soft)] mx-auto flex items-center justify-center mb-3">
                    <FiCpu className="w-5 h-5 text-[var(--accent)]" />
                </div>
                <h3 className="text-[14px] font-semibold text-[var(--text-primary)] mb-1.5">
                    Connect your AI key
                </h3>
                <p className="text-[12.5px] text-[var(--text-muted)] leading-relaxed mb-4">
                    Bring your own Anthropic Claude or Google Gemini key. Your
                    provider, your costs, your control. TaxSync only uses it
                    for compliance and finance work.
                </p>
                <Link
                    href="/dashboard/settings/ai"
                    className="
                        inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md
                        text-[12.5px] font-medium
                        bg-[var(--accent)] text-white
                        hover:bg-[var(--accent-strong)] cursor-pointer
                        transition-colors
                    "
                >
                    <FiSettings className="w-3 h-3" />
                    Open AI settings
                </Link>
            </div>
        </div>
    );
}

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
    return (
        <div className="text-center py-8 px-2">
            <p className="text-[13px] text-[var(--text-muted)] mb-4 leading-relaxed">
                Ask anything about your compliance notices, vendor invoices,
                deadlines, or TaxSync workflow.
            </p>
            <div className="flex flex-col gap-1.5">
                {PROMPT_HINTS.map((h) => (
                    <button
                        key={h}
                        type="button"
                        onClick={() => onPick(h)}
                        className="
                            text-left text-[12.5px] text-[var(--text-secondary)]
                            px-3 py-2 rounded-md
                            bg-[var(--bg-elevated)]
                            border border-[var(--border-default)]
                            hover:border-[var(--accent-edge)]
                            hover:bg-[var(--bg-hover)]
                            transition-colors duration-150 cursor-pointer
                        "
                    >
                        {h}
                    </button>
                ))}
            </div>
        </div>
    );
}

function ChatBubble({ turn }: { turn: ChatTurn }) {
    const isUser = turn.role === "user";
    if (turn.out_of_scope) {
        return (
            <div className="flex justify-start">
                <div
                    className="
                        max-w-[88%] px-3 py-2 rounded-lg
                        bg-[var(--warning-soft)]
                        border border-[var(--warning)]/30
                        text-[12.5px] text-[var(--warning)]
                        leading-relaxed
                    "
                >
                    <span className="font-mono text-[10.5px] uppercase tracking-wider opacity-70 mr-1.5">
                        ⚠ Out of scope
                    </span>
                    {turn.content}
                </div>
            </div>
        );
    }
    return (
        <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
            <div
                className={`
                    max-w-[88%] px-3 py-2 rounded-lg
                    text-[13px] leading-relaxed whitespace-pre-wrap
                    ${
                        isUser
                            ? "bg-[var(--accent)] text-white rounded-br-sm"
                            : "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-primary)] rounded-bl-sm"
                    }
                `}
            >
                {turn.content}
            </div>
        </div>
    );
}

function TypingBubble() {
    return (
        <div className="flex justify-start">
            <div className="px-3 py-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center gap-1.5">
                <Dot delay="0ms" />
                <Dot delay="150ms" />
                <Dot delay="300ms" />
            </div>
        </div>
    );
}

function Dot({ delay }: { delay: string }) {
    return (
        <span
            className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)] inline-block"
            style={{
                animation: "ai-typing 1.2s ease-in-out infinite",
                animationDelay: delay,
            }}
        />
    );
}
