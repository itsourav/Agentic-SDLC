"""
MODULE 3c - RAG compliance check: is the dominant spec aligned with the design guidelines?

    python -m module3_engineering.rag_check

RAG = Retrieval-Augmented Generation:
  1. INDEX     - embed every guideline chunk once
  2. RETRIEVE  - for each spec attribute, embed a query and pull the top-k most similar chunks
  3. GENERATE  - the model judges compliance using ONLY the retrieved text, and must cite rule IDs
Production path (open source): Qdrant, Chroma or PostgreSQL + pgvector as the vector store; nomic-embed-text or bge-m3 embeddings.
"""
import json
import sys

from common import llm
from common.workspace import data, load, save

GUIDE = data("design_guidelines.json")
ATTRS = {
    "body_colour": lambda d: f"body colour paint {d['body_paint_name']} {d['body_paint']} finish {d['body_paint_finish']} status {d['body_paint_status']}",
    "door_colour": lambda d: f"door colour {d['door_paint_name']} two-tone contrast doors versus body {d['body_paint_name']}",
    "mirror_colour": lambda d: f"exterior mirror cap finish {d['mirror_name']} {d['mirror_code']}",
    "bonnet_design": lambda d: f"bonnet design {d['bonnet_name']} {d['bonnet_code']} pedestrian protection",
    "tyre_style": lambda d: f"wheel tyre fitment {d['wheel_name']} {d['wheel_code']} body style {d['body_style']}",
    "overall": lambda d: f"overall brand design number of exterior colours {d['colour_count']}",
}


class GuidelineIndex:
    def __init__(self):
        self.chunks = GUIDE["guidelines"]
        self.vecs = llm.embed([f"{g['title']}. {g['text']}" for g in self.chunks])

    def search(self, query: str, k: int = 3, attribute: str | None = None):
        qv = llm.embed([query])[0]
        scored = []
        for g, v in zip(self.chunks, self.vecs):
            s = llm.cosine(qv, v)
            if attribute and g.get("applies_to") == attribute:  # metadata filter boost (hybrid retrieval)
                s += 0.3
            scored.append((round(s, 3), g))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]


SCHEMA = {"type": "object", "properties": {"findings": {"type": "array", "items": {"type": "object", "properties": {
    "attribute": {"type": "string"}, "value": {"type": "string"}, "status": {"type": "string", "enum": ["compliant", "needs_review", "non_compliant"]},
    "rule_ids": {"type": "array", "items": {"type": "string"}}, "evidence": {"type": "string"}, "recommendation": {"type": "string"}},
    "required": ["attribute", "value", "status", "rule_ids", "evidence", "recommendation"]}}, "overall": {"type": "string"}},
    "required": ["findings", "overall"]}


def _mock_judge(dom, retrieved):
    """Offline judge: applies the machine-readable 'check' blocks of the RETRIEVED rules only."""
    rank = {"compliant": 0, "needs_review": 1, "non_compliant": 2}
    findings = []
    for attr, hits in retrieved.items():
        status, ids, ev = "compliant", [], []
        for _, g in hits:
            c = g.get("check")
            if not c or (g["applies_to"] not in (attr,)):
                continue
            f = c["field"]
            val = "always" if f == "always" else dom.get(f)
            st = None
            if "fail_unless_body" in c:
                st = "non_compliant" if val in c["codes"] and dom["body_style"].lower() not in c["fail_unless_body"] else "compliant"
            elif "max" in c:
                st = "compliant" if val <= c["max"] else "non_compliant"
            elif val in c.get("fail", []):
                st = "non_compliant"
            elif val in c.get("review", []):
                st = "needs_review"
            elif val in c.get("pass", []):
                st = "compliant"
            if st:
                ids.append(g["id"])
                ev.append(f"{g['id']}: {g['text'][:140]}...")
                if rank[st] > rank[status]:
                    status = st
        val = {"body_colour": dom["body_paint_name"], "door_colour": dom["door_paint_name"], "mirror_colour": dom["mirror_name"],
               "bonnet_design": dom["bonnet_name"], "tyre_style": dom["wheel_name"], "overall": f"{dom['colour_count']} exterior colours"}[attr]
        rec = {"compliant": "No action.", "needs_review": "Raise an engineering review / approval as cited.", "non_compliant": "Change the spec or raise a design deviation."}[status]
        findings.append({"attribute": attr, "value": val, "status": status, "rule_ids": ids, "evidence": " | ".join(ev) or "No applicable rule retrieved.", "recommendation": rec})
    worst = max((f["status"] for f in findings), key=lambda s: rank[s])
    return {"findings": findings, "overall": {"compliant": "Spec is compliant.", "needs_review": "Spec is releasable subject to the reviews flagged.", "non_compliant": "Spec is NOT compliant."}[worst]}


def check(dom: dict, k: int = 3, test_spec_released: bool = False):
    dom = {**dom, "test_spec_released": test_spec_released}
    idx = GuidelineIndex()
    retrieved = {a: idx.search(q(dom), k, a) for a, q in ATTRS.items()}
    context = "\n".join(sorted({f"[{g['id']}] {g['title']}: {g['text']}" for hits in retrieved.values() for _, g in hits}))
    prompt = f"""Check this vehicle specification against the guideline extracts below.
Use ONLY these extracts. Cite rule IDs for every finding. If no extract covers an attribute, say 'needs_review'.
SPEC:
{json.dumps(dom, indent=1)}
GUIDELINE EXTRACTS:
{context}
Return one finding per attribute: {list(ATTRS)}."""
    verdict = llm.generate(prompt, system="You are a homologation and design-compliance engineer.", schema=SCHEMA, mock=lambda: _mock_judge(dom, retrieved))
    return {"retrieval": {a: [{"id": g["id"], "score": s} for s, g in hits] for a, hits in retrieved.items()}, **verdict}


if __name__ == "__main__":
    team = sys.argv[1] if len(sys.argv) > 1 else "team1"
    res = check(load(team, "dominant_spec.json"), test_spec_released=load(team, "test_spec.json") is not None)
    save(team, "compliance.json", res)
    for f in res["findings"]:
        print(f"{f['status']:<14} {f['attribute']:<14} {f['value']:<32} {f['rule_ids']}")
    print(res["overall"])
