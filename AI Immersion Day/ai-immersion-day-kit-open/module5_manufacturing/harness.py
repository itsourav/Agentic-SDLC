"""
MODULE 5b - The QA agent HARNESS: CONTEXT + MEMORY + HARNESS

A model on its own is not a quality system. The HARNESS is the code around the model that makes
it dependable on a production line:
  1. CONTEXT   - assemble exactly what the model needs (spec, checklist, memory) and nothing else
  2. PLAN      - order the checks (memory says what failed recently -> check it first)
  3. PERCEIVE  - one vision call that returns structured observations (schema-validated, retried)
  4. EVALUATE  - deterministic comparison of observations vs spec (code, not vibes)
  5. HUMAN     - physical checks need a human sign-off (human-in-the-loop)
  6. DECIDE    - release rule applied by code
  7. REMEMBER  - write the outcome to long-term memory
Every step is logged to a trace you can audit.

    python -m module5_manufacturing.harness data/sample_builds/build_team_piston_defects.png
"""
import json
import sys
import time

from common import catalogue, llm, vision_mock
from common.workspace import data, load

from . import memory

CHECKLIST = data("quality_checklist.json")

OBS_SCHEMA = {
    "type": "object",
    "properties": {
        "body_colour": {"type": "string"}, "door_colour": {"type": "string", "description": "describe both doors if they differ"},
        "mirror_count": {"type": "integer"}, "mirror_colour": {"type": "string"},
        "bonnet_feature": {"type": "string", "description": "flat, power dome, vents, scoop, stripes"},
        "wheel_count": {"type": "integer"}, "wheel_style": {"type": "string"},
        "windscreen_present": {"type": "boolean"}, "lights_present": {"type": "boolean"}, "symmetry_ok": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": ["body_colour", "door_colour", "mirror_count", "mirror_colour", "bonnet_feature", "wheel_count", "wheel_style",
                 "windscreen_present", "lights_present", "symmetry_ok"],
}


def _validate(obs: dict) -> list[str]:
    errs = [f"missing {k}" for k in OBS_SCHEMA["required"] if k not in obs]
    for k in ("mirror_count", "wheel_count"):
        if k in obs and not isinstance(obs[k], int):
            errs.append(f"{k} must be an integer")
    return errs


def _mock_observe(img):
    emb = vision_mock.embedded_spec(img["data"])
    if emb and "observations" in emb:
        return emb["observations"]
    cols = [c for c, _ in vision_mock.dominant_colours(img["data"]) if c not in ("white", "grey", "silver", "sky blue")] or ["red"]
    body = cols[0] if cols[0] != "black" else (cols[1] if len(cols) > 1 else "black")
    return {"body_colour": body, "door_colour": body, "mirror_count": 2, "mirror_colour": "black", "bonnet_feature": "flat", "wheel_count": 4,
            "wheel_style": "5-spoke", "windscreen_present": True, "lights_present": True, "symmetry_ok": True, "notes": "mock: colour-only analysis"}


class QAHarness:
    def __init__(self, team: str, spec: dict, max_retries: int = 2, on_event=None):
        self.team, self.spec, self.max_retries = team, spec, max_retries
        self.trace, self.on_event, self.t0 = [], on_event, time.time()

    def log(self, step, msg, data=None):
        ev = {"t": round(time.time() - self.t0, 2), "step": step, "msg": msg, "data": data}
        self.trace.append(ev)
        if self.on_event:
            self.on_event(ev)

    # 1. CONTEXT -------------------------------------------------------------
    def build_context(self) -> dict:
        mem = memory.recall(self.team)
        expected = {k: self.spec.get(k) for k in ("body_paint", "body_paint_name", "door_paint", "door_paint_name", "mirror_code", "mirror_name",
                                                   "bonnet_code", "bonnet_name", "wheel_code", "wheel_name")}
        ctx = {
            "role": "You are an end-of-line quality inspector at a car plant. Describe ONLY what is visible in the photo; do not guess.",
            "expected_spec": expected,
            "checklist": [{k: i[k] for k in ("id", "check", "method", "severity")} for i in CHECKLIST["items"]],
            "memory": mem,
        }
        size = len(json.dumps(ctx))
        self.log("context", f"Context assembled: spec + {len(ctx['checklist'])} checks + memory of {mem['inspections_so_far']} past inspections "
                            f"(~{size // 4} tokens). Excluded: supplier data, costs, other teams' photos.", {"approx_tokens": size // 4})
        return ctx

    # 2. PLAN ----------------------------------------------------------------
    def plan(self, ctx) -> list[dict]:
        hot = [d for d, _ in ctx["memory"]["this_team_defects"]] + [d for d, _ in ctx["memory"]["most_common_defects"]]
        sev = {"critical": 0, "major": 1, "minor": 2}
        items = sorted(CHECKLIST["items"], key=lambda i: (i["id"] not in hot, sev[i["severity"]]))
        self.log("plan", "Check order: " + ", ".join(i["id"] + ("*" if i["id"] in hot else "") for i in items) + ("  (* = flagged by memory)" if hot else ""))
        return items

    # 3. PERCEIVE ------------------------------------------------------------
    def perceive(self, image, ctx) -> dict:
        img = llm.load_image(image)
        prompt = ("Inspect this photo of a toy-brick model car built on our line. Report observations as JSON.\n"
                  f"Pay extra attention to recently failed checks: {ctx['memory']['this_team_defects'] or ctx['memory']['most_common_defects'] or 'none'}.\n"
                  "Count mirrors and wheels carefully. Use plain colour words.")
        for attempt in range(1, self.max_retries + 2):
            try:
                obs = llm.generate(prompt, system=ctx["role"], images=[img], schema=OBS_SCHEMA, mock=lambda: _mock_observe(img))
                errs = _validate(obs)
                if not errs:
                    self.log("perceive", f"Vision observations received (attempt {attempt})", obs)
                    return obs
                self.log("perceive", f"Attempt {attempt} failed validation: {errs} - retrying")
                prompt += f"\nYour previous answer was invalid: {errs}. Fix it."
            except Exception as e:
                self.log("perceive", f"Attempt {attempt} error: {e} - retrying")
        raise RuntimeError("Vision step failed after retries - escalate to human inspector")

    # 4. EVALUATE (deterministic) ----------------------------------------------
    def evaluate(self, items, obs) -> list[dict]:
        fam = lambda code: next((p["family"] for p in catalogue.CAT["paints"] if p["code"] == code), code)
        obs_fam = lambda txt: fam(catalogue.lookup_paint(txt.split("(")[0]).get("code"))
        s, out = self.spec, []
        for i in items:
            st, why = "pass", ""
            if i["method"] == "physical":
                st, why = "pending_human", "Physical check - needs inspector sign-off"
            elif i["id"] == "QC-01":
                ok = obs_fam(obs["body_colour"]) == fam(s["body_paint"])
                st, why = ("pass" if ok else "fail"), f"saw '{obs['body_colour']}', expected {s['body_paint_name']} ({fam(s['body_paint'])} family)"
            elif i["id"] == "QC-02":
                ok = obs_fam(obs["door_colour"]) == fam(s["door_paint"]) and "one door" not in obs["door_colour"]
                st, why = ("pass" if ok else "fail"), f"saw '{obs['door_colour']}', expected {s['door_paint_name']}"
            elif i["id"] == "QC-03":
                exp = catalogue.lookup_mirror(obs["mirror_colour"], obs["body_colour"])["code"]
                ok = obs["mirror_count"] == 2 and (exp == s["mirror_code"] or (s["mirror_code"] == "MR-BODY" and obs_fam(obs["mirror_colour"]) == fam(s["body_paint"])))
                st, why = ("pass" if ok else "fail"), f"saw {obs['mirror_count']} x '{obs['mirror_colour']}' ({exp}), expected 2 x {s['mirror_code']}"
            elif i["id"] == "QC-04":
                code = catalogue.lookup_bonnet(obs["bonnet_feature"])["code"]
                st, why = ("pass" if code == s["bonnet_code"] else "fail"), f"saw '{obs['bonnet_feature']}' ({code}), expected {s['bonnet_code']}"
            elif i["id"] == "QC-05":
                code = catalogue.lookup_wheel(obs["wheel_style"])["code"]
                ok = obs["wheel_count"] == 4 and code == s["wheel_code"]
                st, why = ("pass" if ok else "fail"), f"saw {obs['wheel_count']} x '{obs['wheel_style']}' ({code}), expected 4 x {s['wheel_code']}"
            elif i["id"] == "QC-06":
                st, why = ("pass" if obs["windscreen_present"] else "fail"), "windscreen " + ("present" if obs["windscreen_present"] else "missing")
            elif i["id"] == "QC-07":
                st, why = ("pass" if obs["lights_present"] else "fail"), "lights " + ("present" if obs["lights_present"] else "missing")
            elif i["id"] == "QC-10":
                st, why = ("pass" if obs["symmetry_ok"] else "fail"), "symmetric" if obs["symmetry_ok"] else "asymmetry observed"
            out.append({"id": i["id"], "check": i["check"], "severity": i["severity"], "status": st, "evidence": why})
        self.log("evaluate", f"{sum(r['status']=='pass' for r in out)} pass, {sum(r['status']=='fail' for r in out)} fail, "
                             f"{sum(r['status']=='pending_human' for r in out)} awaiting human")
        return out

    # 5 + 6. HUMAN + DECIDE ----------------------------------------------------
    def decide(self, results, human_signoff: dict | None) -> str:
        for r in results:
            if r["status"] == "pending_human" and human_signoff and r["id"] in human_signoff:
                r["status"] = "pass" if human_signoff[r["id"]] else "fail"
                r["evidence"] = "Signed off by inspector" if human_signoff[r["id"]] else "Rejected by inspector"
        blocking = [r for r in results if r["status"] == "fail" and r["severity"] in ("critical", "major")]
        pending = [r for r in results if r["status"] == "pending_human"]
        verdict = "REJECTED" if blocking else ("HOLD - awaiting human sign-off" if pending else "RELEASED")
        self.log("decide", f"Verdict: {verdict}", {"blocking": [r["id"] for r in blocking], "pending": [r["id"] for r in pending]})
        return verdict

    def summarise(self, report) -> str:
        fails = [r for r in report["results"] if r["status"] == "fail"]
        mock = lambda: (f"Car from {self.team}: {report['verdict']}. " +
                        ("Defects: " + "; ".join(f"{r['id']} {r['check']} ({r['evidence']})" for r in fails) + ". Rework at the relevant station and re-inspect."
                         if fails else "No defects found by vision checks."))
        return llm.generate("Write a 2-3 sentence shift-handover note for this inspection. Be specific about rework.\n" + json.dumps(report), mock=mock)

    # RUN ----------------------------------------------------------------------
    def run(self, image, human_signoff: dict | None = None, remember: bool = True) -> dict:
        ctx = self.build_context()
        items = self.plan(ctx)
        obs = self.perceive(image, ctx)
        results = self.evaluate(items, obs)
        verdict = self.decide(results, human_signoff)
        report = {"team": self.team, "verdict": verdict, "observations": obs, "results": results}
        report["summary"] = self.summarise(report)
        if remember:
            memory.remember(self.team, report)
            self.log("remember", "Outcome written to long-term memory")
        report["trace"] = self.trace
        return report


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else "data/sample_builds/build_team_piston_defects.png"
    team = sys.argv[2] if len(sys.argv) > 2 else "team1"
    spec = load(team, "dominant_spec.json")
    rep = QAHarness(team, spec, on_event=lambda e: print(f"[{e['t']:>5}s] {e['step'].upper():<9} {e['msg']}")).run(img, human_signoff={"QC-08": True, "QC-09": True})
    for r in rep["results"]:
        print(f"  {r['status']:<14} {r['id']} {r['check']:<50} {r['evidence']}")
    print(rep["summary"])
