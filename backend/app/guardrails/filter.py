"""
Output Filtering & Compliance Enforcement.
Ensures the system never issues an actual insurance authorization,
always provides the statutory medical officer disclaimer, and filters out
any unauthorized commitments or ungrounded promises.
"""
import re
from typing import Dict, Any

STATUTORY_DISCLAIMER = (
    "DISCLAIMER: This output represents an automated coverage recommendation based on retrieved "
    "policy wording. It does NOT constitute an insurance authorization or financial guarantee. "
    "The final determination rests exclusively with the authorized Medical Officer."
)

class OutputFilter:
    FORBIDDEN_PHRASES = [
        r"\bwe hereby authorise\b",
        r"\bclaim is officially approved\b",
        r"\bguaranteed payout\b",
        r"\bfinal decision made by ai\b",
        r"\bpolicyholder is entitled unconditionally\b"
    ]

    @classmethod
    def sanitize_output(cls, recommendation_text: str) -> str:
        text = recommendation_text
        for pat in cls.FORBIDDEN_PHRASES:
            text = re.sub(pat, "coverage position recommended for medical review", text, flags=re.IGNORECASE)
            
        if "DISCLAIMER:" not in text:
            text = f"{text}\n\n{STATUTORY_DISCLAIMER}"
            
        return text

class ToxicityGuard:
    TOXIC_TERMS = [
        r"\bfraudster\b",
        r"\bliar\b",
        r"\bcheater\b",
        r"\bmalicious hospital\b",
        r"\bscammer\b"
    ]

    @classmethod
    def check_toxicity(cls, text: str) -> bool:
        if not text:
            return False
        for term in cls.TOXIC_TERMS:
            if re.search(term, text, re.IGNORECASE):
                return True
        return False
