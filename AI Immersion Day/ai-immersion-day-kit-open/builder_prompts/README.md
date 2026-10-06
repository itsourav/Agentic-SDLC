# Builder and no-code tracks (all open source)

| Track | Tool | Licence | How |
|---|---|---|---|
| Builder | **Continue** extension in **VSCodium** (or VS Code) | Apache 2.0 / MIT | Open the kit folder, point Continue at the room's Ollama server, use `continue_prompts.md` |
| No-code | **Open WebUI** (or LibreChat, MIT, if your policy needs an OSI licence) | BSD-3 plus a branding clause - check current terms | Browse to `http://<server>:3000`, pick the vision model, paste a prompt from `openwebui_prompts.md` |
| 3D (optional) | three.js | MIT | `module3_3d.md` |

Continue config (`~/.continue/config.yaml`) for the room server:
```yaml
name: immersion-day
version: 0.0.1
models:
  - name: Room Qwen3
    provider: ollama
    model: qwen3:8b
    apiBase: http://<server>:11434
    roles: [chat, edit, apply]
mcpServers:
  - name: meridian-catalogue
    command: python3
    args: ["/ABSOLUTE/PATH/TO/ai-immersion-day-kit-open/module2_multimodal/mcp_server/catalogue_server.py"]
```
Continue's config format changes between releases - check its docs if this doesn't load.
