"""ClientMembership ORM model — Phase 9 RBAC-04, CLIENT-04.

Maps to migration 0013 table compliance_client_memberships.

Per CONTEXT D-14: many-to-many Client<->User. CAs/Compliance Heads can be
members of multiple clients with potentially different compliance_role per
client.

Per CONTEXT D-25: 7 compliance_role values gate compliance feature access
(parallel to v1.0 system roles which gate document features).

Per CONTEXT D-27: Auditor role uses access_start/access_end for time-bound
read-only access. Middleware (Plan 04) calls is_active_at(now()) on every
request and rejects if False — auto-revoked when window expires.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# Source-of-truth role list. Mirrors the CHECK constraint in migration 0013
# and the permission_registry.ComplianceRole enum.
VALID_COMPLIANCE_ROLES = (
    "compliance_head",
    "legal_team",
    "finance_team",
    "auditor",
    "ca_consultant",
    "staff",
    "cfo",
)


class ClientMembership(Base):
    __tablename__ = "compliance_client_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    compliance_role = Column(String(30), nullable=False, index=True)
    # D-27: Auditor needs time-bound access; other roles leave NULL = unbounded.
    access_start = Column(DateTime(timezone=True), nullable=True)
    access_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    client = relationship("Client", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "client_id",
            name="uq_memberships_user_client",
        ),
        CheckConstraint(
            "compliance_role IN ("
            "'compliance_head', 'legal_team', 'finance_team', "
            "'auditor', 'ca_consultant', 'staff', 'cfo')",
            name="ck_memberships_compliance_role",
        ),
    )

    def is_active_at(self, when: datetime) -> bool:
        """Return True iff `when` is within [access_start, access_end].

        NULL bounds are unbounded:
          - access_start NULL  => no lower bound
          - access_end   NULL  => no upper bound (most non-auditor roles)

        Comparison uses the timezone of `when`; both stored fields are
        DateTime(timezone=True), so naive `when` will raise TypeError.
        """
        if self.access_start is not None and when < self.access_start:
            return False
        if self.access_end is not None and when > self.access_end:
            return False
        return True

    def __repr__(self):
        return (
            f"<ClientMembership(user_id={self.user_id}, "
            f"client_id={self.client_id}, role='{self.compliance_role}')>"
        )
