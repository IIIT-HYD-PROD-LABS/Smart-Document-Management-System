"use client";

import type { AxiosRequestConfig } from "axios";
import api from "@/lib/api";
import { useCurrentClient } from "@/stores/currentClientStore";
import type {
    Membership,
    ClientDetail,
    Client,
    ClientBrandingUpdate,
    DashboardAggregates,
    ComplianceNotice,
    NoticeActivity,
    BulkUpdateResult,
    NoticeType,
    AuditLogEntry,
    Authority,
    ReviewQueueListResponse,
    ReviewQueueItem,
    ReviewAssignRequest,
    CalendarEntry,
    AlertLogEntry,
    AlertRule,
    ComplianceScore,
    AdjustDeadlineResult,
} from "@/types/compliance";

/**
 * Read X-Client-Id header from Zustand store on every call (not cached)
 * so that switching clients takes effect immediately for the next request.
 *
 * Convention (RESEARCH Pattern 7 + Plan 04 TenantContextMiddleware):
 * - "X-Client-Id: <int>"  — single-tenant operation
 * - "X-Client-Id: *"      — cross-client mode (only allowed for compliance_head/ca_consultant/cfo)
 * - header omitted        — request is non-tenanted (e.g., /clients/me)
 *
 * Note: we use useCurrentClient.getState() (not the hook) here so this can be
 * called from non-React contexts. The Zustand store update is synchronous, so
 * subsequent reads observe the latest activeClientId.
 */
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

// ──── Request payload types ────

export interface OnboardClientPayload {
    details: {
        name: string;
        client_type: string;
        industry?: string;
        primary_contact_email?: string;
    };
    registrations: { type: string; value: string; state?: string }[];
    team: {
        // Same exactly-one-of rule as the membership add endpoint: the
        // backend (services/invitation_service.py) accepts either email
        // (pre-creates a pending User + sends invite) or user_id (legacy
        // path used by the wizard's auto-add of the creating admin).
        email?: string;
        user_id?: number;
        full_name?: string;
        compliance_role: string;
        access_start?: string;
        access_end?: string;
    }[];
}

export interface AddMemberPayload {
    // Exactly one of email or user_id. Email is preferred: when the
    // invitee has no TaxSync account yet the backend pre-creates a
    // pending User and sends an accept-invite link.
    email?: string;
    user_id?: number;
    full_name?: string;
    compliance_role: string;
    access_start?: string;
    access_end?: string;
}

export interface AddMemberResponse {
    id: number;
    user_id: number;
    client_id: number;
    compliance_role: string;
    invited: boolean;
    // Set only in DEBUG mode when SMTP is unconfigured; lets dev paste
    // the accept-invite URL into the browser manually.
    accept_invite_token?: string | null;
}

export interface ListNoticesParams {
    authority?: string;
    status?: string;
    notice_type_id?: number;
    response_deadline_before?: string;
    response_deadline_after?: string;
    gstin_or_pan?: string;
    assigned_user_id?: number;
    page?: number;
    page_size?: number;
}

export interface CreateNoticePayload extends Partial<ComplianceNotice> {
    client_id: number;
    notice_number: string;
    authority: Authority;
    received_date: string;
    legal_sections?: string[];
    tags?: string[];
}

export interface BulkUpdatePayload {
    notice_ids: number[];
    new_status: string;
    reason?: string;
}

export interface ListAuditParams {
    date_from?: string;
    date_to?: string;
    actor_user_id?: number;
    action?: string;
    resource_type?: string;
    page?: number;
    page_size?: number;
}

export interface CalendarParams {
    year: number;
    month?: number;
    authority?: string;
    category?: string;
}

export interface NoticesPage {
    items: ComplianceNotice[];
    total: number;
    page: number;
    page_size: number;
}

// ──── Phase 17 — AI extraction types ────

export interface ExtractedFieldDto {
    value: string | number | string[] | null;
    confidence: number;
    source_span?: string | null;
    original_confidence?: number | null;
    validation_failure?: string | null;
}

export interface ExtractionEnvelopeDto {
    fields: Record<string, ExtractedFieldDto>;
    average_confidence: number;
    model: string;
    tokens_in: number;
    tokens_out: number;
    latency_ms: number;
}

export interface ExtractionRouteDecisionDto {
    action: "apply" | "review_queue" | "failed";
    reason: string | null;
    average_confidence: number;
    critical_field_confidence: Record<string, number>;
}

export interface ExtractPreviewResponse {
    envelope: ExtractionEnvelopeDto;
    decision: ExtractionRouteDecisionDto;
}

export interface ExtractionResponseDto {
    notice_id: number;
    extraction_status:
        | "pending"
        | "completed"
        | "failed"
        | "accepted"
        | "superseded"
        | null;
    extraction_confidence: number | null;
    extracted_by_provider: string | null;
    extracted_at: string | null;
    envelope: ExtractionEnvelopeDto | null;
}

export interface AcceptExtractionItem {
    field: string;
    value: string | number | null;
    accept_as_is: boolean;
}

// ──── complianceApi ────

export const complianceApi = {
    // ──── Clients ────
    listMyMemberships: () =>
        api.get<Membership[]>("/compliance/clients/me", withTenant()),

    onboardClient: (payload: OnboardClientPayload) =>
        api.post<ClientDetail>("/compliance/clients", payload, withTenant()),

    getClient: (clientId: number) =>
        api.get<ClientDetail>(`/compliance/clients/${clientId}`, withTenant()),

    getClientDashboard: (clientId: number) =>
        api.get<DashboardAggregates>(
            `/compliance/clients/${clientId}/dashboard`,
            withTenant()
        ),

    // ──── Branding (migration 0031) ────
    updateClientBranding: (
        clientId: number,
        payload: ClientBrandingUpdate,
    ) =>
        api.patch<Client>(
            `/compliance/clients/${clientId}/branding`,
            payload,
            withTenant(),
        ),

    uploadClientLogo: (clientId: number, file: File) => {
        const form = new FormData();
        form.append("file", file);
        return api.post<Client>(
            `/compliance/clients/${clientId}/logo`,
            form,
            {
                ...withTenant(),
                headers: {
                    ...withTenant().headers,
                    "Content-Type": "multipart/form-data",
                },
            },
        );
    },

    deleteClientLogo: (clientId: number) =>
        api.delete<Client>(
            `/compliance/clients/${clientId}/logo`,
            withTenant(),
        ),

    // ──── Memberships ────
    addMember: (clientId: number, payload: AddMemberPayload) =>
        api.post<Membership>(
            `/compliance/clients/${clientId}/memberships`,
            payload,
            withTenant()
        ),

    removeMember: (clientId: number, membershipId: number) =>
        api.delete(
            `/compliance/clients/${clientId}/memberships/${membershipId}`,
            withTenant()
        ),

    // ──── Notices ────
    listNotices: (params: ListNoticesParams) =>
        api.get<NoticesPage>("/compliance/notices", {
            ...withTenant(),
            params,
        }),

    createNotice: (payload: CreateNoticePayload) =>
        api.post<ComplianceNotice>("/compliance/notices", payload, withTenant()),

    getNotice: (id: number) =>
        api.get<ComplianceNotice>(`/compliance/notices/${id}`, withTenant()),

    updateNotice: (id: number, payload: Partial<ComplianceNotice>) =>
        api.patch<ComplianceNotice>(
            `/compliance/notices/${id}`,
            payload,
            withTenant()
        ),

    transitionStatus: (
        id: number,
        payload: { new_status: string; reason?: string }
    ) =>
        api.patch<ComplianceNotice>(
            `/compliance/notices/${id}/status`,
            payload,
            withTenant()
        ),

    bulkUpdate: (payload: BulkUpdatePayload) =>
        api.post<BulkUpdateResult>(
            "/compliance/notices/bulk",
            payload,
            withTenant()
        ),

    getChain: (id: number, max_depth: number = 10) =>
        api.get(`/compliance/notices/${id}/chain`, {
            ...withTenant(),
            params: { max_depth },
        }),

    uploadNoticeFile: (id: number, file: File) => {
        const fd = new FormData();
        fd.append("file", file);
        return api.post<ComplianceNotice>(
            `/compliance/notices/${id}/upload`,
            fd,
            withTenant({
                headers: { "Content-Type": "multipart/form-data" },
                timeout: 120000,
            })
        );
    },

    /** Phase B — import a portal-exported PDF into the notice pipeline. */
    importPortalExport: (
        file: File,
        opts: {
            portal:
                | "gst_portal"
                | "it_efiling"
                | "mca"
                | "sebi"
                | "rbi"
                | "other";
            create_notice?: boolean;
            authority?: string;
        },
    ) => {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("portal", opts.portal);
        fd.append("create_notice", String(opts.create_notice ?? true));
        if (opts.authority) fd.append("authority", opts.authority);
        return api.post<{
            document_id: number;
            notice_id: number | null;
            portal: string;
            authority: string | null;
            notice_number: string | null;
            source: string;
            detail: string;
        }>("/compliance/portal/import", fd, withTenant({
            headers: { "Content-Type": "multipart/form-data" },
            timeout: 120000,
        }));
    },

    listPortalKinds: () =>
        api.get<
            { id: string; label: string; default_authority: string }[]
        >("/compliance/portal/kinds", withTenant()),

    // ──── Phase 17 — AI extraction (BYOK) ────
    extractPreview: (file: File) => {
        const fd = new FormData();
        fd.append("file", file);
        return api.post<ExtractPreviewResponse>(
            `/compliance/notices/extract-preview`,
            fd,
            withTenant({
                headers: { "Content-Type": "multipart/form-data" },
                // OCR + a full LLM round-trip on a multi-page PDF routinely
                // exceeds the shared 30s axios timeout; without this override a
                // still-succeeding extraction aborts client-side and silently
                // drops the user to manual entry with a misleading "timeout".
                timeout: 120000,
            }),
        );
    },

    getExtraction: (id: number) =>
        api.get<ExtractionResponseDto>(
            `/compliance/notices/${id}/extraction`,
            withTenant(),
        ),

    acceptExtraction: (
        id: number,
        items: AcceptExtractionItem[],
        envelope?: ExtractionEnvelopeDto,
    ) =>
        api.post<ComplianceNotice>(
            `/compliance/notices/${id}/accept-extraction`,
            { items, envelope },
            withTenant(),
        ),

    // ──── Phase 18 — AI response drafting (BYOK) ────
    aiDraftResponse: (noticeId: number, userGuidance?: string) =>
        api.post<{
            draft_body_markdown: string;
            model: string;
            tokens_in: number;
            tokens_out: number;
            latency_ms: number;
            extracted_fields_used: string[];
        }>(
            `/compliance/ai/notice-response-draft/${noticeId}`,
            { user_guidance: userGuidance ?? "" },
            withTenant(),
        ),

    listActivity: (id: number) =>
        api.get<NoticeActivity[]>(
            `/compliance/notices/${id}/activity`,
            withTenant()
        ),

    addNote: (id: number, note: string) =>
        api.post<NoticeActivity>(
            `/compliance/notices/${id}/activity/note`,
            { note },
            withTenant()
        ),

    // ──── Lookups ────
    listNoticeTypes: (authority?: string) =>
        api.get<NoticeType[]>("/compliance/notice-types", {
            ...withTenant(),
            params: authority ? { authority } : undefined,
        }),

    listCalendarEntries: (params: CalendarParams) =>
        api.get("/compliance/regulatory-calendar", {
            ...withTenant(),
            params,
        }),

    // ──── Audit ────
    listAudit: (params: ListAuditParams) =>
        api.get<AuditLogEntry[]>("/compliance/audit", {
            ...withTenant(),
            params,
        }),

    // ──── Reports ────
    healthSummary: (payload: { client_id: number; month: string }) =>
        api.post(
            "/compliance/reports/health-summary",
            payload,
            withTenant()
        ),

    // ──── Phase 10 — Review Queue ────
    listPendingReview: (page: number = 1, page_size: number = 50) =>
        api.get<ReviewQueueListResponse>("/compliance/review/pending", {
            ...withTenant(),
            params: { page, page_size },
        }),

    getReviewItem: (reviewId: number) =>
        api.get<ReviewQueueItem>(
            `/compliance/review/${reviewId}`,
            withTenant()
        ),

    manualEnqueueReview: (noticeId: number, reasonNote?: string) =>
        api.post<ReviewQueueItem>(
            `/compliance/review/manual-enqueue/${noticeId}`,
            reasonNote ? { reason: reasonNote } : {},
            withTenant(),
        ),

    assignReviewLabel: (reviewId: number, payload: ReviewAssignRequest) =>
        api.patch<{
            review_id: number;
            notice_id: number;
            assigned_authority: string | null;
            assigned_notice_type_id: number | null;
            reviewed_at: string;
        }>(
            `/compliance/review/${reviewId}/assign`,
            payload,
            withTenant()
        ),

    // ──── Phase 11 — Calendar ────
    listCalendarEntriesV2: (params: {
        year: number;
        month?: number;
        authority?: string;
        category?: string;
    }) =>
        api.get<CalendarEntry[]>("/compliance/calendar/entries", {
            ...withTenant(),
            params,
        }),

    adjustDeadline: (payload: { deadline: string; state_code?: string }) =>
        api.post<AdjustDeadlineResult>(
            "/compliance/calendar/adjust-deadline",
            payload,
            withTenant()
        ),

    getComplianceScore: (windowDays: number = 90) =>
        api.get<ComplianceScore>("/compliance/calendar/compliance-score", {
            ...withTenant(),
            params: { window_days: windowDays },
        }),

    // ──── Phase 11 — Alerts ────
    listPendingAlerts: (page: number = 1, page_size: number = 50) =>
        api.get<{
            items: AlertLogEntry[];
            total: number;
            page: number;
            page_size: number;
        }>("/compliance/alerts/pending", {
            ...withTenant(),
            params: { page, page_size },
        }),

    listAlertRules: () =>
        api.get<AlertRule[]>("/compliance/alerts/rules", withTenant()),

    upsertAlertRule: (payload: {
        notice_type_id?: number | null;
        rules: Record<string, unknown>;
        is_active: boolean;
    }) =>
        api.put<AlertRule>("/compliance/alerts/rules", payload, withTenant()),

    // ──── Phase 12 — Response workflow ────
    getResponse: (noticeId: number) =>
        api.get<import("@/types/compliance").NoticeResponseDetail>(
            `/compliance/notices/${noticeId}/responses`,
            withTenant(),
        ),

    createOrUpdateResponse: (
        noticeId: number,
        payload: import("@/types/compliance").ResponseDraftPayload,
    ) =>
        api.post<import("@/types/compliance").NoticeResponseDetail>(
            `/compliance/notices/${noticeId}/responses`,
            payload,
            withTenant(),
        ),

    patchResponse: (
        noticeId: number,
        payload: import("@/types/compliance").ResponseDraftPayload,
    ) =>
        api.patch<import("@/types/compliance").NoticeResponseDetail>(
            `/compliance/notices/${noticeId}/responses`,
            payload,
            withTenant(),
        ),

    submitResponse: (noticeId: number) =>
        api.post<import("@/types/compliance").NoticeResponse>(
            `/compliance/notices/${noticeId}/responses/submit`,
            {},
            withTenant(),
        ),

    withdrawResponse: (noticeId: number) =>
        api.post<import("@/types/compliance").NoticeResponse>(
            `/compliance/notices/${noticeId}/responses/withdraw`,
            {},
            withTenant(),
        ),

    rollbackResponse: (noticeId: number, target_version_id: number) =>
        api.post<import("@/types/compliance").NoticeResponseDetail>(
            `/compliance/notices/${noticeId}/responses/rollback`,
            { target_version_id },
            withTenant(),
        ),

    approveResponse: (noticeId: number, reason?: string) =>
        api.post<import("@/types/compliance").ResponseApproval>(
            `/compliance/notices/${noticeId}/responses/approve`,
            { decision: "approved", reason },
            withTenant(),
        ),

    rejectResponse: (noticeId: number, reason: string) =>
        api.post<import("@/types/compliance").ResponseApproval>(
            `/compliance/notices/${noticeId}/responses/reject`,
            { decision: "rejected", reason },
            withTenant(),
        ),

    // ──── Phase 12 — Evidence attachments ────
    listEvidence: (noticeId: number) =>
        api.get<import("@/types/compliance").EvidenceAttachment[]>(
            `/compliance/notices/${noticeId}/evidence`,
            withTenant(),
        ),

    attachEvidence: (
        noticeId: number,
        payload: { document_id: number; description?: string; display_order?: number },
    ) =>
        api.post<import("@/types/compliance").EvidenceAttachment>(
            `/compliance/notices/${noticeId}/evidence`,
            payload,
            withTenant(),
        ),

    detachEvidence: (noticeId: number, document_id: number) =>
        api.delete(
            `/compliance/notices/${noticeId}/evidence/${document_id}`,
            withTenant(),
        ),

    // ──── Phase 13 — Unified search + analytics ────
    unifiedSearch: (params: {
        q: string;
        entity_types?: string;
        page?: number;
        page_size?: number;
    }) =>
        api.get<import("@/types/compliance").UnifiedSearchResponse>(
            "/compliance/search/unified",
            { ...withTenant(), params },
        ),

    penaltyByAuthority: (window_days: number = 90) =>
        api.get<import("@/types/compliance").PenaltyByAuthorityRow[]>(
            "/compliance/reports/penalty-by-authority",
            { ...withTenant(), params: { window_days } },
        ),

    noticeVolumeByStatus: (window_days: number = 90) =>
        api.get<import("@/types/compliance").NoticeVolumeByStatusRow[]>(
            "/compliance/reports/notice-volume-by-status",
            { ...withTenant(), params: { window_days } },
        ),

    responseTimeDistribution: (window_days: number = 90) =>
        api.get<import("@/types/compliance").ResponseTimeStats>(
            "/compliance/reports/response-time",
            { ...withTenant(), params: { window_days } },
        ),

    // ──── Phase 13 v2.0.1 — CSV exports (Blob downloads) ────
    exportPenaltyByAuthority: (window_days: number = 90) =>
        api.get<Blob>(
            "/compliance/reports/penalty-by-authority/export",
            { ...withTenant(), params: { window_days }, responseType: "blob" },
        ),

    exportNoticeVolumeByStatus: (window_days: number = 90) =>
        api.get<Blob>(
            "/compliance/reports/notice-volume-by-status/export",
            { ...withTenant(), params: { window_days }, responseType: "blob" },
        ),

    exportResponseTime: (window_days: number = 90) =>
        api.get<Blob>(
            "/compliance/reports/response-time/export",
            { ...withTenant(), params: { window_days }, responseType: "blob" },
        ),

    exportHealthSummary: (payload: { client_id: number; month: string }) =>
        api.post<Blob>(
            "/compliance/reports/health-summary/export",
            payload,
            { ...withTenant(), responseType: "blob" },
        ),
};

// Re-export the Client type so consumers don't need to import from two places
export type { Client, ClientDetail, Membership };
