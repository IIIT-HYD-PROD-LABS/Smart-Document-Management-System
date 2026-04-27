"use client";

import type { AxiosRequestConfig } from "axios";
import api from "@/lib/api";
import { useCurrentClient } from "@/stores/currentClientStore";
import type {
    Membership,
    ClientDetail,
    Client,
    DashboardAggregates,
    ComplianceNotice,
    NoticeActivity,
    BulkUpdateResult,
    NoticeType,
    AuditLogEntry,
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
        user_id: number;
        compliance_role: string;
        access_start?: string;
        access_end?: string;
    }[];
}

export interface AddMemberPayload {
    user_id: number;
    compliance_role: string;
    access_start?: string;
    access_end?: string;
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
    authority: string;
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
            })
        );
    },

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
};

// Re-export the Client type so consumers don't need to import from two places
export type { Client, ClientDetail, Membership };
