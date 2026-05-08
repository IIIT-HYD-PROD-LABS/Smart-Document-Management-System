// Phase 16 — BYOK AI types. Mirror backend/app/compliance/schemas/ai.py.

export type AIProvider = "anthropic" | "google";

export interface AICredential {
    provider: AIProvider;
    model: string;
    has_key: boolean;
    created_at: string;
    updated_at: string;
    last_used_at: string | null;
}

export interface AICredentialCreate {
    provider: AIProvider;
    model: string;
    api_key: string;
}

export interface AICredentialTestResult {
    ok: boolean;
    detail?: string | null;
    latency_ms?: number | null;
}

export interface AIActionItem {
    label: string;
    rationale: string;
    urgency: "high" | "medium" | "low";
}

export interface NoticeSummaryResponse {
    summary: string;
    key_points: string[];
    deadline_iso: string | null;
}

export interface NoticeActionsResponse {
    actions: AIActionItem[];
}

export interface InvoiceSummaryResponse {
    summary: string;
    anomalies: string[];
}

export interface InvoiceActionsResponse {
    actions: AIActionItem[];
}

export interface InvoiceTimingResponse {
    recommendation: string;
    rationale: string;
    suggested_payment_date: string | null;
}

// ── Chat ──

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
    role: ChatRole;
    content: string;
}

/** Local-only — adds the out_of_scope flag the assistant message carries
 *  back from the backend so the drawer can style refused turns distinctly. */
export interface ChatTurn extends ChatMessage {
    out_of_scope?: boolean;
}

export interface ChatRequest {
    messages: ChatMessage[];
}

export interface ChatResponse {
    reply: string;
    out_of_scope: boolean;
}

// Sensible defaults per provider — surfaced in the Settings page so the
// user doesn't have to memorise model identifiers.
export const DEFAULT_MODEL: Record<AIProvider, string> = {
    anthropic: "claude-sonnet-4-6",
    google: "gemini-1.5-flash",
};

export const PROVIDER_LABEL: Record<AIProvider, string> = {
    anthropic: "Anthropic Claude",
    google: "Google Gemini",
};
