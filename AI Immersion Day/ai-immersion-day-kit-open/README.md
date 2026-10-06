# AI Immersion Day — Automotive Starter Kit — OPEN EDITION

Same 90-minute lab as the Google edition — a dream car goes **from paper sketch → AI spec → engineering
spec → supply-chain risk → LEGO build → AI quality gate** — rebuilt on an **open-source stack with
open-weight models**. Nothing calls a cloud AI API; the whole room can run on one GPU server or offline.

| # | Module | Driver | Concepts | Code |
|---|---|---|---|---|
| 1 | Agent basics | Everyone | Prompt · Model · Tool, agent loop | `module1_agent_basics/` |
| 2 | Design studio | Marketing | Multi-modal vision, structured output, LLM-as-judge, **MCP** | `module2_multimodal/` |
| 3 | Engineering | Engineering | De-dup, weighted vote, grounded generation, **RAG**, optional 3D | `module3_engineering/` |
| 4 | Supply chain | Supply chain | **Knowledge graph** + supplier **what-if**, **guardrails**, **evals** | `module4_supply_chain/` |
| 5 | Manufacturing | Manufacturing | **Context**, **memory**, **harness**, human-in-the-loop | `module5_manufacturing/` |

**What changed from the Google edition:** no Gemini/Claude/Vertex/AI Studio/Antigravity/Cloud Run; the parts
graph runs on NetworkX; the printed graph cards and string are gone — Module 4 starts with a spoken guess and an
in-app "knock out a supplier" what-if that lights up every part and option it breaks.

## The stack
| Layer | Open-source component | Licence |
|---|---|---|
| Model serving | **Ollama** (default) · vLLM · llama.cpp server — any OpenAI-compatible endpoint | MIT / Apache 2.0 / MIT |
| Text + tools model | `qwen3:8b` (bigger GPU: `mistral-small3.1`) | Apache 2.0 |
| Vision model | `qwen2.5vl:7b` (or `mistral-small3.1`) | Apache 2.0 (check the card for the size you pull) |
| Embeddings | `nomic-embed-text` | Apache 2.0 |
| Agent loop, RAG, harness | plain Python in `common/llm.py` + module code | this kit |
| Tool protocol | **MCP** Python SDK | MIT |
| Knowledge graph | **NetworkX** | BSD-3 |
| Lab app | **Streamlit** + Graphviz + three.js | Apache 2.0 / EPL / MIT |
| Builder track | **Continue** in **VSCodium** | Apache 2.0 / MIT |
| No-code track | **Open WebUI** (or LibreChat) + **mcpo** for MCP tools | see `builder_prompts/README.md` |
| Packaging | Docker Compose | Apache 2.0 |

Model tags and licences change; confirm each model card before the event. "Open-weight" models publish weights
under the licence shown — training data is not necessarily open.

## Quick start — facilitator server (recommended)
One machine with an NVIDIA GPU (≥16 GB VRAM comfortably serves 6 tables with the 7–8B models) or an Apple
Silicon Mac with ≥32 GB (run Ollama natively):
```bash
docker compose up -d
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama pull qwen2.5vl:7b
docker compose exec ollama ollama pull nomic-embed-text
# participants open http://<server>:8501  (lab app)  and optionally http://<server>:3000 (Open WebUI)
```

## Quick start — one laptop
```bash
# install Ollama from ollama.com, then:
ollama pull qwen3:8b && ollama pull qwen2.5vl:7b && ollama pull nomic-embed-text
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/smoke_test.py      # all PASS = ready (LLM_PROVIDER=mock first if you have no models yet)
streamlit run app/app.py
```
No GPU, no models, bad Wi-Fi? `LLM_PROVIDER=mock` runs every module offline with deterministic answers.

## Folder map
```
common/            llm.py (OpenAI-compatible client for local open models + mock), catalogue lookups, workspace hand-offs
data/              all lab data as JSON + sample sketches + sample LEGO build photos
module1..5/        one folder per module, each file runnable on its own:  python -m module4_supply_chain.kg --what-if S-SEMITW
app/app.py         Streamlit lab app – one tab per module
builder_prompts/   Continue (builder) prompts, Open WebUI (no-code) prompts, Continue config
props/             sketch template (A4), print pack (role badges, guardrail paddles, QA sheet, eval scorecard)
scripts/           smoke_test.py, make_samples.py, build_kg.py, make_print_pack.py
docker-compose.yml Ollama + lab app + Open WebUI + mcpo on one server
```

## Data files (`/data`)
| File | Used in | What it is |
|---|---|---|
| `vehicle_fleet.json` | M1 | Fictional Meridian Motors line-up + dealer stock |
| `paint_catalogue.json` | M2, M3 | Colours, mirror caps, bonnets, wheels (served via MCP) |
| `sample_sketches/*.png` | M2 | 8 sketches incl. duplicates and a guideline-breaker |
| `design_guidelines.json` | M3 | RAG corpus – 12 design & engineering rules |
| `paint_test_standards.json` | M3 | Test-spec template |
| `parts_knowledge_graph.json` | M4 | 71 nodes / 112 edges: options → parts → raw materials → suppliers |
| `guardrail_policy.json`, `eval_cases.json` | M4 | Rails and the 10-case golden set |
| `lego_bom.json`, `quality_checklist.json` | M5 | Brick mapping, build steps, 10 QA checks |
| `sample_builds/*.png` | M5 | One good build, one with defects |

All company names, parts, suppliers and limits are **fictional/illustrative**.

## Production path (open source talk track)
Serving: vLLM · Agents: LangGraph (MIT) or this kit's loop · RAG: Qdrant / pgvector · Graph: Neo4j Community or
Apache AGE · Guardrails: NeMo Guardrails, Guardrails AI, Presidio · Evals: promptfoo, DeepEval, Ragas ·
Memory: Mem0 or PostgreSQL · Observability: Langfuse · Apps: Docker / Kubernetes on your own infrastructure.
