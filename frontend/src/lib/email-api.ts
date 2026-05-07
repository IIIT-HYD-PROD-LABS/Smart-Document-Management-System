/**
 * Phase 15 Email API client.
 *
 * Reuses the pre-configured axios instance from @/lib/api which attaches
 * `Authorization: Bearer <Cookies.get("token")>` via request interceptor
 * (see src/lib/api.ts:38-44). Reconciliation #3: JWT is read from the
 * js-cookie package via the shared interceptor — do not duplicate the
 * cookie read here, and do not introduce browser-storage shortcuts.
 *
 * Email routes are gated by `require_compliance_permission('email_integration:use')`
 * on the backend, which means Phase 9's TenantContextMiddleware requires the
 * `X-Client-Id` header on every call. We replicate the `tenantHeaders()`
 * pattern from `src/lib/api/compliance.ts:40` so the active client (or
 * cross-client mode) is sent on every email request.
 */
import type { AxiosRequestConfig } from "axios";
import api from "@/lib/api";
import { useCurrentClient } from "@/stores/currentClientStore";

function tenantHeaders(): Record<string, string> {
    const state = useCurrentClient.getState();
    if (state.crossClientMode) return { "X-Client-Id": "*" };
    if (state.activeClientId !== null) {
        return { "X-Client-Id": String(state.activeClientId) };
    }
    return {};
}

function withTenant(config?: AxiosRequestConfig): AxiosRequestConfig {
    return {
        ...(config ?? {}),
        headers: {
            ...(config?.headers ?? {}),
            ...tenantHeaders(),
        },
    };
}

export interface GmailCredentialResponse {
    id: number;
    google_account_email: string | null;
    status: "active" | "revoked" | "disabled";
    cadence_minutes: number;
    last_scan_at: string | null;
    created_at: string;
}

export type FilterRouteTo =
    | "compliance_notice"
    | "bill"
    | "dms_only"
    | "ignore";

export interface GmailFilterRule {
    id: number;
    credential_id: number;
    priority: number;
    sender_pattern: string | null;
    subject_pattern: string | null;
    label_include: string | null;
    label_exclude: string | null;
    route_to: FilterRouteTo;
    enabled: boolean;
    created_at: string;
}

export type FetchStatus =
    | "SUCCESS_EMPTY"
    | "SUCCESS_WITH_RESULTS"
    | "FETCH_FAILED";

export interface GmailFetchLog {
    id: number;
    credential_id: number;
    status: FetchStatus;
    messages_processed: number;
    error_message: string | null;
    started_at: string;
    completed_at: string | null;
}

export type BillPaymentStatus = "pending" | "paid" | "overdue";

export interface Bill {
    id: number;
    biller_name: string;
    biller_category: string;
    amount_due: string;
    currency: string;
    due_date: string | null;
    account_number_last4: string | null;
    payment_status: BillPaymentStatus;
    is_recurring: boolean;
    recurrence_period: string | null;
    parent_bill_id: number | null;
    source_document_id: number | null;
    source_email_id: number | null;
    payment_date: string | null;
    payment_reference: string | null;
    payment_method: string | null;
    created_at: string;
}

export type BillStatusBucket = "upcoming" | "due_soon" | "overdue" | "paid";

export interface BillFilters {
    status?: BillStatusBucket;
    biller_category?: string;
    due_before?: string;
    due_after?: string;
    is_recurring?: boolean;
}

export interface MarkPaidPayload {
    payment_date: string;
    payment_reference: string;
    payment_method: string;
}

export interface BulkMarkPaidPayload extends MarkPaidPayload {
    ids: number[];
}

export interface BulkMarkPaidResponse {
    results: { id: number; status: string; error?: string }[];
    summary: { ok: number; failed: number };
}

export interface SourceEmailView {
    sender: string;
    subject: string;
    date: string;
    body: string;
    attachments: Array<{
        filename: string;
        mime_type: string;
        size_bytes: number;
        attachment_id: string;
    }>;
}

export const emailApi = {
    connectGmail: () =>
        api.post<{ authorize_url: string }>(
            "/email/gmail/oauth/authorize",
            null,
            withTenant(),
        ),

    listCredentials: () =>
        api.get<GmailCredentialResponse[]>("/email/credentials", withTenant()),

    updateCredential: (id: number, body: { cadence_minutes?: number }) =>
        api.patch<GmailCredentialResponse>(
            `/email/credentials/${id}`,
            body,
            withTenant(),
        ),

    deleteCredential: (id: number) =>
        api.delete(`/email/credentials/${id}`, withTenant()),

    listFilterRules: (credId: number) =>
        api.get<GmailFilterRule[]>(
            `/email/credentials/${credId}/filter-rules`,
            withTenant(),
        ),

    createFilterRule: (credId: number, body: Partial<GmailFilterRule>) =>
        api.post<GmailFilterRule>(
            `/email/credentials/${credId}/filter-rules`,
            body,
            withTenant(),
        ),

    updateFilterRule: (id: number, body: Partial<GmailFilterRule>) =>
        api.patch<GmailFilterRule>(
            `/email/filter-rules/${id}`,
            body,
            withTenant(),
        ),

    deleteFilterRule: (id: number) =>
        api.delete(`/email/filter-rules/${id}`, withTenant()),

    listActivity: (credId: number, limit = 50) =>
        api.get<GmailFetchLog[]>(
            `/email/credentials/${credId}/activity`,
            withTenant({ params: { limit } }),
        ),

    listBills: (filters: BillFilters = {}) =>
        api.get<Bill[]>("/email/bills", withTenant({ params: filters })),

    getBill: (id: number) =>
        api.get<Bill>(`/email/bills/${id}`, withTenant()),

    markBillPaid: (id: number, body: MarkPaidPayload) =>
        api.post<Bill>(`/email/bills/${id}/mark-paid`, body, withTenant()),

    bulkMarkBillsPaid: (body: BulkMarkPaidPayload) =>
        api.post<BulkMarkPaidResponse>(
            "/email/bills/bulk-mark-paid",
            body,
            withTenant(),
        ),

    viewSourceEmail: (messageLogId: number) =>
        api.get<SourceEmailView>(
            `/email/messages/${messageLogId}/view`,
            withTenant(),
        ),
};

export default emailApi;
