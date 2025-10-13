import os
from typing import List, Dict

# ---------------------------------------------------------------------------
# Disable telemetry for Groq & Chroma for this process
# ---------------------------------------------------------------------------
os.environ.setdefault("GROQ_DISABLE_TELEMETRY", "1")
os.environ.setdefault("CHROMADB_ALLOW_TELEMETRY", "false")
os.environ.setdefault("CHROMA_TELEMETRY_DISABLED", "1")


# ---------------------------------------------------------------------------
# Message builder for Groq chat completion
# ---------------------------------------------------------------------------
def build_messages(system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
    """
    Builds a message list compatible with Groq's chat.completions API.

    Args:
        system_prompt: Text for the system (context-setting) message.
        user_prompt: Text for the user input message.

    Returns:
        List of message dicts in the format Groq expects.
    """
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


# ---------------------------------------------------------------------------
# LLM caller wrapper
# ---------------------------------------------------------------------------
def call_llm(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 400,
) -> str:
    """
    Calls the Groq LLM API with the provided messages.

    Args:
        messages: List of message dicts from build_messages().
        model: Model name (e.g., 'llama3-70b-8192' or as specified by assignment).
        temperature: Sampling temperature for creativity control.
        max_tokens: Maximum tokens to generate in the response.

    Returns:
        The LLM's text response (stripped of leading/trailing whitespace).
    """
    # Offline-friendly fallback if GROQ_API_KEY is missing or API call fails
    def _fallback_answer() -> str:
        # Try to extract the user message and echo top snippet lines with citations
        user_msg = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        snippet_lines = []
        for line in (user_msg.splitlines() if user_msg else []):
            line = line.strip()
            if line.startswith("[") and "]" in line and "(doc=" in line:
                snippet_lines.append(line)
        snippet_lines = snippet_lines[:3]
        header = "Answer (offline fallback) based on provided snippets: "
        refs = ", ".join([f"[{i+1}]" for i in range(len(snippet_lines))]) or "(no snippets)"
        body = "\n\n" + "\n".join(snippet_lines) if snippet_lines else ""
        return (header + refs + body).strip()

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return _fallback_answer()

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        # Any API failure -> fallback deterministic answer
        return _fallback_answer()
