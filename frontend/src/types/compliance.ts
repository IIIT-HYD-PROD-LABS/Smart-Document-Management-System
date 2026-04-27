// Phase 9 type definitions — mirrors backend Pydantic schemas in backend/app/schemas/

export type Authority = "GST" | "IT" | "MCA" | "RBI" | "SEBI";

export type NoticeStatus =
    | "received"
    | "under_review"
    | "response_drafted"
    | "submitted"
    | "resolved"
    | "dismissed";

export type ComplianceRole =
    | "compliance_head"
    | "legal_team"
    | "finance_team"
    | "auditor"
    | "ca_consultant"
    | "staff"
    | "cfo";

export type RegistrationType = "GSTIN" | "PAN" | "CIN" | "DIN";

export type ClientType = "pvt_ltd" | "llp" | "partnership" | "sole_prop" | "opc";

export interface Membership {
    id: number;
    user_id: number;
    client_id: number;
    compliance_role: ComplianceRole;
    access_start: string | null;
    access_end: string | null;
    created_at: string;
}

export interface Registration {
    id: number;
    type: RegistrationType;
    value: string;
    state: string | null;
    is_active: boolean;
    created_at: string;
}

export interface Client {
    id: number;
    name: string;
    client_type: ClientType;
    industry: string | null;
    primary_contact_email: string | null;
    config_overrides: Record<string, unknown>;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface ClientDetail extends Client {
    registrations: Registration[];
    memberships: Membership[];
}

export interface DashboardAggregates {
    total: number;
    by_status: Record<string, number>;
    by_authority: Record<string, number>;
    by_risk_tier: Record<string, number>;
    overdue: number;
}

export interface ComplianceNotice {
    id: number;
    client_id: number;
    notice_number: string;
    authority: Authority;
    status: NoticeStatus;
    received_date: string;
    response_deadline: string | null;
    hearing_date: string | null;
    compliance_date: string | null;
    appeal_deadline: string | null;
    tax_demand: string | null;
    interest: string | null;
    penalty: string | null;
    total_liability: string | null;
    legal_sections: string[];
    assigned_user_id: number | null;
    parent_notice_id: number | null;
    document_id: number | null;
    notice_type_id: number | null;
    registration_id: number | null;
    status_changed_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface NoticeActivity {
    id: number;
    notice_id: number;
    user_id: number | null;
    type: "status_change" | "note_added" | "file_attached" | "assigned";
    details: Record<string, unknown>;
    created_at: string;
}

export interface AuditLogEntry {
    id: number;
    user_id: number | null;
    action: string;
    resource_type: string | null;
    resource_id: number | null;
    details: Record<string, unknown> | null;
    ip_address: string | null;
    created_at: string;
}

export interface NoticeType {
    id: number;
    authority: Authority;
    code: string;
    label: string;
    description: string | null;
    is_active: boolean;
}

export interface BulkUpdateResult {
    results: { id: number; success: boolean; error: string | null }[];
    summary: { ok: number; failed: number };
}

// Compliance roles eligible for "All Clients" cross-client mode (per CONTEXT D-23)
export const ROLES_ELIGIBLE_FOR_CROSS_CLIENT: ComplianceRole[] = [
    "compliance_head",
    "ca_consultant",
    "cfo",
];

export const COMPLIANCE_ROLE_LABELS: Record<ComplianceRole, string> = {
    compliance_head: "Compliance Head",
    legal_team: "Legal Team",
    finance_team: "Finance Team",
    auditor: "Auditor",
    ca_consultant: "CA / Consultant",
    staff: "Staff",
    cfo: "CFO",
};

// UI-SPEC Section 7 — 7-role chip color contract (D-25, D-26 flat permissions)
export const COMPLIANCE_ROLE_COLORS: Record<ComplianceRole, string> = {
    compliance_head: "#3b82f6",
    legal_team: "#8b5cf6",
    finance_team: "#06b6d4",
    auditor: "#f59e0b",
    ca_consultant: "#10b981",
    staff: "#71717a",
    cfo: "#ec4899",
};
