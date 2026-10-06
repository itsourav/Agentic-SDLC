"""
MODULE 4c - Supply-chain agent = model + knowledge-graph tools, wrapped in guardrails.

    python -m module4_supply_chain.agent "What happens if TaiSemi stops shipping?"
"""
import json
import re
import sys

from common import llm

from . import guardrails, kg

SYSTEM = """You are the Meridian Motors supply-chain risk analyst.
Rules:
- Answer ONLY from knowledge-graph tool results. Never invent part numbers, suppliers or lead times.
- Always quote node IDs (e.g. CHIP-MCU-7) and lead times in days.
- Never disclose costs or prices (confidential).
- You give analysis and recommendations; you never place orders.
- Finish with a one-line 'Recommended action'."""

ID_RE = re.compile(r"(?<![A-Za-z0-9-])[A-Z]{1,5}(?:-[A-Z0-9]+)+(?![A-Za-z0-9-])")


def _first_id(p, types=None):
    for i in ID_RE.findall(p):
        if i in kg.NODES and (not types or kg.NODES[i]["type"] in types):
            return i
    return None


def _supplier_in(p):
    sid = _first_id(p, {"Supplier"})
    if sid:
        return sid
    for n in kg.NODES.values():
        if n["type"] == "Supplier" and n["name"].split()[0].lower() in p.lower():
            return n["id"]
    return None


TOOLS = [
    llm.Tool("find_node", "Resolve a free-text part/option/supplier name to its graph node and ID.",
             {"type": "object", "properties": {"name_or_id": {"type": "string"}}, "required": ["name_or_id"]}, kg.find_node),
    llm.Tool("get_dependencies", "All parts an option or part requires (multi-hop), with lead times, suppliers and risk, plus the longest lead-time path.",
             {"type": "object", "properties": {"node_id": {"type": "string"}}, "required": ["node_id"]}, kg.get_dependencies,
             mock_trigger=lambda p: (lambda i: {"node_id": i} if i else None)(_first_id(p, {"Option", "Part"}) if not re.search(r"alternative", p, re.I) else None)),
    llm.Tool("supplier_impact", "If a supplier stops shipping: which parts and customer-facing options are affected.",
             {"type": "object", "properties": {"supplier_id": {"type": "string"}}, "required": ["supplier_id"]}, kg.supplier_impact,
             mock_trigger=lambda p: (lambda s: {"supplier_id": s} if s and re.search(r"stop|disrupt|affect|impact|fail|lose", p, re.I) else None)(_supplier_in(p))),
    llm.Tool("find_alternatives", "Qualified alternative / second-source parts for a part.",
             {"type": "object", "properties": {"part_id": {"type": "string"}}, "required": ["part_id"]}, kg.find_alternatives,
             mock_trigger=lambda p: (lambda i: {"part_id": i} if i and re.search(r"alternative|second source|substitute", p, re.I) else None)(_first_id(p, {"Part"}))),
    llm.Tool("single_points_of_failure", "Parts shared across several option families (mirror, bonnet, wheels, paint) - hidden concentration risk.",
             {"type": "object", "properties": {"option_ids": {"type": "array", "items": {"type": "string"}}}}, kg.single_points_of_failure,
             mock_trigger=lambda p: {} if re.search(r"shared|single point|common part|concentration", p, re.I) else None),
]


def _mock_answer(prompt, trace):
    lines = []
    for s in trace:
        if s["type"] != "tool_call":
            continue
        r = s["result"]
        if s["name"] == "get_dependencies" and "root" in r:
            root = r["root"]
            head = f"{root['id']} ({root['name']})"
            if root.get("supplier"):
                head += f" is supplied by {root['supplier']} ({root['supplier_name']}, risk {root['supplier_risk']})"
            lines.append(head + f" and requires {r['count']} parts:")
            lines += [f"- {d['id']} {d['name']}: {d['lead_time_days']} days, {d['supplier']} (risk {d['supplier_risk']})" for d in r["dependencies"]]
            if r["longest_lead_time"]:
                lt = r["longest_lead_time"]
                lines.append(f"Longest lead time: {lt['id']} at {lt['days']} days via {lt['path']}.")
        elif s["name"] == "supplier_impact" and "supplier" in r:
            lines.append(f"If {r['supplier']['id']} ({r['supplier']['name']}, risk {r['supplier']['risk']}) stops shipping, parts {', '.join(r['parts_supplied'])} "
                         f"are lost, affecting options: {', '.join(r['affected_options'])}.")
        elif s["name"] == "find_alternatives":
            alts = r["alternatives"]
            lines.append(f"Alternatives for {r['part']}: " + (", ".join(f"{a['id']} ({a.get('note')})" for a in alts) if isinstance(alts, list) else alts))
        elif s["name"] == "single_points_of_failure":
            top = r["single_points_of_failure"][:3]
            lines.append("Shared parts across option families: " + "; ".join(f"{t['id']} used by {', '.join(t['used_by_option_families'])} (supplier {t['supplier']}, risk {t['supplier_risk']})" for t in top))
    if not lines:
        return "I could not find that in the knowledge graph. Please give a part, option or supplier ID."
    return "\n".join(lines) + "\nRecommended action: review high-risk suppliers and qualify alternatives on the critical path."


def ask(question: str) -> dict:
    """Full guarded pipeline: input rails -> agent -> output rails."""
    gin = guardrails.check_input(question)
    if not gin["allowed"]:
        return {"answer": gin["message"], "blocked": True, "input_rails": gin, "output_rails": None, "trace": []}
    res = llm.run_agent(gin["text"], TOOLS, system=SYSTEM, max_steps=8, mock_answer=_mock_answer)
    gout = guardrails.check_output(res.text)
    return {"answer": gout["text"], "blocked": False, "input_rails": gin, "output_rails": gout, "trace": res.trace, "seconds": round(res.seconds, 2)}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What happens if S-SEMITW stops shipping?"
    r = ask(q)
    for s in r["trace"]:
        if s["type"] == "tool_call":
            print("TOOL", s["name"], json.dumps(s["args"]))
    print(r["answer"])
    print("rails:", r["input_rails"]["violations"], (r["output_rails"] or {}).get("violations"))
