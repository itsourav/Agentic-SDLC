"""
MODULE 2 - MCP server: "Meridian Colour & Trim Catalogue"

MCP (Model Context Protocol) is a standard plug for giving ANY agent access to a system.
Write the server once -> use it from Continue (VS Code / VSCodium), Open WebUI (via mcpo), or our lab app.

Run standalone (stdio):     python module2_multimodal/mcp_server/catalogue_server.py
Inspect it in a browser:    npx @modelcontextprotocol/inspector python module2_multimodal/mcp_server/catalogue_server.py
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from common import catalogue  # noqa: E402

mcp = FastMCP("meridian-catalogue", log_level="WARNING")


@mcp.tool()
def lookup_paint_code(colour_description: str) -> dict:
    """Map a free-text colour (e.g. 'bright red', 'navy') to the official Meridian paint code,
    name, finish and release status (approved / limited_edition / concept_only)."""
    return catalogue.lookup_paint(colour_description)


@mcp.tool()
def lookup_wheel_code(style_description: str) -> dict:
    """Map a free-text wheel/tyre style (e.g. '5-spoke', 'chunky off-road') to the catalogue wheel code."""
    return catalogue.lookup_wheel(style_description)


@mcp.tool()
def lookup_bonnet_code(design_description: str) -> dict:
    """Map a free-text bonnet design (e.g. 'scoop', 'vents', 'racing stripes') to the catalogue bonnet code."""
    return catalogue.lookup_bonnet(design_description)


@mcp.tool()
def list_approved_paints() -> list:
    """List every paint in the MY2027 catalogue with its status."""
    return [{"code": p["code"], "name": p["name"], "status": p["status"], "finish": p["finish"]} for p in catalogue.CAT["paints"]]


@mcp.tool()
def register_design_submission(team: str, sketch_id: str, spec_json: str) -> dict:
    """Register an analysed sketch in the design review log (writes to workspace/design_register.jsonl)."""
    log = ROOT / "workspace" / "design_register.jsonl"
    log.parent.mkdir(exist_ok=True)
    rec = {"ts": datetime.utcnow().isoformat(timespec="seconds"), "team": team, "sketch_id": sketch_id, "spec": json.loads(spec_json)}
    with log.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return {"status": "registered", "ticket": "DSR-" + hashlib.md5((team + sketch_id).encode()).hexdigest()[:6].upper()}


@mcp.resource("catalogue://paints")
def paints_resource() -> str:
    """The full paint catalogue as a readable resource."""
    return json.dumps(catalogue.CAT["paints"], indent=1)


if __name__ == "__main__":
    mcp.run()  # stdio transport
