"""
MODULE 2 - Multi-modal AI: paper sketch -> structured car specification + quality rank

    python -m module2_multimodal.analyse_sketches data/sample_sketches/*.png
    python -m module2_multimodal.analyse_sketches --mcp data/sample_sketches/sketch_01.png

Concepts: multi-modal input (image + text), structured output (JSON schema),
LLM-as-a-judge with a rubric (quality score), and MCP tool calls (catalogue lookup).
"""
import json
import sys

from common import llm, vision_mock

SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "body_colour": {"type": "string", "description": "Main body colour in plain words, e.g. 'bright red'"},
        "door_colour": {"type": "string", "description": "Colour of the doors (may equal body colour)"},
        "mirror_colour": {"type": "string", "description": "Colour/finish of the wing mirrors; 'not visible' if absent"},
        "bonnet_design": {"type": "string", "description": "One of: flat, power dome, vents, scoop, stripes, or a short description"},
        "tyre_style": {"type": "string", "description": "Wheel/tyre style: 5-spoke, multi-spoke, off-road, turbine, steel, or description"},
        "body_style": {"type": "string", "description": "coupe, saloon, hatchback, SUV, pickup, estate, convertible"},
        "notable_features": {"type": "array", "items": {"type": "string"}},
        "quality": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 1, "maximum": 10},
                "clarity": {"type": "integer", "minimum": 1, "maximum": 5},
                "completeness": {"type": "integer", "minimum": 1, "maximum": 5},
                "creativity": {"type": "integer", "minimum": 1, "maximum": 5},
                "rationale": {"type": "string"},
            },
            "required": ["score", "clarity", "completeness", "creativity", "rationale"],
        },
        "confidence": {"type": "number", "description": "0-1 confidence in the extracted spec"},
    },
    "required": ["body_colour", "door_colour", "mirror_colour", "bonnet_design", "tyre_style", "body_style", "quality", "confidence"],
}

SYSTEM = """You are a senior automotive exterior designer reviewing hand-drawn concept sketches
from a marketing workshop. Extract the specification exactly as drawn - do not invent features
that are not visible. Use everyday colour words. If something is not visible say 'not visible'."""

PROMPT = """Analyse this car sketch.
1. Extract: body colour, door colour, mirror colour, bonnet design, tyre/wheel style, body style, notable features.
2. Judge sketch QUALITY with this rubric (be fair, it is a 3-minute marker sketch):
   - clarity (1-5): can a reviewer read the design intent?
   - completeness (1-5): are body, doors, mirrors, bonnet and wheels all shown and coloured?
   - creativity (1-5): is it distinctive and on-brand for a premium car maker?
   - score (1-10): overall, weighted 40% completeness, 35% clarity, 25% creativity.
Return JSON only."""


def _mock_spec(img: dict) -> dict:
    truth = vision_mock.embedded_spec(img["data"])
    if truth:  # bundled samples: behave like a perfect model
        q = truth["quality_score"]
        return {
            **{k: truth[k] for k in ("body_colour", "door_colour", "mirror_colour", "bonnet_design", "tyre_style", "body_style")},
            "notable_features": [],
            "quality": {"score": q, "clarity": min(5, q // 2 + 1), "completeness": min(5, q // 2 + 1), "creativity": 3,
                        "rationale": "Clean, fully coloured sketch." if q >= 7 else "Rough hatching; details harder to read."},
            "confidence": 0.9 if q >= 7 else 0.7,
        }
    cols = [c for c, _ in vision_mock.dominant_colours(img["data"]) if c not in ("black", "white", "grey")] or ["silver"]
    return {
        "body_colour": cols[0], "door_colour": cols[1] if len(cols) > 1 else cols[0], "mirror_colour": cols[2] if len(cols) > 2 else "black",
        "bonnet_design": vision_mock.seeded_choice(img["data"], ["flat", "scoop", "vents", "power dome", "stripes"], "b"),
        "tyre_style": vision_mock.seeded_choice(img["data"], ["5-spoke", "multi-spoke", "turbine"], "w"),
        "body_style": "coupe", "notable_features": ["(mock) colour-based analysis only"],
        "quality": {"score": 6, "clarity": 3, "completeness": 3, "creativity": 3, "rationale": "Mock mode: colours detected from pixels."},
        "confidence": 0.5,
    }


def analyse_one(image, sketch_id: str | None = None) -> dict:
    img = llm.load_image(image)
    spec = llm.generate(PROMPT, system=SYSTEM, images=[img], schema=SPEC_SCHEMA, mock=lambda: _mock_spec(img))
    spec["sketch_id"] = sketch_id or img.get("name", "sketch")
    return spec


def analyse_batch(images, on_progress=None) -> list[dict]:
    """Process ALL uploaded images, then rank by quality score (ties -> confidence)."""
    out = []
    for i, im in enumerate(images):
        img = llm.load_image(im)
        out.append(analyse_one(img, img.get("name", f"sketch_{i+1}")))
        if on_progress:
            on_progress(i + 1, len(images))
    out.sort(key=lambda s: (-s["quality"]["score"], -s.get("confidence", 0)))
    for r, s in enumerate(out, 1):
        s["quality_rank"] = r
    return out


# ---------------------------------------------------------------- MCP step
MCP_SYSTEM = """You are the design-intake agent. For the sketch spec you are given:
1. Use lookup_paint_code for the body colour AND the door colour.
2. Use lookup_wheel_code and lookup_bonnet_code.
3. Register the submission with register_design_submission (spec_json = the enriched spec as a JSON string).
4. Reply with a short table: attribute | sketch value | catalogue code | status. Flag anything not 'approved'."""


def mcp_enrich(spec: dict, team: str = "team1"):
    from module2_multimodal import mcp_bridge

    triggers = {
        "lookup_paint_code": lambda p: {"colour_description": spec["body_colour"]},
        "lookup_wheel_code": lambda p: {"style_description": spec["tyre_style"]},
        "lookup_bonnet_code": lambda p: {"design_description": spec["bonnet_design"]},
        "register_design_submission": lambda p: {"team": team, "sketch_id": spec["sketch_id"], "spec_json": json.dumps(spec)},
    }
    tools = mcp_bridge.as_agent_tools(triggers)

    def mock_answer(prompt, trace):
        rows = [f"| {s['name']} | {json.dumps(s['args'])[:60]} | {json.dumps(s['result'])[:90]} |" for s in trace if s["type"] == "tool_call"]
        return "| MCP tool | input | result |\n|---|---|---|\n" + "\n".join(rows)

    prompt = f"Team: {team}\nSketch spec:\n{json.dumps(spec, indent=1)}"
    return llm.run_agent(prompt, tools, system=MCP_SYSTEM, max_steps=10, mock_answer=mock_answer)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--mcp" in sys.argv:
        spec = analyse_one(args[0])
        res = mcp_enrich(spec)
        for s in res.trace:
            if s["type"] == "tool_call":
                print("MCP TOOL ->", s["name"], s["args"], "=>", s["result"])
        print(res.text)
    else:
        for s in analyse_batch(args):
            print(f"#{s['quality_rank']} {s['sketch_id']:<16} score={s['quality']['score']:<2} body={s['body_colour']:<11} door={s['door_colour']:<10} "
                  f"mirror={s['mirror_colour']:<8} bonnet={s['bonnet_design']:<11} tyres={s['tyre_style']}")
