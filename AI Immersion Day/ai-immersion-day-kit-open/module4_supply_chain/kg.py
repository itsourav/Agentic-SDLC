"""
MODULE 4a - Parts KNOWLEDGE GRAPH (open edition: NetworkX)

Nodes: Option (what the customer picks) -> Part -> raw material ... -> Supplier
Edges: REQUIRES, SUPPLIED_BY, ALTERNATIVE
Why a graph? Questions like "what breaks if TaiSemi stops shipping?" are multi-hop
relationship questions - easy as graph traversal, unreliable as free-text search.
Production path (open source): Neo4j Community Edition (Cypher) or Apache AGE on PostgreSQL;
the agent calls it as a tool exactly like below.

    python -m module4_supply_chain.kg BN-SCOOP
    python -m module4_supply_chain.kg --what-if S-SEMITW
"""
import json
import sys

import networkx as nx

from common.catalogue import _best
from common.workspace import data

KG = data("parts_knowledge_graph.json")
CONFIDENTIAL = set(KG["confidential_fields"])
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

G = nx.MultiDiGraph()
for n in KG["nodes"]:
    G.add_node(n["id"], **n)
for e in KG["edges"]:
    G.add_edge(e["source"], e["target"], key=e["type"], type=e["type"], note=e.get("note"))
NODES = dict(G.nodes(data=True))

# Sub-graph of REQUIRES edges only: option -> part -> raw material
REQ = nx.DiGraph([(u, v) for u, v, k in G.edges(keys=True) if k == "REQUIRES"])
REQ.add_nodes_from(G.nodes)


def public(node: dict) -> dict:
    """Strip confidential fields before anything leaves the graph (a guardrail at the data layer)."""
    return {k: v for k, v in node.items() if k not in CONFIDENTIAL}


def supplier_of(part_id: str):
    for _, v, k in G.out_edges(part_id, keys=True):
        if k == "SUPPLIED_BY":
            return NODES[v]
    return None


def find_node(name_or_id: str) -> dict:
    """Resolve a free-text name ('bonnet scoop', 'TaiSemi') or an ID to a node."""
    if name_or_id.upper() in NODES:
        return public(NODES[name_or_id.upper()])
    items = [{"name": n["name"], "code": i, "synonyms": []} for i, n in NODES.items()]
    best, score = _best(items, name_or_id)
    return public(NODES[best["code"]]) | {"match_confidence": score} if best and score > 0.5 else {"error": f"No node matches '{name_or_id}'"}


def get_dependencies(node_id: str, max_depth: int = 6) -> dict:
    """Every part a spec option or part needs (transitively), with lead time and supplier risk."""
    node_id = node_id.upper()
    if node_id not in NODES:
        return {"error": f"Unknown node {node_id}"}
    paths = nx.single_source_shortest_path(REQ, node_id, cutoff=max_depth)
    rows = []
    for pid, path in sorted(paths.items(), key=lambda kv: (len(kv[1]), kv[0])):
        if pid == node_id:
            continue
        p, s = NODES[pid], supplier_of(pid) or {}
        rows.append({"id": pid, "name": p["name"], "depth": len(path) - 1, "path": " -> ".join(path),
                     "lead_time_days": p.get("lead_time_days"), "stock_weeks": p.get("stock_weeks"),
                     "supplier": s.get("id"), "supplier_risk": s.get("risk")})
    root = public(NODES[node_id])
    rs = supplier_of(node_id)
    if rs:
        root["supplier"], root["supplier_name"], root["supplier_risk"] = rs["id"], rs["name"], rs["risk"]
    longest = max(rows, key=lambda r: r["lead_time_days"] or 0, default=None)
    return {"root": root, "dependencies": rows, "count": len(rows),
            "longest_lead_time": {"id": longest["id"], "days": longest["lead_time_days"], "path": longest["path"]} if longest else None,
            "high_risk": [r["id"] for r in rows if r["supplier_risk"] == "high"]}


def supplier_impact(supplier_id: str) -> dict:
    """If this supplier stops shipping, which parts and customer options are hit? (reverse traversal)"""
    s = find_node(supplier_id)
    if "error" in s or s.get("type") != "Supplier":
        return {"error": f"Unknown supplier {supplier_id}"}
    parts = [u for u, _, k in G.in_edges(s["id"], keys=True) if k == "SUPPLIED_BY"]
    affected = set().union(*(nx.ancestors(REQ, p) for p in parts)) if parts else set()
    return {"supplier": s, "parts_supplied": parts,
            "affected_options": sorted(a for a in affected if NODES[a]["type"] == "Option"),
            "affected_intermediate_parts": sorted(a for a in affected if NODES[a]["type"] == "Part")}


def find_alternatives(part_id: str) -> dict:
    part_id = part_id.upper()
    alts = [{"id": v, "name": NODES[v]["name"], "note": d.get("note"), "supplier": (supplier_of(v) or {}).get("id"),
             "lead_time_days": NODES[v].get("lead_time_days")}
            for _, v, d in G.out_edges(part_id, data=True) if d["type"] == "ALTERNATIVE"]
    alts += [{"id": u, "name": NODES[u]["name"], "note": d.get("note")} for u, _, d in G.in_edges(part_id, data=True) if d["type"] == "ALTERNATIVE"]
    return {"part": part_id, "alternatives": alts or "No qualified alternative in the graph"}


def single_points_of_failure(option_ids: list[str] | None = None) -> dict:
    """Parts shared by 2+ different option families (e.g. mirrors AND bonnet AND wheels)."""
    opts = option_ids or [i for i, n in NODES.items() if n["type"] == "Option"]
    used = {}
    for o in opts:
        for d in nx.descendants(REQ, o):
            used.setdefault(d, set()).add(NODES[o]["attribute"])
    spof = [{"id": p, "name": NODES[p]["name"], "used_by_option_families": sorted(f), "supplier": (supplier_of(p) or {}).get("id"),
             "supplier_risk": (supplier_of(p) or {}).get("risk"), "lead_time_days": NODES[p].get("lead_time_days")}
            for p, f in used.items() if len(f) >= 2]
    spof.sort(key=lambda r: (-len(r["used_by_option_families"]), -RISK_ORDER.get(r["supplier_risk"] or "low", 0)))
    return {"single_points_of_failure": spof}


def spec_codes(spec: dict) -> list[str]:
    codes = [spec[k] for k in ("body_paint", "mirror_code", "bonnet_code", "wheel_code") if spec.get(k) in NODES]
    if spec.get("door_paint") != spec.get("body_paint") and spec.get("door_paint") in NODES:
        codes.append(spec["door_paint"])
    return codes


def spec_risk_report(spec: dict) -> dict:
    """Supply-chain readiness for the engineering dominant spec."""
    codes = spec_codes(spec)
    per = {c: get_dependencies(c) for c in codes}
    crit = max(((c, r["longest_lead_time"]) for c, r in per.items() if r["longest_lead_time"]), key=lambda x: x[1]["days"])
    high = sorted({h for r in per.values() for h in r["high_risk"]})
    return {"options": codes, "critical_path": {"option": crit[0], **crit[1]},
            "high_risk_parts": [{"id": h, "supplier": supplier_of(h)["id"], "alternatives": find_alternatives(h)["alternatives"]} for h in high],
            "single_points_of_failure": single_points_of_failure(codes)["single_points_of_failure"],
            "per_option": {c: {"parts": r["count"], "longest_lead_time": r["longest_lead_time"]} for c, r in per.items()}}


def spec_suppliers(spec: dict) -> list[dict]:
    """Suppliers that feed this spec (for the what-if picker), riskiest first."""
    ids = {supplier_of(d)["id"] for c in spec_codes(spec) for d in nx.descendants(REQ, c) if supplier_of(d)}
    return sorted((NODES[i] for i in ids), key=lambda s: (-RISK_ORDER[s["risk"]], s["name"]))


def what_if(spec: dict, supplier_id: str) -> dict:
    """Knock out one supplier: which parts and which of THIS spec's options go dark?"""
    imp = supplier_impact(supplier_id)
    if "error" in imp:
        return imp
    hit_parts = set(imp["parts_supplied"]) | set(imp["affected_intermediate_parts"])
    codes = spec_codes(spec)
    hit_options = [c for c in codes if c in imp["affected_options"]]
    alts = {p: find_alternatives(p)["alternatives"] for p in imp["parts_supplied"]}
    return {"supplier": imp["supplier"], "parts_lost": sorted(hit_parts), "spec_options_hit": hit_options,
            "spec_options_safe": [c for c in codes if c not in hit_options], "alternatives": alts}


def to_dot(spec: dict, disrupted: str | None = None) -> str:
    """Graphviz DOT for the spec's sub-graph. With `disrupted`, knocked-out nodes turn red and get a thick border."""
    risk_fill = {"high": "#f4a6a6", "medium": "#ffd88a", "low": "#bfe3c0"}
    hit = set()
    if disrupted:
        w = what_if(spec, disrupted)
        hit = set(w.get("parts_lost", [])) | set(w.get("spec_options_hit", []))
    lines = ['digraph G { rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", fontname=Helvetica, fontsize=10];']
    seen = set()
    for c in spec_codes(spec):
        style = 'fillcolor="#d9534f", fontcolor="white", penwidth=3' if c in hit else 'fillcolor="#9ec5fe"'
        lines.append(f'"{c}" [{style}, label="{c}\\n{NODES[c]["name"]}"];')
        for u, v in nx.bfs_edges(REQ, c):
            if (u, v) in seen:
                continue
            seen.add((u, v))
            s = supplier_of(v) or {}
            if v in hit:
                style = 'fillcolor="#d9534f", fontcolor="white", penwidth=3'
            else:
                style = 'fillcolor="#e9ecef", fontcolor="#888888"' if hit else f'fillcolor="{risk_fill.get(s.get("risk"), "#eeeeee")}"' 
            lines.append(f'"{v}" [{style}, label="{v}\\n{NODES[v].get("lead_time_days")}d · {s.get("id")}"];')
            lines.append(f'"{u}" -> "{v}"' + (' [color="#d9534f", penwidth=2]' if v in hit else "") + ";")
    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--what-if":
        from common.workspace import load

        print(json.dumps(what_if(load("team1", "dominant_spec.json") or {}, sys.argv[2]), indent=1))
    else:
        print(json.dumps(get_dependencies(sys.argv[1] if len(sys.argv) > 1 else "BN-SCOOP"), indent=1))
