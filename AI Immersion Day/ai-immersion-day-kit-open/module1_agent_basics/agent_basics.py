"""
MODULE 1 - AI agent basics: PROMPT + MODEL + TOOL
Run each step and compare the answers:

    python -m module1_agent_basics.agent_basics --step 1   # prompt only
    python -m module1_agent_basics.agent_basics --step 2   # better prompt (role, context, format)
    python -m module1_agent_basics.agent_basics --step 3   # prompt + tools = agent
    LLM_PROVIDER=local LLM_MODEL=mistral-small3.1 python -m module1_agent_basics.agent_basics --step 3   # swap the MODEL, keep everything else
"""
import argparse
import json

from common import llm
from common.workspace import data

FLEET = data("vehicle_fleet.json")
QUESTION = "How far can a fully charged Aurora EV drive, in miles, and is one in stock in Manchester?"

# ---------------------------------------------------------------- PROMPTS
PROMPT_V1 = QUESTION  # a naive prompt

SYSTEM_V2 = """You are 'Meri', the Meridian Motors showroom assistant.
- Audience: a customer on the phone. Be friendly, max 3 sentences.
- If you do not KNOW a fact (range, stock, price), say so - never guess.
- Always state units."""

SYSTEM_V3 = SYSTEM_V2 + "\n- You have tools. ALWAYS use them for vehicle facts and stock, then answer."


# ---------------------------------------------------------------- TOOLS (plain python functions)
def get_vehicle_spec(model: str) -> dict:
    """Look up a vehicle in the Meridian line-up."""
    for v in FLEET["vehicles"]:
        if v["model"].lower() == model.lower().strip():
            return v
    return {"error": f"Unknown model '{model}'. Known: {[v['model'] for v in FLEET['vehicles']]}"}


def calculate_range(battery_kwh: float, efficiency_kwh_per_100km: float) -> dict:
    """Deterministic maths beats model maths."""
    km = battery_kwh / efficiency_kwh_per_100km * 100
    return {"range_km": round(km), "range_miles": round(km * 0.621371)}


def check_dealer_stock(model: str, city: str) -> dict:
    stock = FLEET["dealer_stock"].get(model, {})
    return {"model": model, "city": city, "units_in_stock": stock.get(city.title(), 0)}


def _mentions(prompt, word):
    return word.lower() in prompt.lower()


TOOLS = [
    llm.Tool("get_vehicle_spec", "Get official specs (battery_kwh, efficiency, power, price) for a Meridian Motors model.",
             {"type": "object", "properties": {"model": {"type": "string", "description": "e.g. 'Aurora EV'"}}, "required": ["model"]},
             get_vehicle_spec, mock_trigger=lambda p: {"model": "Aurora EV"} if _mentions(p, "aurora") else None),
    llm.Tool("calculate_range", "Calculate driving range from battery size (kWh) and efficiency (kWh/100km). Returns km and miles.",
             {"type": "object", "properties": {"battery_kwh": {"type": "number"}, "efficiency_kwh_per_100km": {"type": "number"}},
              "required": ["battery_kwh", "efficiency_kwh_per_100km"]},
             calculate_range, mock_trigger=lambda p: {"battery_kwh": 64, "efficiency_kwh_per_100km": 14.8} if _mentions(p, "far") else None),
    llm.Tool("check_dealer_stock", "Units in stock for a model at a dealer city (London, Manchester, Birmingham).",
             {"type": "object", "properties": {"model": {"type": "string"}, "city": {"type": "string"}}, "required": ["model", "city"]},
             check_dealer_stock, mock_trigger=lambda p: {"model": "Aurora EV", "city": "Manchester"} if _mentions(p, "stock") else None),
]


def _mock_final(prompt, trace):
    r = {s["name"]: s["result"] for s in trace if s["type"] == "tool_call"}
    if "calculate_range" in r:
        return (f"A fully charged Aurora EV can drive about {r['calculate_range']['range_miles']} miles "
                f"({r['calculate_range']['range_km']} km), and Manchester has {r.get('check_dealer_stock', {}).get('units_in_stock', '?')} in stock right now.")
    return "I'm not sure - I don't have that information."


def step1():
    return llm.generate(PROMPT_V1, mock=lambda: "The Aurora EV has a range of around 300 miles and is generally available at most dealers. (Plausible... but invented!)")


def step2():
    return llm.generate(QUESTION, system=SYSTEM_V2, mock=lambda: "I don't have the official range or live stock data, so I can't confirm - let me connect you to a specialist.")


def step3():
    return llm.run_agent(QUESTION, TOOLS, system=SYSTEM_V3, mock_answer=_mock_final)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, default=3)
    a = ap.parse_args()
    print(f"provider={llm.provider()} model={llm.model_name()}\n")
    if a.step == 1:
        print(step1())
    elif a.step == 2:
        print(step2())
    else:
        res = step3()
        for s in res.trace:
            if s["type"] == "tool_call":
                print(f"TOOL  {s['name']}({json.dumps(s['args'])}) -> {json.dumps(s['result'])}")
        print("\nANSWER:", res.text)
