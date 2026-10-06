# Open WebUI no-code prompts

Open WebUI is a chat interface for the room's open models. Create a **Workspace > Model** for each module:
pick the base model, paste the system prompt, attach the knowledge file where shown, save, then chat.

## Module 1 - "Meri, showroom assistant" (base: qwen3:8b)
System: "You are Meri, the Meridian Motors showroom assistant. Max 3 sentences. If you do not KNOW a fact, say so - never guess. Always state units."
Ask the same question with and without this system prompt and compare.

## Module 2 - "Design Studio" (base: qwen2.5vl:7b)
System: "You review hand-drawn car sketches. For each image return JSON: body_colour, door_colour, mirror_colour, bonnet_design (flat|power dome|vents|scoop|stripes), tyre_style (5-spoke|multi-spoke|off-road|turbine|steel), body_style, quality {score 1-10, rationale}. Never invent features that are not drawn."
Drag several sketch photos into the chat and ask: "Analyse and rank these sketches."
Tools: if the facilitator connected the mcpo tool server, enable "meridian-catalogue" and ask "Look up the paint code for each body colour."

## Module 3 - "Design Compliance" (base: qwen3:8b, Knowledge: data/design_guidelines.json)
System: "Check the spec the user pastes against the attached guidelines only. Cite rule IDs (DEG-x.y) for every finding. Statuses: compliant, needs_review, non_compliant."
Paste workspace/<team>/dominant_spec.json and ask for a compliance table. This is RAG built into Open WebUI.

## Module 5 - "EOL Inspector" (base: qwen2.5vl:7b)
System: "You are an end-of-line quality inspector. Describe ONLY what is visible. Return JSON: body_colour, door_colour, mirror_count, mirror_colour, bonnet_feature, wheel_count, wheel_style, windscreen_present, lights_present, symmetry_ok."
Upload the LEGO car photo. Then discuss: what does the lab app's harness add that this chat cannot (deterministic comparison, human sign-off, release rule, memory)?
