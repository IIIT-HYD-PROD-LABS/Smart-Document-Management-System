"""Phase 9 compliance ORM models package.

Models registered here map to the 8 compliance tables created by
migration 0013_compliance_foundation_schema:

  - Client + ClientRegistration  (compliance_clients, compliance_client_registrations)
  - ClientMembership             (compliance_client_memberships)
  - NoticeType                   (compliance_notice_types)
  - ComplianceNotice + NoticeActivity + NoticeTag
                                 (compliance_notices, compliance_notice_activity,
                                  compliance_notice_tags)
  - RegulatoryCalendar           (compliance_regulatory_calendar)

Importing this package (or `app.models`) is sufficient to register every
class with the SQLAlchemy declarative_base so relationship() targets resolve
at first ORM access.
"""
