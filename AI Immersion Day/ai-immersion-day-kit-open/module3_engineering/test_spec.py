"""
MODULE 3b - Generate a body-colour TEST SPECIFICATION from the dominant spec.

    python -m module3_engineering.test_spec

Concept: grounded generation - the model writes the document, but it must use the
standards template (context) and the catalogue facts; output is schema-checked JSON.
"""
import json
import sys
from datetime import date

from common import catalogue, llm
from common.workspace import data, load, save

STANDARDS = data("paint_test_standards.json")

SCHEMA = {
    "type": "object",
    "properties": {
        "spec_id": {"type": "string"}, "title": {"type": "string"}, "paint_code": {"type": "string"}, "paint_name": {"type": "string"},
        "finish": {"type": "string"}, "scope": {"type": "string"},
        "tests": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "name": {"type": "string"}, "method": {"type": "string"}, "standard": {"type": "string"},
            "acceptance_criteria": {"type": "string"}, "sample_size": {"type": "string"}, "frequency": {"type": "string"}},
            "required": ["id", "name", "method", "standard", "acceptance_criteria", "sample_size", "frequency"]}},
        "additional_checks": {"type": "array", "items": {"type": "string"}},
        "release_conditions": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["spec_id", "title", "paint_code", "paint_name", "finish", "scope", "tests", "release_conditions", "risks"],
}


def build_test_spec(dominant: dict) -> dict:
    paint = next(p for p in catalogue.CAT["paints"] if p["code"] == dominant["body_paint"]) if dominant["body_paint"] != "UNKNOWN" else {
        "code": "UNKNOWN", "name": dominant.get("body_paint_name"), "finish": "solid", "status": "unknown", "lab": None}
    sid = f"MTS-PAINT-{paint['code']}-{date.today():%Y%m%d}"

    def mock():
        tests = []
        for t in STANDARDS["tests"]:
            lim = t["default_limit"]
            if t["id"] == "T01":
                lim = ("<= 1.2" if paint["finish"] in ("metallic", "pearl") else "<= 1.0") + f" vs master panel L*a*b* {paint.get('lab')}"
            tests.append({"id": t["id"], "name": t["name"], "method": t["method"], "standard": t["standard"],
                          "acceptance_criteria": f"{t['metric']}: {lim}", "sample_size": t["sample_size"], "frequency": t["frequency"]})
        return {
            "spec_id": sid, "title": f"Body paint test specification - {paint['name']} ({paint['code']})", "paint_code": paint["code"],
            "paint_name": paint["name"], "finish": paint["finish"],
            "scope": f"Exterior body panels painted {paint['name']} for the {dominant.get('body_style','coupe')} concept, all plants.",
            "tests": tests, "additional_checks": [STANDARDS["finish_adjustments"].get(paint["finish"], "None")],
            "release_conditions": ["All tests T01-T07 passed on 3 consecutive batches", "Master panel signed by Colour & Trim", "PPAP level 3 submission approved"],
            "risks": [f"Release status is '{paint['status']}'" + (" - needs Brand Council approval" if paint["status"] != "approved" else ""),
                      "Red pigments are prone to UV fade - watch T06 results closely" if paint["family"] == "red" else "Monitor batch-to-batch Delta E drift"],
        }

    prompt = f"""Write a body-paint TEST SPECIFICATION for production release.
Paint (from the official catalogue): {json.dumps(paint)}
Vehicle context: {json.dumps(dominant)}
Standards template you MUST use (keep every test, tighten limits only if justified): {json.dumps(STANDARDS)}
Use spec_id '{sid}'. Add finish-specific checks and realistic release conditions and risks."""
    return llm.generate(prompt, system="You are a paint & materials test engineer at an automotive OEM.", schema=SCHEMA, mock=mock)


def to_markdown(spec: dict) -> str:
    rows = "\n".join(f"| {t['id']} | {t['name']} | {t['standard']} | {t['acceptance_criteria']} | {t['sample_size']} | {t['frequency']} |" for t in spec["tests"])
    return (f"# {spec['title']}\n\n**Spec ID:** {spec['spec_id']}  \n**Paint:** {spec['paint_name']} ({spec['paint_code']}), {spec['finish']}  \n"
            f"**Scope:** {spec['scope']}\n\n| ID | Test | Standard | Acceptance | Samples | Frequency |\n|---|---|---|---|---|---|\n{rows}\n\n"
            "**Additional checks**\n" + "\n".join(f"- {c}" for c in spec.get("additional_checks", [])) +
            "\n\n**Release conditions**\n" + "\n".join(f"- {c}" for c in spec["release_conditions"]) +
            "\n\n**Risks**\n" + "\n".join(f"- {r}" for r in spec["risks"]) + "\n")


if __name__ == "__main__":
    team = sys.argv[1] if len(sys.argv) > 1 else "team1"
    dom = load(team, "dominant_spec.json")
    ts = build_test_spec(dom)
    save(team, "test_spec.json", ts)
    print(to_markdown(ts))
