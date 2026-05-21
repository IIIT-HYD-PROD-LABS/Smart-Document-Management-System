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
    // Branding (migration 0031). logo_url is a `data:image/...;base64,...`
    // URL when present — see backend/app/compliance/routers/clients.py.
    logo_url: string | null;
    website: string | null;
    address: string | null;
    config_overrides: Record<string, unknown>;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface ClientBrandingUpdate {
    website?: string | null;
    address?: string | null;
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

export type RiskTier = "critical" | "high" | "medium" | "low";

export type NoticeSource = "manual" | "portal" | "gmail" | "imap";

export interface RiskFactor {
    feature: string;
    contribution: number;
    phrase: string;
}

export interface NerExtractedFields {
    gstins?: string[];
    pans?: string[];
    cins?: string[];
    section_references?: string[];
    risk_top_factors?: RiskFactor[];
    regex_extractor_version?: string;
    [key: string]: unknown;
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
    // Phase 10 ML fields (NULL for v2.0 rule-based output;
    // confidences populate when v2.1 BERT classifier ships)
    classifier_authority_confidence: number | null;
    classifier_type_confidence: number | null;
    risk_score: number | null;
    risk_tier: RiskTier | null;
    ner_extracted_fields: NerExtractedFields | null;
    model_version: string | null;
    classified_at: string | null;
    risk_scored_at: string | null;
    source: NoticeSource;
}

// Phase 10 — review queue
export interface ReviewQueueItem {
    id: number;
    notice_id: number;
    client_id: number;
    predicted_authority: Authority | null;
    predicted_authority_confidence: string | null;
    predicted_type_id: number | null;
    predicted_type_confidence: string | null;
    model_version: string;
    // `manual_flag` and `manual_flag:<note>` come from the operator-flag
    // endpoint (POST /api/compliance/review/manual-enqueue/{notice_id}).
    // The string is opaque past the colon, so the type stays as `string`
    // and the page-level helpers normalize it to one of four buckets.
    reason: string;
    reviewer_id: number | null;
    reviewed_at: string | null;
    reviewer_assigned_authority: Authority | null;
    reviewer_assigned_type_id: number | null;
    created_at: string;
}

export interface ReviewQueueListResponse {
    items: ReviewQueueItem[];
    page: number;
    page_size: number;
    total: number;
}

export interface ReviewAssignRequest {
    authority?: Authority;
    notice_type_id?: number;
}

// Phase 11 — calendar + alerts
export type CalendarCategory = "holiday" | "filing_deadline" | "circular_extension";

export interface CalendarEntry {
    id: number;
    year: number;
    date: string;  // ISO date
    authority: Authority | null;
    label: string;
    category: CalendarCategory;
    reference_url: string | null;
    notes: string | null;
}

export type AlertType =
    | "deadline_t7"
    | "deadline_t3"
    | "deadline_t1"
    | "overdue"
    | "status_change"
    | "received"
    | "escalation";

export type AlertChannel = "email" | "sms" | "websocket";

export type AlertDeliveryStatus = "queued" | "sent" | "delivered" | "failed" | "bounced";

export interface AlertLogEntry {
    id: number;
    notice_id: number;
    client_id: number;
    alert_type: AlertType;
    recipient_user_id: number | null;
    recipient_email: string | null;
    channel: AlertChannel;
    delivery_status: AlertDeliveryStatus;
    provider_message_id: string | null;
    error: string | null;
    created_at: string;
    delivered_at: string | null;
}

export interface AlertRule {
    id: number;
    client_id: number;
    notice_type_id: number | null;
    rules: {
        channels?: AlertChannel[];
        min_risk_tier?: RiskTier;
        recipient_roles?: ComplianceRole[];
        escalation_chain?: ComplianceRole[];
        [key: string]: unknown;
    };
    is_active: boolean;
}

export interface ComplianceScore {
    score: number;
    window_days: number;
    notices_total: number;
    notices_on_time: number;
    notices_overdue: number;
    as_of: string;
}

export interface AdjustDeadlineResult {
    original: string;
    adjusted: string;
    shifted: boolean;
}

// In-app notification envelope received over the WebSocket
export interface NotificationEnvelope {
    type: "notice_alert";
    recipient_user_id: number | null;
    payload: {
        notice_id: number;
        notice_number: string;
        authority: Authority;
        status: NoticeStatus;
        response_deadline: string | null;
        risk_tier: RiskTier | null;
        alert_type: AlertType;
        client_id?: number;
        [key: string]: unknown;
    };
}

// Phase 12 — response workflow + evidence
export type ResponseStatus =
    | "draft"
    | "reviewer_pending"
    | "legal_pending"
    | "cfo_pending"
    | "approved"
    | "rejected"
    | "withdrawn";

export type ApprovalStage = "reviewer" | "legal" | "cfo";

export interface ResponseVersion {
    id: number;
    response_id: number;
    version_no: number;
    subject: string | null;
    body_markdown: string;
    recipient: string | null;
    response_date: string | null;
    metadata_json: Record<string, unknown> | null;
    rolled_back_from_version_id: number | null;
    created_by_user_id: number | null;
    created_at: string;
}

export interface ResponseApproval {
    id: number;
    response_id: number;
    version_id: number | null;
    stage: ApprovalStage;
    decision: "approved" | "rejected";
    actor_user_id: number | null;
    reason: string | null;
    created_at: string;
}

export interface NoticeResponse {
    id: number;
    notice_id: number;
    client_id: number;
    status: ResponseStatus;
    current_version_id: number | null;
    created_by_user_id: number | null;
    created_at: string;
    updated_at: string;
    current_version: ResponseVersion | null;
}

export interface NoticeResponseDetail extends NoticeResponse {
    versions: ResponseVersion[];
    approvals: ResponseApproval[];
}

export interface ResponseDraftPayload {
    subject?: string;
    body_markdown?: string;
    recipient?: string;
    response_date?: string;
    metadata_json?: Record<string, unknown>;
}

export interface EvidenceAttachment {
    id: number;
    notice_id: number;
    document_id: number;
    display_order: number;
    description: string | null;
    added_by_user_id: number | null;
    created_at: string;
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

// ─────────────────────────────────────────────────────────────────────
// Phase 13 — unified search + analytics
// ─────────────────────────────────────────────────────────────────────
export interface UnifiedSearchHit {
    entity_type: "notice" | "document";
    entity_id: number;
    rank: number;
    title: string;
    snippet: string;
    metadata: Record<string, unknown>;
}

export interface UnifiedSearchResponse {
    items: UnifiedSearchHit[];
    query: string;
    page: number;
    page_size: number;
    backend: string;
}

export interface PenaltyByAuthorityRow {
    authority: string;
    count: number;
    total_penalty: number;
    total_tax_demand: number;
}

export interface NoticeVolumeByStatusRow {
    status: string;
    count: number;
}

export interface ResponseTimeStats {
    p50: number;
    p90: number;
    p95: number;
    mean: number;
    count: number;
}
