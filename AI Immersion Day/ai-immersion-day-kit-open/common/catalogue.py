"""Shared catalogue lookups (used by the MCP server, reconciliation and the knowledge graph)."""
import difflib
from .workspace import data

CAT = data("paint_catalogue.json")


def _best(items, text, keys=("name", "synonyms")):
    t = (text or "").lower().strip()
    if not t:
        return None, 0.0
    best, score = None, 0.0
    for it in items:
        cands = [it.get("name", "").lower(), it.get("code", "").lower()] + [s.lower() for s in it.get("synonyms", [])]
        for c in cands:
            s = 1.0 if c == t else (0.9 if c and (c in t or t in c) else difflib.SequenceMatcher(None, c, t).ratio())
            if s > score:
                best, score = it, s
    return best, round(score, 2)


def lookup_paint(colour: str) -> dict:
    p, s = _best(CAT["paints"], colour)
    if not p or s < 0.55:
        return {"query": colour, "match": None, "status": "unknown", "confidence": s}
    return {"query": colour, "code": p["code"], "name": p["name"], "finish": p["finish"], "status": p["status"], "hex": p["hex"], "confidence": s}


def lookup_bonnet(design: str) -> dict:
    b, s = _best(CAT["bonnets"], design)
    return {"query": design, "code": b["code"] if b and s >= 0.5 else "BN-FLAT", "name": b["name"] if b and s >= 0.5 else "Flat bonnet (default)", "confidence": s}


def lookup_wheel(style: str) -> dict:
    w, s = _best(CAT["wheels"], style)
    return {"query": style, "code": w["code"] if w and s >= 0.5 else "WH-5S-19", "name": w["name"] if w and s >= 0.5 else "19in Aero 5-spoke (default)", "confidence": s}


def lookup_mirror(mirror_colour: str, body_colour: str = "") -> dict:
    m = lookup_paint(mirror_colour)
    b = lookup_paint(body_colour) if body_colour else {}
    t = (mirror_colour or "").lower()
    if "carbon" in t:
        code = "MR-CARBON"
    elif m.get("code") and m.get("code") == b.get("code"):
        code = "MR-BODY"
    elif m.get("code") == "OB-900":
        code = "MR-GB"
    elif m.get("code") == "LS-450":
        code = "MR-SILVER"
    elif "body" in t or "same" in t:
        code = "MR-BODY"
    else:
        code = "MR-CUSTOM"
    name = next(x["name"] for x in CAT["mirror_caps"] if x["code"] == code)
    return {"query": mirror_colour, "code": code, "name": name}


def canonicalise(spec: dict) -> dict:
    """Turn free-text spec from the vision model into catalogue codes."""
    body = lookup_paint(spec.get("body_colour", ""))
    door = lookup_paint(spec.get("door_colour", "") or spec.get("body_colour", ""))
    mirror = lookup_mirror(spec.get("mirror_colour", ""), spec.get("body_colour", ""))
    bonnet = lookup_bonnet(spec.get("bonnet_design", ""))
    wheel = lookup_wheel(spec.get("tyre_style", ""))
    return {
        "body_paint": body.get("code") or "UNKNOWN", "body_paint_name": body.get("name") or spec.get("body_colour"),
        "body_paint_status": body.get("status", "unknown"), "body_paint_finish": body.get("finish", "unknown"),
        "door_paint": door.get("code") or "UNKNOWN", "door_paint_name": door.get("name") or spec.get("door_colour"),
        "mirror_code": mirror["code"], "mirror_name": mirror["name"],
        "bonnet_code": bonnet["code"], "bonnet_name": bonnet["name"],
        "wheel_code": wheel["code"], "wheel_name": wheel["name"],
        "body_style": (spec.get("body_style") or "coupe").lower(),
    }
