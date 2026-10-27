"""
Strict Data Contracts for Pre-Authorisation Requests, Responses, and Quarantine.
Enforces schema, type, range, categorical, and cross-field constraints at the ingestion boundary.
Malformed requests are quarantined and never reach the agent reasoning layer.
"""
from datetime import date
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_validator
import uuid

class PreAuthRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:8].upper()}")
    policy_number: str = Field(..., min_length=6, max_length=32, description="Policy schedule number")
    insured_id: str = Field(..., min_length=4, max_length=32, description="Member / Insured identifier")
    policy_inception_date: date = Field(..., description="First policy inception date with the insurer")
    policy_expiry_date: date = Field(..., description="Current policy period expiry date")
    hospital_name: str = Field(..., min_length=3, max_length=120)
    hospital_tier: Literal["network", "non-network"] = Field(..., description="Network status of provider")
    admission_type: Literal["planned-surgical", "day-care", "emergency", "maternity"] = Field(...)
    procedure_name: str = Field(..., min_length=3, max_length=120)
    procedure_code: Optional[str] = Field(None, max_length=30)
    diagnosis: str = Field(..., min_length=3, max_length=200)
    icd10_code: Optional[str] = Field(None, max_length=15)
    room_category: Literal["general_ward", "semi_private", "single_private", "deluxe", "suite", "day_care_bed"] = Field(...)
    estimated_cost: float = Field(..., ge=500.0, le=5000000.0, description="Estimated total cost in INR (500 to 50L)")
    room_rent_per_day: Optional[float] = Field(None, ge=0.0, le=500000.0)
    proposed_admission_date: date = Field(..., description="Date of admission or surgery")
    prior_coverage_months: int = Field(default=0, ge=0, le=600, description="Months of continuous prior coverage from portability")
    declared_pre_existing_conditions: List[str] = Field(default_factory=list)
    clinical_notes: Optional[str] = Field(None, max_length=3000, description="Untrusted hospital clinical notes")

    @field_validator("procedure_name", "diagnosis", "hospital_name")
    @classmethod
    def clean_text_fields(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or purely whitespace.")
        return cleaned

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "PreAuthRequest":
        # 1. Expiry must be after inception
        if self.policy_expiry_date <= self.policy_inception_date:
            raise ValueError(
                f"policy_expiry_date ({self.policy_expiry_date}) must be strictly after "
                f"policy_inception_date ({self.policy_inception_date})."
            )

        # 2. Admission date must be within policy term or valid portability window
        if self.proposed_admission_date < self.policy_inception_date:
            raise ValueError(
                f"proposed_admission_date ({self.proposed_admission_date}) cannot be before "
                f"policy_inception_date ({self.policy_inception_date})."
            )
        if self.proposed_admission_date > self.policy_expiry_date:
            raise ValueError(
                f"proposed_admission_date ({self.proposed_admission_date}) exceeds "
                f"policy_expiry_date ({self.policy_expiry_date}). Policy expired."
            )

        # 3. Room rent cannot exceed total estimated cost
        if self.room_rent_per_day is not None and self.room_rent_per_day > self.estimated_cost:
            raise ValueError(
                f"room_rent_per_day (INR {self.room_rent_per_day}) cannot exceed "
                f"total estimated_cost (INR {self.estimated_cost})."
            )

        # 4. Day care admission should specify day care bed or general accommodation
        if self.admission_type == "day-care" and self.room_category in ["deluxe", "suite"]:
            raise ValueError("Day care admission cannot be requested with deluxe or suite room category.")

        return self

class QuarantineRecord(BaseModel):
    quarantine_id: str = Field(default_factory=lambda: f"QRN-{uuid.uuid4().hex[:8].upper()}")
    request_id: Optional[str] = None
    raw_payload: Dict[str, Any]
    validation_errors: List[Dict[str, Any]]
    quarantined_at: str
    reason: str

class ClauseCitation(BaseModel):
    document_name: str
    page_number: int
    clause_id: str
    clause_title: str
    quoted_passage: str

class PreAuthResponse(BaseModel):
    run_id: str
    request_id: str
    status: Literal["completed", "failed", "processing", "quarantined", "escalated"]
    route: Literal["approve-recommended", "query-to-hospital", "medical-review"]
    indicative_limit: Optional[float] = None
    coverage_position: str
    clauses: List[ClauseCitation] = Field(default_factory=list)
    applicable_waiting_periods: List[str] = Field(default_factory=list)
    applicable_exclusions: List[str] = Field(default_factory=list)
    room_eligibility_status: str
    verification_status: Literal["verified", "failed", "escalated"]
    escalation_reason: Optional[str] = None
    explanation: str
    trace_id: str
    prompt_version: str
    processing_duration_ms: float
    cost_breakdown: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str

class FeedbackRequest(BaseModel):
    run_id: str
    satisfactory: bool = True
    reason: str = Field(..., min_length=3, max_length=500)
    reviewer_id: Optional[str] = Field(default="medical-officer-01")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Support alternative field names from UI / API clients
            if "satisfactory" not in data and "decision_agreed" in data:
                data["satisfactory"] = bool(data["decision_agreed"])
            if "reason" not in data and "comments" in data:
                data["reason"] = str(data["comments"])
            if "reviewer_id" not in data and "clinician_id" in data:
                data["reviewer_id"] = str(data["clinician_id"])
        return data

class FeedbackStats(BaseModel):
    total_feedbacks: int
    satisfactory_count: int
    unsatisfactory_count: int
    satisfaction_rate_percent: float
    recent_feedbacks: List[Dict[str, Any]]
