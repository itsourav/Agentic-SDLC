"""
MODULE 4b - GUARDRAILS: deterministic checks wrapped AROUND the model.

  user text -> [INPUT RAILS] -> agent + tools -> [OUTPUT RAILS] -> user
Input rails : prompt injection, personal data, off-topic, confidential requests
Output rails: groundedness (every ID must exist in the graph), confidential leak redaction, no purchasing commitments
Production options (open source): NVIDIA NeMo Guardrails, Guardrails AI, Microsoft Presidio for personal data.
"""
import re

from common.workspace import data

from .kg import NODES

POLICY = data("guardrail_policy.json")
ID_RE = re.compile(r"(?<![A-Za-z0-9-])[A-Z]{1,5}(?:-[A-Z0-9]+)+(?![A-Za-z0-9-])")
NAME_TOKENS = {t for n in NODES.values() for t in n["name"].replace("(", " ").replace(")", " ").split()}
EURO_RE = re.compile(r"(€\s?\d[\d.,]*|\d[\d.,]*\s?(?:EUR|€|euros?)\b|EUR\s?\d[\d.,]*)", re.I)
COMMIT_RE = re.compile(r"\b(I have ordered|PO raised|purchase order (has been )?(raised|placed)|I placed an order)\b", re.I)


def _rail(i):
    return next(r for r in POLICY["input_rails"] if r["id"] == i)


def check_input(text: str) -> dict:
    violations, out = [], text
    for p in _rail("IN-01")["patterns"]:
        if re.search(p, text, re.I):
            violations.append({"rail": "IN-01", "name": "Prompt injection", "action": "block"})
            break
    for p in _rail("IN-02")["patterns"]:
        if re.search(p, out):
            out = re.sub(p, "[REDACTED]", out)
            violations.append({"rail": "IN-02", "name": "Personal data", "action": "redact"})
    for p in _rail("IN-04")["patterns"]:
        if re.search(r"\b" + p + r"\b", text, re.I):
            violations.append({"rail": "IN-04", "name": "Commercially confidential", "action": "block"})
            break
    low = text.lower()
    mentions_node = any(n["name"].split()[0].lower() in low for n in NODES.values() if len(n["name"].split()[0]) > 3)
    if not ID_RE.search(text) and not mentions_node and not any(t in low for t in _rail("IN-03")["allowed_topics"]):
        violations.append({"rail": "IN-03", "name": "Off-topic", "action": "block"})
    blocked = any(v["action"] == "block" for v in violations)
    msg = None
    if blocked:
        names = ", ".join(v["name"] for v in violations if v["action"] == "block")
        msg = f"Sorry - I can't help with that ({names}). I answer questions about parts, suppliers, dependencies and supply risk."
    return {"allowed": not blocked, "text": out, "violations": violations, "message": msg}


def check_output(text: str) -> dict:
    violations, out = [], text
    unknown = sorted({i for i in ID_RE.findall(text) if i not in NODES and i not in NAME_TOKENS and not i.startswith(("ISO-", "UN-", "DEG-", "MTS-"))})
    if unknown:
        violations.append({"rail": "OUT-01", "name": "Ungrounded IDs (possible hallucination)", "ids": unknown, "action": "flag"})
    if EURO_RE.search(out) or "unit_cost" in out:
        out = EURO_RE.sub("[CONFIDENTIAL]", out).replace("unit_cost_eur", "[CONFIDENTIAL]")
        violations.append({"rail": "OUT-02", "name": "Confidential cost redacted", "action": "redact"})
    if COMMIT_RE.search(out):
        violations.append({"rail": "OUT-03", "name": "Purchasing commitment language", "action": "flag"})
    return {"text": out, "grounded": not unknown, "violations": violations}
