# Phase 9: Compliance Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 09-compliance-foundation
**Areas discussed:** Notice data model & workflow, Client & multi-entity architecture, Extended RBAC (6→7 roles), Compliance dashboard & notice UX

---

## Notice Data Model & Workflow

### Authority & Notice Type Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Enum-based | Authority as Python enum, notice types as separate table with authority FK | ✓ |
| Flat config | Both as string columns, types in JSON config | |
| Hierarchical table | 3-level table hierarchy (Authority → Category → Type) | |

**User's choice:** "this is like a realtime project then choose which is better and why"
**Notes:** User delegated all notice model decisions to Claude for production-quality choices.

### Status Workflow Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| State machine in code | Python dict with valid transitions, backend validates | ✓ |
| Database constraint | PostgreSQL trigger enforces transitions | |
| You decide | Claude picks | |

**User's choice:** You decide → Claude selected state machine in code

### Notice Chaining

| Option | Description | Selected |
|--------|-------------|----------|
| Parent-child FK | parent_notice_id FK, recursive CTE queries | ✓ |
| Separate chain table | Junction table with relationship types | |
| You decide | Claude picks | |

**User's choice:** You decide → Claude selected parent-child FK

### Model Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Separate model | New ComplianceNotice, links to Document via FK | ✓ |
| Extend Document | Add compliance fields to existing Document | |
| You decide | Claude picks | |

**User's choice:** You decide → Claude selected separate model

### Deadline Tracking → Claude selected multiple milestone dates
### Metadata Extraction → Claude selected manual entry only (Phase 9 scope)
### Notice Number Validation → Claude selected regex per authority
### Penalty/Demand Amounts → Claude selected structured fields (tax_demand, interest, penalty, total_liability)
### Activity Timeline → Claude selected dedicated NoticeActivity table
### File Attachments → Claude selected notice-linked documents via existing Document model
### Tags → Claude selected simple tags via junction table
### Legal Sections → Claude selected structured JSON array with badge display

---

## Client & Multi-Entity Architecture

### RLS Implementation → Claude selected session-level context (set_config)
### Client-User Relationship → Claude selected many-to-many with role (ClientMembership)
### Registration Model → Claude selected separate ClientRegistration table
### Onboarding Flow → Claude selected multi-step wizard
### Config Overrides → Claude selected JSONB column on Client
### Dashboard Aggregation → Claude selected real-time query
### Report Generation → Claude selected on-demand generation
### Branding → Claude selected no branding in Phase 9
### v1.0 Documents → Claude selected keep user-scoped (no migration)
### Client Switcher → Claude selected top-bar dropdown
### All Clients View → Claude selected yes (for CA/Compliance Head roles)

---

## Extended RBAC

### Role Coexistence

| Option | Description | Selected |
|--------|-------------|----------|
| Parallel systems | v1.0 roles for docs, compliance roles for compliance | ✓ |
| Replace v1.0 roles | Migrate all to new 6-role system | |
| You decide | Claude picks | |

**User's choice:** Parallel systems (Recommended)
**Notes:** User explicitly selected this option.

### Additional Role Request
**User added:** CFO role — read-only across all clients, escalation endpoint for critical notices.
**Result:** Role count expanded from 6 to 7.

### Permission Hierarchy → Claude selected flat permissions (no inheritance)
### Auditor Access → Claude selected date range on ClientMembership
### Permission Enforcement → Claude selected dependency injection (Depends)

---

## Compliance Dashboard & Notice UX

### Dashboard Structure → Claude selected stats + table (consistent with v1.0)
### Notice Filtering → Claude selected sidebar filter panel
### Detail Page Layout → Claude selected two-column layout
### Bulk Actions → Claude selected checkbox + floating action bar

---

## Claude's Discretion

All technical implementation details delegated to Claude:
- Database schema specifics, field types, indexes
- API route structure and endpoint design
- Frontend component composition and state management
- Celery task configuration for reports
- Migration strategy and ordering

## Deferred Ideas

None — discussion stayed within phase scope.
