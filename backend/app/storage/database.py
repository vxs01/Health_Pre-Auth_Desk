"""
Persistent SQLite / SQLAlchemy Database Engine.
Stores requests, runs, audit steps, quarantined payloads, and reviewer feedback.
Provides an immutable audit trail for complete run reconstruction.
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DB_DIR = "data"
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "preauth_desk.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

Base = declarative_base()

class DBRequest(Base):
    __tablename__ = "requests"
    request_id = Column(String(50), primary_key=True)
    policy_number = Column(String(50), nullable=False)
    insured_id = Column(String(50), nullable=False)
    hospital_name = Column(String(150), nullable=False)
    procedure_name = Column(String(150), nullable=False)
    diagnosis = Column(String(250), nullable=False)
    estimated_cost = Column(Float, nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class DBQuarantinedRequest(Base):
    __tablename__ = "quarantined_requests"
    quarantine_id = Column(String(50), primary_key=True)
    request_id = Column(String(50), nullable=True)
    raw_payload_json = Column(Text, nullable=False)
    errors_json = Column(Text, nullable=False)
    reason = Column(String(255), nullable=False)
    quarantined_at = Column(DateTime, default=datetime.utcnow)

class DBRun(Base):
    __tablename__ = "runs"
    run_id = Column(String(50), primary_key=True)
    request_id = Column(String(50), nullable=False)
    trace_id = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False) # completed, failed, escalated
    route = Column(String(30), nullable=False) # approve-recommended, query-to-hospital, medical-review
    verification_status = Column(String(30), nullable=False)
    indicative_limit = Column(Float, nullable=True)
    result_json = Column(Text, nullable=False)
    prompt_version = Column(String(20), nullable=False)
    processing_duration_ms = Column(Float, nullable=False)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class DBAuditStep(Base):
    __tablename__ = "audit_steps"
    step_id = Column(String(50), primary_key=True)
    run_id = Column(String(50), nullable=False)
    step_index = Column(Integer, nullable=False)
    agent_name = Column(String(50), nullable=False)
    step_type = Column(String(50), nullable=False) # handoff, tool_call, verification, routing
    tool_name = Column(String(50), nullable=True)
    tool_input_json = Column(Text, nullable=True)
    tool_output_json = Column(Text, nullable=True)
    duration_ms = Column(Float, default=0.0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DBFeedback(Base):
    __tablename__ = "feedback"
    feedback_id = Column(String(50), primary_key=True)
    run_id = Column(String(50), nullable=False)
    satisfactory = Column(Boolean, nullable=False)
    reason = Column(String(500), nullable=False)
    reviewer_id = Column(String(50), default="medical-officer-01")
    created_at = Column(DateTime, default=datetime.utcnow)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

class StorageService:
    @staticmethod
    def save_request(req_data: Dict[str, Any]):
        db = SessionLocal()
        try:
            req = DBRequest(
                request_id=req_data["request_id"],
                policy_number=req_data["policy_number"],
                insured_id=req_data["insured_id"],
                hospital_name=req_data["hospital_name"],
                procedure_name=req_data["procedure_name"],
                diagnosis=req_data["diagnosis"],
                estimated_cost=req_data["estimated_cost"],
                payload_json=json.dumps(req_data, default=str)
            )
            db.merge(req)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def save_quarantined_request(quarantine_id: str, request_id: Optional[str], raw_payload: Dict[str, Any], errors: List[Dict[str, Any]], reason: str):
        db = SessionLocal()
        try:
            q = DBQuarantinedRequest(
                quarantine_id=quarantine_id,
                request_id=request_id,
                raw_payload_json=json.dumps(raw_payload, default=str),
                errors_json=json.dumps(errors, default=str),
                reason=reason
            )
            db.add(q)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def save_run(run_data: Dict[str, Any]):
        db = SessionLocal()
        try:
            run = DBRun(
                run_id=run_data["run_id"],
                request_id=run_data["request_id"],
                trace_id=run_data["trace_id"],
                status=run_data["status"],
                route=run_data["route"],
                verification_status=run_data["verification_status"],
                indicative_limit=run_data.get("indicative_limit"),
                result_json=json.dumps(run_data, default=str),
                prompt_version=run_data["prompt_version"],
                processing_duration_ms=run_data["processing_duration_ms"],
                total_tokens=run_data.get("cost_breakdown", {}).get("total_tokens", 0),
                cost_usd=run_data.get("cost_breakdown", {}).get("estimated_cost_usd", 0.0)
            )
            db.merge(run)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def save_audit_step(step_data: Dict[str, Any]):
        db = SessionLocal()
        try:
            step = DBAuditStep(
                step_id=step_data["step_id"],
                run_id=step_data["run_id"],
                step_index=step_data["step_index"],
                agent_name=step_data["agent_name"],
                step_type=step_data["step_type"],
                tool_name=step_data.get("tool_name"),
                tool_input_json=json.dumps(step_data.get("tool_input"), default=str) if step_data.get("tool_input") else None,
                tool_output_json=json.dumps(step_data.get("tool_output"), default=str) if step_data.get("tool_output") else None,
                duration_ms=step_data.get("duration_ms", 0.0),
                prompt_tokens=step_data.get("prompt_tokens", 0),
                completion_tokens=step_data.get("completion_tokens", 0),
                cost_usd=step_data.get("cost_usd", 0.0)
            )
            db.merge(step)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def get_run(run_id: str) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            run = db.query(DBRun).filter(DBRun.run_id == run_id).first()
            if not run:
                return None
            return json.loads(run.result_json)
        finally:
            db.close()

    @staticmethod
    def get_run_audit_steps(run_id: str) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            steps = db.query(DBAuditStep).filter(DBAuditStep.run_id == run_id).order_by(DBAuditStep.step_index).all()
            return [
                {
                    "step_id": s.step_id,
                    "run_id": s.run_id,
                    "step_index": s.step_index,
                    "agent_name": s.agent_name,
                    "step_type": s.step_type,
                    "tool_name": s.tool_name,
                    "tool_input": json.loads(s.tool_input_json) if s.tool_input_json else None,
                    "tool_output": json.loads(s.tool_output_json) if s.tool_output_json else None,
                    "duration_ms": s.duration_ms,
                    "prompt_tokens": s.prompt_tokens,
                    "completion_tokens": s.completion_tokens,
                    "cost_usd": s.cost_usd,
                    "timestamp": s.timestamp.isoformat() + "Z" if s.timestamp else None
                }
                for s in steps
            ]
        finally:
            db.close()

    @staticmethod
    def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            runs = db.query(DBRun).order_by(DBRun.created_at.desc()).limit(limit).all()
            return [json.loads(r.result_json) for r in runs]
        finally:
            db.close()

    @staticmethod
    def list_quarantined(limit: int = 50) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            items = db.query(DBQuarantinedRequest).order_by(DBQuarantinedRequest.quarantined_at.desc()).limit(limit).all()
            return [
                {
                    "quarantine_id": i.quarantine_id,
                    "request_id": i.request_id,
                    "raw_payload": json.loads(i.raw_payload_json),
                    "validation_errors": json.loads(i.errors_json),
                    "reason": i.reason,
                    "quarantined_at": i.quarantined_at.isoformat() + "Z"
                }
                for i in items
            ]
        finally:
            db.close()

    @staticmethod
    def save_feedback(feedback_id: str, run_id: str, satisfactory: bool, reason: str, reviewer_id: str):
        db = SessionLocal()
        try:
            fb = DBFeedback(
                feedback_id=feedback_id,
                run_id=run_id,
                satisfactory=satisfactory,
                reason=reason,
                reviewer_id=reviewer_id
            )
            db.add(fb)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def get_feedback_stats() -> Dict[str, Any]:
        db = SessionLocal()
        try:
            items = db.query(DBFeedback).order_by(DBFeedback.created_at.desc()).all()
            total = len(items)
            sat = sum(1 for i in items if i.satisfactory)
            unsat = total - sat
            rate = round((sat / total) * 100.0, 1) if total > 0 else 100.0
            recent = [
                {
                    "feedback_id": i.feedback_id,
                    "run_id": i.run_id,
                    "satisfactory": i.satisfactory,
                    "reason": i.reason,
                    "reviewer_id": i.reviewer_id,
                    "created_at": i.created_at.isoformat() + "Z"
                }
                for i in items[:20]
            ]
            return {
                "total_feedbacks": total,
                "satisfactory_count": sat,
                "unsatisfactory_count": unsat,
                "satisfaction_rate_percent": rate,
                "recent_feedbacks": recent
            }
        finally:
            db.close()

init_db()
