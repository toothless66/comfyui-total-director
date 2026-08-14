# AGENTS.md

## Environment

- OS: Windows, shell = PowerShell 5.1. Escape special chars with backtick; use `;` / `if ($?) {}` for chaining (no `&&`).
- ComfyUI root: `D:\MiniMaxH3\ComfyUI_windows_portable\ComfyUI`
- ComfyUI python (has aiohttp): `D:\MiniMaxH3\ComfyUI_windows_portable\python_embeded\python.exe`
- System python (C:\...\Python312) does NOT have aiohttp — always use the embedded python for tests.
- Project lives at `C:\project\comfyui-total-director`; a junction points `ComfyUI\custom_nodes\comfyui-total-director` at it (edit here = edit there; don't create duplicate files under custom_nodes).
- ComfyUI is currently running on 127.0.0.1:8188 (PID may change). The /api/director/* routes and frontend panel only exist after a restart that loads this custom node.

## Architecture (read-only mental model)

- `__init__.py`: `WEB_DIRECTORY="./js"`, registers routes onto `PromptServer.instance.routes` at import time via `routes.register()` (uses aiohttp decorator-call syntax `routes.get("/path")(handler)` — NOT `.add_get`, that doesn't exist).
- `server/routes.py`: aiohttp handlers for `/director/{status,plan,refine,build,config,models}`. All endpoints return `{ok, ...}`; errors `{ok:false, error}`.
- `server/llm.py`: two-stage: Stage A strict param JSON → `normalize_plan()` (strips unknown keys, so `megaprompt` is added later by `_merge_stage_b`); Stage B megaprompt JSON. `_ollama_chat` falls back to `thinking` field when content empty (qwen3-vl behavior).
- `server/workflow.py`: load save-format template → patch widgets/links. `workflow.build()` computes `_width/_height` and dispatches t2v/i2v/r2v/sdxl2v. `_find()` returns a LIST — index `[0]` to get a node.
- `server/env.py`: `snapshot()` = system_stats + object_info + disk models + Ollama + pipeline_availability. Model discovery via MODEL_COMBO_NODES and disk walk (`.safetensors/.ckpt/.pt/.pth/.bin`).
- `server/config.py`: `_DEFAULTS` merged with persisted `config.json` (deep merge). `save(patch)` merges + persists.

## Key facts verified against source

- Routes get `/api/` prefix automatically: `PromptServer.add_routes()` runs AFTER `nodes.init_extra_nodes()`, iterating `self.routes` (server.py:1220+). So `/director/*` and `/api/director/*` both work.
- `/prompt` POST accepts API-format prompt only; each node needs `class_type`. save-format cannot be submitted directly.
- `app.graphToPrompt()` (FrontComfyApp) returns `{output, workflow}`; `output` = API-format, `workflow` = save-format.
- `app.loadGraphData(wf)` loads a JSON workflow into the canvas.
- `api.queuePrompt(number, {output, workflow})` POSTs to /prompt.
- `api.fetchApi('/director/x')` → auto-prefixes to `/api/director/x`; `/upload/image` (FormData) returns `{name, subfolder, type}`; LoadImage widget value = `subfolder/name`.
- Frontend shims: `static/scripts/app.js` exports `app` (= `window.comfyAPI.app.app`), `static/scripts/api.js` exports `api`.

## Common gotchas

- Never use system python for anything importing aiohttp/server modules.
- After modifying backend, restart ComfyUI for routes to reload. The junction reflects changes instantly.
- `normalize_plan()` drops extra keys — tests that bypass `plan()` must inject `megaprompt` manually.
- Templates contain a subgraph (`definitions.subgraphs`); subgraph instance widget slots: [prompt,width,height,duration,seed].
- Try not to kill the running ComfyUI without asking the user (it predates extension deployment; restart needed to activate).

## Tests

```powershell
& <embedded python> test_standalone.py env|build|plan "<brief>"
& <embedded python> test_routes.py
```

After any backend change: run test_routes.py (fast, mocked) and, if sensible, test_standalone.py build.