# 🎬 ComfyUI Director — From One Sentence to a Finished Video

> **"I vibe-coded this project because manually assembling ComfyUI workflows is tedious and totally unfriendly to beginners."**
> So I attached a "Director" to ComfyUI: you say one sentence, and it plays scriptwriter, producer, cinematographer and editor — handing you the finished video.

---

## What is it?

A **floating director panel** on the left side of ComfyUI. Type one sentence (or a storyboard script) and it will:

1. **Plan** — a local LLM parses your request and decides the pipeline, duration, resolution, camera moves
2. **Write the prompt** — generates a full English megaprompt with timecoded shots, camera & audio cues
3. **Assemble the workflow** — patches your MiniMax H3 template automatically (no node wiring needed)
4. **One-click render** — queues, monitors progress, and previews the result right in the panel

Manually building an H3 workflow means dragging dozens of nodes, filling in unet/clip/vae paths, tuning resolution and writing English prompts. The Director does all of that for you.

## ✨ Highlights

- **Zero learning curve**: just speak plain language, e.g. *"a mechanical bird circling over a rain-soaked neon cyberpunk city, 3 seconds"*
- **Four pipelines**: `t2v` text-to-video / `i2v` first-frame image-to-video / `r2v` reference-image-to-video / `sdxl2v` full SDXL keyframe pipeline
- **Multi-model coordination (dual mode)**: deepseek plans the parameters & writes the prompt, qwen does the final review (producer's-eye check) — a real division of labor
- **Always inspectable**: the generated plan is editable, and the assembled workflow lands on your canvas so you can see and tweak it
- **True one-click**: from text to video with a single button, including progress monitoring and in-panel preview

## 🚀 Installation

1. Clone into your ComfyUI `custom_nodes` folder:

   ```bash
   cd D:\MiniMaxH3\ComfyUI_windows_portable\ComfyUI\custom_nodes
   git clone https://github.com/toothless66/comfyui-total-director.git
   ```

2. Drop in your own H3 workflow templates: export `h3_t2v.json` / `h3_i2v.json` / `h3_r2v.json` (save-format, with subgraph) into `server/templates/`.
3. Install [Ollama](https://ollama.com) and pull the models you want (default `qwen3-vl:8b`).
4. Restart ComfyUI. Refresh the browser — the panel appears on the left of the canvas (**Alt+D** toggles it).

## 🎥 How to use

| Step | Action |
|------|--------|
| 1. Say it | In the **Create** tab, type one sentence / storyboard (optionally upload a first-frame image) |
| 2. Plan | Click **Generate Plan** and review how the Director breaks it down |
| 3. Build | Click **Build & Load to Canvas**, tweak if needed |
| 4. Render | Click **One-Click Render**; the panel shows progress and previews the result |

### Dual mode (multi-model coordination)

Set `roles_mode` to `dual` in the **Settings** tab; planning is split across three roles:

| Role | Job | Default model |
|------|-----|---------------|
| 🧠 A | Parse request → parameters | `deepseek-r1:14b` |
| ✍️ B | Write the full megaprompt | `deepseek-r1:14b` |
| 🎬 C | Final review / visual check | `qwen3-vl:8b` |

- The plan preview shows `Coordinated A→B→C` with each model, fully transparent
- `stage_*_model` can be swapped individually; leave empty to skip a role
- deepseek-style reasoning models automatically switch to think mode and drop forced JSON (otherwise output collapses to `{ }`)

> 💡 Speed tip: dual mode takes ~2–4 min per run (deepseek is slow to reason); set stage_a/b to `qwen3-vl:8b` for faster plans.

## ⚙️ Configuration

`config.json` is generated in the extension root on first save:

```jsonc
{
  "llm": {
    "provider": "ollama",            // "ollama" | "api"
    "ollama_host": "http://127.0.0.1:11434",
    "ollama_model": "qwen3-vl:8b",
    "api_base": "https://api.deepseek.com/v1",
    "api_key": "",                    // only needed when provider=api
    "api_model": "deepseek-chat",
    "roles_mode": "single",           // "single" | "dual"
    "stage_a_model": "deepseek-r1:14b",
    "stage_b_model": "deepseek-r1:14b",
    "stage_c_model": "qwen3-vl:8b"
  },
  "build": {
    "default_aspect": "16:9",
    "default_megapixels": 0.4,        // 0.2-0.4 recommended for 8GB VRAM
    "max_duration_s": 15.0,
    "sampler": "res_multistep",
    "steps": 20,
    "output_prefix": "video/Director"
  }
}
```

## 🛠 Architecture

```
┌─────────────────────────────┐     ┌──────────────────────────────────┐
│  Frontend Floating Panel    │     │  Backend (ComfyUI custom node)   │
│  js/director.js             │────▶│  server/routes.py  (aiohttp)      │
│  - Create / Plan / Settings │     │  server/llm.py     (LLM planning) │
│  - Image upload /upload     │     │  server/workflow.py(workflow build)│
│  - Build → loadGraphData()  │     │  server/env.py     (env snapshot) │
│  - Run → api.queuePrompt()  │     │  server/config.py  (config mgmt)  │
└─────────────────────────────┘     └──────────────────────────────────┘
```

## 📡 API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/director/status` | Environment snapshot + config summary |
| POST | `/api/director/plan` | `{message, image_base64?}` → `{plan, preview, model}` |
| POST | `/api/director/refine` | Refine an existing plan |
| POST | `/api/director/build` | Build workflow JSON |
| GET/POST | `/api/director/config` | Read/write config (api_key masked) |
| GET | `/api/director/result/{prompt_id}` | Fetch the rendered video by prompt id |

## 🧪 Development & tests

```powershell
# Use ComfyUI's bundled python (has aiohttp)
& D:\MiniMaxH3\ComfyUI_windows_portable\python_embeded\python.exe test_standalone.py env
& ...\python.exe test_standalone.py build        # pipeline assembly smoke test
& ...\python.exe test_standalone.py plan "需求"   # live LLM test (needs Ollama)
& ...\python.exe test_routes.py                  # route smoke test
```

## 📝 Notes

- Templates are **your own** H3 workflows; the backend only patches parameters, so it stays compatible with your ComfyUI version
- This project is a **vibe-coding** product — built iteratively in conversation, so it may have rough edges. PRs & Issues welcome
- Credits: ComfyUI, [MiniMax H3](https://www.minimax.io/blog/minimax-h3), Ollama
