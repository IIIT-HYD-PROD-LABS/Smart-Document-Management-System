"use client";

import type { AxiosRequestConfig } from "axios";
import api from "@/lib/api";
import { useCurrentClient } from "@/stores/currentClientStore";
import type {
    AICredential,
    AICredentialCreate,
    AICredentialTestResult,
    InvoiceActionsResponse,
    InvoiceSummaryResponse,
    InvoiceTimingResponse,
    NoticeActionsResponse,
    NoticeSummaryResponse,
} from "@/types/ai";

/**
 * AI client — Phase 16. All routes mount under /api/compliance/ai
 * and are tenant-scoped via X-Client-Id (same convention as the rest
 * of the compliance API surface).
 */

function tenantHeaders(): Record<string, string> {
    const { activeClientId, crossClientMode } = useCurrentClient.getState();
    if (crossClientMode) return { "X-Client-Id": "*" };
    if (activeClientId !== null) return { "X-Client-Id": String(activeClientId) };
    return {};
}

function withTenant(extra: AxiosRequestConfig = {}): AxiosRequestConfig {
    return {
        ...extra,
        headers: { ...(extra.headers ?? {}), ...tenantHeaders() },
    };
}

export const aiApi = {
    // ──── Credentials ────
    getCredential: () =>
        api.get<AICredential | null>(
            "/compliance/ai/credentials",
            withTenant(),
        ),

    setCredential: (payload: AICredentialCreate) =>
        api.post<AICredential>(
            "/compliance/ai/credentials",
            payload,
            withTenant(),
        ),

    deleteCredential: () =>
        api.delete("/compliance/ai/credentials", withTenant()),

    testCredential: (payload: AICredentialCreate) =>
        api.post<AICredentialTestResult>(
            "/compliance/ai/credentials/test",
            payload,
            withTenant(),
        ),

    // ──── Notice AI ────
    noticeSummary: (noticeId: number) =>
        api.post<NoticeSummaryResponse>(
            `/compliance/ai/notice-summary/${noticeId}`,
            {},
            withTenant(),
        ),

    noticeActions: (noticeId: number) =>
        api.post<NoticeActionsResponse>(
            `/compliance/ai/notice-actions/${noticeId}`,
            {},
            withTenant(),
        ),

    // ──── Invoice AI ────
    invoiceSummary: (billId: number) =>
        api.post<InvoiceSummaryResponse>(
            `/compliance/ai/invoice-summary/${billId}`,
            {},
            withTenant(),
        ),

    invoiceActions: (billId: number) =>
        api.post<InvoiceActionsResponse>(
            `/compliance/ai/invoice-actions/${billId}`,
            {},
            withTenant(),
        ),

    invoiceTiming: (billId: number) =>
        api.post<InvoiceTimingResponse>(
            `/compliance/ai/invoice-timing/${billId}`,
            {},
            withTenant(),
        ),
};
