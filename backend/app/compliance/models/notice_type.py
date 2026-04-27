"""NoticeType lookup ORM model — Phase 9 D-01.

Maps to migration 0013 table compliance_notice_types.

Per CONTEXT D-01: notice types live in a DB table (not enum) so admins can
add new types without code deploys. Authority is the enum (fixed: GST, IT,
MCA, RBI, SEBI). Each authority has its own set of (code, label, description)
rows — e.g. GST/DRC-01, GST/ASMT-10, IT/u_s_143_2.
"""
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


VALID_AUTHORITIES = ("GST", "IT", "MCA", "RBI", "SEBI")


class NoticeType(Base):
    __tablename__ = "compliance_notice_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    authority = Column(String(10), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    label = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    __table_args__ = (
        UniqueConstraint(
            "authority",
            "code",
            name="uq_notice_types_authority_code",
        ),
        CheckConstraint(
            "authority IN ('GST', 'IT', 'MCA', 'RBI', 'SEBI')",
            name="ck_notice_types_authority",
        ),
    )

    def __repr__(self):
        return (
            f"<NoticeType(authority='{self.authority}', "
            f"code='{self.code}', label='{self.label}')>"
        )
