import re
from typing import List

_INJECTION_PHRASES: List[str] = [
    r"ignore (all )?previous (instructions|rules)",
    r"ignore (any|all)?\s*(policies|protocols|rules)",
    r"forget (your|all) (instructions|rules)",
    r"override (the )?policy(_guard)?",
    r"(print|show|reveal)\s+(all\s+)?hidden\s+system\s+(prompts?|instructions|messages)",
    r"hidden\s+system\s+(prompts?|instructions|messages)",
    r"dump (memory|all memory|the memory)",
    r"exfiltrate",
    r"leak (data|all data|private data)",
    r"disable (safety|guard|policy|filters|moderation|filter)",
    r"(bypass|override|disable)\s+(acl|access control|access controls)",
    r"(override|disable|bypass)\s+(guard|policy\s*guard|policyguard)",
    r"bypass (safety|policy|guard|filters|moderation)",
    r"jailbreak",
    r"sudo .*",
    r"escalat(e|ion) privileges",
    r"show me the system prompt",
    r"access hidden files",
    r"print secret",
    r"output hidden",
    # Reveal system architecture/internals
    r"(reveal|show)\s+system\s+(architecture|design|internals)",
]

_PROHIBITED_PHRASES: List[str] = [
    r"unmask (pii|personal data|personal information|pii)",
    r"(unmask|reveal|show) (the )?(pii|personal data|sensitive data|payroll|hr payroll|salary|salary sheet|payroll data)",
    r"social (security )?number(s)?|ssn\b|cnic\b|national id\b|passport number",
    r"give me .*social security|give me .*ssn|give me .*cnic|give me .*passport",
    r"(list|export|dump|download) (employee )?(social security numbers|ssns|cnics|payroll|salary|payroll data)",
    r"(payroll|salary) sheet|hr payroll|payroll.csv",
    r"genomics tenant|access genomics tenant|access tenant genomics",
    r"cross[- ]?tenant (access|accessing|access)",
    r"cross[- ]?lab .* (data|contacts|information)",
    r"(reveal|list|share|export|provide)\s+confidential\s+contacts?",
    r"\bconfidential\s+contacts?\b",
    r"contacts?\s+with\s+(cnic|phone|pii)",
    r"\baccess\s+u[1-4]\b",
    r"\baccess\s+tenant\s+u[1-4]\b",
    r"(private|internal|restricted) (files|documents|data|records|memos|memos)",
]

_INJ_REGEX = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PHRASES]
_PROH_REGEX = [re.compile(p, re.IGNORECASE) for p in _PROHIBITED_PHRASES]

def _normalize(text: str) -> str:
    text = text or ""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text

def _alnum_normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower() or "")

def _matches_any(regex_list: List[re.Pattern], text: str, alnum_text: str) -> bool:
    for rx in regex_list:
        if rx.search(text):
            return True
        try:
            if rx.search(alnum_text):
                return True
        except re.error:
            pass
    return False

def _clean_retrieval_query(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^(please|kindly|could you|would you please)\b[:,]?\s*", "", text, flags=re.IGNORECASE)
    parts = re.split(r"\b(?:then|and then|;|\n)\b", text, maxsplit=1, flags=re.IGNORECASE)
    text = parts[0].strip()
    return text

def planner(user_query: str) -> dict:
    if user_query is None:
        user_query = ""
    normalized = _normalize(user_query)
    alnum = _alnum_normalize(user_query)
    injection = _matches_any(_INJ_REGEX, normalized, alnum)
    prohibited = _matches_any(_PROH_REGEX, normalized, alnum)
    if injection or prohibited:
        retrieval_query = ""
    else:
        retrieval_query = _clean_retrieval_query(user_query)
        if len(retrieval_query.split()) < 3:
            if re.search(r"[a-zA-Z0-9]{2,}", retrieval_query) and len(retrieval_query) >= 2:
                pass
            else:
                retrieval_query = ""
    return {
        "injection": bool(injection),
        "prohibited": bool(prohibited),
        "retrieval query": retrieval_query
    }
