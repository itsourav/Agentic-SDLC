# Continue agent prompts (open the kit folder in VSCodium first, Agent mode on)

## Setup
- "Read README.md, create a venv, install requirements.txt, run scripts/smoke_test.py with LLM_PROVIDER=mock and tell me if everything passes."

## Module 1 - tools
- "In module1_agent_basics/agent_basics.py add a tool `charging_time(battery_kwh, charger_kw)` returning 10-80% charge time in minutes. Run step 3 with LLM_PROVIDER=local."

## Module 2 - MCP
- "Use the meridian-catalogue MCP server to tell me the paint code for 'deep ocean blue' and whether it is approved."
- "Add an MCP tool `lookup_mirror_code(mirror_colour, body_colour)` to the catalogue server using common/catalogue.lookup_mirror and prove it works with mcp_bridge.py."

## Module 3 - RAG
- "Add guideline DEG-2.5 to data/design_guidelines.json: 'Matte finishes require a 5-year paint warranty extension and are limited editions only.' Re-run module3_engineering/rag_check.py and check retrieval picks it up."

## Module 4 - graph, guardrails, evals
- "Add a supplier S-LITHCO with high risk that supplies TPMS-01 instead of S-MIRRORTEK in scripts/build_kg.py, rebuild the graph, and show me the new what-if for S-LITHCO."
- "Add an input guardrail that blocks questions naming competitor brands. Add two eval cases and run module4_supply_chain/evals.py."
- "Switch LLM_MODEL to a smaller model (e.g. qwen3:1.7b), re-run the evals and compare scores with qwen3:8b."

## Module 5 - harness and memory
- "In module5_manufacturing/harness.py, when the verdict is REJECTED, generate a rework instruction per failed check using the station from data/lego_bom.json."
