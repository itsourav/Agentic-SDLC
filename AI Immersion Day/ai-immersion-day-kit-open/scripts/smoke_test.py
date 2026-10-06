"""Facilitator pre-flight check: runs every module end to end. Use the night before AND on the venue Wi-Fi.
    LLM_PROVIDER=mock   python scripts/smoke_test.py      # offline
    LLM_PROVIDER=local  python scripts/smoke_test.py      # real open model on Ollama / vLLM"""
import sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import llm
from common.workspace import save, load

T = "smoke_test"
ok = True
def step(name, fn):
    global ok
    t0 = time.time()
    try:
        out = fn()
        print(f"PASS  {name:<38} {time.time()-t0:5.1f}s  {str(out)[:90]}")
        return out
    except Exception as e:
        ok = False
        print(f"FAIL  {name:<38} {e}")

print(f"provider={llm.provider()} model={llm.model_name()}")
from module1_agent_basics import agent_basics as m1
step("M1 agent with tools", lambda: m1.step3().text)
from module2_multimodal import analyse_sketches as m2, mcp_bridge
imgs = sorted((ROOT / "data/sample_sketches").glob("*.png"))
specs = step("M2 analyse 8 sketches", lambda: m2.analyse_batch(imgs))
if specs:
    save(T, "sketch_specs.json", specs)
step("M2 MCP server tools", lambda: [t["name"] for t in mcp_bridge.list_tools()])
step("M2 MCP intake agent", lambda: m2.mcp_enrich(specs[0], T).text if specs else None)
from module3_engineering import reconcile, test_spec, rag_check, make_3d
res = step("M3 reconcile", lambda: reconcile.reconcile(specs))
if res:
    save(T, "dominant_spec.json", res["dominant_spec"])
    step("M3 test spec", lambda: test_spec.build_test_spec(res["dominant_spec"])["spec_id"])
    step("M3 RAG compliance", lambda: rag_check.check(res["dominant_spec"])["overall"])
    step("M3 3D render", lambda: len(make_3d.render(res["dominant_spec"])))
from module4_supply_chain import kg, agent, evals
step("M4 knowledge graph risk report", lambda: kg.spec_risk_report(load(T, "dominant_spec.json"))["critical_path"])
step("M4 guarded agent", lambda: agent.ask("What happens if TaiSemi stops shipping?")["answer"])
step("M4 evals", lambda: evals.run()["summary"])
from module5_manufacturing import harness, build_instructions
step("M5 build card", lambda: build_instructions.work_instructions(load(T, "dominant_spec.json"))[:60])
step("M5 QA harness", lambda: harness.QAHarness(T, load(T, "dominant_spec.json")).run(ROOT / "data/sample_builds/build_team_piston_defects.png", remember=False)["verdict"])
print("\nALL GOOD - ready for the workshop" if ok else "\nSOMETHING FAILED - fix before the session or switch to LLM_PROVIDER=mock")
sys.exit(0 if ok else 1)
