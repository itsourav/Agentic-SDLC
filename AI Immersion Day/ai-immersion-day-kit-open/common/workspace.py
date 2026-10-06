"""Each table/team gets a folder under workspace/ so the modules can hand work to each other:
sketch specs (M2) -> dominant spec (M3) -> parts risk (M4) -> build + QA (M5)."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WS = ROOT / "workspace"


def data(name: str):
    return json.loads((DATA / name).read_text())


def team_dir(team: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", team.strip() or "team1")
    d = WS / safe
    (d / "uploads").mkdir(parents=True, exist_ok=True)
    return d


def save(team: str, name: str, obj) -> Path:
    p = team_dir(team) / name
    p.write_text(json.dumps(obj, indent=2, default=str))
    return p


def load(team: str, name: str, default=None):
    p = team_dir(team) / name
    return json.loads(p.read_text()) if p.exists() else default
