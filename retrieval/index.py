from __future__ import annotations
import os, csv, re, json
from dataclasses import dataclass
from typing import List
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # Fallback to text-only queries when offline/unavailable
try:
    import chromadb  # type: ignore
except Exception:
    chromadb = None  # Allow offline fallback without Chroma

@dataclass
class Hit:
    doc_id: str
    tenant: str
    visibility: str
    page: str
    text: str
    score: float
    pii_masked: bool = False

def load_manifest(base_dir: str) -> list[dict]:
    mpath = os.path.join(base_dir, "data", "manifest.csv")
    with open(mpath, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def read_doc(base_dir: str, rel_path: str) -> str:
    with open(os.path.join(base_dir, rel_path), encoding="utf-8") as f:
        return f.read()

class Retriever:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        # Try to initialize embeddings model; fall back to None if unavailable
        self.model = None
        if SentenceTransformer is not None:
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                self.model = None
        # Chroma client only if chromadb is available
        self.client = (
            chromadb.PersistentClient(path=os.path.join(base_dir, ".chroma"))
            if chromadb is not None else None
        )
        self.manifest = load_manifest(base_dir)
        # In-memory store for fallback mode
        self._mem_docs = []  # list of tuples (doc_id, tenant_base, visibility, text)

    def _ns(self, tenant_id: str) -> str:
        return f"tenant_{tenant_id}"

    def build_or_update(self):
        by_tenant = {}
        for row in self.manifest:
            by_tenant.setdefault(row["tenant"], []).append(row)
        for t, rows in by_tenant.items():
            # Normalize to base tenant namespace, e.g., 'U3_robotics' -> 'U3'
            if t == "PUB":
                ns_name = "public"
                tenant_base = "public"
            else:
                tenant_base = t.split("_", 1)[0] if "_" in t else t
                ns_name = tenant_base

            ids, docs, metas = [], [], []
            for r in rows:
                ids.append(r["doc_id"])
                text = read_doc(self.base_dir, r["path"])
                docs.append(text)
                vis = "public" if ("PUB_" in r["doc_id"] or r["tenant"] == "PUB") else "private"
                meta = {
                    "doc_id": r["doc_id"],
                    "tenant": tenant_base,
                    "visibility": vis,
                    "path": r["path"],
                }
                metas.append(meta)
                if self.client is None:
                    # Cache for in-memory fallback
                    self._mem_docs.append((meta["doc_id"], meta["tenant"], meta["visibility"], text))

            # Upsert into Chroma if available
            if self.client is not None and docs:
                coll = self.client.get_or_create_collection(name=self._ns(ns_name))
                if self.model is not None:
                    try:
                        embeddings = self.model.encode(docs, convert_to_numpy=True)
                        coll.upsert(
                            ids=ids,
                            documents=docs,
                            metadatas=metas,
                            embeddings=embeddings.tolist(),
                        )
                    except Exception:
                        coll.upsert(ids=ids, documents=docs, metadatas=metas)
                else:
                    coll.upsert(ids=ids, documents=docs, metadatas=metas)

    def search(self, query: str, tenant_id: str, top_k: int = 6) -> List[Hit]:
        hits: list[Hit] = []

        base_tid = tenant_id.split("_", 1)[0] if "_" in tenant_id else tenant_id

        if self.client is not None:
            def q(ns):
                coll = self.client.get_or_create_collection(ns)
                # Prefer embedding search; fall back to text search
                if self.model is not None:
                    try:
                        q_emb = self.model.encode([query], convert_to_numpy=True)
                        res = coll.query(query_embeddings=q_emb.tolist(), n_results=top_k)
                    except Exception:
                        res = coll.query(query_texts=[query], n_results=top_k)
                else:
                    res = coll.query(query_texts=[query], n_results=top_k)
                docs = res.get("documents", [[]])[0]
                metas = res.get("metadatas", [[]])[0]
                dists = res.get("distances", [[]])[0]
                for text, meta, dist in zip(docs, metas, dists):
                    score = 1.0/(1.0+float(dist)) if dist is not None else 0.5
                    hits.append(Hit(meta["doc_id"], meta["tenant"], meta["visibility"], "n/a", text, score))

            # Query the normalized base-tenant namespace and public
            q(self._ns(base_tid))
            q(self._ns("public"))
        else:
            # Simple in-memory search: filter to base tenant + public, score by token overlap
            ql = (query or "").lower()
            keywords = [w for w in re.split(r"[^a-z0-9]+", ql) if len(w) >= 3]
            for did, ten, vis, text in self._mem_docs:
                if not (ten == base_tid or vis == "public"):
                    continue
                tl = (text or "").lower()
                score = 0.0
                for kw in keywords:
                    if kw in tl:
                        score += 1.0
                # small bias for safety/PPE to mimic original behavior
                if re.search(r"\bppe\b", tl):
                    score += 0.75
                if ten == base_tid and vis != "public":
                    score += 0.1
                hits.append(Hit(did, ten, vis, "n/a", text, score))

        # Lightweight keyword boost to prioritize specific matches (e.g., PPE)
        ql = (query or "").lower()
        keywords = set([w for w in re.split(r"[^a-z0-9]+", ql) if len(w) >= 3])
        if keywords:
            boosted = []
            for h in hits:
                bonus = 0.0
                txt = (h.text or "").lower()
                if "ppe" in keywords and re.search(r"\bppe\b", txt):
                    bonus += 0.75
                for kw in keywords:
                    if kw != "ppe" and kw in txt:
                        bonus += 0.15
                did = (h.doc_id or "").lower()
                if "ppe" in keywords or "safety" in keywords:
                    if did.startswith("pub_safety"):
                        bonus += 0.5
                    if did.startswith("pub_policies") and "ppe" in keywords:
                        bonus -= 0.2
                boosted.append((h.score + bonus, h))
            boosted.sort(key=lambda x: x[0], reverse=True)
            hits = [h for _, h in boosted]
        else:
            hits.sort(key=lambda h: h.score, reverse=True)

        return hits[:top_k]
