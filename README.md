# Agentic RAG — Multi-Tenant Research Assistant
**Author:** Abdullah Naeem

A secure, multi-tenant Retrieval-Augmented Generation (RAG) pipeline that answers research queries using tenant-scoped document retrieval, ACL enforcement, PII masking, and LLM-based synthesis.

## Architecture

```
User Query
    │
    ▼
┌──────────┐     ┌────────────┐     ┌──────────────┐     ┌───────────────┐
│  Planner │────▶│  Retriever │────▶│ Policy Guard │────▶│ LLM Synth.    │
│(injection│     │ (ChromaDB  │     │  (ACL + PII  │     │ (Groq LLaMA)  │
│ detector)│     │  + embeddings)│  │   masking)   │     │               │
└──────────┘     └────────────┘     └──────────────┘     └───────────────┘
```

### Pipeline Stages

1. **Planner** (`agents/planner.py`) — Detects injection attacks and prohibited data requests using regex-based pattern matching. Cleans the user query for retrieval.
2. **Retriever** (`retrieval/index.py`) — Indexes documents per-tenant into ChromaDB with sentence-transformer embeddings. Searches the tenant's namespace plus the public namespace.
3. **Policy Guard** (`retrieval/search.py`) — Enforces ACL rules (only public docs or docs belonging to the active tenant are allowed). Masks PII patterns (CNIC, phone numbers) with `[REDACTED]`.
4. **LLM Synthesizer** (`agents/controller.py`) — Formats allowed snippets into a prompt and calls the Groq API (LLaMA 3.1) to generate a cited answer. Falls back to a deterministic offline response if no API key is set.

## Security Features

- **Tenant Isolation**: Each tenant (U1–U4) can only access their own private documents plus public documents.
- **Cross-Tenant Blocking**: Queries mentioning other tenants are refused before retrieval.
- **Injection Detection**: Prompt injection attempts (e.g., "ignore previous instructions") are caught and refused.
- **PII Masking**: CNIC numbers and Pakistani phone numbers are automatically redacted.
- **Citation Fidelity**: Answers must cite retrieved documents; fabricated citations trigger a refusal.

## Setup

### Prerequisites

- Python 3.10+
- A [Groq API key](https://console.groq.com/) (optional — the app falls back to offline mode without one)

### Installation

```bash
# Clone the repository
git clone https://github.com/abdulah-naeem/Agentic-Assignment-2-RAG.git
cd Agentic-Assignment-2-RAG

# Install dependencies
pip install -r requirements.txt

# Set your Groq API key (optional)
export GROQ_API_KEY="gsk_..."       # Linux/macOS
set GROQ_API_KEY=gsk_...            # Windows CMD
$env:GROQ_API_KEY="gsk_..."         # PowerShell
```

## Usage

### Single-Turn Query

```bash
python -m app.main --tenant U1 --query "What PPE is required in wet labs?"
```

### Interactive Chat REPL

```bash
python -m app.main --tenant U2 --chat
```

REPL commands:
- `/exit` — Quit the REPL
- `/clear` — Clear the current tenant's conversation memory
- `/mode buffer|summary|none` — Switch memory mode

### Memory Modes

| Mode | Description |
|------|-------------|
| `buffer` | Stores full conversation turns in a JSONL file |
| `summary` | Appends user/assistant pairs as plain text |
| `none` | No memory persistence |

### Run Evaluation

```bash
python -m eval.run_eval --config config.yaml
```

Reads per-tenant question files (`eval/U1.json` – `eval/U4.json`) and writes results to `eval/results.json`.

### Run Red-Team Tests

```bash
python -m tools.run_redteam --config config.yaml
```

Runs adversarial prompts from `tests/redteam_prompts.json` and writes results to `eval/redteam_results.json`.

### Run Unit Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
├── agents/
│   ├── controller.py    # Main agent orchestration
│   ├── llm.py           # Groq LLM wrapper with offline fallback
│   └── planner.py       # Injection & prohibited query detection
├── app/
│   ├── main.py          # CLI entry point (single-turn & REPL)
│   └── clear_memory.py  # Memory cleanup utility
├── data/
│   ├── manifest.csv     # Document registry (doc_id, tenant, path)
│   ├── tenant_acl.csv   # ACL reference (visibility, PII flags)
│   ├── L1_genomics/     # U1 tenant documents
│   ├── L2_nlp/          # U2 tenant documents
│   ├── L3_robotics/     # U3 tenant documents
│   ├── L4_materials/    # U4 tenant documents
│   └── public/          # Public documents (all tenants)
├── retrieval/
│   ├── index.py         # ChromaDB indexing & search
│   └── search.py        # Policy guard (ACL + PII masking)
├── policies/
│   └── guard.py         # Refusal templates & policy application
├── eval/
│   ├── run_eval.py      # Automated evaluation harness
│   └── U[1-4].json      # Per-tenant evaluation questions
├── tools/
│   └── run_redteam.py   # Adversarial red-team runner
├── tests/
│   ├── test_acl.py      # Cross-tenant access test
│   ├── test_injection.py # Injection detection test
│   ├── test_pii.py      # PII masking test
│   └── redteam_prompts.json
├── config.yaml          # LLM & retrieval configuration
└── requirements.txt     # Python dependencies
```

## Configuration

Edit `config.yaml` to customize:

```yaml
llm:
  provider: groq
  model: llama-3.1-8b-instant
  temperature: 0.0
  max_tokens: 800

retrieval:
  backend: chroma
  top_k: 6
  chunk_size: 700
  chunk_overlap: 120

logging:
  path: logs/run.jsonl
```

## License

This project is for academic/educational purposes.
