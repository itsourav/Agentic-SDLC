"""
MODULE 5a - MEMORY: what the QA agent remembers between inspections.

  short-term memory : the events of THIS inspection session (cleared per car)
  long-term memory  : lessons that persist - recurring defects per station/team, inspector notes
The harness recalls long-term memory into the context of every new inspection, so the agent
checks the historically weak spots first ("last 2 cars from Team Piston had a missing mirror").
Production path (open source): Mem0, or a PostgreSQL / Redis table behind a LangGraph checkpointer.
"""
import json
from collections import Counter
from datetime import datetime

from common.workspace import WS

FILE = WS / "qa_memory.json"


def _load():
    if FILE.exists():
        return json.loads(FILE.read_text())
    return {"inspections": [], "notes": []}


def _save(m):
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(m, indent=1))


def recall(team: str | None = None, k: int = 5) -> dict:
    m = _load()
    fails = Counter()
    team_fails = Counter()
    for ins in m["inspections"]:
        for f in ins["failed_checks"]:
            fails[f] += 1
            if team and ins["team"] == team:
                team_fails[f] += 1
    return {
        "inspections_so_far": len(m["inspections"]),
        "most_common_defects": fails.most_common(k),
        "this_team_defects": team_fails.most_common(k),
        "inspector_notes": m["notes"][-k:],
    }


def remember(team: str, report: dict):
    m = _load()
    m["inspections"].append({
        "ts": datetime.utcnow().isoformat(timespec="seconds"), "team": team, "verdict": report["verdict"],
        "failed_checks": [r["id"] for r in report["results"] if r["status"] == "fail"],
    })
    _save(m)


def add_note(note: str):
    m = _load()
    m["notes"].append({"ts": datetime.utcnow().isoformat(timespec="seconds"), "note": note})
    _save(m)


def reset():
    if FILE.exists():
        FILE.unlink()
