from __future__ import annotations
import re
from typing import List
from .index import Hit

# -----------------------------------------------------------
# Exact PII patterns required by the assignment:
# CNIC-like: \b{5}-{7}-\b  (5 digits, 7 digits, 1 digit)
# PK phone-like: \+?92-?{3}-?{7}  (Optional +, 92, optional -, 3 digits, optional -, 7 digits)
# -----------------------------------------------------------
PII_PATTERNS = [
    # CNIC-like: e.g., 42101-1234567-8
    re.compile(r"\b\d{5}-\d{7}-\d\b"),
    # PK Phone-like: e.g., +923001234567 or 92300-1234567
    re.compile(r"\+?92-?\d{3}-?\d{7}"),
]


def mask_pii(text: str) -> str:
    """
    Masks PII patterns (CNIC-like and PK phone-like) by replacing them with [REDACTED].
    """
    out = text
    for pat in PII_PATTERNS:
        # Replace all matches with [REDACTED]
        out = pat.sub("[REDACTED]", out)
    return out


def policy_guard(hits: List[Hit], active_tenant: str) -> List[Hit] | dict:
    """
    Policy Guard: Performs ACL enforcement and PII masking.

    1. Removes documents that violate cross-tenant access rules.
    2. Masks PII in allowed documents.
    3. Returns a Refusal dict if no documents remain.
    """
    allowed_hits: list[Hit] = []

    for h in hits:
        # ACL Enforcement [cite: 87]
        # Allow if:
        # 1. Document is public (visibility="public")
        # 2. Document is private (visibility="private") AND tenant matches active_tenant
        is_allowed = (
            h.visibility == "public"
            or (h.visibility == "private" and h.tenant == active_tenant)
        )

        if not is_allowed:
            # Remove hits where hit.tenant != active_tenant and hit.visibility != "public" [cite: 87]
            continue

        # PII Masking
        original_text = h.text
        masked_text = mask_pii(original_text)

        # Update the hit object's text and flag if masking occurred
        h.text = masked_text
        h.pii_masked = (masked_text != original_text)

        # Add the allowed (and masked) hit to the list
        allowed_hits.append(h)

    # Refusal Check [cite: 89]
    if not allowed_hits:
        # If no allowed snippets remain, return Refusal: AccessDenied [cite: 89]
        return {
            "refusal": "AccessDenied",
            "reason": "No allowed snippets remain after ACL filtering and masking.",
        }

    return allowed_hits
