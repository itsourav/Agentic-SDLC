"""
MODULE 5 (part 1) - Generate the build kit list and work instructions for the LEGO car
from the engineering dominant spec.

    python -m module5_manufacturing.build_instructions
"""
import json
import sys

from common import llm
from common.workspace import data, load

BOM = data("lego_bom.json")


def kit_list(spec: dict) -> list[dict]:
    rows = [dict(r, source="base kit") for r in BOM["base_kit"]]
    opt = BOM["by_option"]
    rows.append({**opt["body_colour"], "colour": spec["body_paint_name"], "source": "body_colour"})
    rows.append({**opt["door_colour"], "colour": spec["door_paint_name"], "source": "door_colour"})
    for code in (spec["mirror_code"], spec["bonnet_code"], spec["wheel_code"]):
        o = opt.get(code)
        if o:
            colour = o.get("colour") or spec["body_paint_name"]
            rows.append({"part": o["part"], "qty": o["qty"], "colour": colour, "source": code})
    return rows


def work_instructions(spec: dict) -> str:
    kit = kit_list(spec)

    def mock():
        lines = [f"# Build card - {spec['body_paint_name']} {spec.get('body_style', 'coupe')}", "", "## Kit list (pick before you start)"]
        lines += [f"- [ ] {r['qty']} x {r['part']} - {r['colour']}" for r in kit]
        lines += ["", "## Work instructions"]
        lines += [f"{s['step']}. **{s['station']}** - {s['task']}" for s in BOM["build_steps"]]
        lines += ["", f"**Key characteristics:** {spec['bonnet_name']}, {spec['mirror_name']}, {spec['wheel_name']}. "
                      "Quality will inspect these first."]
        return "\n".join(lines)

    prompt = (f"Write a one-page build card (markdown) for an assembly team building a toy-brick model of this car.\n"
              f"Spec: {json.dumps(spec)}\nKit list (do not change quantities): {json.dumps(kit)}\nStandard steps: {json.dumps(BOM['build_steps'])}\n"
              "Include: kit checklist with tick boxes, numbered steps per station, and 'key characteristics' that quality will check.")
    return llm.generate(prompt, system="You are a manufacturing engineer writing standard work instructions.", mock=mock)


if __name__ == "__main__":
    team = sys.argv[1] if len(sys.argv) > 1 else "team1"
    print(work_instructions(load(team, "dominant_spec.json")))
