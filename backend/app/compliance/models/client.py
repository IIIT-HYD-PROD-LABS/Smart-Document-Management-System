"""Client + ClientRegistration ORM models — Phase 9 CLIENT-01, CLIENT-02, CLIENT-06.

Maps to migration 0013 tables:
  - compliance_clients             (Client)
  - compliance_client_registrations (ClientRegistration)

Per CONTEXT D-15: ClientRegistration is a separate table (not embedded fields)
to support multi-GSTIN per client (one registration row per state).
Per CONTEXT D-17: config_overrides is JSONB to allow per-client alert rules,
approval workflows, and deadline thresholds without schema migrations.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Client(Base):
    __tablename__ = "compliance_clients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    # CONTEXT D-15: 'pvt_ltd' | 'llp' | 'partnership' | 'sole_prop' | 'opc'
    # No DB CHECK constraint here — schemas/client.py Literal[] enforces
    # the allowed set at the API boundary; migration 0013 leaves this open
    # for future client_type values without schema migrations.
    client_type = Column(String(30), nullable=False)
    industry = Column(String(100), nullable=True)
    primary_contact_email = Column(String(255), nullable=True)
    # Branding (migration 0031). logo_url stores a data:image/...;base64,...
    # URL up to ~340 KB — see migration docstring for the trade-off.
    logo_url = Column(Text, nullable=True)
    website = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    config_overrides = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    # Relationships
    registrations = relationship(
        "ClientRegistration",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    memberships = relationship(
        "ClientMembership",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    notices = relationship(
        "ComplianceNotice",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Client(id={self.id}, name='{self.name}')>"


class ClientRegistration(Base):
    __tablename__ = "compliance_client_registrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 'GSTIN' | 'PAN' | 'CIN' | 'DIN'
    type = Column(String(10), nullable=False)
    value = Column(String(30), nullable=False)
    # GSTIN state code (01-37, 97, 99). NULL for non-GSTIN registrations.
    state = Column(String(5), nullable=True)
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    client = relationship("Client", back_populates="registrations")

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "type",
            "value",
            name="uq_client_registrations_client_type_value",
        ),
        CheckConstraint(
            "type IN ('GSTIN', 'PAN', 'CIN', 'DIN')",
            name="ck_client_registrations_type",
        ),
    )

    def __repr__(self):
        return (
            f"<ClientRegistration(client_id={self.client_id}, "
            f"type='{self.type}', value='{self.value}')>"
        )
