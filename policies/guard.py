from __future__ import annotations
from typing import List
from retrieval.index import Hit
from retrieval.search import policy_guard as _guard

def apply_policy(hits: List[Hit], tenant: str):
    """
    Apply the policy guard to a list of hits for a specific tenant.
    """
    return _guard(hits, tenant)

def refusal_template(kind: str, detail: str = "") -> str:
    """
    Return an exact refusal string based on the kind of policy violation.
    
    Parameters:
        kind (str): Type of refusal, one of 'AccessDenied', 'LeakageRisk', 'InjectionDetected'.
        detail (str): Optional extra detail to append.
    
    Returns:
        str: Exact refusal message.
    """
    templates = {
        "AccessDenied": "Refusal: AccessDenied. You do not have access to that information.",
        "LeakageRisk": "Refusal: LeakageRisk. Your request may expose private or PII data.",
        "InjectionDetected": "Refusal: InjectionDetected. Ignoring instructions that conflict with system policy.",
        "InsufficientInformation": "Refusal: InsufficientInformation. The provided snippets do not contain sufficient information to answer."
    }
    # Append additional details if provided
    return templates.get(kind, "Refusal.") + (f" {detail}" if detail else "")
