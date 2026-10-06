"""OPTIONAL MODULE 3 STEP - turn the dominant spec into an interactive 3D model (three.js).
    python -m module3_engineering.make_3d          -> workspace/<team>/car_3d.html (open in a browser)
Stretch goal: ask your local model in Continue to *write* the three.js scene from the spec (see builder_prompts/module3_3d.md)."""
import json, re, sys
from pathlib import Path
from common.workspace import load, team_dir

TEMPLATE = Path(__file__).with_name("viewer_3d_template.html")


def render(spec: dict) -> str:
    return re.sub(r"/\*SPEC\*/.*?/\*END\*/", lambda _: "/*SPEC*/" + json.dumps(spec) + "/*END*/", TEMPLATE.read_text(), flags=re.S)


if __name__ == "__main__":
    team = sys.argv[1] if len(sys.argv) > 1 else "team1"
    out = team_dir(team) / "car_3d.html"
    out.write_text(render(load(team, "dominant_spec.json")))
    print("open", out)
