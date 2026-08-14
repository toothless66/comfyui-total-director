"""LLM brain: turns a natural-language brief / storyboard into a structured Director Plan.

Two-stage design (robust on small local models):
  Stage A — extract compact parameters as a small strict JSON.
  Stage B — write the full English megaprompt (a 1-2 field JSON), which small models
            fill reliably because there is little JSON overhead.

Supports:
  - Ollama (local), including vision models like qwen3-vl (image input)
  - any OpenAI-compatible /chat/completions endpoint
"""

import asyncio
import json
import os
import random

import aiohttp

from . import config

_SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")


def _load_design_skill():
    """Load a condensed Director design digest (style/camera/mood/rhythm cues)."""
    try:
        p = os.path.join(_SKILLS_DIR, "design_skill.md")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                full = f.read()
            # Condense: keep the style table + key camera/mood/rhythm lines only.
            lines = full.splitlines()
            keep = []
            for ln in lines:
                s = ln.strip()
                if not s:
                    continue
                if s.startswith("#") and not s.startswith("## 风格库"):
                    # keep only the main sections that matter most for Stage A
                    if s.startswith("## 镜头语言") or s.startswith("## 色彩与情绪") or s.startswith("## 节奏设计"):
                        keep.append(s)
                elif s.startswith("|") or s.startswith("-") or s.startswith("*"):
                    keep.append(s)
            return "\n".join(keep)[:1400]
    except Exception:
        pass
    return ""


class LLMError(Exception):
    pass


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_ENV_HINT = """Available pipelines:
- t2v   : text-to-video, no starting image
- i2v   : image-to-video, animate a user-provided first-frame image
- r2v   : reference-to-video, animate using 1-2 reference images
- sdxl2v: full pipeline — first generate a keyframe still with SDXL, then animate it with H3

Current environment:
{env}"""

_STAGE_A_SYSTEM = """You are an AI video director producing a STRICT JSON production plan for MiniMax H3 (text+video+native stereo audio in one pass). RTX 5060 8GB VRAM, keep resolution modest.

{env_hint}

# Hard rules
1. Summarize the user's brief faithfully. NEVER invent a theme the user did not mention.
2. Scene splitting: COUNT explicit markers in the user text such as 场景N / 场景 N / Scene N / scene N / [0s-3s] / shot 1. If 2+ distinct markers exist, output one scene object per marker in "scenes". If 1 or none, output "scenes": [].
3. Each scene = its own few-second H3 clip. Scenes share style/subject for continuity.
4. pipeline: pure concept -> sdxl2v; image-led -> i2v; reference-led -> r2v; plain text -> t2v.
5. duration_s 1-15 (default 5); aspect one of 16:9/9:16/1:1/4:3/3:2/2:3/3:4/21:9; megapixels 0.2-0.6 (default 0.4); steps 10-30 (default 20).
6. design_cn: 40-120 Chinese chars, the CREATIVE DIRECTION for THIS brief (style, mood, camera language, pacing, why this pipeline). Must be specific, never generic.
7. mood_tags_cn: 3-6 Chinese editorial keywords unique to this brief.

# Output (STRICT JSON, NO markdown fences, NO extra text, NO comments)
{{
  "pipeline": "t2v",
  "summary_cn": "",
  "design_cn": "",
  "mood_tags_cn": "",
  "duration_s": 5.0,
  "aspect": "16:9",
  "megapixels": 0.4,
  "sampler": "res_multistep",
  "steps": 20,
  "audio": "",
  "notes_cn": "",
  "keyframe_prompt": "",
  "keyframe_negative": "",
  "scenes": [{{"id": 1, "title_cn": "", "summary_cn": "", "duration_s": 5.0, "aspect": "16:9", "megapixels": 0.4}}]
}}"""

_STAGE_B_SYSTEM = """You are a screenwriter who writes the actual prompt that a video diffusion model (MiniMax H3) reads. Write ONLY the English prompt text the model will read. Do not write meta-commentary.

MiniMax H3 generates video WITH native stereo audio in one pass; it has only a positive prompt (no negative prompt). One generation = one continuous take of a few seconds. The prompt should cover shots, camera moves and the audio (ambience / SFX / music) together.

Follow this exact structure:
1) A one-line style / look block.
2) A "Storyboard" with a shot list using timecodes like [0s-1.5s] Shot 1: ..., each shot describing action and camera.
3) A "Camera:" line (hard cuts, no dissolves unless wanted, etc.).
4) An "Audio:" paragraph (ambience, SFX, music, beats).
5) A closing clause: no text/subtitles/logos/watermarks unless the brief explicitly needs on-screen text (then say the text must be legible), no cartoon look unless intended.

Example:
"Realistic live-action cinematic look, post-rain dusk metropolis, anamorphic lens, shallow depth of field, film grain, city volumetric fog.

Storyboard:
[0s-1.5s] Shot 1: high side angle, protagonist sprinting at the roof edge, pursuers appearing behind.
[1s-2.5s] Shot 2: he leaps the gap between buildings, slight slow-motion, light trails behind.
[2.5s-4s] Shot 3: low-angle, he lands, rolls and rises, keeps running.
[4s-5s] Shot 4: freeze on the silhouette at the roof edge.

Camera: hard cuts, each shot its own angle, slight frame jitter on jumps, no dissolves.

Audio: wind, rapid footsteps, city ambience, low score, accent hit on each leap, score bursts at 4s.

No text, subtitles, logos or watermarks, no animation/cartoon rendering, keep live-action texture."

Rules:
- English only. 80-250 words. NEVER use "..." or ellipses; every field fully spelled out.
- For i2v / r2v with a reference image, describe motion relative to it ("the character in the reference image...") and preserve identity.
- For sdxl2v: the megaprompt describes the MOTION / camera / audio starting from the keyframe still described by keyframe_prompt.

Respond with ONE strict JSON object, no markdown fences:
{{"megaprompt": "the full prompt", "keyframe_prompt": "optional SDXL still prompt only if the pipeline is sdxl2v, else empty string"}}
keyframe_prompt must be empty string unless the pipeline is sdxl2v.
MEGAPROMPT MUST BE COMPLETE — never abbreviated, no ellipsis."""

_STAGE_C_SYSTEM = """You are the "Executive Producer / Implementer" of a video production team.
A Director model (DeepSeek) already produced the production parameters and a megaprompt for a MiniMax H3 video (omni-modal: video + native stereo audio in one pass).

Your job is to OPERATE / IMPLEMENT the plan: review it like an executive producer would, catch problems, and hand back a final polished megaprompt that is guaranteed to execute well on the real engine.

# What to check
- Continuity: shots, camera moves and audio must feel like one continuous take (H3 makes a few-second clip, not a feature).
- Completeness: prompt must contain the style/look line, a timecoded storyboard, a Camera: line, and an Audio: paragraph.
- Feasibility: hardware is RTX 5060 Laptop 8GB VRAM — keep resolution modest; do not invent resolutions, keep the given width/height.
- Tone: live-action realism by default; keep a cartoon look only if the brief demanded it.
- No text/subtitles/logos/watermarks unless the brief explicitly wants on-screen text.
- If a first-frame or reference image was provided (i2v/r2v), the motion must be described RELATIVE to that image and identity preserved.

# Rules
- Do NOT change pipeline / aspect / duration / megapixels — those are locked by the Director.
- You may rewrite wording, add missing audio/camera detail, fix impossible instructions, and shorten or expand for a better single-take flow.
- English only. 80-300 words. Never abbreviate. No ellipses.

Respond with ONE strict JSON object, no markdown fences:
{{"megaprompt": "the final complete megaprompt", "review_cn": "one short Chinese sentence summarizing what you changed / confirmed"}}
MEGAPROMPT MUST BE COMPLETE — never abbreviated, no ellipsis."""


def _build_stage_a_system(env_text):
    base = _STAGE_A_SYSTEM.replace("{env_hint}", _ENV_HINT.replace("{env}", env_text))
    skill = _load_design_skill()
    if skill:
        base = base.replace(
            "# Output (STRICT JSON, NO markdown fences, NO extra text, NO comments)",
            "Design cues (apply subtly):\n" + skill +
            "\n\n# Output (STRICT JSON, NO markdown fences, NO extra text, NO comments)")
    return base


def _summarize_env(env):
    lines = []
    models = env.get("models", {})
    for folder in ("diffusion_models", "checkpoints", "text_encoders", "vae", "loras"):
        items = models.get(folder) or []
        if items:
            lines.append(f"- {folder}: {', '.join(items[:8])}")
    pipelines = env.get("pipelines", {})
    avail = ", ".join(k for k, v in pipelines.items() if v.get("available"))
    lines.append(f"- available pipelines: {avail}")
    gpu = env.get("gpu") or []
    if gpu:
        lines.append(f"- gpu: {gpu[0].get('name')} {gpu[0].get('vram_total_gb')}GB VRAM")
    ollama = env.get("ollama", {})
    if ollama.get("running"):
        lines.append(f"- local ollama models: {', '.join(ollama['models'])}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Async clients
# ---------------------------------------------------------------------------

async def _ollama_chat(session, host, model, messages, options=None, images=None):
    # NOTE: qwen3-vl (thinking renderer) drops `images` on /api/chat but handles
    # them correctly on /api/generate (verified: prompt_eval jumps from ~20 to
    # ~1000 with an image). We rebuild the prompt for the generate endpoint.
    last_user = messages[-1]["content"] if messages else ""
    system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
    prompt = f"{system}\n\n{last_user}".strip() if system else last_user

    # Reasoning models (deepseek-r1, etc.) collapse to a literal `{ }` when
    # `format:json` forces structured decoding — verified on deepseek-r1:14b.
    # Let them think, then parse the JSON out of `response`.
    is_reasoner = "deepseek" in (model or "").lower()
    use_json_format = not is_reasoner
    think = is_reasoner or options.get("think", False)
    if is_reasoner:
        prompt += "\n\nRespond ONLY with the requested JSON object. No extra text."

    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json" if use_json_format else None,
        "stream": False,
        "think": think,
        "options": {
            "temperature": options.get("temperature", 0.5),
            "num_predict": options.get("num_predict", 4096),
            "num_ctx": options.get("num_ctx", 8192),
        },
    }
    if images:
        payload["images"] = images
    try:
        async with session.post(f"{host}/api/generate", json=payload, timeout=aiohttp.ClientTimeout(total=900)) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise LLMError(f"Ollama HTTP {resp.status}: {text[:300]}")
            data = await resp.json()
            # qwen3-vl (and other reasoning models) sometimes put the answer in
            # the `thinking` field even with think=false; fall back to it.
            return data.get("response") or data.get("thinking") or ""
    except asyncio.TimeoutError:
        raise LLMError("Ollama timeout after 900s (model too slow?)")
    except aiohttp.ClientError as e:
        raise LLMError(f"Ollama connection error: {e}")


async def _api_chat(session, cfg, messages, images=None):
    base = (cfg.get("api_base") or "").rstrip("/")
    key = cfg.get("api_key") or ""
    model = cfg.get("api_model") or "deepseek-chat"
    if not key:
        raise LLMError("API provider chosen but api_key is empty")

    if images and cfg.get("vision_enabled"):
        content = [{"type": "text", "text": messages[-1]["content"]}]
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
        payload_messages = messages[:-1] + [{"role": "user", "content": content}]
    else:
        payload_messages = messages

    url = base + "/chat/completions" if "/chat/completions" not in base else base
    payload = {
        "model": model,
        "messages": payload_messages,
        "temperature": cfg.get("temperature", 0.5),
        "response_format": {"type": "json_object"},
        "max_tokens": cfg.get("num_predict", 4096),
    }
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=900)) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise LLMError(f"API HTTP {resp.status}: {text[:300]}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]
    except asyncio.TimeoutError:
        raise LLMError("API request timed out after 900s")
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected API response shape: {e}")
    except aiohttp.ClientError as e:
        raise LLMError(f"API connection error: {e}")


def _extract_json(text):
    if not text or not text.strip():
        raise LLMError("LLM returned empty content")
    text = text.strip().lstrip("`").rstrip("`")
    if text.upper().startswith("JSON"):
        text = text[4:].lstrip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("LLM did not return a JSON object")
    snippet = text[start:end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as e:
        # Reasoning models often embed raw control characters (\n, \t, \r) inside
        # string values, which strict json.loads rejects. Escape them and retry.
        escaped = _escape_control_chars(snippet)
        if escaped != snippet:
            try:
                return json.loads(escaped)
            except json.JSONDecodeError:
                pass
        # Try once more: some reasoning models append a trailing stray brace/comment
        # after the object, or leave an unclosed string. Attempt a repair.
        repaired = _repair_json(escaped if escaped != snippet else snippet)
        if repaired is not None:
            return repaired
        raise LLMError(f"LLM JSON parse failed: {e} (len={len(snippet)})") from e


def _escape_control_chars(s):
    """Escape raw control characters INSIDE string literals only (structural newlines stay)."""
    out = []
    i = 0
    n = len(s)
    in_str = False
    while i < n:
        c = s[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                out.append(c)
                out.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
                out.append(c)
                i += 1
                continue
            o = ord(c)
            if o < 0x20:
                out.append("\\u%04x" % o)
            else:
                out.append(c)
            i += 1
        else:
            if c == '"':
                in_str = True
            out.append(c)
            i += 1
    return "".join(out)


def _repair_json(snippet):
    """Best-effort recovery for common JSON output issues from local LLMs."""
    s = snippet
    for _ in range(3):
        # drop a possible trailing ] } ) comma or stray token after the final brace
        m = s.rstrip()
        if m and m[-1] in "])},.·":
            s = m[:-1]
        else:
            break
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # unclosed string before a comma/brace: close it
    try:
        import re
        fixed = re.sub(r'("(?:[^"\\]|\\.)*)\s*,(\s*[}\]])', r"\1\"\2", s)
        return json.loads(fixed)
    except (json.JSONDecodeError, re.error):
        return None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_ASPECT_LABELS = {
    "1:1": "1:1 (Square)", "2:3": "2:3 (Portrait Photo)", "3:2": "3:2 (Photo)",
    "3:4": "3:4 (Portrait Standard)", "4:3": "4:3 (Standard)",
    "9:16": "9:16 (Portrait Widescreen)", "16:9": "16:9 (Widescreen)",
    "21:9": "21:9 (Ultrawide)",
}


def normalize_plan(raw, env, cfg):
    """Clamp & fill a raw plan dict so it is safe to build a workflow from."""
    build = cfg.get("build", {})
    pipelines = env.get("pipelines", {})

    pipeline = str(raw.get("pipeline") or "t2v").lower().strip()
    if pipeline not in pipelines:
        pipeline = "t2v"
    if not pipelines.get(pipeline, {}).get("available"):
        for cand in ("t2v", "i2v", "r2v", "sdxl2v"):
            if pipelines.get(cand, {}).get("available"):
                pipeline = cand
                break
        else:
            pipeline = "t2v"

    try:
        duration = float(raw.get("duration_s") or build.get("default_duration_s", 5.0))
    except (TypeError, ValueError):
        duration = 5.0
    duration = max(float(build.get("min_duration_s", 1.0)),
                   min(float(build.get("max_duration_s", 15.0)), duration))

    aspect = str(raw.get("aspect") or build.get("default_aspect", "16:9"))
    aspect_label = _ASPECT_LABELS.get(aspect)
    if not aspect_label:
        for k, v in _ASPECT_LABELS.items():
            if v == aspect:
                aspect_label, aspect = v, k
                break
        if not aspect_label:
            aspect, aspect_label = "16:9", _ASPECT_LABELS["16:9"]

    try:
        mp = float(raw.get("megapixels") or build.get("default_megapixels", 0.4))
    except (TypeError, ValueError):
        mp = 0.4
    mp = max(0.2, min(0.6, mp))

    sampler = str(raw.get("sampler") or build.get("sampler", "res_multistep"))
    try:
        steps = int(raw.get("steps") or build.get("steps", 20))
    except (TypeError, ValueError):
        steps = 20
    steps = max(4, min(60, steps))

    try:
        seed = int(raw.get("seed") or 0)
    except (TypeError, ValueError):
        seed = 0
    if not seed:
        seed = random.randint(1, 2 ** 53 - 1)

    return {
        "pipeline": pipeline,
        "summary_cn": str(raw.get("summary_cn") or "").strip() or f"{pipeline} 视频",
        "design_cn": str(raw.get("design_cn") or "").strip(),
        "mood_tags_cn": str(raw.get("mood_tags_cn") or "").strip(),
        "duration_s": round(duration, 1),
        "aspect": aspect,
        "aspect_label": aspect_label,
        "megapixels": mp,
        "sampler": sampler,
        "steps": steps,
        "seed": seed,
        "audio": str(raw.get("audio") or "").strip(),
        "notes_cn": str(raw.get("notes_cn") or "").strip(),
        "keyframe_prompt": str(raw.get("keyframe_prompt") or "").strip(),
        "keyframe_negative": str(raw.get("keyframe_negative") or "").strip()
        or str(build.get("sdxl_negative") or ""),
        "scenes": _normalize_scenes(raw.get("scenes"), env, cfg),
    }


def _normalize_scenes(raw_scenes, env, cfg):
    """Normalize the scene split into a list of per-scene mini-plans."""
    if not isinstance(raw_scenes, list):
        return []
    out = []
    for sc in raw_scenes:
        if not isinstance(sc, dict):
            continue
        s = dict(sc)
        # Reuse normalize_plan on a flattened scene dict (recursion-safe: scenes=[]).
        s.pop("scenes", None)
        sub = normalize_plan(s, env, cfg)
        sub["id"] = int(s.get("id") or (len(out) + 1))
        sub["title_cn"] = str(s.get("title_cn") or "").strip() or f"场景 {sub['id']}"
        out.append(sub)
    return out[:6]


def _merge_stage_b(plan, stage_b, env, cfg):
    plan["megaprompt"] = str(stage_b.get("megaprompt") or "").strip()
    if not plan["megaprompt"]:
        raise LLMError("LLM did not produce a megaprompt")
    if plan["pipeline"] == "sdxl2v":
        kp = str(stage_b.get("keyframe_prompt") or "").strip()
        if kp:
            plan["keyframe_prompt"] = kp
    return plan


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def _chat_once(session, cfg, messages, images=None):
    if cfg.get("provider") == "api":
        return await _api_chat(session, cfg, messages, images=images)
    return await _ollama_chat(
        session, cfg.get("ollama_host", "http://127.0.0.1:11434"),
        cfg.get("ollama_model", "qwen3-vl:8b"), messages, cfg, images=images)


def _role_cfg(llm_cfg, role_model):
    """Return an effective per-role LLM config, inheriting top-level settings.

    role_model may be empty -> fall back to the top-level model so a missing
    role never breaks the request. Everything else (provider, host, api keys)
    is inherited from the top-level llm config.
    """
    cfg = dict(llm_cfg)
    if role_model:
        cfg["ollama_model"] = role_model
        cfg["api_model"] = role_model
    return cfg


def _role_models(llm_cfg):
    """Resolve the per-role models for the current roles_mode."""
    mode = (llm_cfg.get("roles_mode") or "single").lower()
    if mode != "dual":
        return None, llm_cfg.get("ollama_model"), llm_cfg.get("api_model")
    return (
        llm_cfg.get("stage_a_model") or llm_cfg.get("ollama_model"),
        llm_cfg.get("stage_b_model") or llm_cfg.get("ollama_model"),
        llm_cfg.get("stage_c_model") or llm_cfg.get("ollama_model"),
    )


def _user_brief(user_text, extra=""):
    return (
        "User brief / storyboard script:\n"
        "------------------------------------\n"
        f"{user_text}\n"
        "------------------------------------\n"
        + extra
    )


async def plan(user_text, env, cfg=None, images=None):
    """Two-stage Director Plan generation (optionally coordinated across two models)."""
    cfg = cfg or config.get()
    llm_cfg = cfg.get("llm", {})
    env_text = _summarize_env(env)
    stage_a_system = _build_stage_a_system(env_text)

    mode_a, mode_b, mode_c = _role_models(llm_cfg)
    dual = llm_cfg.get("roles_mode", "single").lower() == "dual"

    msg_a = [{"role": "system", "content": stage_a_system},
             {"role": "user", "content": _user_brief(user_text, "Respond with the parameter JSON.")}]
    msg_b = [{"role": "system", "content": _STAGE_B_SYSTEM},
             {"role": "user", "content": _user_brief(user_text, "")}]

    async with aiohttp.ClientSession() as session:
        content_a = await _chat_once(session, _role_cfg(llm_cfg, mode_a), msg_a, images=images)
        raw_a = _extract_json(content_a)
        plan = normalize_plan(raw_a, env, cfg)

        b_ctx = (
            f"\n\nChosen production parameters:\n{json.dumps({k: plan[k] for k in ('pipeline', 'duration_s', 'aspect', 'megapixels', 'sampler', 'steps')}, ensure_ascii=False)}\n"
            f"keyframe_prompt (if any): {plan['keyframe_prompt']}\n"
            "Now respond with the megaprompt JSON."
        )
        msg_b[1]["content"] = _user_brief(user_text, b_ctx)
        content_b = await _chat_once(session, _role_cfg(llm_cfg, mode_b), msg_b, images=images)
        raw_b = _extract_json(content_b)
        plan = _merge_stage_b(plan, raw_b, env, cfg)

        # Multi-scene: give each scene its own megaprompt via a dedicated Stage B call.
        scenes = plan.get("scenes") or []
        for sc in scenes:
            sc_ctx = (
                f"\n\nThis is SCENE {sc['id']} of {len(scenes)} ({sc.get('title_cn', '')}).\n"
                f"Scene production parameters:\n{json.dumps({k: sc[k] for k in ('pipeline', 'duration_s', 'aspect', 'megapixels', 'sampler', 'steps')}, ensure_ascii=False)}\n"
                "Write ONE megaprompt for THIS scene only (its own shots/camera/audio). Respond with the megaprompt JSON."
            )
            msg_s = [{"role": "system", "content": _STAGE_B_SYSTEM},
                     {"role": "user", "content": _user_brief(user_text, sc_ctx)}]
            content_s = await _chat_once(session, _role_cfg(llm_cfg, mode_b), msg_s, images=images)
            raw_s = _extract_json(content_s)
            sc["megaprompt"] = str(raw_s.get("megaprompt") or "").strip()
            if not sc["megaprompt"]:
                sc["megaprompt"] = plan.get("megaprompt", "")
            kp = str(raw_s.get("keyframe_prompt") or "").strip()
            if kp and sc["pipeline"] == "sdxl2v":
                sc["keyframe_prompt"] = kp

        if dual and mode_c:
            c_ctx = (
                f"\n\nProduction parameters:\n{json.dumps({k: plan[k] for k in ('pipeline', 'duration_s', 'aspect', 'megapixels', 'sampler', 'steps')}, ensure_ascii=False)}\n"
                f"Draft megaprompt:\n{plan['megaprompt']}\n"
                "Review, fix and return the final megaprompt JSON."
            )
            msg_c = [{"role": "system", "content": _STAGE_C_SYSTEM},
                     {"role": "user", "content": _user_brief(user_text, c_ctx)}]
            content_c = await _chat_once(session, _role_cfg(llm_cfg, mode_c), msg_c, images=images)
            raw_c = _extract_json(content_c)
            if str(raw_c.get("megaprompt") or "").strip():
                plan["megaprompt"] = str(raw_c["megaprompt"]).strip()
                review = str(raw_c.get("review_cn") or "").strip()
                if review:
                    plan["notes_cn"] = ((plan.get("notes_cn") or "") + " | 终审: " + review).strip(" |")

    if dual:
        plan["_meta"] = {"provider": llm_cfg.get("provider"), "model": mode_b,
                         "roles": {"stage_a": mode_a, "stage_b": mode_b, "stage_c": mode_c}}
    else:
        plan["_meta"] = {"provider": llm_cfg.get("provider"), "model": llm_cfg.get("ollama_model" if llm_cfg.get("provider") != "api" else "api_model")}
    return plan


async def refine_plan(previous_plan, instruction, env, cfg=None):
    """Apply a natural-language adjustment to an existing plan, keeping the megaprompt."""
    cfg = cfg or config.get()
    llm_cfg = cfg.get("llm", {})
    env_text = _summarize_env(env)

    mode_a, mode_b, mode_c = _role_models(llm_cfg)
    dual = llm_cfg.get("roles_mode", "single").lower() == "dual"

    msg_a = [{"role": "system", "content": _build_stage_a_system(env_text)},
             {"role": "user", "content": (
                 "Current production parameters:\n"
                 f"{json.dumps({k: v for k, v in previous_plan.items() if k in ('pipeline', 'duration_s', 'aspect', 'megapixels', 'sampler', 'steps')}, ensure_ascii=False)}\n\n"
                 f"User adjustment request: {instruction}\n\n"
                 "Return the FULL updated parameter JSON (all fields, same schema).")}]

    async with aiohttp.ClientSession() as session:
        content_a = await _chat_once(session, _role_cfg(llm_cfg, mode_a), msg_a)
        raw_a = _extract_json(content_a)
        plan = normalize_plan(raw_a, env, cfg)

        msg_b = [{"role": "system", "content": _STAGE_B_SYSTEM},
                 {"role": "user", "content": _user_brief(
                     f"{previous_plan.get('summary_cn', '')} | adjustment: {instruction}",
                     f"\n\nChosen production parameters:\n{json.dumps({k: plan[k] for k in ('pipeline', 'duration_s', 'aspect', 'megapixels')}, ensure_ascii=False)}\n"
                     "Rewrite the megaprompt to match; respond with the megaprompt JSON.")}]
        content_b = await _chat_once(session, _role_cfg(llm_cfg, mode_b), msg_b)
        raw_b = _extract_json(content_b)
        plan = _merge_stage_b(plan, raw_b, env, cfg)

        if dual and mode_c:
            c_ctx = (
                f"\n\nProduction parameters:\n{json.dumps({k: plan[k] for k in ('pipeline', 'duration_s', 'aspect', 'megapixels', 'sampler', 'steps')}, ensure_ascii=False)}\n"
                f"Rewritten megaprompt:\n{plan['megaprompt']}\n"
                "Review, fix and return the final megaprompt JSON."
            )
            msg_c = [{"role": "system", "content": _STAGE_C_SYSTEM},
                     {"role": "user", "content": _user_brief(f"{previous_plan.get('summary_cn', '')} | adjustment: {instruction}", c_ctx)}]
            content_c = await _chat_once(session, _role_cfg(llm_cfg, mode_c), msg_c)
            raw_c = _extract_json(content_c)
            if str(raw_c.get("megaprompt") or "").strip():
                plan["megaprompt"] = str(raw_c["megaprompt"]).strip()
                review = str(raw_c.get("review_cn") or "").strip()
                if review:
                    plan["notes_cn"] = ((plan.get("notes_cn") or "") + " | 终审: " + review).strip(" |")

    if dual:
        plan["_meta"] = {"provider": llm_cfg.get("provider"), "model": mode_b,
                         "roles": {"stage_a": mode_a, "stage_b": mode_b, "stage_c": mode_c}}
    else:
        plan["_meta"] = {"provider": llm_cfg.get("provider"), "model": llm_cfg.get("ollama_model" if llm_cfg.get("provider") != "api" else "api_model")}
    return plan
