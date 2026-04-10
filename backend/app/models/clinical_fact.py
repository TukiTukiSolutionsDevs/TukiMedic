from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime, timezone

from app.core.database import Base


class ClinicalFactModel(Base):
    __tablename__ = "clinical_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    fact_type = Column(String(100), nullable=False)  # symptom, diagnosis, medication, allergy, vital
    value = Column(Text, nullable=False)
    source_agent = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    embedding = Column(Vector(1536))
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
