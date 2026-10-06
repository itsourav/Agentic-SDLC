"""
MODULE 3a - Engineering: reconcile sketches -> merge duplicates -> dominant specification

    python -m module3_engineering.reconcile            (reads workspace/<team>/sketch_specs.json)

Concepts: canonicalisation (free text -> catalogue codes), similarity & de-duplication,
weighted voting, and keeping deterministic code for the parts that must be exact.
"""
import json
import sys
from collections import defaultdict

from common import catalogue, llm
from common.workspace import load, save

KEYS = ["body_paint", "door_paint", "mirror_code", "bonnet_code", "wheel_code"]
LABELS = {"body_paint": "body_colour", "door_paint": "door_colour", "mirror_code": "mirror_colour", "bonnet_code": "bonnet_design", "wheel_code": "tyre_style"}
NAMES = {"body_paint": "body_paint_name", "door_paint": "door_paint_name", "mirror_code": "mirror_name", "bonnet_code": "bonnet_name", "wheel_code": "wheel_name"}


def similarity(a: dict, b: dict) -> float:
    return sum(a["canon"][k] == b["canon"][k] for k in KEYS) / len(KEYS)


def reconcile(specs: list[dict], dup_threshold: float = 0.8) -> dict:
    for s in specs:
        s["canon"] = catalogue.canonicalise(s)

    # --- 1. cluster duplicates (union-find on pairwise similarity)
    parent = list(range(len(specs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs = []
    for i in range(len(specs)):
        for j in range(i + 1, len(specs)):
            sim = similarity(specs[i], specs[j])
            if sim >= dup_threshold:
                parent[find(j)] = find(i)
                pairs.append({"a": specs[i]["sketch_id"], "b": specs[j]["sketch_id"], "similarity": sim})
    groups = defaultdict(list)
    for i, s in enumerate(specs):
        groups[find(i)].append(s)
    clusters = []
    for members in groups.values():
        rep = max(members, key=lambda s: s["quality"]["score"])
        clusters.append({
            "design_id": f"D{len(clusters)+1:02d}", "representative": rep["sketch_id"], "members": [m["sketch_id"] for m in members],
            "votes": len(members), "total_quality": sum(m["quality"]["score"] for m in members), "canon": rep["canon"],
        })
    clusters.sort(key=lambda c: (-c["total_quality"], -c["votes"]))

    # --- 2. dominant spec: quality-weighted vote per attribute
    dominant, breakdown = {}, {}
    total_w = sum(s["quality"]["score"] for s in specs) or 1
    for k in KEYS:
        tally = defaultdict(float)
        for s in specs:
            tally[s["canon"][k]] += s["quality"]["score"]
        ranked = sorted(tally.items(), key=lambda x: -x[1])
        winner = ranked[0][0]
        name = next(s["canon"][NAMES[k]] for s in specs if s["canon"][k] == winner)
        dominant[k] = winner
        dominant[NAMES[k]] = name
        breakdown[LABELS[k]] = [{"code": c, "share": round(w / total_w, 2)} for c, w in ranked]
    # carry paint status/finish + body style of the winner
    win_spec = next(s for s in specs if s["canon"]["body_paint"] == dominant["body_paint"])
    dominant["body_paint_status"] = win_spec["canon"]["body_paint_status"]
    dominant["body_paint_finish"] = win_spec["canon"]["body_paint_finish"]
    dominant["body_style"] = max(set(s["canon"]["body_style"] for s in specs), key=lambda b: sum(x["quality"]["score"] for x in specs if x["canon"]["body_style"] == b))
    dominant["door_rule"] = (
        "matches_body" if dominant["door_paint"] == dominant["body_paint"]
        else "contrast_black_or_silver" if dominant["door_paint"] in ("OB-900", "LS-450") else "other_contrast"
    )
    dominant["colour_count"] = len({dominant["body_paint"], dominant["door_paint"]}) + (0 if dominant["mirror_code"] == "MR-BODY" else 1)
    dominant["confidence"] = breakdown["body_colour"][0]["share"]

    return {"input_sketches": len(specs), "unique_designs": len(clusters), "duplicate_pairs": pairs, "clusters": clusters,
            "dominant_spec": dominant, "vote_breakdown": breakdown}


def explain(result: dict) -> str:
    """Let the model write the engineering summary - the numbers stay computed by code."""
    d = result["dominant_spec"]
    mock = lambda: (f"{result['input_sketches']} sketches reduced to {result['unique_designs']} unique designs. "
                    f"The dominant specification is {d['body_paint_name']} ({d['body_paint']}) with {d['door_paint_name']} doors, "
                    f"{d['mirror_name'].lower()}, {d['bonnet_name'].lower()} and {d['wheel_name']}. "
                    f"Body colour consensus: {int(d['confidence']*100)}% of quality-weighted votes.")
    return llm.generate("Write a 3-sentence engineering summary of this reconciliation for a design review board. "
                        "Use the codes. Do not change any numbers.\n" + json.dumps({k: v for k, v in result.items() if k != "clusters"}),
                        mock=mock)


if __name__ == "__main__":
    team = sys.argv[1] if len(sys.argv) > 1 else "team1"
    specs = load(team, "sketch_specs.json")
    if not specs:
        from module2_multimodal.analyse_sketches import analyse_batch
        from pathlib import Path

        specs = analyse_batch(sorted(Path("data/sample_sketches").glob("*.png")))
        save(team, "sketch_specs.json", specs)
    res = reconcile(specs)
    save(team, "reconciliation.json", res)
    save(team, "dominant_spec.json", res["dominant_spec"])
    print(json.dumps({k: res[k] for k in ("input_sketches", "unique_designs", "duplicate_pairs")}, indent=1))
    for c in res["clusters"]:
        print(f"{c['design_id']}: {c['members']} votes={c['votes']} quality={c['total_quality']}")
    print(json.dumps(res["dominant_spec"], indent=1))
    print(explain(res))
