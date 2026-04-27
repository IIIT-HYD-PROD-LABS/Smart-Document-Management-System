"""Regulatory calendar seed for 2026 — INFRA-05.

Revision ID: 0016_regulatory_calendar_seed
Revises: 0015_compliance_rls_policies
Create Date: 2026-04-27

Sources for 2026 dates:
- cbic.gov.in (GST deadlines, gazetted holidays)
- incometax.gov.in (TDS, ITR deadlines)
- mca.gov.in (ROC filing deadlines)

NOTE: This is a baseline seed. Production deployments should refresh annually
via a follow-up Alembic migration when CBDT/CBIC publish next-year dates.
"""
from alembic import op

revision = "0016_regulatory_calendar_seed"
down_revision = "0015_compliance_rls_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO compliance_regulatory_calendar
          (year, date, authority, label, category, reference_url, notes, created_at)
        VALUES
          (2026, '2026-01-20', 'GST', 'GSTR-3B for December 2025', 'filing_deadline',
           'https://cbic.gov.in', 'Monthly summary return for tax period December 2025', now()),
          (2026, '2026-04-15', 'IT', 'ITR filing for FY 2025-26 (non-audit)', 'filing_deadline',
           'https://incometax.gov.in', 'Income tax return original due date', now()),
          (2026, '2026-04-30', 'IT', 'TDS Quarter 4 (FY 2024-25) filing', 'filing_deadline',
           'https://incometax.gov.in', 'Form 26Q/27Q quarterly TDS return', now()),
          (2026, '2026-05-30', 'MCA', 'Form ROC AOC-4 filing', 'filing_deadline',
           'https://mca.gov.in', 'Annual financial statement filing for FY 2024-25', now()),
          (2026, '2026-09-30', 'GST', 'GSTR-9 Annual Return for FY 2024-25', 'filing_deadline',
           'https://cbic.gov.in', 'Annual GST return (turnover above threshold)', now()),
          (2026, '2026-10-31', 'IT', 'ITR for FY 2025-26 (audit cases)', 'filing_deadline',
           'https://incometax.gov.in', 'ITR for assessees subject to tax audit', now()),
          (2026, '2026-01-26', NULL, 'Republic Day', 'holiday',
           NULL, 'Gazetted national holiday', now()),
          (2026, '2026-03-08', NULL, 'Holi', 'holiday',
           NULL, 'Gazetted holiday (date approximate, varies regionally)', now()),
          (2026, '2026-04-14', NULL, 'Ambedkar Jayanti', 'holiday',
           NULL, 'Gazetted national holiday', now()),
          (2026, '2026-08-15', NULL, 'Independence Day', 'holiday',
           NULL, 'Gazetted national holiday', now()),
          (2026, '2026-10-02', NULL, 'Gandhi Jayanti', 'holiday',
           NULL, 'Gazetted national holiday', now()),
          (2026, '2026-12-25', NULL, 'Christmas', 'holiday',
           NULL, 'Gazetted national holiday', now());
    """)


def downgrade() -> None:
    op.execute("DELETE FROM compliance_regulatory_calendar WHERE year = 2026;")
