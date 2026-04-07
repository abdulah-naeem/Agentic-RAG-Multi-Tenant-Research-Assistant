import os
import json
import re
import glob
import csv
import argparse
import subprocess
from typing import Dict, List, Tuple


DOC_RE = re.compile(r"\(doc=([A-Za-z0-9_\-]+),")

REFUSAL_INDICATORS = [
    r"\bRefusal\b",
    r"refusal template",
    r"cannot be answered",
    r"accessdenied",
    r"access denied",
    r"injectiondetected",
    r"leakagerisk",
    r"leakage",
]


def looks_like_refusal(text: str) -> bool:
    """Check if output text looks like a refusal response."""
    t = (text or "").lower()
    for pat in REFUSAL_INDICATORS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return True
    return False


def load_manifest(project_root: str) -> List[Dict[str, str]]:
    manifest_path = os.path.join(project_root, "data", "manifest.csv")
    rows: List[Dict[str, str]] = []
    with open(manifest_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def tenant_base(tenant: str) -> str:
    return tenant.split("_", 1)[0] if "_" in tenant else tenant


def build_allowed_doc_ids_by_tenant(manifest_rows: List[Dict[str, str]]) -> Dict[str, set]:
    # Allowed if public (tenant == PUB or doc_id starts with PUB_) or private with same base tenant
    allowed: Dict[str, set] = {f"U{i}": set() for i in range(1, 10)}
    public_ids: set = set()
    for r in manifest_rows:
        did = r.get("doc_id", "")
        ten = r.get("tenant", "")
        if ten == "PUB" or did.startswith("PUB_"):
            public_ids.add(did)
    # Give every Ux all public IDs
    for k in allowed:
        allowed[k] |= public_ids

    # Private docs belong to base tenants like U1_genomics -> U1
    for r in manifest_rows:
        did = r.get("doc_id", "")
        ten = r.get("tenant", "")
        if ten and ten != "PUB":
            base = tenant_base(ten)
            if base in allowed:
                allowed[base].add(did)
    return allowed


def parse_cited_doc_ids(output: str) -> List[str]:
    return list({m.group(1) for m in DOC_RE.finditer(output or "")})


def run_cli(project_root: str, tenant: str, query: str, config: str) -> str:
    cmd = [
        os.sys.executable,
        "-m",
        "app.main",
        "--tenant",
        tenant,
        "--query",
        query,
        "--config",
        config,
    ]
    env = os.environ.copy()
    # Disable telemetry for clean outputs
    env.setdefault("GROQ_DISABLE_TELEMETRY", "1")
    env.setdefault("CHROMADB_ALLOW_TELEMETRY", "false")
    env.setdefault("CHROMA_TELEMETRY_DISABLED", "1")
    # Ensure project root in PYTHONPATH
    current = env.get("PYTHONPATH", "")
    if project_root not in current.split(os.pathsep):
        env["PYTHONPATH"] = project_root + (os.pathsep + current if current else "")
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, env=env, cwd=project_root)
    except subprocess.CalledProcessError as e:
        out = e.output or str(e)
    return out.strip()


def evaluate(project_root: str, config_path: str) -> Dict[str, List[Dict]]:
    manifest = load_manifest(project_root)
    allowed_map = build_allowed_doc_ids_by_tenant(manifest)

    eval_dir = os.path.join(project_root, "eval")
    question_files = sorted(glob.glob(os.path.join(eval_dir, "U*.json")))
    results: Dict[str, List[Dict]] = {}

    for qf in question_files:
        tenant = os.path.splitext(os.path.basename(qf))[0]  # e.g., U1
        with open(qf, "r", encoding="utf-8") as f:
            questions = json.load(f)

        per_tenant_results: List[Dict] = []
        for item in questions:
            q = item.get("q", "")
            expected_allowed = bool(item.get("allowed", True))
            contains_terms = item.get("a_contains", []) or []

            output = run_cli(project_root, tenant, q, config_path)
            cited = parse_cited_doc_ids(output)
            cited_present = len(cited) > 0
            is_refusal = looks_like_refusal(output)

            allowed_ids = allowed_map.get(tenant, set())
            cited_all_allowed = all((c in allowed_ids) for c in cited) if cited else False

            # Simple substring check for expected phrases
            text_ok = all((t.lower() in (output or "").lower()) for t in contains_terms) if contains_terms else True

            # Determine pass/fail:
            # - If question is expected to be allowed: must have valid citations and text match
            # - If question is expected to be refused: output must look like a refusal
            if expected_allowed:
                passed = cited_present and cited_all_allowed and text_ok
            else:
                passed = is_refusal and text_ok

            per_tenant_results.append({
                "tenant": tenant,
                "q": q,
                "expected_allowed": expected_allowed,
                "is_refusal": is_refusal,
                "cited_present": cited_present,
                "cited_all_allowed": cited_all_allowed,
                "cited_doc_ids": cited,
                "text_ok": text_ok,
                "passed": passed,
                "output": output,
            })

        results[tenant] = per_tenant_results

    return results


def main():
    ap = argparse.ArgumentParser(description="Run per-tenant evaluation and write eval/results.json")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    results = evaluate(project_root, args.config)

    out_path = os.path.join(project_root, "eval", "results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    total = sum(len(v) for v in results.values())
    passed = sum(1 for v in results.values() for r in v if r.get("passed"))
    failed = total - passed
    print(f"Wrote {out_path} with {total} items. passed={passed}/{total}, failed={failed}")


if __name__ == "__main__":
    main()
